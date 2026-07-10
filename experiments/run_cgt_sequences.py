"""Sloane-style integer sequence mining for HeXO CGT observables."""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import HexGame
from engine.analysis import fork_cells, threat_cells
from engine.cgt import live_line_records, position_summary, temperature_map
from engine.isomorphisms import canonical_board_key
from experiments.harness import default_registry


DEFAULT_AGENTS = ["random", "greedy", "potential", "ca_combo_v2", "mirror"]
JSON_PATH = Path("evidence/results/cgt_sequences.json")
CSV_PATH = Path("evidence/results/cgt_sequences.csv")
FIGURE_PATH = Path("evidence/figures/fig_cgt_sequences.png")


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


def _candidate_orbit_count(game: HexGame, player: int, candidates: set[tuple[int, int]]) -> int:
    keys = set()
    for cell in candidates:
        board = dict(game.board)
        board[cell] = player
        keys.add(canonical_board_key(board))
    return len(keys)


def sequence_snapshot(
    game: HexGame,
    agent_name: str,
    game_idx: int,
    ply: int,
    player: int,
) -> dict[str, int | float | str]:
    """Return integer-ish CGT invariants for one game prefix."""
    records = live_line_records(game)
    temps = temperature_map(game, player)
    summary = position_summary(game, player)
    max_temp = max(temps.values(), default=0.0)
    max_ties = sum(1 for value in temps.values() if value == max_temp)
    candidates = set(temps)
    return {
        "agent": agent_name,
        "game": game_idx,
        "ply": ply,
        "player": player,
        "stones": len(game.board),
        "live_lines": len(records),
        "candidate_count": int(summary["candidate_count"]),
        "candidate_orbit_count": _candidate_orbit_count(game, player, candidates),
        "hot_components": int(summary["component_count"]),
        "max_temperature": float(summary["top_temperature"]),
        "max_temperature_ties": max_ties,
        "total_temperature": float(summary["total_temperature"]),
        "thermal_entropy": float(summary["thermal_entropy"]),
        "top_component_share": float(summary["top_component_share"]),
        "potential_temperature_corr": float(summary["potential_temperature_corr"]),
        "threat_cells": len(threat_cells(game, player)),
        "fork_cells": len(fork_cells(game, player)),
    }


def _choose_move(agent, game: HexGame, rng: random.Random) -> tuple[tuple[int, int], bool]:
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


def collect_sequences(
    agents: list[str],
    n_games: int,
    max_moves: int,
    sample_stride: int,
    seed: int,
) -> tuple[list[dict], list[dict]]:
    registry = default_registry()
    rows: list[dict] = []
    games: list[dict] = []
    for agent_name in agents:
        if agent_name not in registry:
            raise KeyError(f"unknown agent {agent_name!r}; choices: {sorted(registry)}")
        factory = registry[agent_name]
        for game_idx in range(n_games):
            rng = random.Random(seed + 104_729 * game_idx)
            random.seed(seed + 104_729 * game_idx)
            black = factory()
            white = factory()
            game = HexGame()
            fallback_count = 0

            while game.winner is None and len(game.move_history) < max_moves:
                ply = len(game.move_history)
                player = game.current_player
                if ply % sample_stride == 0:
                    rows.append(sequence_snapshot(game, agent_name, game_idx, ply, player))

                agent = black if player == 1 else white
                move, fallback = _choose_move(agent, game, rng)
                fallback_count += int(fallback)
                if not game.make(*move):
                    legal = game.legal_moves()
                    if not legal:
                        break
                    move = rng.choice(legal)
                    game.make(*move)
                    fallback_count += 1

            games.append({
                "agent": agent_name,
                "game": game_idx,
                "winner": game.winner or 0,
                "moves": len(game.move_history),
                "fallback_count": fallback_count,
            })
    return rows, games


def _mean(values: list[float]) -> float:
    clean = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(mean(clean)) if clean else float("nan")


def summarise(rows: list[dict], games: list[dict], agents: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for agent in agents:
        agent_rows = [row for row in rows if row["agent"] == agent]
        agent_games = [game for game in games if game["agent"] == agent]
        out[agent] = {
            "positions": len(agent_rows),
            "games": len(agent_games),
            "mean_live_lines": _mean([row["live_lines"] for row in agent_rows]),
            "mean_candidate_orbit_count": _mean([row["candidate_orbit_count"] for row in agent_rows]),
            "mean_hot_components": _mean([row["hot_components"] for row in agent_rows]),
            "mean_max_temperature": _mean([row["max_temperature"] for row in agent_rows]),
            "mean_thermal_entropy": _mean([row["thermal_entropy"] for row in agent_rows]),
            "mean_threat_cells": _mean([row["threat_cells"] for row in agent_rows]),
            "mean_fork_cells": _mean([row["fork_cells"] for row in agent_rows]),
            "decisive_rate": sum(1 for game in agent_games if game["winner"]) / max(1, len(agent_games)),
            "mean_game_length": _mean([game["moves"] for game in agent_games]),
        }
    return out


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _series(rows: list[dict], agent: str, key: str) -> tuple[list[int], list[float]]:
    grouped: dict[int, list[float]] = {}
    for row in rows:
        if row["agent"] == agent and isinstance(row[key], (int, float)):
            grouped.setdefault(int(row["ply"]), []).append(float(row[key]))
    xs = sorted(grouped)
    ys = [_mean(grouped[x]) for x in xs]
    return xs, ys


def plot_sequences(rows: list[dict], agents: list[str], path: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    panels = (
        ("live_lines", "live 6-lines"),
        ("candidate_orbit_count", "D6 candidate orbits"),
        ("hot_components", "hot components"),
        ("thermal_entropy", "thermal entropy"),
    )
    for ax, (key, title) in zip(axes.ravel(), panels):
        for agent in agents:
            xs, ys = _series(rows, agent, key)
            if xs:
                ax.plot(xs, ys, marker="o", linewidth=1.2, label=agent)
        ax.set_title(title)
        ax.set_xlabel("ply")
        ax.grid(alpha=0.35, linestyle=":")
    axes[0][0].legend(fontsize=8)
    fig.suptitle("HeXO CGT sequence mining")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", nargs="+", default=DEFAULT_AGENTS)
    parser.add_argument("--n-games", type=int, default=6)
    parser.add_argument("--max-moves", type=int, default=96)
    parser.add_argument("--sample-stride", type=int, default=6)
    parser.add_argument("--seed", type=int, default=20260509)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    if args.quick:
        args.n_games = 1
        args.max_moves = 36
        args.sample_stride = max(args.sample_stride, 6)

    started = time.time()
    rows, games = collect_sequences(
        agents=args.agents,
        n_games=args.n_games,
        max_moves=args.max_moves,
        sample_stride=args.sample_stride,
        seed=args.seed,
    )
    elapsed = time.time() - started
    result = {
        "experiment": "cgt_sequences",
        "config": {
            "agents": args.agents,
            "n_games": args.n_games,
            "max_moves": args.max_moves,
            "sample_stride": args.sample_stride,
            "seed": args.seed,
        },
        "wall_time_sec": elapsed,
        "summary": summarise(rows, games, args.agents),
        "games": games,
        "records": rows,
    }

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(_clean_for_json(result), indent=2), encoding="utf-8")
    write_csv(rows, CSV_PATH)
    plot_sequences(rows, args.agents, FIGURE_PATH)
    print(f"wrote {JSON_PATH}, {CSV_PATH}, {FIGURE_PATH} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
