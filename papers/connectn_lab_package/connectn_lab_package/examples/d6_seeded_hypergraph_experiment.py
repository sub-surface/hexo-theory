"""Explore the D6 Hex Connect6 hypergraph with an OEIS-style greedy process.

OEIS A392177 uses a square spiral and a two-color greedy exclusion rule: each
player places at the earliest spiral cell not attacked by the opponent.  This
script ports that idea to normal 1-2-2 Hex Connect6:

    Black seed at (0, 0).
    White places two stones.
    Black then places two stones after each subsequent White move.
    "Attack" is the weighted 2-section of the length-6 A2 winning hypergraph.

The attack threshold chooses how strong a shared winning-line relation must be:
threshold 1 forbids any co-occurrence in a length-6 line, while threshold 5 only
forbids immediately adjacent cells in a Connect6 line.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.d6_seeded_hypergraph import (
    D6SeededProcessResult,
    d6_sector,
    run_d6_seeded_process,
    shell_color_counts,
)
from connectn_lab.progressions import cell_radius
from connectn_lab.lattices import a2_hex


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_jsonable(v) for v in value)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _run_key(result: D6SeededProcessResult) -> str:
    return f"r{result.radius}_t{result.turns}_k{result.k}_w{result.attack_min_weight}"


def _turn_rows(result: D6SeededProcessResult) -> list[dict[str, Any]]:
    rows = []
    for record in result.turn_records:
        rows.append({
            "run": _run_key(result),
            "radius": result.radius,
            "k": result.k,
            "attack_min_weight": result.attack_min_weight,
            "turn": record.turn,
            "black_stones": record.black_stones,
            "white_stones": record.white_stones,
            "black_obligations": record.black_obligations,
            "white_obligations": record.white_obligations,
            "black_tau": record.black_tau,
            "white_tau": record.white_tau,
            "black_components": record.black_components,
            "white_components": record.white_components,
            "black_support": record.black_support,
            "white_support": record.white_support,
            "black_sector_counts": json.dumps(record.black_sector_counts),
            "white_sector_counts": json.dumps(record.white_sector_counts),
            "white_added": json.dumps(record.white_added),
            "black_added": json.dumps(record.black_added),
        })
    return rows


def _sequence_rows(result: D6SeededProcessResult) -> list[dict[str, Any]]:
    index_by_cell = {cell: index for index, cell in enumerate(result.order)}
    rows = []
    for color, stones in (("black", result.black), ("white", result.white)):
        for cell in sorted(stones, key=lambda c: index_by_cell[c]):
            rows.append({
                "run": _run_key(result),
                "color": color,
                "spiral_index": index_by_cell[cell],
                "q": cell[0],
                "r": cell[1],
                "shell": cell_radius(cell, a2_hex()),
                "sector": d6_sector(cell) if cell != (0, 0) else -1,
            })
    return rows


def _shell_rows(result: D6SeededProcessResult) -> list[dict[str, Any]]:
    rows = []
    for shell, (black_count, white_count) in shell_color_counts(result).items():
        rows.append({
            "run": _run_key(result),
            "radius": result.radius,
            "k": result.k,
            "attack_min_weight": result.attack_min_weight,
            "shell": shell,
            "black": black_count,
            "white": white_count,
            "imbalance": black_count - white_count,
            "total": black_count + white_count,
        })
    return rows


def _summary_rows(results: list[D6SeededProcessResult]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        last = result.turn_records[-1] if result.turn_records else None
        black_sector = [0] * 6
        white_sector = [0] * 6
        for cell in result.black:
            if cell != (0, 0):
                black_sector[d6_sector(cell)] += 1
        for cell in result.white:
            if cell != (0, 0):
                white_sector[d6_sector(cell)] += 1
        rows.append({
            "run": _run_key(result),
            "radius": result.radius,
            "requested_turns": result.turns,
            "completed_records": len(result.turn_records),
            "k": result.k,
            "attack_min_weight": result.attack_min_weight,
            "black_stones": len(result.black),
            "white_stones": len(result.white),
            "black_first_terms": json.dumps(result.black_sequence_indices[:80]),
            "white_first_terms": json.dumps(result.white_sequence_indices[:80]),
            "final_black_tau": None if last is None else last.black_tau,
            "final_white_tau": None if last is None else last.white_tau,
            "final_black_obligations": None if last is None else last.black_obligations,
            "final_white_obligations": None if last is None else last.white_obligations,
            "black_sector_counts": json.dumps(black_sector),
            "white_sector_counts": json.dumps(white_sector),
        })
    return rows


def _axial_to_xy(cell):
    q, r = cell
    return q + 0.5 * r, (math.sqrt(3) / 2.0) * r


def _make_figures(out_dir: Path, results: list[D6SeededProcessResult]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        fig, ax = plt.subplots(figsize=(8, 8))
        for color, stones, marker_color in (
            ("black", result.black, "#222222"),
            ("white", result.white, "#d62728"),
        ):
            xs, ys = zip(*[_axial_to_xy(cell) for cell in stones]) if stones else ([], [])
            ax.scatter(xs, ys, s=24, c=marker_color, label=color, alpha=0.86)
        ax.set_title(f"D6 seeded hypergraph occupancy, attack weight >= {result.attack_min_weight}")
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        ax.legend(loc="upper right")
        fig.tight_layout()
        fig.savefig(fig_dir / f"occupancy_w{result.attack_min_weight}.png", dpi=180)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for result in results:
        turns = [record.turn for record in result.turn_records]
        ax.plot(turns, [record.black_tau for record in result.turn_records], label=f"B w>={result.attack_min_weight}")
        ax.plot(turns, [record.white_tau for record in result.turn_records], linestyle="--", label=f"W w>={result.attack_min_weight}")
    ax.axhline(2, color="#555", linewidth=1, alpha=0.6)
    ax.set_xlabel("recorded White turn after seed")
    ax.set_ylabel("capped tau of urgent obligations")
    ax.set_title("Urgent-obligation transversal pressure")
    ax.legend(ncols=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "tau_over_turn.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for result in results:
        turns = [record.turn for record in result.turn_records]
        ax.plot(turns, [record.black_obligations for record in result.turn_records], label=f"B w>={result.attack_min_weight}")
        ax.plot(turns, [record.white_obligations for record in result.turn_records], linestyle="--", label=f"W w>={result.attack_min_weight}")
    ax.set_xlabel("recorded White turn after seed")
    ax.set_ylabel("urgent obligation count")
    ax.set_title("Urgent obligations over greedy D6 process")
    ax.legend(ncols=2, fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "obligations_over_turn.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for result in results:
        shells = shell_color_counts(result)
        xs = sorted(shells)
        ys = [shells[s][0] - shells[s][1] for s in xs]
        ax.plot(xs, ys, marker="o", label=f"w>={result.attack_min_weight}")
    ax.axhline(0, color="#555", linewidth=1, alpha=0.6)
    ax.set_xlabel("D6 shell")
    ax.set_ylabel("black minus white")
    ax.set_title("Shell imbalance")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "shell_imbalance.png", dpi=180)
    plt.close(fig)

    sector_matrix = []
    ylabels = []
    for result in results:
        black = [0] * 6
        white = [0] * 6
        for cell in result.black:
            if cell != (0, 0):
                black[d6_sector(cell)] += 1
        for cell in result.white:
            if cell != (0, 0):
                white[d6_sector(cell)] += 1
        sector_matrix.append([b - w for b, w in zip(black, white)])
        ylabels.append(f"w>={result.attack_min_weight}")
    fig, ax = plt.subplots(figsize=(8, 4.6))
    im = ax.imshow(np.array(sector_matrix), cmap="coolwarm")
    ax.set_xticks(range(6))
    ax.set_xticklabels([f"S{i}" for i in range(6)])
    ax.set_yticks(range(len(ylabels)))
    ax.set_yticklabels(ylabels)
    ax.set_title("D6 sector imbalance")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(fig_dir / "sector_imbalance_heatmap.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    for result in results:
        black_y = [result.attack_min_weight] * len(result.black_sequence_indices)
        white_y = [result.attack_min_weight + 0.15] * len(result.white_sequence_indices)
        ax.scatter(result.black_sequence_indices, black_y, s=8, c="#222222", alpha=0.6)
        ax.scatter(result.white_sequence_indices, white_y, s=8, c="#d62728", alpha=0.6)
    ax.set_xlabel("D6 spiral index")
    ax.set_ylabel("attack threshold")
    ax.set_title("OEIS-style readout sequence positions")
    fig.tight_layout()
    fig.savefig(fig_dir / "spiral_sequence_scatter.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, results: list[D6SeededProcessResult]) -> None:
    summary = _summary_rows(results)
    lines = [
        "# D6 Seeded Hypergraph Experiment",
        "",
        "This is an OEIS A392177-inspired exploration of normal 1-2-2 Hex Connect6 on the A2 hex lattice.",
        "",
        "A392177 uses a square spiral and two colors, placing each next piece at the smallest spiral cell not attacked by the opposite color. Here the square-spiral/knight graph is replaced by a D6 shell spiral and the weighted 2-section of the Connect6 winning-set hypergraph.",
        "",
        "## Rule",
        "",
        "- Black starts with a single seed at `(0, 0)`.",
        "- White places two stones at the earliest unoccupied non-attacked D6 spiral cells.",
        "- After White's opening response, Black places two stones after each White move.",
        "- A cell is attacked by an opponent stone when both cells co-occur in at least `attack_min_weight` length-6 hex winning progressions.",
        "",
        "## Runs",
        "",
    ]
    for row in summary:
        lines.append(
            f"- `{row['run']}`: black={row['black_stones']}, white={row['white_stones']}, "
            f"final tau B/W={row['final_black_tau']}/{row['final_white_tau']}, "
            f"final obligations B/W={row['final_black_obligations']}/{row['final_white_obligations']}"
        )
    lines.extend([
        "",
        "## Outputs",
        "",
        "- `run_summary.csv`: one row per threshold run.",
        "- `turn_metrics.csv`: tau, obligation, support, component, and sector metrics per recorded turn.",
        "- `sequence_terms.csv`: OEIS-style spiral-index readout for Black and White stones.",
        "- `shell_counts.csv`: Black/White counts by D6 shell.",
        "- `d6_seeded_hypergraph.json`: full structured corpus.",
        "- `figures/`: occupancy maps, tau curves, obligation curves, shell/sector imbalance, and sequence scatter.",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, preset: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if preset == "smoke":
        radius, turns, thresholds = 8, 18, (1, 3, 5)
    else:
        radius, turns, thresholds = 18, 90, (1, 2, 3, 4, 5)

    results = [
        run_d6_seeded_process(radius=radius, turns=turns, k=6, attack_min_weight=threshold)
        for threshold in thresholds
    ]
    _write_csv(out_dir / "run_summary.csv", _summary_rows(results))
    _write_csv(out_dir / "turn_metrics.csv", [row for result in results for row in _turn_rows(result)])
    _write_csv(out_dir / "sequence_terms.csv", [row for result in results for row in _sequence_rows(result)])
    _write_csv(out_dir / "shell_counts.csv", [row for result in results for row in _shell_rows(result)])
    (out_dir / "d6_seeded_hypergraph.json").write_text(json.dumps(_jsonable(results), indent=2, sort_keys=True), encoding="utf-8")
    _make_figures(out_dir, results)
    _write_report(out_dir, results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=("smoke", "rich"), default="rich")
    parser.add_argument("--out", default="d6_seeded_hypergraph_results/rich_run")
    args = parser.parse_args()
    run(Path(args.out), preset=args.preset)


if __name__ == "__main__":
    main()
