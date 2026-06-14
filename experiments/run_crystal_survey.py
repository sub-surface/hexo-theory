"""Multi-modal survey of bounded crystal structure in HeXO."""
from __future__ import annotations

import argparse
import importlib
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
import numpy as np

# Worktree shim; see CLAUDE.md "Worktree gotcha".
_REAL_HEXGO = Path(r"C:\Users\Leon\Desktop\Psychograph\hexgo")
if _REAL_HEXGO.exists() and str(_REAL_HEXGO) not in sys.path:
    sys.path.insert(0, str(_REAL_HEXGO))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import HexGame
from engine.crystal import axial_to_xy_cell, crystal_observables
from engine.fractal_strategy import generate_strategy_fractal
from experiments.harness import default_registry


JSON_PATH = Path("results/crystal_survey.json")
FIG_GALLERY = Path("figures/fig_crystal_survey_gallery.png")
FIG_METRICS = Path("figures/fig_crystal_survey_metrics.png")
FIG_HARMONICS = Path("figures/fig_crystal_survey_harmonics.png")
FIG_DIFFRACTION = Path("figures/fig_crystal_survey_diffraction.png")
FIG_FRACTAL = Path("figures/fig_crystal_survey_fractal_highres.png")
DEFAULT_AGENTS = ["random", "greedy", "potential", "ca_combo_v2", "mirror"]
METRIC_COLUMNS = [
    "bragg99",
    "d6_jaccard",
    "sector_entropy",
    "box_dimension",
    "d_min",
    "d_max",
    "moment_1",
    "moment_6",
    "moment_12",
]


def _hex_distance(cell: tuple[int, int]) -> int:
    q, r = cell
    return (abs(q) + abs(r) + abs(q + r)) // 2


def _owner_sequence(n_moves: int) -> list[int]:
    """
    Player owning each move index under the HeXO 1-2-2 turn rule:
    P1 places stone 0, then turns alternate with 2 placements each.
    Sequence of owners: 1, 2,2, 1,1, 2,2, 1,1, ...
    """
    owners: list[int] = []
    if n_moves <= 0:
        return owners
    owners.append(1)  # opening single stone
    player = 2
    while len(owners) < n_moves:
        for _ in range(2):
            if len(owners) >= n_moves:
                break
            owners.append(player)
        player = 3 - player
    return owners


def _hex_ball(radius: int) -> list[tuple[int, int]]:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            cells.append((q, r))
    return cells


def _hex_patch_n(n: int) -> list[tuple[int, int]]:
    radius = 0
    while len(_hex_ball(radius)) < n:
        radius += 1
    return sorted(_hex_ball(radius), key=lambda c: (_hex_distance(c), c[0], c[1]))[:n]


def _random_disc_n(n: int, radius: int, rng: random.Random) -> list[tuple[int, int]]:
    cells = _hex_ball(radius)
    if n > len(cells):
        n = len(cells)
    return rng.sample(cells, n)


def _play_agent_self_game(agent_name: str, max_moves: int, seed: int) -> dict:
    random.seed(seed)
    registry = default_registry()
    black = registry[agent_name]()
    white = registry[agent_name]()
    game = HexGame()
    fallback_count = 0
    while game.winner is None and len(game.move_history) < max_moves:
        agent = black if game.current_player == 1 else white
        legal = game.legal_moves()
        if not legal:
            break
        try:
            move = agent.choose_move(game)
        except Exception:
            move = random.choice(legal)
            fallback_count += 1
        if move in game.board or not game.make(*move):
            move = random.choice(legal)
            game.make(*move)
            fallback_count += 1
    cells_sorted = sorted(game.board)
    return {
        "source": agent_name,
        "kind": "agent_self_play",
        "seed": seed,
        "winner": game.winner or 0,
        "moves": len(game.move_history),
        "fallback_count": fallback_count,
        "cells": cells_sorted,
        "cell_owner": [int(game.board[c]) for c in cells_sorted],
        "player_counts": {
            "black": sum(1 for p in game.board.values() if p == 1),
            "white": sum(1 for p in game.board.values() if p == 2),
        },
    }


