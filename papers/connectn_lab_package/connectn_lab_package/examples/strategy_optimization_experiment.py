"""Empirical optimisation-strategy comparison for seeded Hex Connect6.

The experiment is deliberately finite-arena and heuristic.  It asks which value
functions are useful proxies for the infinite-board tactical problem:

    tau > 2 obligation pressure,
    primitive pair-atom witnesses,
    bulk line pressure,
    and direction-family concentration.

Each strategy chooses a two-stone move by minimizing its own value function over
a local candidate-pair set.  This is not a perfect-play solver; it is a way to
stress-test proposed invariants against simulated tactical trajectories.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.strategy_optimization import STRATEGIES, StrategyGameResult, run_strategy_game


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


def _first_threshold_turn(result: StrategyGameResult, side: str, threshold: int = 2) -> int | None:
    for record in result.turn_records:
        tau = record.black_tau if side == "black" else record.white_tau
        if tau > threshold:
            return record.turn
    return None


def _summary_row(result: StrategyGameResult) -> dict[str, Any]:
    final = result.turn_records[-1]
    return {
        "black_strategy": result.black_strategy,
        "white_strategy": result.white_strategy,
        "winner": result.winner or "none",
        "terminal_turn": result.terminal_turn,
        "completed_turns": len(result.turn_records),
        "black_stones": len(result.black),
        "white_stones": len(result.white),
        "final_black_tau": final.black_tau,
        "final_white_tau": final.white_tau,
        "final_black_obligations": final.black_obligations,
        "final_white_obligations": final.white_obligations,
        "final_black_pair_atoms": final.black_pair_atoms,
        "final_white_pair_atoms": final.white_pair_atoms,
        "final_black_bulk_pressure": round(final.black_bulk_pressure, 4),
        "final_white_bulk_pressure": round(final.white_bulk_pressure, 4),
        "final_black_family_max": final.black_family_max,
        "final_white_family_max": final.white_family_max,
        "first_black_tau_gt2": _first_threshold_turn(result, "black"),
        "first_white_tau_gt2": _first_threshold_turn(result, "white"),
        "max_black_obligations": max(record.black_obligations for record in result.turn_records),
        "max_white_obligations": max(record.white_obligations for record in result.turn_records),
        "max_black_pair_atoms": max(record.black_pair_atoms for record in result.turn_records),
        "max_white_pair_atoms": max(record.white_pair_atoms for record in result.turn_records),
    }


def _turn_rows(result: StrategyGameResult) -> list[dict[str, Any]]:
    rows = []
    for record in result.turn_records:
        rows.append({
            "black_strategy": result.black_strategy,
            "white_strategy": result.white_strategy,
            **asdict(record),
            "white_move": json.dumps(record.white_move),
            "black_move": json.dumps(record.black_move),
        })
    return rows


def _aggregate_rows(results: list[StrategyGameResult]) -> list[dict[str, Any]]:
    by_white = defaultdict(list)
    by_black = defaultdict(list)
    for result in results:
        row = _summary_row(result)
        by_white[result.white_strategy].append(row)
        by_black[result.black_strategy].append(row)
    rows = []
    for side, grouped in (("white", by_white), ("black", by_black)):
        for strategy, group in grouped.items():
            black_wins = sum(1 for row in group if row["winner"] == "black")
            white_wins = sum(1 for row in group if row["winner"] == "white")
            no_wins = sum(1 for row in group if row["winner"] == "none")
            rows.append({
                "side": side,
                "strategy": strategy,
                "games": len(group),
                "black_wins": black_wins,
                "white_wins": white_wins,
                "no_wins": no_wins,
                "mean_completed_turns": sum(row["completed_turns"] for row in group) / len(group),
                "mean_final_black_tau": sum(row["final_black_tau"] for row in group) / len(group),
                "mean_final_white_tau": sum(row["final_white_tau"] for row in group) / len(group),
                "mean_black_obligations": sum(row["final_black_obligations"] for row in group) / len(group),
                "mean_white_obligations": sum(row["final_white_obligations"] for row in group) / len(group),
                "mean_black_pair_atoms": sum(row["final_black_pair_atoms"] for row in group) / len(group),
                "mean_white_pair_atoms": sum(row["final_white_pair_atoms"] for row in group) / len(group),
            })
    return rows


def _matrix(results: list[StrategyGameResult], field: str, fill: float = 0.0):
    import numpy as np

    black_strategies = sorted({result.black_strategy for result in results})
    white_strategies = sorted({result.white_strategy for result in results})
    rows = {strategy: i for i, strategy in enumerate(black_strategies)}
    cols = {strategy: i for i, strategy in enumerate(white_strategies)}
    matrix = np.full((len(black_strategies), len(white_strategies)), fill, dtype=float)
    for result in results:
        value = _summary_row(result)[field]
        if value is None:
            value = fill
        matrix[rows[result.black_strategy], cols[result.white_strategy]] = float(value)
    return matrix, black_strategies, white_strategies


def _make_figures(out_dir: Path, results: list[StrategyGameResult]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    matrix, black_labels, white_labels = _matrix(results, "completed_turns")
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(matrix, cmap="viridis")
    ax.set_title("Completed turns before terminal state or horizon")
    ax.set_xlabel("White strategy")
    ax.set_ylabel("Black strategy")
    ax.set_xticks(range(len(white_labels)))
    ax.set_xticklabels(white_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(black_labels)))
    ax.set_yticklabels(black_labels)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(fig_dir / "completed_turns_heatmap.png", dpi=180)
    plt.close(fig)

    matrix, black_labels, white_labels = _matrix(results, "first_black_tau_gt2", fill=-1)
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(matrix, cmap="magma")
    ax.set_title("First Black tau > 2 turn (-1 means not observed)")
    ax.set_xlabel("White strategy")
    ax.set_ylabel("Black strategy")
    ax.set_xticks(range(len(white_labels)))
    ax.set_xticklabels(white_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(black_labels)))
    ax.set_yticklabels(black_labels)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(fig_dir / "first_black_tau_gt2_heatmap.png", dpi=180)
    plt.close(fig)

    matrix, black_labels, white_labels = _matrix(results, "final_black_obligations")
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(matrix, cmap="plasma")
    ax.set_title("Final Black urgent-obligation count")
    ax.set_xlabel("White strategy")
    ax.set_ylabel("Black strategy")
    ax.set_xticks(range(len(white_labels)))
    ax.set_xticklabels(white_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(black_labels)))
    ax.set_yticklabels(black_labels)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(fig_dir / "final_black_obligations_heatmap.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    for result in results:
        summary = _summary_row(result)
        ax.scatter(
            summary["final_black_bulk_pressure"],
            summary["final_black_pair_atoms"] + 0.06 * summary["final_black_obligations"],
            s=46,
            alpha=0.72,
            label=result.black_strategy if result.white_strategy == sorted({r.white_strategy for r in results})[0] else None,
        )
    ax.set_xlabel("final Black bulk pressure")
    ax.set_ylabel("final Black atom count + obligation load")
    ax.set_title("Bulk pressure versus atom/fork load")
    handles, labels = ax.get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    if by_label:
        ax.legend(by_label.values(), by_label.keys(), fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "bulk_vs_atom_load.png", dpi=180)
    plt.close(fig)

    representatives = [
        result
        for result in results
        if (result.black_strategy, result.white_strategy)
        in {("attacker", "min_tau"), ("hybrid", "hybrid"), ("min_bulk", "min_atoms"), ("min_atoms", "min_bulk")}
    ]
    fig, ax = plt.subplots(figsize=(9, 5))
    for result in representatives:
        turns = [record.turn for record in result.turn_records]
        ax.plot(turns, [record.black_tau for record in result.turn_records], label=f"B {result.black_strategy} / W {result.white_strategy}")
    ax.axhline(2, color="#555", linewidth=1, alpha=0.6)
    ax.set_xlabel("turn")
    ax.set_ylabel("Black capped tau")
    ax.set_title("Representative transversal trajectories")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "representative_tau_trajectories.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, results: list[StrategyGameResult]) -> None:
    summaries = [_summary_row(result) for result in results]
    aggregate = _aggregate_rows(results)
    black_wins = sum(1 for row in summaries if row["winner"] == "black")
    white_wins = sum(1 for row in summaries if row["winner"] == "white")
    no_wins = sum(1 for row in summaries if row["winner"] == "none")
    best_white_delay = sorted(
        [row for row in aggregate if row["side"] == "white"],
        key=lambda row: (-row["mean_completed_turns"], row["mean_black_obligations"], row["mean_black_pair_atoms"]),
    )
    best_black_pressure = sorted(
        [row for row in aggregate if row["side"] == "black"],
        key=lambda row: (-row["mean_black_obligations"], -row["mean_final_black_tau"], -row["mean_black_pair_atoms"]),
    )
    lines = [
        "# Strategy Optimisation Experiment",
        "",
        "Finite D6/Hex Connect6 strategy probe: Black seeds `(0, 0)`, then White and Black alternately place two stones. Each strategy minimizes a different local value over candidate two-stone moves.",
        "",
        "This is an empirical invariant test, not a proof of perfect play. The target is to discover which bulk-informed values correlate with `tau > 2` forcing pressure and primitive atom emergence.",
        "",
        "## Results",
        "",
        f"- games: {len(results)}",
        f"- black wins: {black_wins}",
        f"- white wins: {white_wins}",
        f"- no terminal line win by horizon: {no_wins}",
        "",
        "## Best White Delay Proxies",
        "",
    ]
    for row in best_white_delay[:5]:
        lines.append(
            f"- `{row['strategy']}`: mean turns={row['mean_completed_turns']:.2f}, "
            f"mean final Black obligations={row['mean_black_obligations']:.2f}, "
            f"mean final Black pair atoms={row['mean_black_pair_atoms']:.2f}"
        )
    lines.extend(["", "## Strongest Black Pressure Proxies", ""])
    for row in best_black_pressure[:5]:
        lines.append(
            f"- `{row['strategy']}`: mean final Black obligations={row['mean_black_obligations']:.2f}, "
            f"mean final Black tau={row['mean_final_black_tau']:.2f}, "
            f"mean final Black pair atoms={row['mean_black_pair_atoms']:.2f}"
        )
    lines.extend([
        "",
        "## Files",
        "",
        "- `game_summary.csv`: one row per strategy pairing.",
        "- `turn_metrics.csv`: per-turn tau, atom, bulk, and family values.",
        "- `strategy_aggregate.csv`: side-wise aggregate performance.",
        "- `strategy_games.json`: complete structured corpus.",
        "- `figures/`: outcome, tau-threshold, pressure, and trajectory figures.",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, preset: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if preset == "smoke":
        black_strategies = ("attacker", "min_bulk")
        white_strategies = ("min_tau", "hybrid")
        radius, turns, candidate_limit = 5, 8, 9
    else:
        black_strategies = ("attacker", "hybrid", "min_bulk", "min_atoms")
        white_strategies = ("earliest", "min_tau", "min_atoms", "min_bulk", "min_family", "hybrid")
        radius, turns, candidate_limit = 6, 16, 12

    results = [
        run_strategy_game(
            black_strategy=black_strategy,
            white_strategy=white_strategy,
            radius=radius,
            turns=turns,
            k=6,
            candidate_limit=candidate_limit,
        )
        for black_strategy in black_strategies
        for white_strategy in white_strategies
    ]

    summaries = [_summary_row(result) for result in results]
    _write_csv(out_dir / "game_summary.csv", summaries)
    _write_csv(out_dir / "turn_metrics.csv", [row for result in results for row in _turn_rows(result)])
    _write_csv(out_dir / "strategy_aggregate.csv", _aggregate_rows(results))
    (out_dir / "strategy_games.json").write_text(json.dumps(_jsonable(results), indent=2, sort_keys=True), encoding="utf-8")
    _make_figures(out_dir, results)
    _write_report(out_dir, results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=("smoke", "rich"), default="rich")
    parser.add_argument("--out", default="strategy_optimization_results/rich_run")
    args = parser.parse_args()
    run(Path(args.out), preset=args.preset)


if __name__ == "__main__":
    main()
