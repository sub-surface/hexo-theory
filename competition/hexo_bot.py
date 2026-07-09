"""
Standalone HeXO tournament bot -- self-contained, numpy-only, no other
dependency on this repo. Designed to be dropped into another team's agent
harness with minimal glue code.

WHAT THIS ASSUMES ABOUT THE RULES (verify against the opponent's engine
before a real match -- a silent mismatch here is the single biggest risk in
handing this off):

  - Infinite hex board, axial coordinates (q, r), integers, no bounds.
  - Three win-line directions: (1,0), (0,1), (1,-1) -- i.e. HeXO's standard
    Eisenstein-lattice axes. If the other engine uses a different axis
    convention (e.g. includes (1,1) instead of (1,-1)), this bot's threat
    detection will silently miss real lines. Cross-check with a few known
    winning positions before trusting it in a real match.
  - Win condition: 6 in a row along any one of those three directions.
  - Turn rule: player 1 places 1 stone on the very first move of the game;
    thereafter EVERY player, including player 1, places 2 stones per turn
    ("1-2-2"). If the opponent's tournament uses plain 1-1 alternation
    instead, everything here still runs (the interface takes explicit
    per-call state) but the SEARCH's opponent-turn model
    (build_seq/make_move) assumes 2-placement turns and needs
    `stones_per_turn` set accordingly per call -- see choose_move below.
  - No captures -- a placed stone is permanent. If the tournament allows
    overwriting/removal, this bot does not model that at all.

WHAT THIS BOT ACTUALLY DOES (see
competition/2026-07-08-optimal-play-and-bot-design.md for the reasoning,
sections 1-2 for the design, section 3 for what changed on 2026-07-08):

  - Exact win/block detection at the root before any search -- never misses
    an immediate one-placement win or an immediate forced loss, regardless
    of time budget.
  - Exact TACTICAL COMPLETENESS at every node of the search, not just the
    root (_forced_result / _hot_windows below): a 1-2-2 turn places up to 2
    stones, so a live line with 4-of-6 already filled is an UNCONDITIONAL
    win this turn (both remaining placements land in it) even though no
    single placement completes it yet -- and symmetrically, if the
    opponent holds 2+ such lines that can't be jointly covered by the
    mover's remaining placements this turn, the position is a proven loss
    no matter how the search tree looks. This was added 2026-07-08 after a
    controlled ablation showed the PREVIOUS version of this file (search +
    fork bonus, no exact tactical check) LOST 24-0 to a much simpler,
    shallower bot in both fork-bonus-on and fork-bonus-off configurations
    -- the narrow top-k move-ordering beam this search uses was silently
    pruning forced continuations at depth, a classic "search amplifies a
    blind spot" failure mode, not a bad evaluation feature. The exact
    check removes that blind spot entirely rather than trying to out-tune
    around it.
  - True iterative-deepening minimax over the real alternating-turn
    structure (not a static one-sided heuristic comparison, which this
    project found to be actively worse than no search at all).
  - A fork/tau-pressure term (reward for creating or blocking a genuine
    tau>2 double-threat) added to move ordering and the search's leaf
    evaluation, as a SOFT heuristic supplement to the exact check above
    (it helps rank moves the exact check doesn't resolve one way or the
    other -- most of the game, most positions are neither a forced win nor
    a forced loss).
  - A hard internal time budget, checked INSIDE the search recursion (not
    just between candidate moves), so it degrades gracefully under time
    pressure instead of risking an overrun -- tune `TIME_BUDGET_S` to
    whatever margin you want under the tournament's actual per-move limit.

Usage:

    from hexo_bot import choose_move

    q, r = choose_move(
        stones={(0, 0): 1, (1, 0): 2},   # dict[(q, r), player], player in {1, 2}
        turn=1,                          # which player is moving now
        placed_this_turn=0,              # how many of THIS turn's placements
                                          # are already made (0 or 1)
        stones_per_turn=2,               # 1 only for the game's very first
                                          # placement, else 2
    )

`choose_move` is stateless and pure -- call it fresh each time with the
current board; it does not need to be told about game history.
"""
from __future__ import annotations

import time
from typing import Optional

import numpy as np

Cell = tuple[int, int]

WIN_LENGTH = 6
AXES = ((1, 0), (0, 1), (1, -1))
RING = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))
_AXIS_PAIRS = (((1, 0), (-1, 0)), ((0, 1), (0, -1)), ((1, -1), (-1, 1)))

