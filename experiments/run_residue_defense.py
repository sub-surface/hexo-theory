"""
F7 blocking-set defense vs multi-front attack (E5, 2026-07-09).

The split prime pi = 3 + omega gives Z[omega]/pi = F_7 via the repo's own
residue map (arena._residue: c = (q + 2r) mod 7), under which the three axis
steps are 1, 2, -1 -- all invertible -- so a k-window's cells carry k DISTINCT
residues: a 7-window contains every class exactly once, a 6-window (the real
game) misses exactly one. Hence classes {0, 1} form a BLOCKING SET: every
window contains a class-0 or class-1 cell. The defense concentrates claims
on that 2/7-density sublattice, where one stone poisons every live window
through it (up to 18).

This is NOT a periodic pairing, so the k >= 2m+1 = 7 pairing-impossibility
bound does not apply -- it can be stress-tested at k = 6, the actual game,
where no pairing can exist at all. The attacker is adaptive and adversarial:
each front RESERVES exactly the defender's target cells (its class-0/1
cells) for a final same-turn double placement, filling the other cells
first -- the worst case for a blocking-set defender, mirroring the domino
grab that broke the static k=7 matching.

Defender tiers (2 stones/turn):
  tier 1 (exact): brink windows (live, >= k-2 filled, <= 2 empties) must be
    covered NOW -- minimal hitting set via hexo_bot2.covering_placements;
    needing > 2 cells is a true, unrecoverable overrun.
  tier 2 (the structured proactive claim): live windows with >= `mature`
    attacker stones and no defender stone get their class-0 cell claimed
    (class-1 if the window misses class 0), most-advanced windows first,
    shared target cells preferred.

Output: evidence/results/residue_defense.json, evidence/figures/fig_residue_defense.png
    python experiments/run_residue_defense.py --quick
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "competition"))
from hexo_bot2 import covering_placements  # noqa: E402

AXES = ((1, 0), (0, 1), (1, -1))
TARGET_CLASSES = (0, 1)


def residue(q: int, r: int) -> int:
    return (q + 2 * r) % 7


def window_cells(start, axis, k):
    q, r = start
    dq, dr = axis
    return tuple((q + i * dq, r + i * dr) for i in range(k))


def windows_through(cell, k):
    q, r = cell
    out = []
    for axis in AXES:
        dq, dr = axis
        for off in range(k):
            out.append(((q - off * dq, r - off * dr), axis))
    return out


class State:
    def __init__(self):
        self.att: set = set()
        self.dfn: set = set()

    def occupied(self, c):
        return c in self.att or c in self.dfn


def live_windows(state: State, k: int):
    """(cells, n_att) for every window touching an attacker stone with no
    defender stone."""
    seen = set()
    out = []
    for c in state.att:
        for start, axis in windows_through(c, k):
            key = (start, axis)
            if key in seen:
                continue
            seen.add(key)
            cells = window_cells(start, axis, k)
            if any(x in state.dfn for x in cells):
                continue
            out.append((cells, sum(1 for x in cells if x in state.att)))
    return out


def residue_defender_move(state: State, k: int, budget: int = 2,
                          mature: int | None = None, ablate: bool = False):
    """ablate=True is the attribution control: tier-2 claims the window's
    FIRST empty cell instead of its {0,1}-class cell -- if the ablated
    defense survives equally, the win is 'exact tier-1 + reactive
    poisoning', not the F7 blocking-set structure."""
    if mature is None:
        mature = k - 4
    lw = live_windows(state, k)
    brinks = [tuple(c for c in cells if not state.occupied(c))
              for cells, n in lw if n >= k - 2]
    brinks = [b for b in brinks if 0 < len(b) <= 2]
    placements: list = []
    tier1_overrun = False
    if brinks:
        covers = covering_placements(brinks, budget)
        if covers:
            best = min(covers, key=len)
            placements.extend(best)
        else:
            tier1_overrun = True
            # max resistance: greedily hit the most windows
            cell_hits = Counter(c for b in brinks for c in b)
            placements.extend([c for c, _ in cell_hits.most_common(budget)])
    remaining = budget - len(placements)
    n_tier2_needed = 0
    if True:
        # structured proactive claims on the {0,1} blocking set
        targets: Counter = Counter()
        for cells, n in lw:
            if n < mature or n >= k - 2:
                continue
            n_tier2_needed += 1
            if ablate:
                tc = [c for c in cells
                      if not state.occupied(c) and c not in placements]
            else:
                tc = [c for c in cells
                      if residue(*c) in TARGET_CLASSES and not state.occupied(c)
                      and c not in placements]
            for c in tc[:1]:
                targets[c] += n  # weight by maturity
        for c, _ in targets.most_common(remaining):
            placements.append(c)
    return placements, tier1_overrun, n_tier2_needed


def make_front(start, axis, k):
    cells = window_cells(start, axis, k)
    reserve = [c for c in cells if residue(*c) in TARGET_CLASSES]
    if len(reserve) < 2:  # k=6 window missing class 0 or 1
        others = [c for c in cells if c not in reserve]
        reserve = (reserve + others[-(2 - len(reserve)):])
    reserve = reserve[:2]
    free = [c for c in cells if c not in reserve]
    return {"cells": cells, "reserve": reserve, "free": free,
            "free_idx": 0, "grabbed": False, "dead": False}


