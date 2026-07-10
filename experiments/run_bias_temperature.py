"""
Is the ambient temperature of a (p:q) placement game exactly q?

Generalization test of the 2026-07-09 additive-temperature law (verified
exact at (2:2) on 40,785 pairs): for attacker budget p, defender budget q,
the law should read

    draw-draw union non-additive  <=>  h(A) + h(B) >= q + 1

with h the one-turn heat (max over a single placement of the minimal
defender hitting-set size of the resulting brinks). Tested exactly at
(1:1) -- the classic Maker-Maker single-stone game, where the law reduces
to the folklore double-threat principle -- and (2:1), against the same
collinear fragment family. ((2:3)+ needs hitting sets of size 3, beyond
covering_placements' <=2 enumeration -- noted, not run.)

Output: evidence/results/bias_temperature.json
"""
from __future__ import annotations

import json
import sys
import time
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT / "competition"))
from run_two_move_sum import (solve, segment_windows, canon, hotness)  # noqa: E402

OUT = ROOT / "evidence" / "results" / "bias_temperature.json"
ORDER = {-1: 0, 0: 1, 1: 2}


def solve_single(L: int, stones: frozenset, budgets) -> int:
    m1 = sum(1 << s for s in stones)
    return solve(L, segment_windows(L, 0), m1, 0, 1, budgets[0], {}, budgets)


def solve_pair(la, sa, lb, sb, budgets) -> int:
    n = la + lb
    windows = segment_windows(la, 0) + segment_windows(lb, la)
    m1 = sum(1 << s for s in sa) + sum(1 << (la + s) for s in sb)
    return solve(n, windows, m1, 0, 1, budgets[0], {}, budgets)


def main() -> None:
    t0 = time.time()
    seen = {}
    for L in (7, 8):
        for k in (2, 3):
            for comb in combinations(range(L), k):
                key = canon(L, frozenset(comb))
                seen[key] = (key[0], frozenset(key[1]))
    configs = list(seen.values())

    report = {}
    for p, q in ((1, 1), (2, 1), (2, 2)):
        budgets = (p, q)
        singles = {}
        for L, s in configs:
            singles[(L, tuple(sorted(s)))] = {
                "out": solve_single(L, s, budgets), "h": hotness(L, s)}
        drawn = [(L, s) for L, s in configs
                 if singles[(L, tuple(sorted(s)))]["out"] == 0]
        # law sanity on singles: a drawn single must have h <= q
        single_viol = [(L, sorted(s)) for L, s in drawn
                       if singles[(L, tuple(sorted(s)))]["h"] > q]
        n_pairs = n_nonadd = fn = fp = 0
        for i, (la, sa) in enumerate(drawn):
            ea = la - len(sa)
            for lb, sb in drawn[i:]:
                if ea + (lb - len(sb)) > 10:
                    continue
                n_pairs += 1
                u = solve_pair(la, sa, lb, sb, budgets)
                ha = singles[(la, tuple(sorted(sa)))]["h"]
                hb = singles[(lb, tuple(sorted(sb)))]["h"]
                nonadd = ORDER[u] > ORDER[0]
                n_nonadd += nonadd
                if nonadd and ha + hb < q + 1:
                    fn += 1
                if not nonadd and ha + hb >= q + 1:
                    fp += 1
        report[f"p{p}_q{q}"] = {
            "n_configs": len(configs), "n_drawn_singles": len(drawn),
            "drawn_single_with_h_gt_q": single_viol[:10],
            "n_pairs": n_pairs, "n_nonadditive": n_nonadd,
            "law": f"nonadditive <=> h_A + h_B >= {q + 1}",
            "false_negatives": fn, "false_positives": fp,
        }
        print(f"(p={p}, q={q}): drawn singles {len(drawn)}/{len(configs)}, "
              f"pairs {n_pairs}, nonadd {n_nonadd}, FN {fn}, FP {fp}, "
              f"singles h>q {len(single_viol)}")

    report["wall_time_s"] = round(time.time() - t0, 1)
    OUT.write_text(json.dumps(report, indent=2))
    print(f"[saved] {OUT}")


if __name__ == "__main__":
    main()