def _try_rust_parallel_self_play(n_games: int, max_moves: int, sims: int) -> tuple[list[dict], dict]:
    """Use the Rust pure-MCTS path if it is importable in this environment."""
    meta = {"available": False, "reason": "not attempted"}
    theory_root = str(Path(__file__).resolve().parents[1])
    saved_path = list(sys.path)
    saved_hexgo = sys.modules.pop("hexgo", None)
    try:
        sys.path = [
            str(_REAL_HEXGO),
            *[p for p in saved_path if "hexgo-theory" not in str(p) and p != theory_root],
        ]
        mod = importlib.import_module("hexgo")
        path = getattr(mod, "__file__", "")
        if "hexgo-theory" in str(path):
            meta = {"available": False, "reason": f"shadowed by theory shim: {path}"}
            return [], meta
        if not hasattr(mod, "parallel_self_play"):
            meta = {"available": False, "reason": "hexgo module lacks parallel_self_play"}
            return [], meta
        raw = mod.parallel_self_play(n_games, sims, 1.5, 0.2, max_moves)
    except Exception as exc:
        meta = {"available": False, "reason": repr(exc)}
        return [], meta
    finally:
        sys.path = saved_path
        sys.modules.pop("hexgo", None)
        if saved_hexgo is not None:
            sys.modules["hexgo"] = saved_hexgo

    samples = []
    for idx, result in enumerate(raw):
        cells = [tuple(map(int, move)) for move in result.moves]
        # 1-2-2 turn rule: P1 places move 0, then players alternate in pairs.
        owner_by_move = _owner_sequence(len(cells))
        owner_of: dict[tuple[int, int], int] = {}
        for mv_idx, cell in enumerate(cells):
            owner_of.setdefault(cell, owner_by_move[mv_idx])
        cells_sorted = sorted(owner_of)
        samples.append({
            "source": "rust_pure_mcts",
            "kind": "rust_parallel_self_play",
            "seed": idx,
            "winner": int(result.winner or 0),
            "moves": int(result.num_moves),
            "fallback_count": 0,
            "cells": cells_sorted,
            "cell_owner": [owner_of[c] for c in cells_sorted],
            "player_counts": {
                "black": sum(1 for v in owner_of.values() if v == 1),
                "white": sum(1 for v in owner_of.values() if v == 2),
            },
        })
    meta = {"available": True, "reason": "ok", "n_games": n_games, "sims": sims}
    return samples, meta


def _control_samples(
    n_games: int,
    n_points: int,
    radius: int,
    seed: int,
    fractal_depth: int,
    inflation: int,
) -> list[dict]:
    out = []
    for idx in range(n_games):
        rng = random.Random(seed + 50_000 + idx)
        rd_cells = sorted(_random_disc_n(n_points, radius, rng))
        out.append({
            "source": "random_disc",
            "kind": "control",
            "seed": seed + 50_000 + idx,
            "winner": 0,
            "moves": n_points,
            "fallback_count": 0,
            "cells": rd_cells,
            "cell_owner": [0] * len(rd_cells),  # 0 = unowned control point
            "player_counts": {"black": 0, "white": 0},
        })
    hp_cells = sorted(_hex_patch_n(n_points))
    out.append({
        "source": "hex_patch",
        "kind": "control",
        "seed": seed,
        "winner": 0,
        "moves": n_points,
        "fallback_count": 0,
        "cells": hp_cells,
        "cell_owner": [0] * len(hp_cells),
        "player_counts": {"black": 0, "white": 0},
    })
    fractal = generate_strategy_fractal(depth=fractal_depth, inflation=inflation)
    fr_cells = sorted(fractal.board)
    out.append({
        "source": f"fractal_d{fractal_depth}_i{inflation}",
        "kind": "recursive_strategy_control",
        "seed": seed,
        "winner": 1,
        "moves": len(fractal.board),
        "fallback_count": 0,
        "cells": fr_cells,
        "cell_owner": [1] * len(fr_cells),  # verified strategy = all Black (P1)
        "player_counts": {"black": len(fractal.board), "white": 0},
    })
    return out


def _clean_json(obj):
    if isinstance(obj, dict):
        return {str(k): _clean_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_json(v) for v in obj]
    if isinstance(obj, tuple):
        return [_clean_json(v) for v in obj]
    if isinstance(obj, float) and not math.isfinite(obj):
        return None
    return obj


def _mean(values: list[float]) -> float:
    vals = [v for v in values if isinstance(v, (int, float)) and math.isfinite(v)]
    return float(mean(vals)) if vals else float("nan")


def _std(values: list[float]) -> float:
    vals = np.array([v for v in values if isinstance(v, (int, float)) and math.isfinite(v)])
    return float(vals.std(ddof=0)) if len(vals) else float("nan")


def _score_samples(samples: list[dict], diffraction_grid: int) -> list[dict]:
    records = []
    for sample in samples:
        obs = crystal_observables(sample["cells"], diffraction_grid=diffraction_grid)
        black = sample["player_counts"].get("black", 0)
        white = sample["player_counts"].get("white", 0)
        color_total = black + white
        record = dict(sample)
        record["color_imbalance"] = (
            abs(black - white) / color_total if color_total else 0.0
        )
        record["observables"] = obs
        records.append(record)
    return records