# --- tunables (validated against this repo's own bot ladder; see
# competition/2026-07-08-optimal-play-and-bot-design.md before changing) ---
DEFENCE_WEIGHT = 1.1
FORK_BONUS = 60.0
TOP_K = 5
TIME_BUDGET_S = 0.70    # internal soft target; leaves margin under a 1.0s cap
CHECK_EVERY = 16        # how often (in node visits) the search checks the clock

_PAD = 12


def other(p: int) -> int:
    return 2 if p == 1 else 1


def check_win(stones: dict[Cell, int], q: int, r: int, player: int) -> bool:
    for (dq_a, dr_a), (dq_b, dr_b) in _AXIS_PAIRS:
        count = 1
        cq, cr = q + dq_a, r + dr_a
        while stones.get((cq, cr)) == player:
            count += 1; cq += dq_a; cr += dr_a
        cq, cr = q + dq_b, r + dr_b
        while stones.get((cq, cr)) == player:
            count += 1; cq += dq_b; cr += dr_b
        if count >= WIN_LENGTH:
            return True
    return False


def candidates(stones: dict[Cell, int]) -> list[Cell]:
    if not stones:
        return [(0, 0)]
    seen: set[Cell] = set()
    out: list[Cell] = []
    for (q, r) in stones:
        for dq, dr in RING:
            c = (q + dq, r + dr)
            if c in stones or c in seen:
                continue
            seen.add(c)
            out.append(c)
    return out


def _shift(a, dr: int, dq: int):
    h, w = a.shape
    out = np.zeros_like(a)
    ys, yd = (slice(dr, h), slice(0, h - dr)) if dr >= 0 else (slice(0, h + dr), slice(-dr, h))
    xs, xd = (slice(dq, w), slice(0, w - dq)) if dq >= 0 else (slice(0, w + dq), slice(-dq, w))
    out[yd, xd] = a[ys, xs]
    return out


def _board_arrays(stones: dict[Cell, int], me: int):
    qs = [q for q, _ in stones] or [0]
    rs = [r for _, r in stones] or [0]
    q0, r0 = min(qs) - _PAD, min(rs) - _PAD
    h = max(rs) - min(rs) + 1 + 2 * _PAD
    w = max(qs) - min(qs) + 1 + 2 * _PAD
    own = np.zeros((h, w), dtype=np.int16)
    opp = np.zeros((h, w), dtype=np.int16)
    for (q, r), p in stones.items():
        (own if p == me else opp)[r - r0, q - q0] = 1
    return own, opp, q0, r0


def _axis_maps(own, opp, dq: int, dr: int):
    own_s, opp_s = own.astype(np.int32), opp.astype(np.int32)
    for i in range(1, WIN_LENGTH):
        own_s = own_s + _shift(own, i * dr, i * dq)
        opp_s = opp_s + _shift(opp, i * dr, i * dq)
    live = opp_s == 0
    win_pot = np.where(live, np.power(4.0, own_s), 0.0)
    win_thr = (live & (own_s >= 3)).astype(np.float64)
    pot, thr = win_pot.copy(), win_thr.copy()
    for i in range(1, WIN_LENGTH):
        pot += _shift(win_pot, -i * dr, -i * dq)
        thr += _shift(win_thr, -i * dr, -i * dq)
    return pot, thr


def _eval_maps(stones: dict[Cell, int], me: int):
    own, opp, q0, r0 = _board_arrays(stones, me)
    shape = own.shape
    own_pot = np.zeros(shape); own_thr = np.zeros(shape)
    opp_pot = np.zeros(shape); opp_thr = np.zeros(shape)
    for dq, dr in AXES:
        p, t = _axis_maps(own, opp, dq, dr)
        own_pot += p; own_thr += t
        p, t = _axis_maps(opp, own, dq, dr)
        opp_pot += p; opp_thr += t
    return own_pot, own_thr, opp_pot, opp_thr, q0, r0


def _global_potential(own, opp) -> float:
    total = 0.0
    for dq, dr in AXES:
        own_s, opp_s = own.astype(np.int32), opp.astype(np.int32)
        for i in range(1, WIN_LENGTH):
            own_s = own_s + _shift(own, i * dr, i * dq)
            opp_s = opp_s + _shift(opp, i * dr, i * dq)
        live = (opp_s == 0) & (own_s > 0)
        total += float(np.where(live, np.power(4.0, own_s), 0.0).sum())
    return total


