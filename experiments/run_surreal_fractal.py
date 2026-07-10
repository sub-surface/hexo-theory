"""Generate verified surreal-strategy fractals for HeXO."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.fractal_strategy import (
    StrategyFractal,
    generate_strategy_fractal,
    verify_fractal_wins,
    winning_lines_for_board,
)


JSON_PATH = Path("evidence/results/surreal_fractal_strategy.json")
STRATEGY_FIGURE_PATH = Path("evidence/figures/fig_surreal_fractal_strategy.png")
SHELL_FIGURE_PATH = Path("evidence/figures/fig_surreal_fractal_shells.png")


def axial_to_xy(cell: tuple[int, int]) -> tuple[float, float]:
    q, r = cell
    return (q + 0.5 * r, (math.sqrt(3.0) / 2.0) * r)


def _cell_level_map(fractal: StrategyFractal) -> dict[tuple[int, int], int]:
    levels: dict[tuple[int, int], int] = {}
    for motif in fractal.motifs:
        for cell in motif.cells:
            levels[cell] = max(levels.get(cell, motif.level), motif.level)
    return levels


def plot_strategy(fractal: StrategyFractal, path: Path) -> None:
    cell_levels = _cell_level_map(fractal)
    cells = sorted(fractal.board)
    xy = np.array([axial_to_xy(cell) for cell in cells])
    colors = np.array([cell_levels[cell] for cell in cells])

    fig, ax = plt.subplots(figsize=(10, 10))
    if len(xy):
        scatter = ax.scatter(
            xy[:, 0],
            xy[:, 1],
            c=colors,
            s=10,
            cmap="viridis",
            linewidths=0,
            alpha=0.92,
        )
        cbar = fig.colorbar(scatter, ax=ax, fraction=0.035, pad=0.02)
        cbar.set_label("recursion level")
    for motif in fractal.motifs:
        if motif.level < fractal.depth:
            continue
        line_xy = np.array([axial_to_xy(cell) for cell in motif.cells])
        ax.plot(line_xy[:, 0], line_xy[:, 1], color="black", alpha=0.08, linewidth=0.5)
    ax.set_aspect("equal")
    ax.set_title(
        f"Verified HeXO strategy fractal: depth {fractal.depth}, inflation {fractal.inflation}"
    )
    ax.set_xlabel("axial q + r/2")
    ax.set_ylabel("sqrt(3) r / 2")
    ax.grid(alpha=0.25, linestyle=":")
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close(fig)


def _stones_by_level(fractal: StrategyFractal) -> list[int]:
    counts: list[int] = []
    for level in range(fractal.depth + 1):
        stones = {
            cell
            for motif in fractal.motifs
            if motif.level == level
            for cell in motif.cells
        }
        counts.append(len(stones))
    return counts


def plot_shells(fractal: StrategyFractal, path: Path) -> None:
    levels = np.arange(fractal.depth + 1)
    centers = np.array(fractal.shell_counts)
    motifs = centers * 3
    stones = np.array(_stones_by_level(fractal))

    fig, ax = plt.subplots(figsize=(9, 5))
    width = 0.26
    ax.bar(levels - width, centers, width=width, label="centers", color="#4c78a8")
    ax.bar(levels, motifs, width=width, label="winning motifs", color="#f58518")
    ax.bar(levels + width, stones, width=width, label="unique motif stones", color="#54a24b")
    ax.set_yscale("log")
    ax.set_xlabel("recursion level")
    ax.set_ylabel("count (log scale)")
    ax.set_title(f"Branching profile, dimension estimate {fractal.dimension_estimate:.3f}")
    ax.set_xticks(levels)
    ax.grid(axis="y", alpha=0.35, linestyle=":")
    ax.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close(fig)


def _json_cell(cell: tuple[int, int]) -> list[int]:
    return [cell[0], cell[1]]


def build_result(fractal: StrategyFractal, wall_time_sec: float) -> dict:
    winning_lines = winning_lines_for_board(fractal.board, fractal.player)
    return {
        "experiment": "surreal_fractal_strategy",
        "config": {
            "depth": fractal.depth,
            "inflation": fractal.inflation,
            "player": fractal.player,
        },
        "wall_time_sec": wall_time_sec,
        "verified": verify_fractal_wins(fractal),
        "stone_count": len(fractal.board),
        "motif_count": len(fractal.motifs),
        "winning_line_count": len(winning_lines),
        "shell_counts": list(fractal.shell_counts),
        "motif_counts_by_level": [count * 3 for count in fractal.shell_counts],
        "unique_stones_by_level": _stones_by_level(fractal),
        "dimension_estimate_log6_loginflation": fractal.dimension_estimate,
        "sample_winning_lines": [
            [_json_cell(cell) for cell in line]
            for line in winning_lines[:12]
        ],
        "interpretation": (
            "A verified strategy pattern: every recursive motif is a legal "
            "HeXO length-6 line for one player. This is not a legal transcript."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=3)
    parser.add_argument("--inflation", type=int, default=5)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    if args.quick:
        args.depth = min(args.depth, 2)

    started = time.time()
    fractal = generate_strategy_fractal(depth=args.depth, inflation=args.inflation)
    if not verify_fractal_wins(fractal):
        raise RuntimeError("generated fractal failed win verification")
    plot_strategy(fractal, STRATEGY_FIGURE_PATH)
    plot_shells(fractal, SHELL_FIGURE_PATH)
    elapsed = time.time() - started

    result = build_result(fractal, elapsed)
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"wrote {JSON_PATH}, {STRATEGY_FIGURE_PATH}, {SHELL_FIGURE_PATH} "
        f"in {elapsed:.1f}s"
    )


if __name__ == "__main__":
    main()
