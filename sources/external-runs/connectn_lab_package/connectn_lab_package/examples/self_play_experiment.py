"""Run minimal strategy self-play corpora for seeded Hex Connect6."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.self_play import (
    NetworkSizeEstimate,
    SelfPlayConfig,
    SelfPlayRecord,
    StrategyMatchupSummary,
    game_to_viewer_record,
    network_size_sweep,
    run_self_play_corpus,
    summarise_matchups,
)


DEFAULT_BLACK = ("debt_builder", "attacker", "hybrid", "min_bulk")
DEFAULT_WHITE = ("screen_counter", "min_tau", "min_bulk", "min_family")


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


def _record_row(record: SelfPlayRecord) -> dict[str, Any]:
    row = asdict(record)
    row["opening_pair"] = json.dumps(_jsonable(row["opening_pair"]), sort_keys=True)
    row["moves"] = json.dumps(_jsonable(row["moves"]), sort_keys=True)
    row["winner"] = row["winner"] or "none"
    for key in ("final_black_bulk_pressure", "final_white_bulk_pressure", "tactical_score"):
        row[key] = round(row[key], 6)
    return row


def _summary_row(summary: StrategyMatchupSummary) -> dict[str, Any]:
    row = asdict(summary)
    for key, value in list(row.items()):
        if isinstance(value, float):
            row[key] = round(value, 6)
    return row


def _network_row(estimate: NetworkSizeEstimate) -> dict[str, Any]:
    row = asdict(estimate)
    for key, value in list(row.items()):
        if isinstance(value, float):
            row[key] = round(value, 6)
    return row


def _parse_strategy_list(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw:
        return default
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _make_figures(
    out_dir: Path,
    records: tuple[SelfPlayRecord, ...],
    summaries: tuple[StrategyMatchupSummary, ...],
    estimates: tuple[NetworkSizeEstimate, ...],
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    black_labels = sorted({summary.black_strategy for summary in summaries})
    white_labels = sorted({summary.white_strategy for summary in summaries})
    matrix = [[0.0 for _ in white_labels] for _ in black_labels]
    summary_by_pair = {(summary.black_strategy, summary.white_strategy): summary for summary in summaries}
    for i, black in enumerate(black_labels):
        for j, white in enumerate(white_labels):
            summary = summary_by_pair.get((black, white))
            if summary:
                matrix[i][j] = summary.black_win_rate - summary.white_win_rate

    fig, ax = plt.subplots(figsize=(8.2, 5.6))
    im = ax.imshow(matrix, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(white_labels)))
    ax.set_xticklabels(white_labels, rotation=35, ha="right")
    ax.set_yticks(range(len(black_labels)))
    ax.set_yticklabels(black_labels)
    ax.set_title("Self-play strategy matrix")
    fig.colorbar(im, ax=ax, label="Black win rate minus White win rate")
    fig.tight_layout()
    fig.savefig(fig_dir / "strategy_matrix.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.hist([record.tactical_score for record in records], bins=min(24, max(5, len(records) // 2)), color="#4c78a8", alpha=0.85)
    ax.axvline(0, color="#555555", linewidth=1)
    ax.set_xlabel("final tactical score, Black positive")
    ax.set_ylabel("games")
    ax.set_title("Self-play final tactical-score distribution")
    fig.tight_layout()
    fig.savefig(fig_dir / "tactical_score_distribution.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.2, 5))
    radii = [estimate.radius for estimate in estimates]
    ax.plot(radii, [estimate.total_factorized_params for estimate in estimates], marker="o", label="factorized pair policy")
    ax.plot(radii, [estimate.total_full_policy_params for estimate in estimates], marker="o", label="full pair policy")
    ax.set_yscale("log")
    ax.set_xlabel("radius")
    ax.set_ylabel("estimated parameters, log scale")
    ax.set_title("Radius-wise neural scale estimate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "network_size_scaling.png", dpi=180)
    plt.close(fig)


def _write_report(
    out_dir: Path,
    config: SelfPlayConfig,
    summaries: tuple[StrategyMatchupSummary, ...],
    estimates: tuple[NetworkSizeEstimate, ...],
) -> None:
    ranked = sorted(summaries, key=lambda row: (row.black_win_rate - row.white_win_rate, row.mean_tactical_score), reverse=True)
    safest = sorted(summaries, key=lambda row: (row.black_win_rate - row.white_win_rate, row.mean_tactical_score))
    lines = [
        "# Self-Play Strategy Corpus",
        "",
        "Seeded 1-2-2 Hex Connect6 strategy comparison over canonical White opening pairs. This is empirical self-play, not a perfect-play proof.",
        "",
        "## Run",
        "",
        f"- radius: {config.radius}",
        f"- turns after opening: {config.turns}",
        f"- candidate cells per move: {config.candidate_limit}",
        f"- opening limit: {config.opening_limit}",
        f"- black strategies: {', '.join(config.black_strategies)}",
        f"- white strategies: {', '.join(config.white_strategies)}",
        "",
        "## Strongest Black Matchups",
        "",
    ]
    for row in ranked[:8]:
        edge = row.black_win_rate - row.white_win_rate
        lines.append(f"- `{row.black_strategy}` vs `{row.white_strategy}`: edge={edge:.2f}, games={row.games}, mean score={row.mean_tactical_score:.1f}")
    lines.extend(["", "## Strongest White Screens", ""])
    for row in safest[:8]:
        edge = row.black_win_rate - row.white_win_rate
        lines.append(f"- `{row.white_strategy}` against `{row.black_strategy}`: edge={edge:.2f}, games={row.games}, mean score={row.mean_tactical_score:.1f}")
    lines.extend([
        "",
        "## Neural-Scale Interpretation",
        "",
        "The estimator separates full pair-policy size from a factorized pair-policy head. The full policy grows quadratically in board cells; the factorized head keeps the policy tied to local cell logits and a learned pair coupling, which is the only plausible route to radius transfer.",
        "",
    ])
    for estimate in estimates:
        lines.append(
            f"- r={estimate.radius}: cells={estimate.board_cells}, full actions={estimate.full_pair_actions}, "
            f"factorized params={estimate.total_factorized_params}, architecture={estimate.recommended_architecture}, "
            f"regime={estimate.generalization_regime}, boundary/bulk={estimate.boundary_to_bulk_ratio:.3f}"
        )
    lines.extend([
        "",
        "## Files",
        "",
        "- `self_play_games.json`: viewer-loadable move corpus.",
        "- `self_play_games.csv`: flat per-game records.",
        "- `strategy_matrix.csv`: per-matchup aggregates.",
        "- `network_size_estimates.csv`: radius-wise functional model-size estimates.",
        "- `figures/`: outcome matrix, tactical score distribution, and neural-size scaling.",
        "",
        "View with:",
        "",
        "```powershell",
        f"python examples\\game_viewer.py --corpus {out_dir.as_posix()}/self_play_games.json",
        "```",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    out_dir: Path,
    radius: int,
    radius_to: int | None,
    turns: int,
    candidate_limit: int,
    opening_limit: int,
    black_strategies: tuple[str, ...],
    white_strategies: tuple[str, ...],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    config = SelfPlayConfig(
        radius=radius,
        turns=turns,
        candidate_limit=candidate_limit,
        opening_limit=opening_limit,
        black_strategies=black_strategies,
        white_strategies=white_strategies,
    )
    records = run_self_play_corpus(config)
    summaries = summarise_matchups(records)
    estimates = network_size_sweep(radius, radius_to or radius, candidate_limit=candidate_limit)

    _write_csv(out_dir / "self_play_games.csv", [_record_row(record) for record in records])
    _write_csv(out_dir / "strategy_matrix.csv", [_summary_row(summary) for summary in summaries])
    _write_csv(out_dir / "network_size_estimates.csv", [_network_row(estimate) for estimate in estimates])
    (out_dir / "self_play_games.json").write_text(
        json.dumps(
            _jsonable({
                "config": config,
                "games": [game_to_viewer_record(record) for record in records],
                "records": records,
                "strategy_matrix": summaries,
                "network_size_estimates": estimates,
            }),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    _make_figures(out_dir, records, summaries, estimates)
    _write_report(out_dir, config, summaries, estimates)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--radius-to", type=int)
    parser.add_argument("--turns", type=int, default=4)
    parser.add_argument("--candidate-limit", type=int, default=8)
    parser.add_argument("--opening-limit", type=int, default=8)
    parser.add_argument("--black-strategies")
    parser.add_argument("--white-strategies")
    parser.add_argument("--out", default="self_play_results/r3")
    args = parser.parse_args()

    run(
        out_dir=Path(args.out),
        radius=args.radius,
        radius_to=args.radius_to,
        turns=args.turns,
        candidate_limit=args.candidate_limit,
        opening_limit=args.opening_limit,
        black_strategies=_parse_strategy_list(args.black_strategies, DEFAULT_BLACK),
        white_strategies=_parse_strategy_list(args.white_strategies, DEFAULT_WHITE),
    )


if __name__ == "__main__":
    main()