def _global_threats(own, opp, min_own: int = 4) -> float:
    total = 0.0
    for dq, dr in AXES:
        own_s, opp_s = own.astype(np.int32), opp.astype(np.int32)
        for i in range(1, WIN_LENGTH):
            own_s = own_s + _shift(own, i * dr, i * dq)
            opp_s = opp_s + _shift(opp, i * dr, i * dq)
        live = opp_s == 0
        total += float(np.where(live & (own_s >= min_own), 1.0, 0.0).sum())
    return total


def _hot_windows(stones: dict[Cell, int], player: int, min_own: int) -> list[frozenset]:
    """Every LIVE window (no opponent stone) with >= min_own of player's
    EXISTING stones. With min_own = WIN_LENGTH-2 (4) these are exactly the
    windows completable within a single 1-2-2 turn (<=2 empty cells).
    Returns each such window's empty cells."""
    own, opp, q0, r0 = _board_arrays(stones, player)
    hot: list[frozenset] = []
    for dq, dr in AXES:
        own_s = own.astype(np.int32).copy()
        opp_s = opp.astype(np.int32).copy()
        for i in range(1, WIN_LENGTH):
            own_s += _shift(own, i * dr, i * dq)
            opp_s += _shift(opp, i * dr, i * dq)
        mask = (opp_s == 0) & (own_s >= min_own)
        ys, xs = np.nonzero(mask)
        for y, x in zip(ys.tolist(), xs.tolist()):
            wq, wr = x + q0, y + r0
            empties = frozenset(
                (wq + i * dq, wr + i * dr)
                for i in range(WIN_LENGTH)
                if (wq + i * dq, wr + i * dr) not in stones
            )
            if empties:
                hot.append(empties)
    return hot


def _forced_result(stones: dict[Cell, int], player: int, remaining: int) -> Optional[str]:
    """Exact tactical verdict for `player`, who has `remaining` (1 or 2)
    placements left in their CURRENT turn: 'WIN' if some live window
    already completes within `remaining` placements; 'LOSS' if the
    opponent holds >=2 live brink windows (completable within the
    opponent's own upcoming full 2-stone turn) whose empty cells can't be
    jointly covered by `remaining` cells -- an unblockable fork regardless
    of what `player` does. None otherwise. Checked at EVERY search node,
    not just the root -- see the module docstring for why."""
    if _hot_windows(stones, player, WIN_LENGTH - remaining):
        return 'WIN'
    opp = other(player)
    opp_hot = _hot_windows(stones, opp, WIN_LENGTH - 2)
    if len(opp_hot) < 2:
        return None
    cells = set()
    for e in opp_hot:
        cells |= e
    cells = list(cells)
    if remaining >= 2:
        for i, c1 in enumerate(cells):
            for c2 in cells[i:]:
                if all((c1 in e) or (c2 in e) for e in opp_hot):
                    return None
        return 'LOSS'
    if any(all(c in e for e in opp_hot) for c in cells):
        return None
    return 'LOSS'


class _TimeUp(Exception):
    pass