def _summarise(records: list[dict]) -> dict[str, dict]:
    sources = sorted({r["source"] for r in records})
    out = {}
    for source in sources:
        rows = [r for r in records if r["source"] == source]
        metrics = {
            metric: _mean([r["observables"][metric] for r in rows])
            for metric in METRIC_COLUMNS
        }
        out[source] = {
            "n_samples": len(rows),
            "kind": rows[0]["kind"],
            "mean_moves": _mean([r["moves"] for r in rows]),
            "decisive_rate": _mean([1.0 if r["winner"] else 0.0 for r in rows]),
            "color_imbalance": _mean([r["color_imbalance"] for r in rows]),
            "metrics": metrics,
            "metric_std": {
                metric: _std([r["observables"][metric] for r in rows])
                for metric in METRIC_COLUMNS
            },
            "harmonics": {
                str(order): _mean([
                    r["observables"]["harmonics"].get(order, 0.0) for r in rows
                ])
                for order in range(1, 13)
            },
        }
    return out


def _points_array(cells: list[tuple[int, int]]) -> np.ndarray:
    return np.array([axial_to_xy_cell(tuple(cell)) for cell in cells], dtype=np.float64)


# Stone-colour convention: Player 1 = Black, Player 2 = White, 0 = unowned.
_STONE_STYLE = {
    1: dict(facecolor="#111111", edgecolor="#111111"),  # Black (P1)
    2: dict(facecolor="#fafafa", edgecolor="#333333"),  # White (P2)
    0: dict(facecolor="#7a9cc6", edgecolor="#3a567f"),  # unowned control point
}


def _scatter_by_owner(ax, pts: np.ndarray, owners: list[int], size: float = 24.0) -> None:
    """Scatter stones coloured by player: P1 black, P2 white, 0 neutral."""
    owners_arr = np.asarray(owners) if len(owners) == len(pts) else np.zeros(len(pts), int)
    for owner, style in _STONE_STYLE.items():
        mask = owners_arr == owner
        if mask.any():
            ax.scatter(pts[mask, 0], pts[mask, 1], s=size,
                       facecolor=style["facecolor"], edgecolor=style["edgecolor"],
                       linewidths=0.4, alpha=0.95)


def plot_gallery(records: list[dict], path: Path) -> None:
    first_by_source = {}
    for record in records:
        first_by_source.setdefault(record["source"], record)
    sources = list(first_by_source)
    cols = min(4, len(sources))
    rows = int(math.ceil(len(sources) / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows), squeeze=False)
    for ax, source in zip(axes.ravel(), sources):
        record = first_by_source[source]
        pts = _points_array(record["cells"])
        owners = record.get("cell_owner", [0] * len(record["cells"]))
        if len(pts):
            ax.set_facecolor("#d9d9d9")  # mid-grey so both stone colours read
            _scatter_by_owner(ax, pts, owners, size=22.0)
        ax.set_title(
            f"{source}\nN={len(record['cells'])}, B99={record['observables']['bragg99']:.3f}",
            fontsize=9,
        )
        ax.set_aspect("equal")
        ax.grid(alpha=0.25, linestyle=":")
    for ax in axes.ravel()[len(sources):]:
        ax.axis("off")
    fig.suptitle("Crystal survey: real-space samples  (Black = P1, White = P2)")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=170)
    plt.close(fig)


def plot_metrics(summary: dict[str, dict], path: Path) -> None:
    sources = list(summary)
    mat = np.array([
        [summary[source]["metrics"][metric] for metric in METRIC_COLUMNS]
        for source in sources
    ], dtype=np.float64)
    norm = mat.copy()
    for col in range(norm.shape[1]):
        vals = norm[:, col]
        lo = np.nanmin(vals)
        hi = np.nanmax(vals)
        norm[:, col] = 0.0 if hi <= lo else (vals - lo) / (hi - lo)

    fig, ax = plt.subplots(figsize=(12, max(4, 0.45 * len(sources))))
    im = ax.imshow(norm, aspect="auto", cmap="magma")
    ax.set_xticks(np.arange(len(METRIC_COLUMNS)))
    ax.set_xticklabels(METRIC_COLUMNS, rotation=35, ha="right")
    ax.set_yticks(np.arange(len(sources)))
    ax.set_yticklabels(sources)
    for i, source in enumerate(sources):
        for j, metric in enumerate(METRIC_COLUMNS):
            ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7, color="white")
    ax.set_title("Normalized metric heatmap with raw values")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=170)
    plt.close(fig)


def plot_harmonics(summary: dict[str, dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 6))
    orders = np.arange(1, 13)
    for source, data in summary.items():
        vals = [data["harmonics"][str(order)] for order in orders]
        ax.plot(orders, vals, marker="o", linewidth=1.2, label=source)
    ax.axvline(6, color="#222", linewidth=0.8, linestyle=":")
    ax.axvline(12, color="#222", linewidth=0.8, linestyle=":")
    ax.set_xlabel("angular harmonic order")
    ax.set_ylabel("|mean exp(i m theta)|")
    ax.set_title("Where symmetry breaks: angular harmonics")
    ax.set_xticks(orders)
    ax.grid(alpha=0.35, linestyle=":")
    ax.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=170)
    plt.close(fig)


