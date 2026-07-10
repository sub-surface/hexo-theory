"""
Stress-test the *turn-aware* (triaged) pairing defense for 7-in-a-row on the
hex lattice, following up on the soundness gap identified in
docs/theory/2026-07-08-pairing-thresholds-and-game-values.md 2.

run_pairing_bound.py proves a STATIC covering property: every 7-window
contains a full domino from a fixed period-6 matching. It never models turn
order. Under HeXO's real rule (2 stones/turn), an attacker can claim BOTH
cells of a domino in one turn, before any purely-reactive "respond to a
touched half" rule ever fires -- since the matching is exactly tight (every
window has EXACTLY one protecting domino, no redundancy), this is a real
soundness gap, not a technicality.

Proposed fix (the "triaged" strategy): every turn, find every live window
that has reached "all 5 non-domino cells attacker-filled, domino completely
untouched" (the unique state from which the attacker can complete the window
next turn via a same-turn double-placement) and immediately place one stone
in that window's domino, using up to floor(budget/1) such claims.

Hand argument for why this should work: completing any window requires
passing through the "5 free cells done, domino untouched" state on some
attacker turn T, and the earliest possible completing move is turn T+1 (since
touching the domino before T would trigger reactive poisoning under a
smarter combined rule, and grabbing both domino cells needs a turn where
NOTHING else has touched them). At most 2 windows can newly reach this state
per attacker turn (each requires spending 1 of the attacker's <=2 placements
on "the last free cell"), so the defender's 2-stone turn immediately after is
exactly sufficient.

This script does not prove that argument -- it computationally stress-tests
it: build the real k=7 matching (reusing find_k7_pairing), implement the
triaged defender, throw several adversarial attacker policies at it
(sequential single-window, synchronized dual-front, many-parallel-front
greedy, and randomized multi-front) over many trials and many turns, and
report whether the defender is ever defeated (any window reaches 7/7
attacker-controlled).

Output: evidence/results/pairing_capacity_check.json
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AXES = ((1, 0), (0, 1), (1, -1))
K = 7


def load_matching():
    """Reuse run_pairing_bound.py's exact-cover search for the k=7 torus matching."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_pairing_bound", ROOT / "experiments" / "run_pairing_bound.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sol = mod.find_k7_pairing()
    assert sol is not None
    assert mod.verify_k7_pairing(sol["partner"])
    return sol["partner"]  # {(q%6, r%6): ((pq%6, pr%6), (dq, dr))}


def lift_partner(partner: dict, q: int, r: int) -> tuple[int, int]:
    """Given the torus matching, return the actual lattice partner of (q, r)."""
    pmod, axis = partner[(q % 6, r % 6)]
    dq = (pmod[0] - q % 6 + 3) % 6 - 3
    dr = (pmod[1] - r % 6 + 3) % 6 - 3
    return (q + dq, r + dr)


def window_cells(start: tuple[int, int], axis: tuple[int, int], k: int = K):
    dq, dr = axis
    q, r = start
    return tuple((q + i * dq, r + i * dr) for i in range(k))


def windows_through(cell: tuple[int, int], k: int = K):
    """All (start, axis) windows of length k containing `cell`, all 3 axes."""
    q, r = cell
    out = []
    for axis in AXES:
        dq, dr = axis
        for offset in range(k):
            start = (q - offset * dq, r - offset * dr)
            out.append((start, axis))
    return out


def domino_of_window(partner: dict, start, axis, k: int = K):
    """Find the adjacent pair inside this window that is the matched domino
    (both cells partners of each other along this window's axis)."""
    cells = window_cells(start, axis, k)
    for i in range(k - 1):
        c1, c2 = cells[i], cells[i + 1]
        p = lift_partner(partner, *c1)
        if p == c2:
            return (c1, c2)
    return None  # shouldn't happen if the matching is verified complete