def choose_move(stones: dict[Cell, int], turn: int, placed_this_turn: int = 0,
                stones_per_turn: int = 2, time_budget_s: float = TIME_BUDGET_S,
                defence_weight: float = DEFENCE_WEIGHT, fork_bonus: float = FORK_BONUS,
                top_k: int = TOP_K) -> Cell:
    """Return the (q, r) cell to place a stone at for `turn`, given the
    current board. Pure function of its arguments -- call fresh each move.
    """
    me, opp = turn, other(turn)
    cells = candidates(stones)
    my_remaining = stones_per_turn - placed_this_turn

    for (q, r) in cells:  # exact win check -- always correct, never skipped
        nxt = dict(stones); nxt[(q, r)] = me
        if check_win(nxt, q, r, me):
            return (q, r)
    if my_remaining >= 2:
        # Brink win: a live window with exactly 2 empty cells and 4 of my
        # stones is an unconditional win this turn (both remaining
        # placements land in it) -- the check above only catches the
        # 1-empty-cell case. See _forced_result's doc comment.
        brink = _hot_windows(stones, me, WIN_LENGTH - 2)
        if brink:
            return next(iter(brink[0]))
    for (q, r) in cells:  # exact block check
        nxt = dict(stones); nxt[(q, r)] = opp
        if check_win(nxt, q, r, opp):
            return (q, r)

    def board_eval(s) -> float:
        own, o, _, _ = _board_arrays(s, me)
        pot = _global_potential(own, o) - defence_weight * _global_potential(o, own)
        my_fork = max(0.0, _global_threats(own, o) - 1.0)
        opp_fork = max(0.0, _global_threats(o, own) - 1.0)
        return pot + (my_fork + opp_fork * defence_weight) * fork_bonus

    def top_candidates(s, player: int, k: int) -> list[Cell]:
        own_pot, own_thr, opp_pot, opp_thr, q0, r0 = _eval_maps(s, player)
        fork = np.maximum(own_thr - 1, 0) + np.maximum(opp_thr - 1, 0) * defence_weight
        score = own_pot + opp_pot * defence_weight + fork * fork_bonus
        cs = candidates(s)
        cs.sort(key=lambda c: -score[c[1] - r0, c[0] - q0])
        return cs[:k]

    def build_seq(n_plies: int) -> list[int]:
        seq, remaining, player = [], my_remaining, me
        for _ in range(n_plies):
            seq.append(player)
            remaining -= 1
            if remaining == 0:
                player = opp if player == me else me
                remaining = 2
        return seq

    BIG = 1e12
    t0 = time.perf_counter()
    deadline = t0 + time_budget_s
    node_count = [0]

    def check_time():
        node_count[0] += 1
        if node_count[0] % CHECK_EVERY == 0 and time.perf_counter() > deadline:
            raise _TimeUp()

    def search(s, seq, idx: int, alpha: float, beta: float) -> float:
        check_time()
        if idx == len(seq):
            return board_eval(s)
        player = seq[idx]
        remaining_here = 2 if (idx + 1 < len(seq) and seq[idx + 1] == player) else 1
        forced = _forced_result(s, player, remaining_here)
        if forced == 'WIN':
            return (BIG - idx) if player == me else (-BIG + idx)
        if forced == 'LOSS':
            return (-BIG + idx) if player == me else (BIG - idx)
        best = -BIG if player == me else BIG
        for c in top_candidates(s, player, top_k):
            nxt = dict(s); nxt[c] = player
            if check_win(nxt, c[0], c[1], player):
                val = BIG - idx if player == me else -BIG + idx
            else:
                val = search(nxt, seq, idx + 1, alpha, beta)
            if player == me:
                best = max(best, val); alpha = max(alpha, val)
            else:
                best = min(best, val); beta = min(beta, val)
            if beta <= alpha:
                break
        return best

    best_cell: Optional[Cell] = None
    n_plies = my_remaining + 2
    while True:
        seq = build_seq(n_plies)
        try:
            depth_best_cell, depth_best_val = None, -BIG
            for c in top_candidates(stones, me, max(top_k, 6)):
                nxt = dict(stones); nxt[c] = me
                val = search(nxt, seq, 1, -BIG, BIG)
                if val > depth_best_val:
                    depth_best_val, depth_best_cell = val, c
            best_cell = depth_best_cell
        except _TimeUp:
            break
        if time.perf_counter() > deadline:
            break
        n_plies += 2

    return best_cell if best_cell is not None else cells[0]


if __name__ == "__main__":
    # smoke test: opening move, a 1-move forced win, a 2-move ("brink")
    # forced win, and an unblockable-fork forced loss must all resolve
    # correctly and instantly/legally.
    mv = choose_move({}, turn=1, placed_this_turn=0, stones_per_turn=1)
    assert mv == (0, 0), mv
    print(f"opening move: {mv}")

    win_setup = {(0, 0): 1, (1, 0): 1, (2, 0): 1, (3, 0): 1, (4, 0): 1}
    mv2 = choose_move(win_setup, turn=1, placed_this_turn=0, stones_per_turn=2)
    assert mv2 in [(5, 0), (-1, 0)], mv2
    print(f"1-move forced win found: {mv2}")

    brink_setup = {(0, 0): 1, (1, 0): 1, (2, 0): 1, (3, 0): 1}
    mv3 = choose_move(brink_setup, turn=1, placed_this_turn=0, stones_per_turn=2)
    assert mv3 in {(-2, 0), (-1, 0), (4, 0), (5, 0)}, mv3
    print(f"2-move (brink) forced win found: {mv3}")

    fork_setup = {
        (0, 0): 2, (1, 0): 2, (2, 0): 2, (5, 0): 2,
        (10, 0): 2, (10, 1): 2, (10, 2): 2, (10, 5): 2,
    }
    forced = _forced_result(fork_setup, 1, remaining=1)
    assert forced == 'LOSS', forced
    print("unblockable opponent fork correctly detected as a forced loss")

    print("smoke test OK")