def plot_diffraction(summary: dict[str, dict], path: Path) -> None:
    sources = list(summary)
    means = [summary[source]["metrics"]["bragg99"] for source in sources]
    stds = [summary[source]["metric_std"]["bragg99"] for source in sources]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(np.arange(len(sources)), means, yerr=stds, capsize=3, color="#4c78a8")
    ax.set_xticks(np.arange(len(sources)))
    ax.set_xticklabels(sources, rotation=30, ha="right")
    ax.set_ylabel("Bragg99")
    ax.set_title("Reciprocal-space concentration across strategies and controls")
    ax.grid(axis="y", alpha=0.35, linestyle=":")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=170)
    plt.close(fig)


def plot_highres_fractal(depth: int, inflation: int, path: Path) -> None:
    fractal = generate_strategy_fractal(depth=depth, inflation=inflation)
    cells = sorted(fractal.board)
    pts = _points_array(cells)
    fig, ax = plt.subplots(figsize=(11, 11))
    if len(pts):
        radii = np.array([_hex_distance(cell) for cell in cells], dtype=float)
        scatter = ax.scatter(pts[:, 0], pts[:, 1], c=radii, cmap="viridis", s=2.0, linewidths=0)
        fig.colorbar(scatter, ax=ax, fraction=0.035, pad=0.02, label="hex radius")
    ax.set_aspect("equal")
    ax.set_title(f"High-resolution verified strategy fractal, depth {depth}, inflation {inflation}")
    ax.grid(alpha=0.20, linestyle=":")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=220)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict:
    started = time.time()
    samples = []
    for agent_name in args.agents:
        for game_idx in range(args.n_games):
            samples.append(
                _play_agent_self_game(
                    agent_name,
                    max_moves=args.max_moves,
                    seed=args.seed + game_idx + 10_000 * len(samples),
                )
            )
    target_n = max(12, int(_mean([sample["moves"] for sample in samples])))
    target_radius = max(6, int(math.ceil(math.sqrt(target_n))) + 3)
    samples.extend(
        _control_samples(
            n_games=args.n_games,
            n_points=target_n,
            radius=target_radius,
            seed=args.seed,
            fractal_depth=args.fractal_depth,
            inflation=args.inflation,
        )
    )
    rust_samples, rust_meta = _try_rust_parallel_self_play(
        n_games=args.rust_games,
        max_moves=args.max_moves,
        sims=args.rust_sims,
    )
    samples.extend(rust_samples)
    records = _score_samples(samples, args.diffraction_grid)
    summary = _summarise(records)

    plot_gallery(records, FIG_GALLERY)
    plot_metrics(summary, FIG_METRICS)
    plot_harmonics(summary, FIG_HARMONICS)
    plot_diffraction(summary, FIG_DIFFRACTION)
    plot_highres_fractal(args.highres_depth, args.inflation, FIG_FRACTAL)

    return {
        "experiment": "crystal_survey",
        "config": vars(args),
        "wall_time_sec": time.time() - started,
        "rust": rust_meta,
        "summary": summary,
        "records": records,
        "sources": sorted(summary),
        "figures": [
            str(FIG_GALLERY),
            str(FIG_METRICS),
            str(FIG_HARMONICS),
            str(FIG_DIFFRACTION),
            str(FIG_FRACTAL),
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", nargs="+", default=DEFAULT_AGENTS)
    parser.add_argument("--n-games", type=int, default=8)
    parser.add_argument("--max-moves", type=int, default=120)
    parser.add_argument("--seed", type=int, default=20260509)
    parser.add_argument("--diffraction-grid", type=int, default=72)
    parser.add_argument("--fractal-depth", type=int, default=2)
    parser.add_argument("--highres-depth", type=int, default=3)
    parser.add_argument("--inflation", type=int, default=5)
    parser.add_argument("--rust-games", type=int, default=4)
    parser.add_argument("--rust-sims", type=int, default=64)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    if args.quick:
        args.agents = ["random", "greedy", "ca_combo_v2"]
        args.n_games = 2
        args.max_moves = 48
        args.diffraction_grid = 48
        args.fractal_depth = 2
        args.highres_depth = 3
        args.rust_games = 1
        args.rust_sims = 16

    result = run(args)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(_clean_json(result), indent=2), encoding="utf-8")
    print(f"wrote {JSON_PATH}")
    for figure in result["figures"]:
        print(f"wrote {figure}")
    print(f"rust: {result['rust']}")
    print(f"wall_time_sec={result['wall_time_sec']:.1f}")


if __name__ == "__main__":
    main()