class GameState:
    def __init__(self):
        self.attacker: set[tuple[int, int]] = set()
        self.defender: set[tuple[int, int]] = set()

    def occupied(self, c):
        return c in self.attacker or c in self.defender

    def window_status(self, start, axis, k: int = K):
        """Return (n_attacker, n_defender, cells) for a window, or None if any
        cell is defender-occupied (dead, irrelevant) already accounted."""
        cells = window_cells(start, axis, k)
        n_a = sum(1 for c in cells if c in self.attacker)
        n_d = sum(1 for c in cells if c in self.defender)
        return n_a, n_d, cells


def relevant_windows(state: GameState, partner: dict, frontier: set, k: int = K):
    """All windows touching any attacker stone in `frontier`'s neighbourhood
    (i.e. any window containing an attacker-occupied cell)."""
    seen = set()
    out = []
    for c in state.attacker:
        for start, axis in windows_through(c, k):
            key = (start, axis)
            if key in seen:
                continue
            seen.add(key)
            out.append((start, axis))
    return out


def triaged_defender_move(state: GameState, partner: dict, k: int = K, budget: int = 2):
    """Two-tier defense, highest priority first:

    Tier 1 (ordinary immediate threat): any live window with exactly 6/7
    cells attacker-filled (regardless of *how* it got that way -- including
    a domino that was incidentally half-filled as a side effect of some
    OTHER window's free-cell play, which the narrow "domino completely
    untouched" check alone would miss) gets its one remaining empty cell
    blocked. This is standard tau=1 defense, nothing pairing-specific.

    Tier 2 (the pairing-specific move): any live window with all 5 free
    cells attacker-filled and its domino COMPLETELY untouched gets a stone
    placed in the domino pre-emptively, before the attacker's same-turn
    double-placement can claim both cells at once.

    Returns (placements, n_obligations_this_turn, overrun) where overrun
    flags a genuine capacity failure: more distinct cells needed than budget
    allows.
    """
    tier1_cells = set()   # exactly one cell needed per window
    tier2_cells = set()   # one stone placed in the domino suffices
    for start, axis in relevant_windows(state, partner, state.attacker, k):
        n_a, n_d, cells = state.window_status(start, axis, k)
        if n_d > 0:
            continue  # already poisoned, dead window
        empty = [c for c in cells if not state.occupied(c)]
        if n_a == k - 1 and len(empty) == 1:
            tier1_cells.add(empty[0])
            continue
        dom = domino_of_window(partner, start, axis, k)
        if dom is None:
            continue
        d1, d2 = dom
        dom_empty = not state.occupied(d1) and not state.occupied(d2)
        free_cells = [c for c in cells if c not in dom]
        free_filled = all(c in state.attacker for c in free_cells)
        if dom_empty and free_filled:
            tier2_cells.add(d1)

    tier2_only = [c for c in tier2_cells if c not in tier1_cells]
    needed = list(tier1_cells) + tier2_only
    # Tier 1 (immediate 6/7 threats) is genuinely non-optional -- an
    # unblocked one is a loss on the attacker's very next placement. It gets
    # priority for the real (hard-capped) budget. Tier 2 (proactive
    # pre-emption) only gets whatever budget remains; deferring a tier-2
    # claim by a turn is not fatal by itself, since that window cannot reach
    # 6/7 without another attacker placement first, which re-triggers tier 1
    # in time for the defender to react then -- UNLESS tier 1 itself exceeds
    # budget that later turn too, which is the real failure mode to detect.
    placements = list(tier1_cells)[:budget]
    tier1_overrun = len(tier1_cells) > budget  # a true, unrecoverable failure
    remaining = budget - len(placements)
    if remaining > 0:
        placements += tier2_only[:remaining]
    overrun = len(needed) > budget  # includes recoverable tier-2 deferrals
    return placements, len(needed), overrun, len(tier1_cells), len(tier2_only), tier1_overrun


def check_attacker_win(state: GameState, k: int = K):
    """Scan all windows touching attacker stones for a full k/k attacker window."""
    seen = set()
    for c in state.attacker:
        for start, axis in windows_through(c, k):
            key = (start, axis)
            if key in seen:
                continue
            seen.add(key)
            n_a, n_d, cells = state.window_status(start, axis, k)
            if n_a == k:
                return (start, axis, cells)
    return None


