"""
The +₂ two-move disjunctive-sum algebra, tested exactly.

Question (docs/theory/2026-07-08-two-move-sum-execution-paused.md): under
HeXO's 1-2-2 rule a turn can SPLIT its two placements across disjoint
components -- does solve(A ∪ B) ever beat max(solve(A), solve(B))?

Components here are collinear lattice segments (windows = 6-runs fully
inside the segment) with pre-placed attacker stones, placed at r-offsets
that make cross-component windows impossible. Both players place 2 stones
per turn (mid-game regime; the game-opening single stone is irrelevant to
sum algebra). Exact solve = negamax over {P1 win, draw, P2 win} with
transposition memo keyed on raw occupancy bitmasks -- no Zobrist needed,
the whole point of a component is that it is small (the one design insight
kept from the removed cgt_solver crate).

Temperature conjecture under test (2026-07-09 theory discussion): a pair is
non-additive ONLY IF both components are HOT, where hot = some single
placement creates a threat set the defender must spend BOTH stones covering
(cover cost 2 -- exactly hexo_bot2's hitting-set arithmetic, reused via
covering_placements). Analytic prior: centered open-3 in an 8-segment is
hot (stones {2,3,4}, +5 -> brinks {0,1},{1,6},{6,7}, min cover {1,6});
end-anchored open-3 is tepid (cover cost 1). Hot x hot should be the
minimal non-additive pair.

Output: results/two_move_sum.json, figures/fig_two_move_sum_*.png
    python experiments/run_two_move_sum.py --quick   # analytic cases only
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "competition"))
from hexo_bot2 import covering_placements  # noqa: E402  (exact hitting sets)

WIN = 6
OUT = ROOT / "results" / "two_move_sum.json"


# ── exact solver over a fixed cell set ────────────────────────────────────

def segment_windows(length: int, offset: int) -> list[int]:
    """Bitmasks (over union indexing, segment cells = offset..offset+len-1)
    of every 6-run inside the segment."""
    return [sum(1 << (offset + s + j) for j in range(WIN))
            for s in range(length - WIN + 1)]


def solve(n_cells: int, windows: list[int], m1: int, m2: int,
          player: int, left: int, memo: dict,
          budgets: tuple[int, int] = (2, 2)) -> int:
    """Exact value in {1: P1 wins, 0: draw, -1: P2 wins}; `player` to place,
    `left` placements remaining in the current turn. budgets = stones per
    turn for (P1, P2) -- (2,2) is HeXO's mid-game regime; other (p:q) biases
    test whether the additive-temperature threshold tracks the defender
    budget q."""
    key = (m1, m2, player, left)
    v = memo.get(key)
    if v is not None:
        return v
    full = (1 << n_cells) - 1
    empties = full & ~(m1 | m2)
    if empties == 0:
        memo[key] = 0
        return 0
    best = -2 if player == 1 else 2
    goal = 1 if player == 1 else -1
    e = empties
    while e:
        bit = e & -e
        e ^= bit
        nm = (m1 | bit) if player == 1 else (m2 | bit)
        if any((nm & w) == w for w in windows):
            val = goal
        else:
            if left == 1:
                nxt = 2 if player == 1 else 1
                val = solve(n_cells, windows,
                            nm if player == 1 else m1,
                            m2 if player == 1 else nm,
                            nxt, budgets[nxt - 1], memo, budgets)
            else:
                val = solve(n_cells, windows,
                            nm if player == 1 else m1,
                            m2 if player == 1 else nm,
                            player, left - 1, memo, budgets)
        if player == 1:
            best = max(best, val)
        else:
            best = min(best, val)
        if best == goal:
            break
    memo[key] = best
    return best


# ── component configs and their temperature ───────────────────────────────

def canon(length: int, stones: frozenset) -> tuple:
    rev = frozenset(length - 1 - s for s in stones)
    a, b = tuple(sorted(stones)), tuple(sorted(rev))
    return (length, min(a, b))


def cover_cost_after(length: int, stones: set, placed: tuple) -> int:
    """Defender stones needed to kill every brink window (>=4 attacker
    stones, live) after `placed` is added; 0 = no brink, 3 = uncoverable."""
    s = stones | set(placed)
    brinks = []
    for start in range(length - WIN + 1):
        cells = set(range(start, start + WIN))
        n = len(cells & s)
        if n >= WIN - 2:
            emp = tuple(sorted(cells - s))
            if len(emp) <= 2:
                brinks.append(emp)
    if not brinks:
        return 0
    covers = covering_placements(brinks, 2)
    if not covers:
        return 3
    return 1 if any(len(c) == 1 for c in covers) else 2


def hotness(length: int, stones: frozenset) -> int:
    """Max cover cost over single placements: 0 tepid, 1 mild, 2 HOT,
    3 = already one placement from an unstoppable turn."""
    empt = [i for i in range(length) if i not in stones]
    return max((cover_cost_after(length, set(stones), (c,)) for c in empt),
               default=0)


def solve_config(length: int, stones: frozenset) -> dict:
    """Solve a single component with P1 (attacker, owns `stones`) to move,
    and with P2 (defender, no stones) to move."""
    windows = segment_windows(length, 0)
    m1 = sum(1 << s for s in stones)
    a = solve(length, windows, m1, 0, 1, 2, {})
    d = solve(length, windows, m1, 0, 2, 2, {})
    return {"attacker_to_move": a, "defender_to_move": d}


def solve_union(la: int, sa: frozenset, lb: int, sb: frozenset) -> int:
    n = la + lb
    windows = segment_windows(la, 0) + segment_windows(lb, la)
    m1 = sum(1 << s for s in sa) + sum(1 << (la + s) for s in sb)
    return solve(n, windows, m1, 0, 1, 2, {})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--lengths", default="7,8")
    ap.add_argument("--sizes", default="2,3")
    args = ap.parse_args()
    t0 = time.time()

    # enumerate configs up to reversal symmetry
    lengths = [int(x) for x in args.lengths.split(",")]
    sizes = [int(x) for x in args.sizes.split(",")]
    if args.quick:
        configs = [(8, frozenset({2, 3, 4})), (8, frozenset({1, 2, 3})),
                   (7, frozenset({2, 3, 4})), (6, frozenset({1, 2, 3}))]
        configs = list({canon(L, s): (L, frozenset(dict(
            [(x, 1) for x in canon(L, s)[1]]).keys())) for L, s in configs}.values())
        configs = [(L, frozenset(canon(L, s)[1])) for L, s in configs]
    else:
        seen = {}
        for L in lengths:
            for k in sizes:
                for comb in combinations(range(L), k):
                    key = canon(L, frozenset(comb))
                    if key not in seen:
                        seen[key] = (key[0], frozenset(key[1]))
        configs = list(seen.values())

    singles = {}
    for L, s in configs:
        r = solve_config(L, s)
        r["hotness"] = hotness(L, s)
        singles[(L, tuple(sorted(s)))] = r
    print(f"[singles] {len(configs)} configs solved in {time.time()-t0:.1f}s")

    # pairs: attacker owns both components, attacker to move
    ORDER = {-1: 0, 0: 1, 1: 2}
    pairs_out = []
    n_nonadd = 0
    t1 = time.time()
    for i, (la, sa) in enumerate(configs):
        for lb, sb in configs[i:]:
            a_out = singles[(la, tuple(sorted(sa)))]["attacker_to_move"]
            b_out = singles[(lb, tuple(sorted(sb)))]["attacker_to_move"]
            pred = max(a_out, b_out, key=lambda v: ORDER[v])
            u = solve_union(la, sa, lb, sb)
            nonadd = ORDER[u] > ORDER[pred]
            if nonadd:
                n_nonadd += 1
            pairs_out.append({
                "A": [la, sorted(sa)], "B": [lb, sorted(sb)],
                "hot_A": singles[(la, tuple(sorted(sa)))]["hotness"],
                "hot_B": singles[(lb, tuple(sorted(sb)))]["hotness"],
                "out_A": a_out, "out_B": b_out,
                "pred_max": pred, "out_union": u, "nonadditive": nonadd,
            })
    print(f"[pairs] {len(pairs_out)} unions solved in {time.time()-t1:.1f}s; "
          f"{n_nonadd} non-additive")

    # ADDITIVE-temperature law audit (refined 2026-07-09 after the quick run
    # refuted the naive "both hot" form: hot(2)+mild(1) unions win too --
    # temperatures ADD, threshold = the defender's ambient budget 2):
    #   among draw-draw pairs: nonadditive  <=>  hot_A + hot_B >= 3
    dd = [p for p in pairs_out if p["out_A"] == 0 and p["out_B"] == 0]
    viol_pos = [p for p in dd if p["nonadditive"]
                and p["hot_A"] + p["hot_B"] < 3]     # win the law can't explain
    viol_neg = [p for p in dd if not p["nonadditive"]
                and p["hot_A"] + p["hot_B"] >= 3]    # predicted win that isn't

    # matrix: nonadditive fraction by (hot_A, hot_B)
    import numpy as np
    frac = np.zeros((4, 4))
    cnt = np.zeros((4, 4))
    for p in pairs_out:
        i, j = sorted((p["hot_A"], p["hot_B"]))
        cnt[i][j] += 1
        frac[i][j] += p["nonadditive"]
    with np.errstate(invalid="ignore"):
        mat = np.where(cnt > 0, frac / np.maximum(cnt, 1), np.nan)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.4, 4.6), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    im = ax.imshow(mat, origin="lower", cmap=matplotlib.colors.
                   LinearSegmentedColormap.from_list(
                       "seq", ["#cde2fb", "#3987e5", "#0d366b"]),
                   vmin=0, vmax=1)
    for i in range(4):
        for j in range(4):
            if cnt[i][j] > 0:
                ax.text(j, i, f"{mat[i][j]:.2f}\n(n={int(cnt[i][j])})",
                        ha="center", va="center", fontsize=8,
                        color="#0b0b0b" if (mat[i][j] or 0) < 0.55 else "#ffffff")
    ax.set_xlabel("hotness of hotter component", color="#898781")
    ax.set_ylabel("hotness of cooler component", color="#898781")
    ax.set_title("+₂ non-additivity rate vs component temperatures\n"
                 "(exact solves, both players 2 stones/turn)", color="#0b0b0b",
                 fontsize=11)
    ax.tick_params(colors="#898781")
    fig.colorbar(im, ax=ax, label="non-additive fraction")
    fig.tight_layout()
    fpath = ROOT / "figures" / "fig_two_move_sum_matrix.png"
    fig.savefig(fpath, dpi=150)
    plt.close(fig)

    out = {
        "n_configs": len(configs), "n_pairs": len(pairs_out),
        "n_nonadditive": n_nonadd,
        "additive_temperature_law": {
            "claim": "draw-draw pair non-additive <=> hot_A + hot_B >= 3",
            "n_draw_draw_pairs": len(dd),
            "false_negatives_of_law": viol_pos[:20],
            "n_false_negatives": len(viol_pos),
            "false_positives_of_law": viol_neg[:20],
            "n_false_positives": len(viol_neg),
        },
        "singles": {f"L{L}_{list(s)}": singles[(L, tuple(sorted(s)))]
                    for (L, s) in configs},
        "nonadditive_examples": [p for p in pairs_out if p["nonadditive"]][:30],
        "wall_time_s": round(time.time() - t0, 1),
        "quick": args.quick,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out["additive_temperature_law"].items()
                      if not k.startswith("false_")} | {
        "n_pairs": len(pairs_out), "n_nonadditive": n_nonadd}, indent=2,
        default=str))
    print(f"[saved] {OUT}, {fpath.name}")


if __name__ == "__main__":
    main()
