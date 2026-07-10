"""Compare Connect-k parity and primality effects in seeded 1-2-2 Hex."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.connect_k_parity import ConnectKParityRow, sweep_connect_k


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _rounded_row(row: ConnectKParityRow) -> dict[str, Any]:
    out = asdict(row)
    for key, value in list(out.items()):
        if isinstance(value, float):
            out[key] = round(value, 6)
    return out


def _make_figures(out_dir: Path, rows: tuple[ConnectKParityRow, ...]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig_dir = out_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    ks = [row.k for row in rows]

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.plot(ks, [row.seed_tau for row in rows], marker="o", label="seed tau")
    ax.plot(ks, [row.white_max_tau for row in rows], marker="o", label="White first-pair max tau")
    ax.plot(ks, [row.black_reply_max_tau for row in rows], marker="o", label="Black first-reply max tau")
    for row in rows:
        ax.text(row.k, row.black_reply_max_tau + 0.08, "P" if row.prime else "C", ha="center", fontsize=8)
    ax.axhline(2, color="#555555", linewidth=1, linestyle="--", label="defender budget")
    ax.set_xlabel("connect length k")
    ax.set_ylabel("tau, capped at >3 as 4")
    ax.set_title("First-layer parity envelope by connect length")
    ax.legend()
    fig.tight_layout()
    fig.savefig(fig_dir / "tempo_and_reply_tau.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    colors = ["#d62728" if row.prime else "#4c78a8" for row in rows]
    ax.bar([str(row.k) for row in rows], [row.black_reply_tau_gt2_openings for row in rows], color=colors)
    ax.set_xlabel("connect length k")
    ax.set_ylabel("openings where Black first safe reply has tau > 2")
    ax.set_title("Prime/composite first-reply forcing count")
    fig.tight_layout()
    fig.savefig(fig_dir / "prime_composite_reply_tau.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.bar([str(row.k) for row in rows], [row.white_urgent_openings for row in rows], color=["#333333" if row.parity == "odd" else "#888888" for row in rows])
    ax.set_xlabel("connect length k")
    ax.set_ylabel("canonical openings with White urgent obligations")
    ax.set_title("White first-pair urgent openings")
    fig.tight_layout()
    fig.savefig(fig_dir / "white_opening_urgency.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, rows: tuple[ConnectKParityRow, ...], opening_limit: int | None) -> None:
    prime_rows = [row for row in rows if row.prime]
    composite_rows = [row for row in rows if not row.prime]
    prime_reply = sum(row.black_reply_tau_gt2_openings for row in prime_rows)
    composite_reply = sum(row.black_reply_tau_gt2_openings for row in composite_rows)
    lines = [
        "# Connect-k Parity and Primality Sweep",
        "",
        "Seeded 1-2-2 Hex Connect-k first-layer tactical sweep. The tau values are threshold-oriented; values above 3 are capped as 4 because the decisive question here is whether the defender budget 2 is exceeded.",
        "",
        "## Run",
        "",
        f"- k range: {rows[0].k if rows else 'none'} to {rows[-1].k if rows else 'none'}",
        f"- canonical opening limit per k: {opening_limit if opening_limit is not None else 'all'}",
        "",
        "## Rows",
        "",
    ]
    for row in rows:
        lines.append(
            f"- k={row.k} ({'prime' if row.prime else 'composite'}, {row.parity}): tempo={row.tempo_owner}, "
            f"seed_tau={row.seed_tau}, White urgent={row.white_urgent_openings}/{row.white_openings}, "
            f"Black reply tau>2={row.black_reply_tau_gt2_openings}/{row.white_openings}, "
            f"Black immediate wins={row.black_immediate_wins}"
        )
    lines.extend([
        "",
        "## Aggregate Signal",
        "",
        f"- prime k total Black first-reply tau>2 openings: {prime_reply}",
        f"- composite k total Black first-reply tau>2 openings: {composite_reply}",
        "",
        "## Interpretation",
        "",
        "Parity is the stronger first-order effect. Odd k puts the urgent layer on Black's odd rooted stone counts; even k puts it on White's even move rhythm. Primality is a second-order question about whether forcing debt decomposes into smaller line-internal motifs.",
        "",
        "The experiment supports using Connect-5 and Connect-7 as the first serious prime-k laboratories: Connect-3 collapses at the seed, while larger odd primes expose Black's first-reply tau envelope without the degenerate instant win.",
        "",
        "## Files",
        "",
        "- `connect_k_parity.csv`: row-level metrics.",
        "- `figures/tempo_and_reply_tau.png`: seed, White opening, and Black reply tau curves.",
        "- `figures/prime_composite_reply_tau.png`: Black first-reply tau>2 counts.",
        "- `figures/white_opening_urgency.png`: White first-pair urgent openings.",
    ])
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, k_min: int, k_max: int, opening_limit: int | None) -> tuple[ConnectKParityRow, ...]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = sweep_connect_k(k_min=k_min, k_max=k_max, opening_limit=opening_limit)
    _write_csv(out_dir / "connect_k_parity.csv", [_rounded_row(row) for row in rows])
    _make_figures(out_dir, rows)
    _write_report(out_dir, rows, opening_limit)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k-min", type=int, default=3)
    parser.add_argument("--k-max", type=int, default=10)
    parser.add_argument("--opening-limit", type=int, default=48)
    parser.add_argument("--out", default="connect_k_parity_results/k3_to_k10")
    args = parser.parse_args()
    run(Path(args.out), k_min=args.k_min, k_max=args.k_max, opening_limit=args.opening_limit)


if __name__ == "__main__":
    main()
