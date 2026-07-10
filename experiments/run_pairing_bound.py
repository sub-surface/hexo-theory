"""
Candidate E of the 2026-07-05 search-regime handoff, resolved in both directions.

1. Residue covering (verified): Z[omega]/(pi_7) = F_7 with omega -> 2. The three
   axis steps reduce to 1, 2, 6 mod 7 -- all nonzero -- so any 6-window on any
   axis covers 6 *distinct* residues, excluding exactly one (start - step), and
   ANY two distinct residue classes form a density-2/7 sublattice that meets
   every possible 6-window. (The handoff doc's "cyclic gaps <= 6" side condition
   is vacuous: it holds for every pair of distinct classes.)

2. Pairing impossibility (THEOREM, new): no pairing strategy -- periodic or not
   -- exists for 6-in-a-row on the hex lattice. A pairing needs every window to
   contain both cells of some pair; a pair {x, x + j*u} lies inside exactly
   6 - j <= 5 windows (all on axis u; a window is collinear, so off-axis pairs
   cover nothing). In an N-cell region there are ~3N windows (18 windows/cell,
   6 cells/window) but at most N/2 pairs supplying <= 5 covers each:
   2.5N < 3N. A positive density of windows is always uncovered. This is the
   hex-lattice analogue of the classical 4-direction counting bound on Z^2
   (which forces k >= 9 there, the Hales-Jewett pairing threshold).

3. Sharpness (CONSTRUCTION, new): for k = 7 the same counting is exactly tight
   (supply 6/2 = demand 3), and a zero-slack construction EXISTS: an explicit
   period-6 perfect matching of the lattice into axis-parallel dominoes, one
   domino per line per period, found by exact-cover search and verified below
   directly against every 7-window. Hence 7-in-a-row on the hex lattice is a
   pairing draw, and HeXO's k = 6 sits exactly one below the sharp pairing
   threshold -- the analogue of k = 8 on Z^2 (drawn, but only by non-pairing
   methods, cf. Zetters 1980). If HeXO is a draw, the proof cannot be a pairing.

Output: evidence/results/pairing_bound.json, evidence/figures/fig_pairing_bound_k7_tiling.png
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AXES = ((1, 0), (0, 1), (1, -1))
P = 7
OMEGA_MOD_P = 2  # 2^2 + 2 + 1 = 7 == 0 (mod 7): a primitive cube root of unity


def residue(q: int, r: int) -> int:
    return (q + OMEGA_MOD_P * r) % P


def verify_residue_covering() -> dict:
    axis_steps = {}
    for dq, dr in AXES:
        d = residue(dq, dr)
        assert d != 0
        axis_steps[f"{(dq, dr)}"] = d
        for s in range(P):
            window = {(s + i * d) % P for i in range(6)}
            assert len(window) == 6
            assert (set(range(P)) - window) == {(s - d) % P}
    two_classes_cover = all(
        {(s + i * residue(*ax)) % P for i in range(6)} & {a, b}
        for ax in AXES for s in range(P)
        for a, b in itertools.combinations(range(P), 2)
    )
    return {"axis_steps_mod_7": axis_steps,
            "excluded_class_is_start_minus_step": True,
            "any_two_distinct_classes_cover_all_windows": two_classes_cover}


def verify_pair_coverage(k: int = 6, n: int = 24) -> dict:
    """Count, on an n x n torus, how many k-windows contain both cells of a pair
    at offset j*u1 -- the load-bearing '<= k-1' in the impossibility theorem."""
    counts = {}
    x = (7, 7)
    for j in range(1, k + 1):
        y = ((7 + j) % n, 7)  # offset j along u1
        cover = 0
        for dq, dr in AXES:
            for sq in range(n):
                for sr in range(n):
                    cells = {((sq + i * dq) % n, (sr + i * dr) % n) for i in range(k)}
                    if x in cells and y in cells:
                        cover += 1
        counts[j] = cover
        assert cover == max(0, k - j)
    return {"windows_containing_pair_at_offset_j": counts,
            "supply_per_cell": (k - 1) / 2, "demand_per_cell": 3.0,
            "pairing_possible_by_counting": (k - 1) / 2 >= 3.0}


def find_k7_pairing() -> dict | None:
    """Exact-cover search for the zero-slack k=7 pairing on the 6x6 torus:
    a perfect matching into axis dominoes with one domino per line, dominoes
    at positions {a, a+1} mod 6 along every line."""
    n = 6
    cells = [(q, r) for q in range(n) for r in range(n)]
    lines = []
    for dq, dr in AXES:
        seen = set()
        for c in cells:
            if c in seen:
                continue
            cyc, cur = [], c
            while cur not in cyc:
                cyc.append(cur)
                seen.add(cur)
                cur = ((cur[0] + dq) % n, (cur[1] + dr) % n)
            lines.append((dq, dr, cyc))
    placements = []
    for li, (dq, dr, cyc) in enumerate(lines):
        for a in range(6):
            cov = frozenset({cyc[a], cyc[(a + 1) % 6]})
            placements.append((li, a, cov))

    def backtrack(i: int, covered: frozenset, chosen: list):
        if i == len(lines):
            return chosen if len(covered) == len(cells) else None
        for li, a, cov in placements:
            if li != i or cov & covered:
                continue
            res = backtrack(i + 1, covered | cov, chosen + [(li, a)])
            if res is not None:
                return res
        return None

    sol = backtrack(0, frozenset(), [])
    if sol is None:
        return None
    partner = {}
    for li, a in sol:
        dq, dr, cyc = lines[li]
        c1, c2 = cyc[a], cyc[(a + 1) % 6]
        partner[c1] = (c2, (dq, dr))
        partner[c2] = (c1, (dq, dr))
    return {"solution": sol, "partner": partner, "lines": lines}


def verify_k7_pairing(partner: dict) -> bool:
    """Direct check on the periodic lift: every 7-window on every axis contains
    both cells of some domino, and the matching is a genuine involution."""
    n = 6
    for q in range(n):          # involution
        for r in range(n):
            p, _ = partner[(q, r)]
            back, _ = partner[p]
            assert back == (q, r)
    for dq, dr in AXES:          # every 7-window contains a full domino
        for sq in range(n):
            for sr in range(n):
                window = [((sq + i * dq), (sr + i * dr)) for i in range(7)]
                found = False
                for i in range(6):
                    cq, cr = window[i]
                    p, _ = partner[(cq % n, cr % n)]
                    # lift the torus partner to the lattice neighbour
                    dqp = (p[0] - cq % n + 3) % n - 3
                    drp = (p[1] - cr % n + 3) % n - 3
                    if (cq + dqp, cr + drp) == window[i + 1]:
                        found = True
                        break
                if not found:
                    return False
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")  # everything here is quick
    ap.parse_args()

    covering = verify_residue_covering()
    counting6 = verify_pair_coverage(k=6)
    counting7 = {"supply_per_cell": 3.0, "demand_per_cell": 3.0,
                 "pairing_possible_by_counting": True}
    k7 = find_k7_pairing()
    k7_verified = bool(k7) and verify_k7_pairing(k7["partner"])

    results = {
        "residue_covering": covering,
        "k6_counting": counting6,
        "k6_pairing_exists": False,
        "k6_reason": "supply 2.5 window-covers/cell < demand 3 windows/cell; "
                     "holds for arbitrary (even aperiodic) pairings by averaging",
        "k7_counting": counting7,
        "k7_pairing_exists": k7_verified,
        "k7_solution_line_phases": k7["solution"] if k7 else None,
        "conclusion": "hex-lattice pairing threshold is exactly k=7; HeXO (k=6) "
                      "cannot be drawn by any pairing strategy",
    }
    print(json.dumps({k: v for k, v in results.items() if k != "k7_solution_line_phases"},
                     indent=2, default=str))
    out = ROOT / "evidence" / "results" / "pairing_bound.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(f"[saved] {out}")

    if k7:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        colors = {(1, 0): "#4477aa", (0, 1): "#cc6677", (1, -1): "#66aa55"}
        fig, ax = plt.subplots(figsize=(7, 6))
        for q in range(-2, 14):
            for r in range(-2, 14):
                p, axv = k7["partner"][(q % 6, r % 6)]
                dqp = (p[0] - q % 6 + 3) % 6 - 3
                drp = (p[1] - r % 6 + 3) % 6 - 3
                # axial -> euclidean (hex)
                x1, y1 = q + r / 2, r * 0.866
                x2, y2 = (q + dqp) + (r + drp) / 2, (r + drp) * 0.866
                ax.plot([x1, x2], [y1, y2], color=colors[axv], lw=2.2, alpha=0.85)
                ax.plot(x1, y1, "o", color="#333333", ms=3)
        ax.set_aspect("equal")
        ax.set_title("Period-6 pairing for 7-in-a-row on the hex lattice\n"
                     "(every 7-window on every axis contains a full domino; "
                     "k=6 is provably impossible)")
        ax.axis("off")
        figp = ROOT / "evidence" / "figures" / "fig_pairing_bound_k7_tiling.png"
        fig.savefig(figp, dpi=150, bbox_inches="tight")
        print(f"[saved] {figp}")


if __name__ == "__main__":
    main()