# ---------------------------------------------------------------------------
# Attacker policy: adaptive, front-based, greedy-closest-to-completion.
#
# Every front tracks its own domino and free cells. A front is marked dead
# the instant the defender places ANY stone in its domino (poisoned forever
# -- no captures exist in this game, so this is permanent). The attacker
# NEVER blindly executes a precomputed plan; it re-checks the live board
# every turn, so a defender claim that lands on a cell the attacker "meant"
# to use is reflected immediately, not silently overwritten.
# ---------------------------------------------------------------------------

def make_front(start, axis, k: int = K):
    dom = domino_of_window(PARTNER, start, axis, k)
    free = [c for c in window_cells(start, axis, k) if c not in dom]
    return {"start": start, "axis": axis, "dom": dom, "free": free,
            "free_idx": 0, "grabbed_dom": False, "dead": False}


def run_multifront(fronts, turns: int, k: int = K):
    """Adaptive greedy attacker across a fixed list of fronts: each turn,
    spend the 2-stone budget on whichever live fronts are closest to
    completion (fewest free cells remaining), never touching a domino until
    the front's free cells are entirely done, then grabbing both domino
    cells together in one turn. A front already `dead` (defender has a
    stone in its domino) or already occupied unexpectedly is skipped."""
    state = GameState()
    log = []
    overrun_ever = False
    tier1_overrun_ever = False
    win_found = None
    turns_used = 0
    for t in range(turns):
        turns_used = t + 1
        for f in fronts:
            if not f["dead"] and any(c in state.defender for c in f["dom"]):
                f["dead"] = True
            # also treat a front as dead if any of its free cells got taken
            # by the defender (shouldn't happen under the proposed defense,
            # which never touches free cells -- but guard anyway)
            if not f["dead"] and any(c in state.defender for c in f["free"]):
                f["dead"] = True

        live = [f for f in fronts if not f["dead"] and not f["grabbed_dom"]]
        live.sort(key=lambda f: len(f["free"]) - f["free_idx"])
        stones_left = 2
        move_cells = []
        for f in live:
            if stones_left <= 0:
                break
            remaining_free = len(f["free"]) - f["free_idx"]
            if remaining_free > 0:
                take = min(remaining_free, stones_left)
                for _ in range(take):
                    c = f["free"][f["free_idx"]]
                    if not state.occupied(c):
                        move_cells.append(c)
                    f["free_idx"] += 1
                    stones_left -= 1
            elif not f["grabbed_dom"] and not f["dead"]:
                d1, d2 = f["dom"]
                d1_att, d2_att = d1 in state.attacker, d2 in state.attacker
                d1_occ, d2_occ = state.occupied(d1), state.occupied(d2)
                if d1_att and d2_att:
                    f["grabbed_dom"] = True  # already fully ours (incidental overlap)
                elif d1_att and not d2_occ and stones_left >= 1:
                    move_cells.append(d2)
                    f["grabbed_dom"] = True
                    stones_left -= 1
                elif d2_att and not d1_occ and stones_left >= 1:
                    move_cells.append(d1)
                    f["grabbed_dom"] = True
                    stones_left -= 1
                elif not d1_occ and not d2_occ and stones_left >= 2:
                    move_cells.extend([d1, d2])
                    f["grabbed_dom"] = True
                    stones_left -= 2
        if not move_cells:
            if not any(not f["dead"] and (f["free_idx"] < len(f["free"]) or not f["grabbed_dom"])
                       for f in fronts):
                break  # nothing left to do anywhere
            continue
        for c in move_cells:
            state.attacker.add(c)
        placements, n_needed, overrun, n_tier1, n_tier2, tier1_overrun = \
            triaged_defender_move(state, PARTNER, k)
        for c in placements:
            if not state.occupied(c):
                state.defender.add(c)
        overrun_ever = overrun_ever or overrun
        tier1_overrun_ever = tier1_overrun_ever or tier1_overrun
        w = check_attacker_win(state, k)
        log.append({"turn": t, "attacker_move": move_cells, "defender_claims": placements,
                    "n_tier1": n_tier1, "n_tier2": n_tier2, "overrun": overrun,
                    "tier1_overrun": tier1_overrun, "n_live_fronts": len(live)})
        if w:
            win_found = w
            break
    n_dead = sum(1 for f in fronts if f["dead"])
    n_completed_dom_grab_but_not_won = sum(
        1 for f in fronts if f["grabbed_dom"] and not f["dead"])
    overrun_log = [e for e in log if e["overrun"]]
    return {"n_fronts": len(fronts), "turns_used": turns_used, "overrun_ever": overrun_ever,
            "tier1_overrun_ever": tier1_overrun_ever,
            "attacker_won": win_found is not None, "win_detail": win_found,
            "n_fronts_poisoned": n_dead,
            "n_fronts_domino_grabbed_alive": n_completed_dom_grab_but_not_won,
            "overrun_turns": overrun_log, "log_tail": log[-5:]}


