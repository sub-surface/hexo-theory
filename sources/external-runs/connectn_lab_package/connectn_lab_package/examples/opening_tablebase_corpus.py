"""Build a radius-n opening corpus using cached minimax/tablebase search."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.opening_tablebase import SearchConfig, build_opening_corpus
from examples.game_viewer import classify_game_wlu, flatten_corpus_games


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


def _row(record) -> dict[str, Any]:
    d = asdict(record)
    d["wlu"] = _row_wlu(record)
    for key in ("white_pair", "best_black_reply", "principal_variation"):
        d[key] = json.dumps(_jsonable(d[key]), sort_keys=True)
    d["score"] = round(d["score"], 6)
    d["black_bulk_pressure"] = round(d["black_bulk_pressure"], 6)
    d["white_bulk_pressure"] = round(d["white_bulk_pressure"], 6)
    return d


def _row_wlu(record) -> str:
    game = flatten_corpus_games({"openings": [_jsonable(record)]})[0]
    return classify_game_wlu(game)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _make_figures(out_dir: Path, rows: list) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(rows, key=lambda row: row.score, reverse=True)
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.plot([row.score for row in ranked], color="#1f77b4")
    ax.axhline(0, color="#555", linewidth=1, alpha=0.6)
    ax.set_xlabel("canonical opening rank, Black-favorable to White-favorable")
    ax.set_ylabel("minimax score")
    ax.set_title("Radius opening tablebase score spectrum")
    fig.tight_layout()
    fig.savefig(fig_dir / "score_spectrum.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    sc = ax.scatter(
        [row.black_bulk_pressure for row in rows],
        [row.black_obligations for row in rows],
        c=[row.black_tau for row in rows],
        cmap="magma",
        s=36,
        alpha=0.78,
    )
    ax.set_xlabel("Black bulk pressure after best reply")
    ax.set_ylabel("Black urgent obligations after best reply")
    ax.set_title("Best-reply bulk versus obligation debt")
    fig.colorbar(sc, ax=ax, label="Black tau")
    fig.tight_layout()
    fig.savefig(fig_dir / "bulk_vs_obligations.png", dpi=180)
    plt.close(fig)

    counts = Counter(row.final_class for row in rows)
    wlu_counts = Counter(_row_wlu(row) for row in rows)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    labels = list(counts)
    x = list(range(len(labels)))
    ax.bar(x, [counts[label] for label in labels], color="#4c78a8")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("openings")
    ax.set_title("Opening classes after best Black reply")
    fig.tight_layout()
    fig.savefig(fig_dir / "opening_classes.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 4.2))
    labels = ["B", "W", "U"]
    ax.bar(labels, [wlu_counts[label] for label in labels], color=["#222222", "#d62728", "#888888"])
    ax.set_ylabel("openings")
    ax.set_title("Viewer W/L/U replay classification")
    fig.tight_layout()
    fig.savefig(fig_dir / "wlu_counts.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, radius: int, config: SearchConfig, rows: list) -> None:
    counts = Counter(row.final_class for row in rows)
    wlu_counts = Counter(_row_wlu(row) for row in rows)
    pruning_counts = Counter(row.pruning_mode for row in rows)
    total_nodes = sum(row.nodes for row in rows)
    total_hits = sum(row.cache_hits for row in rows)
    estimated = max((row.estimated_tree_nodes for row in rows), default=0)
    naive = max((row.naive_leaf_nodes for row in rows), default=0)
    effective_depth = rows[0].effective_depth if rows else config.depth
    effective_candidates = rows[0].effective_candidate_cells if rows else config.candidate_cells
    top = sorted(rows, key=lambda row: row.score, reverse=True)[:8]
    bottom = sorted(rows, key=lambda row: row.score)[:8]
    lines = [
        "# Opening Tablebase Corpus",
        "",
        "Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.",
        "",
        "## Run",
        "",
        f"- radius: {radius}",
        f"- depth: {config.depth}",
        f"- candidate cells per ply: {config.candidate_cells}",
        f"- effective depth after pruning: {effective_depth}",
        f"- effective candidate cells after pruning: {effective_candidates}",
        f"- openings: {len(rows)}",
        f"- naive leaf nodes per opening before candidate pruning: {naive}",
        f"- estimated candidate-tree nodes per opening: {estimated}",
        f"- total nodes: {total_nodes}",
        f"- transposition hits: {total_hits}",
        f"- pruning modes: {dict(sorted(pruning_counts.items()))}",
        f"- classes: {dict(sorted(counts.items()))}",
        f"- viewer W/L/U: {dict(sorted(wlu_counts.items()))}",
        "",
        "## Most Black-Favorable Openings",
        "",
    ]
    for row in top:
        lines.append(f"- `{row.opening_id}` score={row.score:.2f}, class={row.final_class}, reply={row.best_black_reply}")
    lines.extend(["", "## Most White-Favorable / Screened Openings", ""])
    for row in bottom:
        lines.append(f"- `{row.opening_id}` score={row.score:.2f}, class={row.final_class}, reply={row.best_black_reply}")
    lines.extend([
        "",
        "## Files",
        "",
        "- `opening_tablebase.csv`: flat corpus.",
        "- `opening_tablebase.json`: structured corpus with principal variations for the viewer.",
        "- `figures/`: score, pressure, and class plots.",
        "",
        "View with:",
        "",
        "```bash",
        f"python examples/game_viewer.py --corpus {out_dir.as_posix()}/opening_tablebase.json",
        "```",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, radius: int, depth: int, candidate_cells: int, limit: int | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    config = SearchConfig(radius=radius, depth=depth, candidate_cells=candidate_cells, k=6)
    rows = list(build_opening_corpus(radius=radius, config=config, limit=limit))
    _write_csv(out_dir / "opening_tablebase.csv", [_row(row) for row in rows])
    (out_dir / "opening_tablebase.json").write_text(
        json.dumps(
            _jsonable({
                "radius": radius,
                "depth": depth,
                "candidate_cells": candidate_cells,
                "openings": rows,
            }),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _make_figures(out_dir, rows)
    _write_report(out_dir, radius, config, rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--depth", type=int, default=2)
    parser.add_argument("--candidate-cells", type=int, default=10)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", default="opening_tablebase_results/r3_corpus")
    args = parser.parse_args()
    run(Path(args.out), args.radius, args.depth, args.candidate_cells, args.limit)


if __name__ == "__main__":
    main()
