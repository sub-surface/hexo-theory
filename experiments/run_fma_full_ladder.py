r"""First-mover-advantage curve across the *full* ladder.

Extends [run_fma_curve.py](run_fma_curve.py) from 5 hand-crafted agents
to 8 points spanning all agent families: random, the classical ladder,
the pretrained AlphaZero policy head (Phase 1), and an untrained
NeuralCAAgent. Answers the headline question the paper's introduction
needs:

    Does p_B (Black's share of decisive self-play games) grow, saturate,
    or invert as agent strength scales? And what does the *curve* look
    like across fundamentally different agent families -- hand-crafted
    vs learned vs neural-CA?

Per CLAUDE.md, this is a prerequisite for any strong claim about "perfect
play is P1-win" in the write-up: we need to see the full shape before
extrapolating.

Design choices:

* Self-play only (agent A as Black vs same agent A as White) -- p_B
  is well-defined and the strategy-stealing bound p_B >= 1/2 applies
  pointwise.
* CUDA-bound agents (az_policy*, neural_ca) force parallelism=1; the
  CPU-only classical agents run with default parallelism.
* az_policy at t=0 (deterministic argmax) produces the *same*
  trajectory every game when playing itself -- verified empirically:
  seeds 0, 7, 42 all produce identical first-12-move sequences
  [(0,0), (0,1), (-1,1), ...]. That makes n_games iid-with-seed
  effectively n=1 for self-play measurements, and the Wilson CI
  becomes meaningless. So the FMA measurement uses t=0.3 (softened
  argmax) which retains most of the top-move preference but breaks
  determinism. t=0.5 is shown for temperature-sensitivity context;
  at t=0 self-play is documented in
  [results/az_policy_eval.json](../results/az_policy_eval.json) as
  a Phase 1 failure mode.

Outputs:
    results/fma_full_ladder.json
    figures/fig_fma_full_ladder.png

Usage:
    python experiments/run_fma_full_ladder.py           # n=40 / agent
    python experiments/run_fma_full_ladder.py --quick   # n=15 / agent
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_REAL_HEXGO = Path(r"C:\Users\Leon\Desktop\Psychograph\hexgo")
if _REAL_HEXGO.exists() and str(_REAL_HEXGO) not in sys.path:
    sys.path.insert(0, str(_REAL_HEXGO))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from experiments.harness import run_matchup, _wilson


# Full ladder, ordered by expected strength.
# - CUDA=True forces parallelism=1 (torch+cuda can't fork).
# - family labels group agents on the plot.
LADDER: list[tuple[str, str, bool]] = [
    # (name, family, needs_cuda)
    ("random",         "baseline",    False),
    ("greedy",         "handcrafted", False),
    ("fork_aware",     "handcrafted", False),
    ("combo",          "handcrafted", False),
    ("ca_combo_v2",    "handcrafted", False),
    ("az_policy_t03",  "learned",     True),
    ("az_policy_t05",  "learned",     True),
    ("neural_ca",      "neural-CA",   True),
]

FAMILY_COLOURS = {
    "baseline":    "#999",
    "handcrafted": "#4c78a8",
    "learned":     "#e45756",
    "neural-CA":   "#54a24b",
}


def _run(n_games: int, parallelism: int, max_moves: int, seed: int) -> dict:
    print(f"\n-- FMA full ladder --  n={n_games}  horizon={max_moves}  "
          f"cpu_parallel={parallelism}\n")
    out: dict = {}
    t0 = time.perf_counter()
    for idx, (agent, family, needs_cuda) in enumerate(LADDER):
        par = 1 if needs_cuda else parallelism
        r = run_matchup(
            agent, agent,
            n_games=n_games,
            parallelism=par,
            seed=seed + idx * 100_000,
            max_moves=max_moves,
        )
        print(f"  [{family:>11s}] " + r.summary())
        d = r.to_dict()
        d["_family"] = family
        d["_needs_cuda"] = needs_cuda
        out[agent] = d
    out["_wall_time"] = time.perf_counter() - t0
    out["_params"] = dict(n_games=n_games, parallelism=parallelism,
                          max_moves=max_moves, seed=seed,
                          ladder=[a for a, _, _ in LADDER])
    return out


def _black_share(r: dict) -> tuple[float, float, float, int]:
    b, w = r["wins_black"], r["wins_white"]
    dec = b + w
    if dec == 0:
        return (0.5, 0.0, 1.0, 0)
    lo, hi = _wilson(b, dec)
    return (b / dec, lo, hi, dec)


def _decisive_rate(r: dict) -> float:
    return (r["wins_black"] + r["wins_white"]) / max(1, r["n_games"])


def _verdict(results: dict) -> str:
    lines = ["p_B = Black share of decisive games. d = decisive fraction.\n"]
    lines.append(
        f"{'agent':>14s}  {'family':>11s}  {'p_B':>5s}  "
        f"{'[lo,hi]':>13s}  {'d':>5s}  {'n_dec':>5s}"
    )
    q1_violations = []
    for agent, _, _ in LADDER:
        r = results[agent]
        pB, lo, hi, dec = _black_share(r)
        d = _decisive_rate(r)
        lines.append(
            f"{agent:>14s}  {r['_family']:>11s}  {pB:5.2f}  "
            f"[{lo:.2f},{hi:.2f}]  {d:5.2f}  {dec:5d}"
        )
        if hi < 0.5:
            q1_violations.append(agent)
    lines.append("")
    if q1_violations:
        lines.append(f"(Q1) strategy-stealing VIOLATED by: "
                     f"{', '.join(q1_violations)}")
    else:
        lines.append("(Q1) strategy-stealing respected pointwise.")
    return "\n".join(lines)


def _plot(results: dict, path: str) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    pBs, los, his, ds, fams = [], [], [], [], []
    for agent, family, _ in LADDER:
        pB, lo, hi, _ = _black_share(results[agent])
        pBs.append(pB); los.append(lo); his.append(hi)
        ds.append(_decisive_rate(results[agent]))
        fams.append(family)

    x = np.arange(len(LADDER))
    colours = [FAMILY_COLOURS[f] for f in fams]

    # Left panel: p_B with Wilson CI.
    yerr_low = [p - lo for p, lo in zip(pBs, los)]
    yerr_high = [hi - p for p, hi in zip(pBs, his)]
    # Linking line first, scatter on top so per-point colouring shows.
    ax1.plot(x, pBs, "-", color="#444", linewidth=1.2, alpha=0.5, zorder=1)
    for xi, pB, yl, yh, c in zip(x, pBs, yerr_low, yerr_high, colours):
        ax1.errorbar(xi, pB, yerr=[[yl], [yh]],
                     fmt="o", color=c, ecolor=c, alpha=0.8,
                     capsize=4, markersize=8, zorder=2)
        ax1.text(xi, pB + max(yh, 0.02) + 0.015, f"{pB:.2f}",
                 ha="center", fontsize=8)
    ax1.axhline(0.5, color="#a22", linestyle="--", linewidth=1,
                label="strategy-stealing lower bound")
    ax1.set_xticks(x)
    ax1.set_xticklabels([a for a, _, _ in LADDER], rotation=30, ha="right")
    ax1.set_ylabel(r"$p_B$ = Black share of decisive games")
    ax1.set_title("First-mover advantage across the full agent ladder")
    ax1.set_ylim(0.0, 1.05)
    ax1.grid(axis="y", linestyle=":", alpha=0.5)
    ax1.legend(loc="lower left", fontsize=9)

    # Right panel: decisive-game rate.
    ax2.bar(x, ds, color=colours)
    for xi, d in zip(x, ds):
        ax2.text(xi, d + 0.02, f"{d:.2f}", ha="center", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels([a for a, _, _ in LADDER], rotation=30, ha="right")
    ax2.set_ylabel("decisive-game fraction")
    ax2.set_title("Decisiveness across the ladder")
    ax2.set_ylim(0.0, 1.05)
    ax2.grid(axis="y", linestyle=":", alpha=0.5)

    # Family legend on the right panel (avoids clashing with strategy-stealing
    # line on the left).
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=c, label=fam)
               for fam, c in FAMILY_COLOURS.items()]
    ax2.legend(handles=handles, loc="upper left", fontsize=9, title="family")

    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--parallelism", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--max-moves", type=int, default=240)
    ap.add_argument("--seed", type=int, default=20260419)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    if args.quick:
        args.n = 15
        args.max_moves = 120

    results = _run(args.n, args.parallelism, args.max_moves, args.seed)

    rpath = Path("results") / "fma_full_ladder.json"
    rpath.parent.mkdir(parents=True, exist_ok=True)
    with open(rpath, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[saved] {rpath}")

    fig = Path("figures") / "fig_fma_full_ladder.png"
    _plot(results, str(fig))
    print(f"[saved] {fig}")

    print("\n-- Verdict --\n" + _verdict(results))


if __name__ == "__main__":
    main()
