"""
Empirical CGT / Hackenbush probes for HeXO.

The experiment instruments self-play positions with threat-Hackenbush
observables from engine.cgt:

  - move_temp_percentile: did the agent play in a hot local component?
  - component_count: how many hot subgames are active?
  - top_component_share: is heat concentrated or split?
  - potential_temperature_corr: does Erdos-Selfridge mass track urgency?

Outputs:
  evidence/results/cgt_hackenbush.json
  evidence/figures/fig_cgt_hackenbush_summary.png
  evidence/figures/fig_cgt_hackenbush_scatter.png
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import HexGame
from engine.analysis import potential_map
from engine.cgt import move_rank_percentile, position_summary, temperature_map
from experiments.harness import default_registry


DEFAULT_AGENTS = ["random", "greedy", "potential", "ca_combo_v2", "mirror"]


def _finite_or_none(value: float) -> float | None:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _clean_for_json(obj):
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_clean_for_json(v) for v in obj]
    if isinstance(obj, float):
        return _finite_or_none(obj)
    return obj


def _choose_move(agent, game: HexGame, rng: random.Random) -> tuple[tuple[int, int], bool]:
    """Return (move, fallback_used)."""
    legal = game.legal_moves()
    if not legal:
        return (0, 0), True
    try:
        move = agent.choose_move(game)
    except Exception:
        return rng.choice(legal), True
    if move in game.board:
        return rng.choice(legal), True
    return move, False


def _play_agent_self_games(
    agent_name: str,
    n_games: int,
    max_moves: int,
    seed: int,
    sample_stride: int,
) -> tuple[list[dict], list[dict]]:
    registry = default_registry()
    if agent_name not in registry:
        raise KeyError(f"unknown agent {agent_name!r}; choices: {sorted(registry)}")
    factory = registry[agent_name]
    records: list[dict] = []
    games: list[dict] = []

    for game_idx in range(n_games):
        rng = random.Random(seed + 100_003 * game_idx)
        random.seed(seed + 100_003 * game_idx)
        black = factory()
        white = factory()
        game = HexGame()
        fallback_count = 0

        while game.winner is None and len(game.move_history) < max_moves:
            player = game.current_player
            agent = black if player == 1 else white
            should_sample = (len(game.move_history) % sample_stride == 0)
            if should_sample:
                temps = temperature_map(game, player)
                pot = potential_map(game)
                summary = position_summary(game, player)
            else:
                temps = {}
                pot = {}
                summary = {}
            move, fallback = _choose_move(agent, game, rng)
            fallback_count += int(fallback)

            if should_sample:
                move_temp = temps.get(move, 0.0)
                move_pot = pot.get(move, 0.0)
                rank = move_rank_percentile(temps, move)
            made = game.make(*move)
            if not made:
                legal = game.legal_moves()
                move = rng.choice(legal) if legal else move
                game.make(*move)
                fallback_count += 1

            if should_sample:
                records.append({
                    "agent": agent_name,
                    "game": game_idx,
                    "ply": len(game.move_history) - 1,
                    "player": player,
                    "move": move,
                    "move_temperature": float(move_temp),
                    "move_potential": float(move_pot),
                    "move_temp_percentile": float(rank),
                    "component_count": int(summary["component_count"]),
                    "candidate_count": int(summary["candidate_count"]),
                    "top_temperature": float(summary["top_temperature"]),
                    "mean_temperature": float(summary["mean_temperature"]),
                    "total_temperature": float(summary["total_temperature"]),
                    "top_component_share": float(summary["top_component_share"]),
                    "thermal_entropy": float(summary["thermal_entropy"]),
                    "potential_temperature_corr": float(summary["potential_temperature_corr"]),
                    "fallback": bool(fallback),
                    "winner_after": game.winner,
                })

        games.append({
            "agent": agent_name,
            "game": game_idx,
            "winner": game.winner or 0,
            "moves": len(game.move_history),
            "fallback_count": fallback_count,
        })
    return records, games


def _nanmean(values: list[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(mean(vals)) if vals else float("nan")


def _summarise(records: list[dict], games: list[dict], agents: list[str]) -> dict:
    out: dict[str, dict] = {}
    for agent in agents:
        rs = [r for r in records if r["agent"] == agent]
        gs = [g for g in games if g["agent"] == agent]
        out[agent] = {
            "positions": len(rs),
            "games": len(gs),
            "decisive_rate": sum(1 for g in gs if g["winner"]) / max(1, len(gs)),
            "mean_game_length": _nanmean([g["moves"] for g in gs]),
            "mean_move_temp_percentile": _nanmean([r["move_temp_percentile"] for r in rs]),
            "hot_move_rate_p95": _nanmean([1.0 if r["move_temp_percentile"] >= 0.95 else 0.0 for r in rs]),
            "mean_component_count": _nanmean([r["component_count"] for r in rs]),
            "mean_top_component_share": _nanmean([r["top_component_share"] for r in rs]),
            "mean_thermal_entropy": _nanmean([r["thermal_entropy"] for r in rs]),
            "mean_potential_temperature_corr": _nanmean([r["potential_temperature_corr"] for r in rs]),
            "fallback_rate": sum(1 for r in rs if r["fallback"]) / max(1, len(rs)),
        }
    return out


def _bin_series(records: list[dict], agent: str, key: str, bin_size: int) -> tuple[np.ndarray, np.ndarray]:
    rs = [r for r in records if r["agent"] == agent]
    if not rs:
        return np.array([]), np.array([])
    max_ply = max(r["ply"] for r in rs)
    xs, ys = [], []
    for start in range(0, max_ply + 1, bin_size):
        vals = [
            r[key] for r in rs
            if start <= r["ply"] < start + bin_size
            and isinstance(r[key], (int, float))
            and math.isfinite(r[key])
        ]
        if vals:
            xs.append(start + bin_size / 2)
            ys.append(float(np.mean(vals)))
    return np.array(xs), np.array(ys)


def _plot_summary(results: dict, path: str) -> None:
    records = results["records"]
    agents = results["config"]["agents"]
    summary = results["summary"]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    ax_rank, ax_comp, ax_corr, ax_share = axes.ravel()

    for agent in agents:
        x, y = _bin_series(records, agent, "move_temp_percentile", bin_size=10)
        ax_rank.plot(x, y, marker="o", linewidth=1.2, label=agent)
    ax_rank.set_ylim(0, 1.02)
    ax_rank.set_xlabel("ply")
    ax_rank.set_ylabel("mean move thermal percentile")
    ax_rank.set_title("Do agents play the hot local game?")
    ax_rank.grid(alpha=0.35, linestyle=":")
    ax_rank.legend(fontsize=8)

    for agent in agents:
        x, y = _bin_series(records, agent, "component_count", bin_size=10)
        ax_comp.plot(x, y, marker="o", linewidth=1.2, label=agent)
    ax_comp.set_xlabel("ply")
    ax_comp.set_ylabel("hot component count")
    ax_comp.set_title("Threat-Hackenbush decomposition over time")
    ax_comp.grid(alpha=0.35, linestyle=":")

    xs = np.arange(len(agents))
    corrs = [summary[a]["mean_potential_temperature_corr"] for a in agents]
    ax_corr.bar(xs, corrs, color="#496a9a")
    ax_corr.axhline(0, color="#222", linewidth=0.8)
    ax_corr.set_xticks(xs)
    ax_corr.set_xticklabels(agents, rotation=30, ha="right")
    ax_corr.set_ylabel("Pearson r")
    ax_corr.set_title("Potential mass vs CGT urgency")
    ax_corr.grid(axis="y", alpha=0.35, linestyle=":")

    width = 0.38
    top_share = [summary[a]["mean_top_component_share"] for a in agents]
    entropy = [summary[a]["mean_thermal_entropy"] for a in agents]
    ax_share.bar(xs - width / 2, top_share, width=width, label="top heat share", color="#c7833d")
    ax_share.bar(xs + width / 2, entropy, width=width, label="thermal entropy", color="#5c8f5c")
    ax_share.set_xticks(xs)
    ax_share.set_xticklabels(agents, rotation=30, ha="right")
    ax_share.set_title("Concentrated threat vs split subgames")
    ax_share.grid(axis="y", alpha=0.35, linestyle=":")
    ax_share.legend(fontsize=8)

    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)


def _plot_scatter(results: dict, path: str) -> None:
    records = results["records"]
    agents = results["config"]["agents"]
    fig, ax = plt.subplots(figsize=(8, 6))
    rng = np.random.default_rng(0)
    for agent in agents:
        rs = [r for r in records if r["agent"] == agent]
        if len(rs) > 450:
            idx = rng.choice(len(rs), size=450, replace=False)
            rs = [rs[i] for i in idx]
        x = np.array([math.log1p(r["move_potential"]) for r in rs], dtype=float)
        y = np.array([math.log1p(r["move_temperature"]) for r in rs], dtype=float)
        ax.scatter(x, y, s=12, alpha=0.45, label=agent)
    ax.set_xlabel("log(1 + Erdos-Selfridge potential of played move)")
    ax.set_ylabel("log(1 + CGT temperature of played move)")
    ax.set_title("Mass is not always urgency")
    ax.grid(alpha=0.35, linestyle=":")
    ax.legend(fontsize=8)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)


def _verdict(results: dict) -> str:
    lines = [
        "CGT / Hackenbush empirical readout",
        "agent            rank   hot95  comps  top_share  entropy  pot_temp_r",
    ]
    for agent, s in results["summary"].items():
        lines.append(
            f"{agent:14s}  "
            f"{s['mean_move_temp_percentile']:.3f}  "
            f"{s['hot_move_rate_p95']:.3f}  "
            f"{s['mean_component_count']:.2f}  "
            f"{s['mean_top_component_share']:.3f}  "
            f"{s['mean_thermal_entropy']:.3f}  "
            f"{s['mean_potential_temperature_corr']:.3f}"
        )
    lines.append("")
    lines.append("Interpretation: high rank/hot95 means the agent tends to play the local hot game.")
    lines.append("High component count plus high entropy means several independent subgames are alive.")
    lines.append("Low potential-temperature correlation means potential is measuring mass, not urgency.")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    agents = list(args.agents)
    records: list[dict] = []
    games: list[dict] = []
    t0 = time.perf_counter()
    for i, agent in enumerate(agents):
        print(f"\n-- CGT trace: {agent} ({args.n_games} games, max {args.max_moves} moves)")
        rs, gs = _play_agent_self_games(
            agent,
            n_games=args.n_games,
            max_moves=args.max_moves,
            seed=args.seed + 1_000_000 * i,
            sample_stride=args.sample_stride,
        )
        records.extend(rs)
        games.extend(gs)
        print(f"   positions={len(rs)}  decisive={sum(1 for g in gs if g['winner'])}/{len(gs)}")

    out = {
        "config": {
            "agents": agents,
            "n_games": args.n_games,
            "max_moves": args.max_moves,
            "sample_stride": args.sample_stride,
            "seed": args.seed,
        },
        "summary": _summarise(records, games, agents),
        "games": games,
        "records": records,
        "_wall_time_s": time.perf_counter() - t0,
    }
    return _clean_for_json(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agents", nargs="+", default=DEFAULT_AGENTS)
    ap.add_argument("--n-games", type=int, default=16)
    ap.add_argument("--max-moves", type=int, default=140)
    ap.add_argument("--sample-stride", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260509)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    if args.quick:
        args.n_games = 2
        args.max_moves = 48
        args.sample_stride = max(args.sample_stride, 4)

    results = run(args)

    rpath = Path("evidence/results") / "cgt_hackenbush.json"
    rpath.parent.mkdir(parents=True, exist_ok=True)
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[saved] {rpath}")

    fig1 = Path("evidence/figures") / "fig_cgt_hackenbush_summary.png"
    fig2 = Path("evidence/figures") / "fig_cgt_hackenbush_scatter.png"
    _plot_summary(results, str(fig1))
    _plot_scatter(results, str(fig2))
    print(f"[saved] {fig1}")
    print(f"[saved] {fig2}")
    print("\n" + _verdict(results))


if __name__ == "__main__":
    main()