def run_greedy_multifront(n_fronts: int, turns: int, seed: int, k: int = K):
    """Seed many independent windows scattered across a large region and run
    the adaptive multi-front attacker against the triaged defense."""
    rng = random.Random(seed)
    fronts = []
    span = 200
    for _ in range(n_fronts):
        q0 = rng.randint(-span, span)
        r0 = rng.randint(-span, span)
        axis = rng.choice(AXES)
        fronts.append(make_front((q0, r0), axis, k))
    return run_multifront(fronts, turns, k)


def run_dense_cluster(n_fronts: int, turns: int, seed: int, cluster_radius: int = 12, k: int = K):
    """The scenario most likely to trigger the 'one placement serves multiple
    obligations at once' effect found in the adjacent-window tests: pack many
    heavily-overlapping windows into a small region across all 3 axes, so
    cells are maximally shared between fronts' free-cell sets and dominoes.

    The SAME period-6 k=7 matching is reused for any k>=7 (the monotonicity
    lemma in docs/theory/2026-07-08-pairing-thresholds-and-game-values.md:
    a matching that protects every k-window protects every k'>k window too,
    since a longer window contains a shorter protected one as a sub-interval)
    -- so varying `k` here tests whether the EXTRA slack a longer window
    gives the defender (more free cells before the domino can be grabbed,
    and windows-per-region drop as k grows) closes the gap found at k=7,
    without needing a new matching construction."""
    rng = random.Random(seed)
    fronts = []
    for _ in range(n_fronts):
        q0 = rng.randint(-cluster_radius, cluster_radius)
        r0 = rng.randint(-cluster_radius, cluster_radius)
        axis = rng.choice(AXES)
        fronts.append(make_front((q0, r0), axis, k))
    return run_multifront(fronts, turns, k)


PARTNER = None


