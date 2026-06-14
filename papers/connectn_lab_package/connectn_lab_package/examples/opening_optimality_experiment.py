"""Canonical opening atlas for seeded 1-2-2 Hex Connect6.

This combines the earlier findings:

* Black and White should use distinct value functions.
* Early play is mostly proto-atomic: bulk/family/tau debt matters before
  primitive pair atoms appear.
* Static opening fields are cheap and can be batched on the GPU; exact rollout
  needs the CPU hypergraph/tau logic.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.opening_optimality import (
    BLACK_OPENING_STRATEGIES,
    WHITE_SCREENING_STRATEGIES,
    OpeningAnalysisRecord,
    analyse_opening,
    canonical_white_openings,
    torch_static_opening_features,
)


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


def _opening_rows(openings, features) -> list[dict[str, Any]]:
    rows = []
    for i, opening in enumerate(openings):
        black_bulk = features["black_bulk_pressure"][i]
        white_bulk = features["white_bulk_pressure"][i]
        blocked = features["root_lines_blocked"][i]
        white_two = features["white_two_lines"][i]
        vulnerability = black_bulk - white_bulk - 0.75 * blocked + 0.35 * white_two
        rows.append({
            "opening_id": opening.opening_id,
            "pair": json.dumps(opening.pair),
            "orbit_size": opening.orbit_size,
            "max_radius": opening.max_radius,
            "min_pair_distance": opening.min_pair_distance,
            "black_bulk_pressure": round(black_bulk, 6),
            "white_bulk_pressure": round(white_bulk, 6),
            "root_lines_blocked": blocked,
            "white_two_lines": white_two,
            "static_vulnerability": round(vulnerability, 6),
        })
    return rows


def _select_rollout_openings(openings, opening_rows: list[dict[str, Any]], target: int):
    by_id = {opening.opening_id: opening for opening in openings}
    ranked = sorted(opening_rows, key=lambda row: row["static_vulnerability"])
    selected_ids: list[str] = []
    for row in ranked[: target // 3]:
        selected_ids.append(row["opening_id"])
    for row in ranked[-target // 3 :]:
        selected_ids.append(row["opening_id"])
    if target - len(set(selected_ids)) > 0:
        step = max(1, len(ranked) // (target - len(set(selected_ids))))
        for row in ranked[::step]:
            selected_ids.append(row["opening_id"])
            if len(set(selected_ids)) >= target:
                break
    return [by_id[opening_id] for opening_id in dict.fromkeys(selected_ids).keys()]


def _analysis_row(record: OpeningAnalysisRecord) -> dict[str, Any]:
    row = asdict(record)
    row["white_pair"] = json.dumps(row["white_pair"])
    row["black_reply"] = json.dumps(row["black_reply"])
    row["winner"] = row["winner"] or "none"
    return row


def _aggregate_opening_rows(records: list[OpeningAnalysisRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[OpeningAnalysisRecord]] = defaultdict(list)
    for record in records:
        grouped[record.opening_id].append(record)
    rows = []
    for opening_id, group in grouped.items():
        winners = Counter(record.winner or "none" for record in group)
        rows.append({
            "opening_id": opening_id,
            "rollouts": len(group),
            "black_wins": winners["black"],
            "white_wins": winners["white"],
            "none": winners["none"],
            "mean_completed_turns": sum(record.completed_turns for record in group) / len(group),
            "mean_final_black_tau": sum(record.final_black_tau for record in group) / len(group),
            "mean_final_white_tau": sum(record.final_white_tau for record in group) / len(group),
            "max_black_tau": max(record.max_black_tau for record in group),
            "max_white_tau": max(record.max_white_tau for record in group),
            "mean_black_obligations": sum(record.final_black_obligations for record in group) / len(group),
            "mean_white_obligations": sum(record.final_white_obligations for record in group) / len(group),
            "max_black_obligations": max(record.max_black_obligations for record in group),
            "max_white_obligations": max(record.max_white_obligations for record in group),
        })
    return sorted(rows, key=lambda row: (row["black_wins"], row["mean_black_obligations"], -row["mean_completed_turns"]), reverse=True)


def _strategy_matrix(records: list[OpeningAnalysisRecord]):
    import numpy as np

    black = sorted({record.black_strategy for record in records})
    white = sorted({record.white_strategy for record in records})
    matrix = np.zeros((len(black), len(white)))
    counts = np.zeros((len(black), len(white)))
    bi = {name: i for i, name in enumerate(black)}
    wi = {name: i for i, name in enumerate(white)}
    for record in records:
        i = bi[record.black_strategy]
        j = wi[record.white_strategy]
        matrix[i, j] += 1 if record.winner == "black" else -1 if record.winner == "white" else 0
        counts[i, j] += 1
    return matrix / counts.clip(min=1), black, white


def _make_figures(out_dir: Path, opening_rows: list[dict[str, Any]], records: list[OpeningAnalysisRecord]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    x = [row["black_bulk_pressure"] for row in opening_rows]
    y = [row["white_bulk_pressure"] for row in opening_rows]
    c = [row["root_lines_blocked"] for row in opening_rows]
    sc = ax.scatter(x, y, c=c, cmap="viridis", s=28, alpha=0.78)
    ax.set_xlabel("Black rooted bulk pressure after White pair")
    ax.set_ylabel("White bulk pressure after White pair")
    ax.set_title("Canonical opening static field, GPU-batched")
    fig.colorbar(sc, ax=ax, label="root lines blocked")
    fig.tight_layout()
    fig.savefig(fig_dir / "static_bulk_scatter.png", dpi=180)
    plt.close(fig)

    ranked = sorted(opening_rows, key=lambda row: row["static_vulnerability"])
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot([row["static_vulnerability"] for row in ranked], color="#1f77b4")
    ax.axhline(0, color="#555", linewidth=1, alpha=0.6)
    ax.set_xlabel("canonical opening rank, safe to vulnerable")
    ax.set_ylabel("static vulnerability")
    ax.set_title("White opening vulnerability spectrum")
    fig.tight_layout()
    fig.savefig(fig_dir / "opening_vulnerability_spectrum.png", dpi=180)
    plt.close(fig)

    matrix, black_labels, white_labels = _strategy_matrix(records)
    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    im = ax.imshow(matrix, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(white_labels)))
    ax.set_xticklabels(white_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(black_labels)))
    ax.set_yticklabels(black_labels)
    ax.set_title("Outcome pressure by asymmetric strategy pair\n(+1 Black win, -1 White win)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(fig_dir / "strategy_outcome_matrix.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(
        [record.final_black_bulk_pressure for record in records],
        [record.final_black_obligations for record in records],
        c=[record.max_black_tau for record in records],
        cmap="magma",
        s=24,
        alpha=0.65,
    )
    ax.set_xlabel("final Black bulk pressure")
    ax.set_ylabel("final Black obligations")
    ax.set_title("Opening rollouts: bulk pressure versus obligation debt")
    fig.tight_layout()
    fig.savefig(fig_dir / "rollout_bulk_vs_obligations.png", dpi=180)
    plt.close(fig)

    agg = _aggregate_opening_rows(records)[:20]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    labels = [row["opening_id"] for row in agg]
    x = list(range(len(labels)))
    ax.bar(x, [row["mean_black_obligations"] for row in agg], label="Black obligations")
    ax.plot(x, [row["mean_completed_turns"] for row in agg], color="#d62728", marker="o", label="completed turns")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_title("Most Black-favorable selected openings")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "black_favorable_openings.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, static_radius: int, eval_radius: int, opening_rows, selected, records, device: str) -> None:
    winners = Counter(record.winner or "none" for record in records)
    aggregate = _aggregate_opening_rows(records)
    safest = sorted(aggregate, key=lambda row: (row["black_wins"], row["mean_black_obligations"], -row["mean_completed_turns"]))[:8]
    vulnerable = aggregate[:8]
    lines = [
        "# Opening Optimality Atlas",
        "",
        "Canonical D6 White opening pairs are enumerated against the normal Black seed `(0, 0)`. Static opening fields are computed in one Torch batch, then a selected frontier of openings is tested by asymmetric Black/White rollout strategies.",
        "",
        "## Run",
        "",
        f"- static opening radius: {static_radius}",
        f"- exact rollout radius: {eval_radius}",
        f"- static openings: {len(opening_rows)}",
        f"- selected rollout openings: {len(selected)}",
        f"- rollout records: {len(records)}",
        f"- Torch device: `{device}`",
        f"- rollout outcomes: {dict(sorted(winners.items()))}",
        "",
        "## Safest Selected White Openings",
        "",
    ]
    for row in safest:
        lines.append(
            f"- `{row['opening_id']}`: black wins={row['black_wins']}, mean Black obligations={row['mean_black_obligations']:.2f}, mean turns={row['mean_completed_turns']:.2f}"
        )
    lines.extend(["", "## Most Black-Favorable Selected Openings", ""])
    for row in vulnerable:
        lines.append(
            f"- `{row['opening_id']}`: black wins={row['black_wins']}, mean Black obligations={row['mean_black_obligations']:.2f}, max Black tau={row['max_black_tau']}"
        )
    lines.extend([
        "",
        "## Interpretation",
        "",
        "This atlas is not a perfect-play proof. It is designed to separate opening pairs that merely look central from pairs that suppress Black's conversion from rooted bulk pressure into `tau > 2` obligation debt under asymmetric local strategies.",
        "",
        "## Files",
        "",
        "- `opening_static.csv`: every canonical opening and GPU-batched static features.",
        "- `opening_rollouts.csv`: exact asymmetric rollout records.",
        "- `opening_aggregate.csv`: per-opening aggregate over strategy pairs.",
        "- `opening_atlas.json`: structured corpus.",
        "- `figures/`: static spectrum, strategy matrix, and rollout pressure figures.",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, preset: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if preset == "smoke":
        static_radius, eval_radius, target, rollout_turns, candidate_limit = 2, 5, 6, 2, 7
        black_strategies = ("debt_builder", "hybrid")
        white_strategies = ("screen_counter", "min_tau")
    else:
        static_radius, eval_radius, target, rollout_turns, candidate_limit = 5, 6, 30, 4, 8
        black_strategies = ("debt_builder", "attacker", "hybrid", "min_bulk")
        white_strategies = ("screen_counter", "min_tau", "min_bulk", "min_family")

    openings = canonical_white_openings(static_radius)
    features = torch_static_opening_features(openings, eval_radius=eval_radius, k=6, prefer_cuda=True)
    opening_rows = _opening_rows(openings, features)
    selected = _select_rollout_openings(openings, opening_rows, target=target)
    records = [
        analyse_opening(
            opening=opening,
            black_strategy=black_strategy,
            white_strategy=white_strategy,
            eval_radius=eval_radius,
            rollout_turns=rollout_turns,
            candidate_limit=candidate_limit,
            k=6,
        )
        for opening in selected
        for black_strategy in black_strategies
        for white_strategy in white_strategies
    ]

    _write_csv(out_dir / "opening_static.csv", opening_rows)
    _write_csv(out_dir / "opening_rollouts.csv", [_analysis_row(record) for record in records])
    _write_csv(out_dir / "opening_aggregate.csv", _aggregate_opening_rows(records))
    (out_dir / "opening_atlas.json").write_text(
        json.dumps(
            _jsonable({
                "preset": preset,
                "static_radius": static_radius,
                "eval_radius": eval_radius,
                "torch_device": features["device"],
                "openings": openings,
                "selected_opening_ids": [opening.opening_id for opening in selected],
                "rollouts": records,
            }),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _make_figures(out_dir, opening_rows, records)
    _write_report(out_dir, static_radius, eval_radius, opening_rows, selected, records, str(features["device"]))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=("smoke", "rich"), default="rich")
    parser.add_argument("--out", default="opening_optimality_results/rich_run")
    args = parser.parse_args()
    run(Path(args.out), preset=args.preset)


if __name__ == "__main__":
    main()
