"""
Candidate C of the 2026-07-05 search-regime handoff: is tau (transversal number
of the obligation hypergraph) cheaply *exact* on real positions, or only heuristic?

Theory this experiment tests (see docs/theory/2026-07-06-search-regime-verdicts.md):

  1. One-turn obligations are 6-windows with >=4 attacker stones and no defender
     stone; their hyperedge is the window's empty cells -- at most 2 of them. So
     the real obligation hypergraph is a *graph* (edges of size 1-2) and tau is
     minimum vertex cover, whose LP relaxation is half-integral
     (Nemhauser-Trotter). Gap is therefore always in {0, 1/2, 1, ...} x integer
     rounding, and LP > 2 is a *sound certificate* of tau > 2 (LP <= IP).
  2. Obligations along a single axis form an interval graph on that line
     (consecutive windows share empties) -- interval graphs are perfect, so
     single-axis instances must show zero integrality gap.
  3. Any nonzero gap needs an odd cycle mixing >= 2 axes -- which is exactly a
     multi-axis fork structure. Prediction: gaps are rare and localized to
     forcing-rich positions.

Mines positions from arena self-play (randomized openings, seeded), builds the
obligation graph for both players, solves IP (scipy.optimize.milp) and LP
relaxation, and reports the gap distribution plus the per-axis zero-gap check.

Output: results/tau_lp_gap.json, figures/fig_tau_lp_gap_dist.png
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import LinearConstraint, milp

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "competition"))
import arena  # the standalone rules engine + bot ladder

AXES = ((1, 0), (0, 1), (1, -1))


def obligation_edges(stones: dict, attacker: int, min_own: int):
    """Hyperedges (frozenset of empty cells) of obligations, with axis tag.

    min_own=4: one-turn obligations (completable in one 2-stone turn), edge
    size <=2, so the hypergraph is a graph and tau = min vertex cover.
    min_own=3: adds the proto tier (two-turn threats), edge size <=3 -- a true
    hypergraph, the tier the atom-compositions bundle mined.
    """
    defender = arena.other(attacker)
    edges = {}
    for (q, r), p in stones.items():
        if p != attacker:
            continue
        for ai, (dq, dr) in enumerate(AXES):
            for offset in range(-5, 1):
                own, blocked, empties = 0, False, []
                for i in range(6):
                    c = (q + dq * (offset + i), r + dr * (offset + i))
                    occ = stones.get(c)
                    if occ == defender:
                        blocked = True
                        break
                    if occ == attacker:
                        own += 1
                    else:
                        empties.append(c)
                if not blocked and own >= min_own and empties:
                    edges[frozenset(empties)] = ai  # dedupe identical edges
    # drop dominated edges (superset of another edge): they never change tau
    keep = {}
    for e, a in edges.items():
        if not any(e2 < e for e2 in edges):
            keep[e] = a
    return list(keep.items())


def solve_cover(edges: list, integral: bool) -> float | None:
    """Min hitting set (IP) or its LP relaxation over the given hyperedges."""
    verts = sorted({v for e, _ in edges for v in e})
    if not verts:
        return 0.0
    vidx = {v: i for i, v in enumerate(verts)}
    A = np.zeros((len(edges), len(verts)))
    for row, (e, _) in enumerate(edges):
        for v in e:
            A[row, vidx[v]] = 1
    res = milp(
        c=np.ones(len(verts)),
        constraints=LinearConstraint(A, lb=1),
        bounds=None,
        integrality=np.ones(len(verts)) if integral else np.zeros(len(verts)),
    )
    return float(res.fun) if res.success else None


def mine_positions(n_games: int, seed_base: int, sample_every: int = 3):
    """Arena self-play positions, randomized openings. Odd stride keeps mid-turn
    states in the sample -- one-turn obligations exist mostly transiently inside
    a turn (competent bots block them on their next placement), so sampling
    only turn boundaries would miss nearly all of them (first run: 1 instance
    in 234 positions)."""
    positions = []
    pairs = (
        (arena.make_fork_aware(1.2), arena.make_heuristic(1.1)),
        (arena.greedy_offence(), arena.greedy_offence()),   # threat-rich
        (arena.make_fork_aware(1.2), arena.greedy_offence()),
        # random never blocks, so tau>2 fork instances actually accumulate --
        # the only cheap source of them (competent pairs prevent forks by design)
        (arena.random_bot(seed=seed_base + 7777), arena.random_bot(seed=seed_base + 8888)),
    )
    for g in range(n_games):
        s = arena.State()
        opener = arena.random_bot(seed=seed_base + g)
        a, b = pairs[g % len(pairs)]
        players = {1: a, 2: b} if g % 2 == 0 else {1: b, 2: a}
        placements = 0
        while s.winner is None and placements < 240:
            bot = opener if len(s.stones) < 6 else players[s.turn]
            mv = bot(s)
            if mv in s.stones:
                break
            s = arena.place(s, *mv)
            placements += 1
            if placements >= 10 and placements % sample_every == 0:
                positions.append(dict(s.stones))
    return positions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--games", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    n_games = args.games or (6 if args.quick else 40)

    t0 = time.time()
    positions = mine_positions(n_games, args.seed)
    instances = []
    for pos in positions:
        for attacker in (1, 2):
            for tier, min_own in (("one_turn", 4), ("proto", 3)):
                edges = obligation_edges(pos, attacker, min_own)
                if not edges:
                    continue
                tau_ip = solve_cover(edges, integral=True)
                tau_lp = solve_cover(edges, integral=False)
                if tau_ip is None or tau_lp is None:
                    continue
                # per-axis sub-instances: interval hypergraphs, must have zero gap
                axis_gap = 0.0
                for ai in range(3):
                    sub = [(e, a) for e, a in edges if a == ai]
                    if sub:
                        ip_a = solve_cover(sub, True)
                        lp_a = solve_cover(sub, False)
                        axis_gap = max(axis_gap, (ip_a or 0) - (lp_a or 0))
                instances.append({
                    "tier": tier,
                    "n_stones": len(pos),
                    "n_edges": len(edges),
                    "tau_ip": tau_ip,
                    "tau_lp": round(tau_lp, 4),
                    "gap": round(tau_ip - tau_lp, 4),
                    "max_single_axis_gap": round(axis_gap, 4),
                    "lp_certifies_fork": tau_lp > 2 + 1e-9,
                    "is_fork": tau_ip > 2,
                })

    def tier_stats(tier: str) -> dict:
        sub = [i for i in instances if i["tier"] == tier]
        gaps = [i["gap"] for i in sub]
        forks = [i for i in sub if i["is_fork"]]
        certified = [i for i in forks if i["lp_certifies_fork"]]
        return {
            "n_instances": len(sub),
            "zero_gap_fraction": (sum(1 for g in gaps if g < 1e-9) / len(gaps)) if gaps else None,
            "max_gap": max(gaps) if gaps else None,
            "single_axis_gap_always_zero": all(i["max_single_axis_gap"] < 1e-9 for i in sub),
            "n_fork_instances": len(forks),
            "fork_lp_certified_fraction": (len(certified) / len(forks)) if forks else None,
        }

    summary = {
        "n_games": n_games,
        "n_positions": len(positions),
        "one_turn": tier_stats("one_turn"),
        "proto": tier_stats("proto"),
        "wall_time_s": round(time.time() - t0, 1),
        "notes": "one_turn: own>=4 windows, edges<=2 cells -> graph, tau = vertex "
                 "cover, LP half-integral (Nemhauser-Trotter); proto: own>=3, "
                 "edges<=3 cells -> true hypergraph. LP > 2 soundly certifies "
                 "tau > 2 in both tiers (LP <= IP). Single-axis subinstances are "
                 "interval hypergraphs (consecutive-ones -> totally unimodular) "
                 "and must show zero gap.",
    }
    print(json.dumps(summary, indent=2))
    gaps = [i["gap"] for i in instances]

    out = ROOT / "results" / "tau_lp_gap.json"
    out.write_text(json.dumps({"summary": summary, "instances": instances}, indent=2))
    print(f"[saved] {out}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    axes[0].hist(gaps, bins=20, color="#4477aa")
    axes[0].set_xlabel("integrality gap (tau_IP - tau_LP)")
    axes[0].set_ylabel("instances")
    axes[0].set_title("Obligation-graph LP gap on real positions")
    axes[1].scatter([i["tau_lp"] for i in instances], [i["tau_ip"] for i in instances],
                    s=14, alpha=0.5, color="#cc6677")
    lim = max([i["tau_ip"] for i in instances], default=1) + 0.5
    axes[1].plot([0, lim], [0, lim], "k--", lw=0.8)
    axes[1].axhline(2, color="gray", lw=0.8)
    axes[1].axvline(2, color="gray", lw=0.8)
    axes[1].set_xlabel("tau_LP")
    axes[1].set_ylabel("tau_IP")
    axes[1].set_title("LP vs exact tau (lines at defender budget 2)")
    fig.tight_layout()
    figp = ROOT / "figures" / "fig_tau_lp_gap_dist.png"
    fig.savefig(figp, dpi=150)
    print(f"[saved] {figp}")


if __name__ == "__main__":
    main()