def run_trial(n_fronts: int, turns: int, seed: int, k: int,
              cluster_radius: int, mature: int | None = None,
              ablate: bool = False) -> dict:
    rng = random.Random(seed)
    fronts = []
    for _ in range(n_fronts):
        q0 = rng.randint(-cluster_radius, cluster_radius)
        r0 = rng.randint(-cluster_radius, cluster_radius)
        fronts.append(make_front((q0, r0), rng.choice(AXES), k))
    state = State()
    t1_overrun_ever = False
    won = False
    for t in range(turns):
        for f in fronts:
            if not f["dead"] and any(c in state.dfn for c in f["cells"]):
                f["dead"] = True
        live = [f for f in fronts if not f["dead"] and not f["grabbed"]]
        live.sort(key=lambda f: len(f["free"]) - f["free_idx"])
        left = 2
        moves = []
        for f in live:
            if left <= 0:
                break
            rem = len(f["free"]) - f["free_idx"]
            if rem > 0:
                take = min(rem, left)
                for _ in range(take):
                    c = f["free"][f["free_idx"]]
                    if not state.occupied(c):
                        moves.append(c)
                    f["free_idx"] += 1
                    left -= 1
            elif left >= 2:
                r1, r2 = f["reserve"]
                if not state.occupied(r1) and not state.occupied(r2):
                    moves.extend([r1, r2])
                    f["grabbed"] = True
                    left -= 2
        if not moves:
            if not any(not f["dead"] and not f["grabbed"] for f in fronts):
                break
            continue
        for c in moves:
            state.att.add(c)
        # win check: any fully-attacker window
        done = False
        for cells, n in live_windows(state, k):
            if n == k:
                done = True
                break
        if done:
            won = True
            break
        placements, t1_over, _ = residue_defender_move(state, k, 2, mature,
                                                       ablate)
        t1_overrun_ever = t1_overrun_ever or t1_over
        for c in placements:
            if not state.occupied(c):
                state.dfn.add(c)
        for cells, n in live_windows(state, k):
            if n == k:
                won = True
                break
        if won:
            break
    return {"attacker_won": won, "tier1_overrun_ever": t1_overrun_ever,
            "turns_used": t + 1, "n_fronts": n_fronts, "k": k,
            "cluster_radius": cluster_radius, "seed": seed}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--k", type=int, default=0, help="0 = both 6 and 7")
    args = ap.parse_args()
    t0 = time.time()

    ks = [6, 7] if args.k == 0 else [args.k]
    n_seeds = 5 if args.quick else 30
    nf_list = [15, 40] if args.quick else [10, 20, 30, 40, 60, 80]
    turns = 80 if args.quick else 300
    radius = 12

    grid = []
    for k in ks:
        for nf in nf_list:
            wins = 0
            t1 = 0
            for seed in range(n_seeds):
                r = run_trial(nf, turns, seed, k, radius)
                wins += r["attacker_won"]
                t1 += r["tier1_overrun_ever"]
            grid.append({"k": k, "n_fronts": nf, "n_seeds": n_seeds,
                         "attacker_win_rate": wins / n_seeds,
                         "tier1_overrun_rate": t1 / n_seeds})
            print(f"  k={k} nf={nf}: win_rate={wins/n_seeds:.2f} "
                  f"t1_overrun={t1/n_seeds:.2f}")

    # comparison baseline: the domino triaged defense at k=7, radius 12
    # (from the existing Modal phase diagram)
    base_path = ROOT / "evidence" / "results" / "pairing_capacity_phase_diagram.json"
    baseline = {}
    if base_path.exists():
        for c in json.loads(base_path.read_text())["phase_diagram"]:
            if c["k"] == 7 and c["cluster_radius"] == radius:
                baseline[c["n_fronts"]] = c["attacker_win_rate"]

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
    fig, ax = plt.subplots(figsize=(5.8, 4.3), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for k, col in zip(ks, ("#2a78d6", "#1baf7a")):
        pts = [(g["n_fronts"], g["attacker_win_rate"]) for g in grid
               if g["k"] == k]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], color=col, lw=2,
                marker="o", ms=5, label=f"F₇ blocking-set, k={k}")
    if baseline:
        xs = sorted(baseline)
        ax.plot(xs, [baseline[x] for x in xs], color="#e34948", lw=2,
                ls="--", marker="s", ms=4, label="domino pairing, k=7")
    ax.axhline(0.5, color=MUTED, lw=1, ls=":")
    ax.set_xlabel("fronts n (dense cluster, R=12)", color=MUTED)
    ax.set_ylabel("attacker win rate", color=MUTED)
    ax.set_title("F₇ blocking-set defense vs adversarial multi-front attack",
                 color=INK, fontsize=11)
    ax.grid(color=GRID, lw=0.6)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout()
    fpath = ROOT / "evidence" / "figures" / "fig_residue_defense.png"
    fig.savefig(fpath, dpi=150)
    plt.close(fig)

    out = {"grid": grid, "baseline_domino_k7_R12": baseline,
           "radius": radius, "turns": turns, "quick": args.quick,
           "wall_time_s": round(time.time() - t0, 1)}
    (ROOT / "evidence" / "results" / "residue_defense.json").write_text(
        json.dumps(out, indent=2))
    print(f"[saved] evidence/results/residue_defense.json, {fpath.name} "
          f"({time.time()-t0:.0f}s)")


if __name__ == "__main__":
    main()
