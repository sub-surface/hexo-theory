r"""Does the MC-trained value head usefully break argmax ties?

After Phase 2a (docs/theory/2026-04-18-unified-agent-design.md §12.4),
the UnifiedNet has a value head trained on final-return targets from
~8000 cached positions. This experiment measures whether plugging V(s')
into a 1-ply tie-break at decision time produces a measurably stronger
agent than the pure policy head.

Design: four comparisons, self-play and vs fixed opponents.

  1. Self-play decisiveness:
     az_value_t0k4 vs az_value_t0k4   (n=40)   -- decisive-rate + p_B
     az_policy_t03 vs az_policy_t03   (n=40)   -- baseline from §12
     If value-aware play terminates more games (higher d) at t=0, that
     is direct evidence the head is scoring positions, not just adding
     noise.

  2. Vs the handcrafted ladder (4 games each, 3 opponents):
     az_value_t0k4 vs {combo, ca_combo_v2, fork_aware}
     az_policy_t03 vs same set  (paired control)
     Stronger if az_value beats az_policy on at least 2/3 opponents
     by non-overlapping Wilson CI.

  3. Head-to-head:
     az_value_t0k4 vs az_policy_t03 (both Black and White, n=20 each)
     Clean A/B: is the value tie-break a net improvement at the agent
     level, controlling for the trunk (same net, different decision
     rule)?

Outputs:
    results/az_value_probe.json
    figures/fig_az_value_probe.png

Usage:
    python experiments/run_az_value_probe.py           # n=40/20
    python experiments/run_az_value_probe.py --quick   # n=10/8
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


OPPONENTS = ["combo", "ca_combo_v2", "fork_aware"]
AZ_VARIANTS = ["az_policy_t03", "az_value_t0k4"]  # baseline, treatment


def _pB(r: dict) -> tuple[float, float, float, int]:
    b, w = r["wins_black"], r["wins_white"]
    dec = b + w
    if dec == 0:
        return (0.5, 0.0, 1.0, 0)
    lo, hi = _wilson(b, dec)
    return (b / dec, lo, hi, dec)


def _decisive(r: dict) -> float:
    return (r["wins_black"] + r["wins_white"]) / max(1, r["n_games"])


def _run(n_self: int, n_vs: int, n_h2h: int, max_moves: int, seed: int) -> dict:
    print(f"\n-- az value probe -- n_self={n_self} n_vs={n_vs} n_h2h={n_h2h} "
          f"horizon={max_moves}\n")
    out: dict = {"self_play": {}, "vs_ladder": {}, "h2h": {}}

    # CUDA-bound agents run single-process (torch+fork is unsafe).
    par = 1
    t0 = time.perf_counter()

    print("  [1] self-play (decisiveness + p_B)")
    for i, var in enumerate(AZ_VARIANTS):
        r = run_matchup(var, var, n_games=n_self, parallelism=par,
                        seed=seed + i * 10_000, max_moves=max_moves)
        print("    " + r.summary())
        out["self_play"][var] = r.to_dict()

    print("  [2] vs handcrafted ladder")
    for j, opp in enumerate(OPPONENTS):
        for i, var in enumerate(AZ_VARIANTS):
            # Play both colours so draw from the net's side comes through:
            # (var as Black) and (var as White). n_games split half/half.
            n_half = max(1, n_vs // 2)
            r_black = run_matchup(var, opp, n_games=n_half, parallelism=par,
                                  seed=seed + 100_000 + j * 1_000 + i * 100,
                                  max_moves=max_moves)
            r_white = run_matchup(opp, var, n_games=n_half, parallelism=par,
                                  seed=seed + 200_000 + j * 1_000 + i * 100,
                                  max_moves=max_moves)
            # Pool: wins by `var` across both colours.
            wins_var = r_black.wins_black + r_white.wins_white
            wins_opp = r_black.wins_white + r_white.wins_black
            total_dec = wins_var + wins_opp
            total_n = r_black.n_games + r_white.n_games
            print(f"    {var:>14s} vs {opp:<14s}  "
                  f"wins={wins_var}/{total_n}  "
                  f"opp={wins_opp}  "
                  f"unf={total_n - total_dec}")
            out["vs_ladder"].setdefault(opp, {})[var] = {
                "wins_var": wins_var,
                "wins_opp": wins_opp,
                "n_games": total_n,
                "as_black": r_black.to_dict(),
                "as_white": r_white.to_dict(),
            }

    print("  [3] head-to-head (same trunk, different decision rule)")
    # az_value as Black vs az_policy as White, and flipped.
    r_vb = run_matchup("az_value_t0k4", "az_policy_t03",
                       n_games=n_h2h, parallelism=par,
                       seed=seed + 300_000, max_moves=max_moves)
    r_vw = run_matchup("az_policy_t03", "az_value_t0k4",
                       n_games=n_h2h, parallelism=par,
                       seed=seed + 400_000, max_moves=max_moves)
    print("    " + r_vb.summary())
    print("    " + r_vw.summary())
    out["h2h"]["value_as_black"] = r_vb.to_dict()
    out["h2h"]["value_as_white"] = r_vw.to_dict()

    out["_wall_time"] = time.perf_counter() - t0
    out["_params"] = dict(n_self=n_self, n_vs=n_vs, n_h2h=n_h2h,
                          max_moves=max_moves, seed=seed,
                          opponents=OPPONENTS, variants=AZ_VARIANTS)
    return out


def _verdict(results: dict) -> str:
    lines = []
    lines.append("\n-- Verdict --\n")
    lines.append("Self-play decisiveness (does value tie-break unstick loops?):")
    for var in AZ_VARIANTS:
        r = results["self_play"][var]
        pB, lo, hi, _ = _pB(r)
        d = _decisive(r)
        lines.append(f"  {var:>14s}   p_B={pB:.2f} [{lo:.2f},{hi:.2f}]   "
                     f"d={d:.2f}   unfin={r['unfinished']}/{r['n_games']}")
    lines.append("")
    lines.append("vs ladder  (wins for az-variant across both colours):")
    lines.append(f"  {'opp':>14s}  "
                 + "  ".join(f"{v:>14s}" for v in AZ_VARIANTS))
    for opp in OPPONENTS:
        row = f"  {opp:>14s}  "
        parts = []
        for var in AZ_VARIANTS:
            e = results["vs_ladder"][opp][var]
            n = e["n_games"]
            lo, hi = _wilson(e["wins_var"], n)
            parts.append(f"{e['wins_var']:2d}/{n:2d} [{lo:.2f},{hi:.2f}]")
        row += "  ".join(f"{p:>14s}" for p in parts)
        lines.append(row)
    lines.append("")
    lines.append("Head-to-head  (az_value vs az_policy, same trunk):")
    r_vb = results["h2h"]["value_as_black"]
    r_vw = results["h2h"]["value_as_white"]
    total_n = r_vb["n_games"] + r_vw["n_games"]
    wins_value = r_vb["wins_black"] + r_vw["wins_white"]
    wins_policy = r_vb["wins_white"] + r_vw["wins_black"]
    lo, hi = _wilson(wins_value, total_n)
    lines.append(f"  az_value total wins:  {wins_value}/{total_n}  "
                 f"[{lo:.2f},{hi:.2f}]")
    lines.append(f"  az_policy total wins: {wins_policy}/{total_n}")
    if lo > 0.5:
        lines.append(f"  -> value tie-break measurably helps (lower Wilson > 0.5)")
    elif hi < 0.5:
        lines.append(f"  -> value tie-break measurably *hurts*")
    else:
        lines.append(f"  -> inconclusive (Wilson straddles 0.5 at n={total_n})")
    return "\n".join(lines)


def _plot(results: dict, path: str) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

    # Panel 1: self-play decisiveness.
    ax = axes[0]
    xs = np.arange(len(AZ_VARIANTS))
    ds = [_decisive(results["self_play"][v]) for v in AZ_VARIANTS]
    ax.bar(xs, ds, color=["#888", "#4c78a8"])
    for x, d in zip(xs, ds):
        ax.text(x, d + 0.02, f"{d:.2f}", ha="center", fontsize=9)
    ax.set_xticks(xs)
    ax.set_xticklabels(AZ_VARIANTS, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("decisive fraction")
    ax.set_title("Self-play decisiveness\n(does V(s') unstick loops?)")
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # Panel 2: win rate vs ladder.
    ax = axes[1]
    width = 0.35
    xs = np.arange(len(OPPONENTS))
    for i, var in enumerate(AZ_VARIANTS):
        rates = []
        for opp in OPPONENTS:
            e = results["vs_ladder"][opp][var]
            rates.append(e["wins_var"] / max(1, e["n_games"]))
        ax.bar(xs + (i - 0.5) * width, rates, width,
               label=var, color=["#888", "#4c78a8"][i])
    ax.axhline(0.5, color="#a22", linestyle="--", linewidth=1)
    ax.set_xticks(xs)
    ax.set_xticklabels(OPPONENTS, rotation=15, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("win rate (both colours)")
    ax.set_title("vs handcrafted ladder")
    ax.legend(fontsize=8)
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    # Panel 3: head-to-head.
    ax = axes[2]
    r_vb = results["h2h"]["value_as_black"]
    r_vw = results["h2h"]["value_as_white"]
    value_b = r_vb["wins_black"] / max(1, r_vb["n_games"])
    value_w = r_vw["wins_white"] / max(1, r_vw["n_games"])
    total_n = r_vb["n_games"] + r_vw["n_games"]
    wins_value = r_vb["wins_black"] + r_vw["wins_white"]
    pooled = wins_value / max(1, total_n)
    lo, hi = _wilson(wins_value, total_n)
    ax.bar([0, 1, 2], [value_b, value_w, pooled],
           color=["#4c78a8", "#4c78a8", "#54a24b"])
    ax.errorbar(2, pooled, yerr=[[pooled - lo], [hi - pooled]],
                fmt="none", ecolor="#333", capsize=5)
    ax.text(2, pooled + 0.04, f"{pooled:.2f}\n[{lo:.2f},{hi:.2f}]",
            ha="center", fontsize=8)
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(["value as B", "value as W", "pooled"], rotation=15)
    ax.axhline(0.5, color="#a22", linestyle="--", linewidth=1)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("value-variant win rate")
    ax.set_title("Head-to-head:\naz_value vs az_policy (same trunk)")
    ax.grid(axis="y", linestyle=":", alpha=0.5)

    fig.suptitle("Phase 2b probe: does MC-trained V(s') help az_policy?",
                 fontsize=12)
    fig.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-self", type=int, default=40)
    ap.add_argument("--n-vs", type=int, default=20)  # split across colours
    ap.add_argument("--n-h2h", type=int, default=20)  # per colour
    ap.add_argument("--max-moves", type=int, default=240)
    ap.add_argument("--seed", type=int, default=20260419)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    if args.quick:
        args.n_self = 10
        args.n_vs = 8
        args.n_h2h = 8
        args.max_moves = 120

    results = _run(args.n_self, args.n_vs, args.n_h2h,
                   args.max_moves, args.seed)

    rpath = Path("results") / "az_value_probe.json"
    rpath.parent.mkdir(parents=True, exist_ok=True)
    with open(rpath, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[saved] {rpath}")

    fig = Path("figures") / "fig_az_value_probe.png"
    _plot(results, str(fig))
    print(f"[saved] {fig}")

    print(_verdict(results))


if __name__ == "__main__":
    main()
