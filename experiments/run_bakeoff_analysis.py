"""
Analytic figures for the Modal bake-off (results/modal_bakeoff_screen.json).

Four views:
  1. Pareto plane: measured evaluator cost (ms/move, benchmarked locally at a
     fixed 80-stone position) vs strength (decisive-win share of all games) --
     the search-time-bounded analogue of the ROADMAP's (|P|, H_T) MDL plane.
  2. Head-to-head decisive-share matrix (row's share of decisive games vs
     column, NaN where all games drew).
  3. Conversion speed: stones-to-win distributions against the two weak
     opponents (random, residue_static) -- the margin metric that actually
     separated the top bots when strong-vs-strong drew 549/550.
  4. Draw structure: game-length histogram split decisive vs cutoff.

Output: figures/fig_bakeoff_pareto.png, fig_bakeoff_matrix.png,
        fig_bakeoff_conversion.png, fig_bakeoff_lengths.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "competition"))
import arena

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

COLORS = {"random": "#999999", "greedy_offence": "#e08214",
          "heuristic_d1.1": "#4477aa", "fork_aware_d1.2": "#cc6677",
          "fast_tactical": "#66aa55", "residue_bias": "#aa66aa",
          "residue_static": "#88ccee"}


def bench_cost_ms(names: list[str], n_stones: int = 80, reps: int = 3) -> dict:
    """Median per-move latency at a reproducible 80-stone midgame position."""
    h = arena.make_heuristic(1.1)
    fa = arena.make_fork_aware(1.2)
    s = arena.State()
    bots = {1: h, 2: fa}
    while len(s.stones) < n_stones and s.winner is None:
        s = arena.place(s, *bots[s.turn](s))
    roster = arena.default_roster()
    out = {}
    for name in names:
        bot = roster[name]
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            bot(s)
            ts.append((time.perf_counter() - t0) * 1000)
        out[name] = sorted(ts)[len(ts) // 2]
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")  # cheap anyway
    ap.add_argument("--source", default=str(ROOT / "results" / "modal_bakeoff_screen.json"))
    args = ap.parse_args()
    data = json.loads(Path(args.source).read_text())
    names = data["bots"]
    raw = data["raw"]

    # per-bot aggregates over ALL games
    stats = {n: {"wins": 0, "losses": 0, "draws": 0} for n in names}
    for key, games in raw.items():
        a, b = key.split("|")
        for g in games:
            if g["result"] == "a":
                stats[a]["wins"] += 1; stats[b]["losses"] += 1
            elif g["result"] == "b":
                stats[b]["wins"] += 1; stats[a]["losses"] += 1
            else:
                stats[a]["draws"] += 1; stats[b]["draws"] += 1

    cost = bench_cost_ms(names)

    # 1. Pareto plane ---------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 5))
    for n in names:
        tot = stats[n]["wins"] + stats[n]["losses"] + stats[n]["draws"]
        share = stats[n]["wins"] / tot
        ax.scatter(cost[n], share, s=90, color=COLORS[n], zorder=3)
        ax.annotate(n, (cost[n], share), textcoords="offset points",
                    xytext=(8, 4), fontsize=8)
    ax.set_xscale("log")
    ax.set_xlabel("evaluator cost (ms/move at 80 stones, log scale)")
    ax.set_ylabel("win share of all games played")
    ax.set_title("Bake-off Pareto plane: cost vs strength\n"
                 "(top-left = cheap and strong; the 1 s budget binds nobody)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "fig_bakeoff_pareto.png", dpi=150)
    plt.close(fig)

    # 2. head-to-head decisive-share matrix -----------------------------------
    m = np.full((len(names), len(names)), np.nan)
    for key, games in raw.items():
        a, b = key.split("|")
        ia, ib = names.index(a), names.index(b)
        aw = sum(1 for g in games if g["result"] == "a")
        bw = sum(1 for g in games if g["result"] == "b")
        if aw + bw:
            m[ia, ib] = aw / (aw + bw)
            m[ib, ia] = bw / (aw + bw)
    fig, ax = plt.subplots(figsize=(7.2, 6))
    im = ax.imshow(m, cmap="RdYlBu_r", vmin=0, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=40, ha="right", fontsize=8)
    ax.set_yticks(range(len(names)), names, fontsize=8)
    for i in range(len(names)):
        for j in range(len(names)):
            if i != j:
                ax.text(j, i, "all\ndraws" if np.isnan(m[i, j]) else f"{m[i, j]:.2f}",
                        ha="center", va="center", fontsize=7)
    ax.set_title("Row's share of decisive games vs column")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "fig_bakeoff_matrix.png", dpi=150)
    plt.close(fig)

    # 3. conversion speed vs weak opponents -----------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.5))
    strong = [n for n in names if n not in ("random", "residue_static")]
    positions, labels = [], []
    for i, n in enumerate(strong):
        lens = []
        for weak in ("random", "residue_static"):
            key = f"{n}|{weak}" if f"{n}|{weak}" in raw else f"{weak}|{n}"
            me = "a" if key.startswith(n) else "b"
            lens += [g["n_stones"] for g in raw[key] if g["result"] == me]
        if lens:
            positions.append(lens); labels.append(f"{n}\n(n={len(lens)})")
    bp = ax.boxplot(positions, tick_labels=labels, showmeans=True)
    ax.set_ylabel("stones on board at win")
    ax.set_title("Conversion speed vs weak opponents (random + residue_static)\n"
                 "lower = kills faster; the margin metric that separates the draw-wall bots")
    ax.grid(alpha=0.25, axis="y")
    plt.setp(ax.get_xticklabels(), fontsize=7)
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "fig_bakeoff_conversion.png", dpi=150)
    plt.close(fig)

    # 4. game-length structure -------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 4.5))
    dec = [g["n_stones"] for games in raw.values() for g in games if g["result"] != "draw"]
    dr = [g["n_stones"] for games in raw.values() for g in games if g["result"] == "draw"]
    bins = np.linspace(0, 410, 42)
    ax.hist(dec, bins=bins, alpha=0.75, label=f"decisive (n={len(dec)})", color="#cc6677")
    ax.hist(dr, bins=bins, alpha=0.75, label=f"draw/cutoff (n={len(dr)})", color="#4477aa")
    ax.set_xlabel("stones on board at end")
    ax.set_ylabel("games")
    ax.set_yscale("log")
    ax.legend()
    ax.set_title("Game-length structure: decisive games end early or not at all")
    fig.tight_layout()
    fig.savefig(ROOT / "figures" / "fig_bakeoff_lengths.png", dpi=150)
    plt.close(fig)

    summary = {"cost_ms": cost,
               "win_share": {n: stats[n]["wins"] / 300 for n in names},
               "stats": stats}
    (ROOT / "results" / "bakeoff_analysis.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["cost_ms"], indent=2))
    print("[saved] 4 figures -> figures/fig_bakeoff_*.png, results/bakeoff_analysis.json")


if __name__ == "__main__":
    main()