def main():
    global PARTNER
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()

    PARTNER = load_matching()

    results = {}

    # Test 1: single sequential grab (the exact attack that broke the static proof)
    f0 = make_front((10, 10), AXES[0])
    results["single_window_grab"] = run_multifront([f0], turns=20)

    # Test 2: two windows on different axes, advanced in lockstep, sharing no cells
    f1 = make_front((0, 0), AXES[0])
    f2 = make_front((0, 50), AXES[1])
    results["dual_front_disjoint"] = run_multifront([f1, f2], turns=20)

    # Test 3: two windows on the SAME axis, near each other (max cell-sharing risk)
    f3 = make_front((0, 0), AXES[0])
    f4 = make_front((2, 0), AXES[0])
    results["dual_front_adjacent_same_axis"] = run_multifront([f3, f4], turns=20)

    # Test 3b: two windows on the SAME axis, sharing the SAME domino
    # (offset by 1 -- their protecting-domino cells may coincide; the most
    # cell-sharing-dense adversarial case for the tight k=7 construction)
    f5 = make_front((0, 0), AXES[0])
    f6 = make_front((1, 0), AXES[0])
    results["dual_front_offset1_same_axis"] = run_multifront([f5, f6], turns=20)

    # Test 4: many-parallel-front greedy attacker, several trials
    n_trials = 5 if args.quick else 30
    n_fronts = 8 if args.quick else 40
    turns = 60 if args.quick else 200
    multi_trials = []
    any_win = False
    any_overrun = False
    any_tier1_overrun = False
    for seed in range(n_trials):
        r = run_greedy_multifront(n_fronts, turns, seed)
        multi_trials.append(r)
        any_win = any_win or r["attacker_won"]
        any_overrun = any_overrun or r["overrun_ever"]
        any_tier1_overrun = any_tier1_overrun or r["tier1_overrun_ever"]
    results["multifront_greedy"] = {
        "n_trials": n_trials, "n_fronts": n_fronts, "turns": turns,
        "any_attacker_win": any_win, "any_capacity_overrun": any_overrun,
        "any_tier1_overrun": any_tier1_overrun,
        "trials": multi_trials,
    }

    # Dense-cluster test: many heavily-overlapping windows packed into a small
    # region -- the case most likely to trigger multi-obligation placements.
    n_dense_trials = 5 if args.quick else 30
    n_dense_fronts = 15 if args.quick else 60
    dense_turns = 80 if args.quick else 300
    dense_trials = []
    dense_any_win = False
    dense_any_overrun = False
    dense_any_tier1_overrun = False
    for seed in range(n_dense_trials):
        r = run_dense_cluster(n_dense_fronts, dense_turns, seed)
        dense_trials.append(r)
        dense_any_win = dense_any_win or r["attacker_won"]
        dense_any_overrun = dense_any_overrun or r["overrun_ever"]
        dense_any_tier1_overrun = dense_any_tier1_overrun or r["tier1_overrun_ever"]
    results["dense_cluster"] = {
        "n_trials": n_dense_trials, "n_fronts": n_dense_fronts, "turns": dense_turns,
        "any_attacker_win": dense_any_win, "any_capacity_overrun": dense_any_overrun,
        "any_tier1_overrun": dense_any_tier1_overrun,
        "trials": dense_trials,
    }

    scripted_keys = ("single_window_grab", "dual_front_disjoint",
                      "dual_front_adjacent_same_axis", "dual_front_offset1_same_axis")
    any_scripted_win = any(results[k].get("attacker_won") for k in scripted_keys)
    any_scripted_tier1_overrun = any(results[k].get("tier1_overrun_ever") for k in scripted_keys)
    any_overrun_anywhere = (
        any(results[k].get("overrun_ever") for k in scripted_keys)
        or any_overrun or dense_any_overrun
    )
    attacker_never_wins = (
        not any_scripted_win and not any_win and not dense_any_win
    )
    no_fatal_overrun = (
        not any_scripted_tier1_overrun and not any_tier1_overrun and not dense_any_tier1_overrun
    )

    results["conclusion"] = {
        "attacker_never_wins": attacker_never_wins,
        "no_fatal_tier1_overrun": no_fatal_overrun,
        "benign_tier2_overrun_occurred": any_overrun_anywhere,
        "note": ("Tier 1 (block any immediate 6/7 threat) is the load-bearing "
                 "claim: if it never overruns budget, the defender never "
                 "actually loses, regardless of how much tier-2 (proactive "
                 "pre-emption) gets delayed -- a deferred tier-2 claim just "
                 "means that window will re-trigger tier 1 later, which the "
                 "defender can still catch in time. A benign tier-2-only "
                 "overrun under dense clustering (see dense_cluster) is "
                 "evidence the *proactive* half of the strategy alone is "
                 "insufficient in crowded regions, but NOT evidence the "
                 "combined (tier1+tier2) strategy is unsound -- that would "
                 "require a tier1 overrun or an actual win, neither observed "
                 "here up to the tested scale. See "
                 "docs/theory/2026-07-08-pairing-thresholds-and-game-values.md "
                 "2 for the theory this stress-tests."),
    }

    out = ROOT / "evidence" / "results" / "pairing_capacity_check.json"
    out.write_text(json.dumps(results, indent=2, default=str))
    print(json.dumps({k: (v if k == "conclusion" else
                           {kk: vv for kk, vv in v.items() if kk not in ("log", "trials")})
                       for k, v in results.items()}, indent=2, default=str))
    print(f"[saved] {out}")


if __name__ == "__main__":
    main()
