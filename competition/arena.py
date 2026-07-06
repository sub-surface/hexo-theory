"""
HeXO bot competition arena.

A self-contained testbed for breeding the opponent that ships on the garden's
/hexo page. The rules engine here is a faithful, dependency-free mirror of the
garden's TypeScript engine (src/lib/hexo.ts) and the upstream `hexgo` engine:
infinite hex board on Z[omega], 1-2-2 turn rule, win = 6 in a row along any of the
three axes. Keeping it standalone means (a) no fragile import path into ../hexgo,
and (b) the winning strategy ports back to TypeScript line-for-line.

Each bot gets a fixed compute budget per move (default 1.0s). A bot that overruns
its budget forfeits the move to a fallback (nearest legal cell), so slow-but-strong
search strategies are penalised exactly as they would be in the browser.

Run:  python competition/arena.py            # round-robin tournament
      python competition/arena.py --quick    # fast smoke run
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

# --- rules engine (mirror of src/lib/hexo.ts) --------------------------------

WIN_LENGTH = 6
AXES = (((1, 0), (-1, 0)), ((0, 1), (0, -1)), ((1, -1), (-1, 1)))
RING = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))

Cell = tuple[int, int]
Player = int  # 1 or 2


@dataclass
class State:
    stones: dict[Cell, Player] = field(default_factory=dict)
    turn: Player = 1
    placed_this_turn: int = 0
    stones_per_turn: int = 1
    move_number: int = 1
    winner: Optional[Player] = None


def other(p: Player) -> Player:
    return 2 if p == 1 else 1


def check_win(stones: dict[Cell, Player], q: int, r: int, player: Player) -> bool:
    for (dq_a, dr_a), (dq_b, dr_b) in AXES:
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


def place(state: State, q: int, r: int) -> State:
    """Pure: place a stone for the current player; illegal moves return state copy."""
    if state.winner is not None or (q, r) in state.stones:
        return state
    stones = dict(state.stones)
    stones[(q, r)] = state.turn
    s = State(stones=stones, turn=state.turn,
              placed_this_turn=state.placed_this_turn + 1,
              stones_per_turn=state.stones_per_turn,
              move_number=state.move_number, winner=state.winner)
    if check_win(stones, q, r, state.turn):
        s.winner = state.turn
        return s
    if s.placed_this_turn >= s.stones_per_turn:
        s.turn = other(state.turn)
        s.placed_this_turn = 0
        s.stones_per_turn = 2
        s.move_number += 1
    return s


def candidates(stones: dict[Cell, Player]) -> list[Cell]:
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


# --- bot interface -----------------------------------------------------------
#
# A bot is a callable: (state) -> (q, r). It must return a legal candidate cell.
# It is called once per stone (so twice in a normal turn).

Bot = Callable[[State], Cell]


def cell_score(stones: dict[Cell, Player], q: int, r: int, player: Player) -> float:
    """Erdos-Selfridge-style live-line value (mirror of the TS heuristic)."""
    opp = other(player)
    score = 0.0
    for dq, dr in ((1, 0), (0, 1), (1, -1)):
        for offset in range(-5, 1):
            own = 0
            blocked = False
            for i in range(6):
                cq = q + dq * (offset + i)
                cr = r + dr * (offset + i)
                if cq == q and cr == r:
                    continue
                occ = stones.get((cq, cr))
                if occ == opp:
                    blocked = True
                    break
                if occ == player:
                    own += 1
            if not blocked:
                score += 4 ** own
    return score


def make_heuristic(defence_weight: float = 1.1) -> Bot:
    """The garden's shipped heuristic, parameterised by how much it values blocking."""
    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        # 1. take a win
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        # 2. block a loss
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)
        # 3. best blended score
        best, best_s = cells[0], -1.0
        for (q, r) in cells:
            s = cell_score(state.stones, q, r, me) + cell_score(state.stones, q, r, opp) * defence_weight
            if s > best_s:
                best_s, best = s, (q, r)
        return best
    return bot


def random_bot(seed: int = 0) -> Bot:
    state_seed = [seed]
    def bot(state: State) -> Cell:
        cells = candidates(state.stones)
        # simple LCG so we don't import random (deterministic, seedable)
        state_seed[0] = (state_seed[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return cells[state_seed[0] % len(cells)]
    return bot


def greedy_offence() -> Bot:
    """Pure attack: maximise own potential, ignore defence (a useful sparring foil)."""
    return make_heuristic(defence_weight=0.0)


def threat_count(stones: dict[Cell, Player], q: int, r: int, player: Player, min_own: int) -> int:
    """
    Number of distinct length-6 windows through (q,r) that, AFTER placing here,
    would hold >= min_own of `player`'s stones and no opponent stone. With
    min_own=4 this counts the "near-complete, still-open" lines a move creates —
    a cheap proxy for the transversal pressure tau(O): two or more such windows
    at once is a fork the opponent's 2-stone budget cannot cover.
    """
    opp = other(player)
    count = 0
    for dq, dr in ((1, 0), (0, 1), (1, -1)):
        for offset in range(-5, 1):
            own = 1  # the stone we are placing at (q,r)
            blocked = False
            for i in range(6):
                cq = q + dq * (offset + i)
                cr = r + dr * (offset + i)
                if cq == q and cr == r:
                    continue
                occ = stones.get((cq, cr))
                if occ == opp:
                    blocked = True
                    break
                if occ == player:
                    own += 1
            if not blocked and own >= min_own:
                count += 1
    return count


def make_fork_aware(defence_weight: float = 1.1, fork_bonus: float = 60.0) -> Bot:
    """
    The theory-informed cheap heuristic (DIRECTION.md). Same Erdos-Selfridge base
    as `make_heuristic`, plus an explicit reward for creating/blocking *forks* —
    moves that open two or more near-complete lines at once (tau > 2). This is the
    single highest-value upgrade the transversal framework predicts, and it costs
    one extra local scan per candidate (still O(cells), no search tree).
    """
    base = cell_score
    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        # 1. take a win
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        # 2. block a loss
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)
        # 3. blended potential + fork pressure (offence and defence).
        # A fork only matters at >=2 simultaneous near-complete lines (that is the
        # tau>2 double-threat). A SINGLE near-complete line is already valued by the
        # ES base, so we must not re-reward it — only the surplus beyond the first
        # threat counts. Linear in (count-1), not squared: a 1-threat move adds 0,
        # a genuine 2-fork adds the bonus once. This is the fix for the d1.1 bug
        # where squaring made the bot chase its own single threats and lose.
        best, best_s = cells[0], -1e18
        for (q, r) in cells:
            off = base(state.stones, q, r, me) + base(state.stones, q, r, opp) * defence_weight
            my_fork = max(0, threat_count(state.stones, q, r, me, min_own=4) - 1)
            opp_fork = max(0, threat_count(state.stones, q, r, opp, min_own=4) - 1)
            fork = (my_fork + opp_fork * defence_weight) * fork_bonus
            s = off + fork
            if s > best_s:
                best_s, best = s, (q, r)
        return best
    return bot


# --- fast vectorized evaluator (candidates B+D of the 2026-07-05 handoff) ----
#
# The cube-coordinate decomposition (verified: each axis fixes one cube coord)
# says the threat landscape is three independent 1-D window families coupled
# only through shared cells -- so the whole board evaluates with per-axis
# sliding-window sums instead of per-candidate rescans. For length-6 kernels
# shifted adds beat FFT; same numbers as cell_score/threat_count, ~100x fewer
# Python-level ops, which is what buys depth-2 lookahead inside the budget.
# numpy is imported lazily so the rules engine above stays dependency-free.

_PAD = 12  # stones sit >= _PAD from array edge, so no window escapes the grid


def _board_arrays(np, stones: dict[Cell, Player], me: Player):
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


def _shift(np, a, dr: int, dq: int):
    """out[y, x] = a[y + dr, x + dq], zero-filled (no wraparound)."""
    h, w = a.shape
    out = np.zeros_like(a)
    ys, yd = (slice(dr, h), slice(0, h - dr)) if dr >= 0 else (slice(0, h + dr), slice(-dr, h))
    xs, xd = (slice(dq, w), slice(0, w - dq)) if dq >= 0 else (slice(0, w + dq), slice(-dq, w))
    out[yd, xd] = a[ys, xs]
    return out


def _axis_maps(np, own, opp, dq: int, dr: int):
    """Per-cell (potential, threat-count) contributions of one axis family."""
    own_s, opp_s = own.astype(np.int32), opp.astype(np.int32)
    for i in range(1, WIN_LENGTH):
        own_s = own_s + _shift(np, own, i * dr, i * dq)
        opp_s = opp_s + _shift(np, opp, i * dr, i * dq)
    live = opp_s == 0
    win_pot = np.where(live, np.power(4.0, own_s), 0.0)
    win_thr = (live & (own_s >= 3)).astype(np.float64)  # own>=3 + placed stone -> >=4
    pot = win_pot.copy()
    thr = win_thr.copy()
    for i in range(1, WIN_LENGTH):
        pot += _shift(np, win_pot, -i * dr, -i * dq)
        thr += _shift(np, win_thr, -i * dr, -i * dq)
    return pot, thr


def _eval_maps(np, stones: dict[Cell, Player], me: Player):
    """Whole-board (own_pot, own_thr, opp_pot, opp_thr) maps + grid origin.

    Matches cell_score / threat_count exactly on every empty cell (see
    --selftest): pot[cell] == cell_score(stones, *cell, player) and
    thr[cell] == threat_count(stones, *cell, player, min_own=4).
    """
    own, opp, q0, r0 = _board_arrays(np, stones, me)
    shape = own.shape
    own_pot = np.zeros(shape); own_thr = np.zeros(shape)
    opp_pot = np.zeros(shape); opp_thr = np.zeros(shape)
    for dq, dr in ((1, 0), (0, 1), (1, -1)):
        p, t = _axis_maps(np, own, opp, dq, dr)
        own_pot += p; own_thr += t
        p, t = _axis_maps(np, opp, own, dq, dr)
        opp_pot += p; opp_thr += t
    return own_pot, own_thr, opp_pot, opp_thr, q0, r0


def make_fast_tactical(defence_weight: float = 1.2, fork_bonus: float = 60.0,
                       top_k: int = 12, reply_discount: float = 0.8) -> Bot:
    """
    Candidates B+D unified: the same ES-potential + tau-fork-surplus score as
    make_fork_aware, but computed for every cell at once via per-axis sliding
    sums -- cheap enough to afford a 1-placement opponent-reply lookahead
    (depth 2 in placements) on the top_k static candidates. This is the "next
    real gain is shallow search" rung of DIRECTION.md's heuristic ladder.
    """
    import numpy as np

    def static_scores(stones, me):
        own_pot, own_thr, opp_pot, opp_thr, q0, r0 = _eval_maps(np, stones, me)
        fork = (np.maximum(own_thr - 1, 0) + np.maximum(opp_thr - 1, 0) * defence_weight)
        return own_pot + opp_pot * defence_weight + fork * fork_bonus, q0, r0

    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        for (q, r) in cells:  # 1. take a win
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        for (q, r) in cells:  # 2. block a loss
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)
        score, q0, r0 = static_scores(state.stones, me)
        ranked = sorted(cells, key=lambda c: -score[c[1] - r0, c[0] - q0])
        best, best_s = ranked[0], -1e18
        for (q, r) in ranked[:top_k]:  # 3. depth-2: my move minus their best reply
            nxt = dict(state.stones); nxt[(q, r)] = me
            my_s = score[r - r0, q - q0]
            reply, rq0, rr0 = static_scores(nxt, opp)
            opp_cells = candidates(nxt)
            opp_best = max(reply[rc[1] - rr0, rc[0] - rq0] for rc in opp_cells)
            s = my_s - reply_discount * opp_best
            if s > best_s:
                best_s, best = s, (q, r)
        return best
    return bot


def _global_potential(np, own, opp) -> float:
    """Whole-board ES potential for the player in `own`: sum of 4^own over
    live windows containing at least one own stone (all-empty windows are
    excluded so the value does not depend on the array bounding box)."""
    total = 0.0
    for dq, dr in ((1, 0), (0, 1), (1, -1)):
        own_s, opp_s = own.astype(np.int32), opp.astype(np.int32)
        for i in range(1, WIN_LENGTH):
            own_s = own_s + _shift(np, own, i * dr, i * dq)
            opp_s = opp_s + _shift(np, opp, i * dr, i * dq)
        live = (opp_s == 0) & (own_s > 0)
        total += float(np.where(live, np.power(4.0, own_s), 0.0).sum())
    return total


def make_fast_minimax(defence_weight: float = 1.1, top_k: int = 4,
                      soft_deadline_s: float = 0.7) -> Bot:
    """
    The Phase-2 retry of "spend the spare budget on search", with the defect
    that killed fast_tactical fixed. fast_tactical scored my_move minus the
    opponent's best STATIC REPLY SCORE, which punishes sharp lines (they raise
    the opponent's reply score) and produced passive play -- 16/50 losses to
    greedy_offence and 3x slower conversions in the 2026-07-06 Phase-1 screen.

    This is a true minimax over the game's actual turn structure: max over my
    remaining placements this turn, min over the opponent's two, alpha-beta
    over the top_k candidates per node (ordered by the vectorized static map),
    exact win detection at every node, and a plain ES *position* differential
    at the leaves -- the champion heuristic_d1.1's own value, one full
    turn-exchange deeper.
    """
    import numpy as np

    def board_eval(stones, me: Player) -> float:
        own, opp, _, _ = _board_arrays(np, stones, me)
        return _global_potential(np, own, opp) \
            - defence_weight * _global_potential(np, opp, own)

    def top_candidates(stones, player: Player, k: int) -> list[Cell]:
        own_pot, own_thr, opp_pot, opp_thr, q0, r0 = _eval_maps(np, stones, player)
        score = own_pot + opp_pot * defence_weight
        cells = candidates(stones)
        cells.sort(key=lambda c: -score[c[1] - r0, c[0] - q0])
        return cells[:k]

    BIG = 1e12

    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        for (q, r) in cells:  # exact win/block guarantees at the root
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)

        # mover sequence from this placement to the end of the opponent's turn
        my_remaining = state.stones_per_turn - state.placed_this_turn
        seq = [me] * my_remaining + [opp] * 2
        t0 = time.perf_counter()

        def search(stones, idx: int, alpha: float, beta: float) -> float:
            if idx == len(seq):
                return board_eval(stones, me)
            player = seq[idx]
            best = -BIG if player == me else BIG
            for c in top_candidates(stones, player, top_k):
                nxt = dict(stones); nxt[c] = player
                if check_win(nxt, c[0], c[1], player):
                    val = BIG - idx if player == me else -BIG + idx
                else:
                    val = search(nxt, idx + 1, alpha, beta)
                if player == me:
                    best = max(best, val); alpha = max(alpha, val)
                else:
                    best = min(best, val); beta = min(beta, val)
                if beta <= alpha:
                    break
            return best

        best_cell, best_val = None, -BIG
        for c in top_candidates(state.stones, me, max(top_k, 6)):
            nxt = dict(state.stones); nxt[c] = me
            val = search(nxt, 1, -BIG, BIG)
            if val > best_val:
                best_val, best_cell = val, c
            if time.perf_counter() - t0 > soft_deadline_s:
                break  # keep best-so-far; candidates were tried best-first
        return best_cell if best_cell is not None else cells[0]
    return bot


# --- Eisenstein-residue covering bots (candidate E of the handoff) ------------
#
# Z[omega]/(pi) = F_7 with omega -> 2 (2^2+2+1 = 7). Any 6-window along any
# axis covers 6 of the 7 residue classes (axis steps 1, 2, 6 are all nonzero
# mod 7), so ANY two distinct classes intersect every possible 6-window --
# a density-2/7 covering sublattice, verified in run_pairing_bound.py. The
# covering cannot be upgraded to a pairing strategy (impossibility theorem,
# same experiment), so these bots test the weaker empirical claim: does
# biasing defensive placement onto the covering set help at ~zero cost?

_RES_COVER = (0, 1)  # any two distinct classes work; phase is arbitrary


def _residue(q: int, r: int) -> int:
    return (q + 2 * r) % 7


def make_residue_static() -> Bot:
    """The handoff's cheapest falsifier: win/block exactly like the ladder,
    otherwise pure covering-set placement nearest the opponent's centroid --
    no potential function at all."""
    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)
        theirs = [c for c, p in state.stones.items() if p == opp] or [(0, 0)]
        cq = sum(q for q, _ in theirs) / len(theirs)
        cr = sum(r for _, r in theirs) / len(theirs)
        covered = [c for c in cells if _residue(*c) in _RES_COVER] or cells
        return min(covered, key=lambda c: (c[0] - cq) ** 2 + (c[1] - cr) ** 2
                   + (c[0] - cq) * (c[1] - cr))  # squared Eisenstein norm
    return bot


def make_residue_bias(defence_weight: float = 1.2, fork_bonus: float = 60.0,
                      bias: float = 0.5) -> Bot:
    """fork_aware plus an epsilon tie-break toward the covering sublattice.
    bias is far below any real score gap, so this only reorders near-ties --
    exactly the 'negligible cost' version of candidate E. Scoring is
    make_fork_aware's, inlined to add the bias term."""
    def bot(state: State) -> Cell:
        me = state.turn
        opp = other(me)
        cells = candidates(state.stones)
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = me
            if check_win(nxt, q, r, me):
                return (q, r)
        for (q, r) in cells:
            nxt = dict(state.stones); nxt[(q, r)] = opp
            if check_win(nxt, q, r, opp):
                return (q, r)
        best, best_s = cells[0], -1e18
        for (q, r) in cells:
            off = cell_score(state.stones, q, r, me) \
                + cell_score(state.stones, q, r, opp) * defence_weight
            my_fork = max(0, threat_count(state.stones, q, r, me, min_own=4) - 1)
            opp_fork = max(0, threat_count(state.stones, q, r, opp, min_own=4) - 1)
            s = off + (my_fork + opp_fork * defence_weight) * fork_bonus
            if _residue(q, r) in _RES_COVER:
                s += bias
            if s > best_s:
                best_s, best = s, (q, r)
        return best
    return bot


def selftest() -> None:
    """Exact-match check: vectorized maps vs cell_score/threat_count on random boards."""
    import numpy as np
    rng = [7]
    def lcg(n):
        rng[0] = (rng[0] * 1103515245 + 12345) & 0x7FFFFFFF
        return rng[0] % n
    for trial in range(20):
        stones: dict[Cell, Player] = {}
        for _ in range(5 + lcg(60)):
            stones[(lcg(17) - 8, lcg(17) - 8)] = 1 + lcg(2)
        own_pot, own_thr, opp_pot, opp_thr, q0, r0 = _eval_maps(np, stones, 1)
        for (q, r) in candidates(stones):
            assert abs(own_pot[r - r0, q - q0] - cell_score(stones, q, r, 1)) < 1e-6, (trial, q, r)
            assert abs(opp_pot[r - r0, q - q0] - cell_score(stones, q, r, 2)) < 1e-6, (trial, q, r)
            assert own_thr[r - r0, q - q0] == threat_count(stones, q, r, 1, 4), (trial, q, r)
            assert opp_thr[r - r0, q - q0] == threat_count(stones, q, r, 2, 4), (trial, q, r)
    print("selftest OK: fast maps == cell_score/threat_count on 20 random boards")


# --- arena -------------------------------------------------------------------

def play_game(bot1: Bot, bot2: Bot, budget_s: float = 1.0, max_moves: int = 400,
              opening_seed: Optional[int] = None, opening_placements: int = 6,
              return_stats: bool = False, move_log: Optional[list] = None):
    """Return winner (1 or 2) or 0 for draw/cutoff. Budget overruns forfeit to fallback.

    opening_seed randomizes the first `opening_placements` stones (both sides play
    the seeded random bot), then hands over to the real bots. Deterministic
    strong-vs-strong pairs otherwise replay one canonical game forever -- the
    2026-06-15 arena finding -- so decisive statistics require an opening book,
    and a seeded random prefix is the cheapest unbiased one.

    move_log, if given, receives (cell, player, in_opening) per placement --
    used by the replay renderer and corpus tooling.
    """
    s = State()
    bots = {1: bot1, 2: bot2}
    opener = random_bot(seed=opening_seed) if opening_seed is not None else None
    for _ in range(max_moves):
        if s.winner is not None:
            return (s.winner, len(s.stones)) if return_stats else s.winner
        cells = candidates(s.stones)
        if not cells:
            return (0, len(s.stones)) if return_stats else 0
        in_opening = opener is not None and len(s.stones) < opening_placements
        t0 = time.perf_counter()
        try:
            mv = (opener if in_opening else bots[s.turn])(s)
        except Exception:
            mv = cells[0]
        over = time.perf_counter() - t0 > budget_s
        if over or mv not in cells:
            # over budget or illegal -> forfeit the placement to first candidate
            mv = cells[0]
        if move_log is not None:
            move_log.append((mv, s.turn, in_opening))
        s = place(s, mv[0], mv[1])
    return (0, len(s.stones)) if return_stats else 0


def round_robin(roster: dict[str, Bot], games: int = 2, budget_s: float = 1.0,
                json_out: str = "", opening_seed_base: Optional[int] = None) -> dict:
    names = list(roster)
    wins = {n: 0 for n in names}
    pairings = []
    print(f"\nRound-robin: {len(names)} bots, {games} games/pairing/side, {budget_s}s budget"
          + (f", random openings from seed {opening_seed_base}" if opening_seed_base is not None else "") + "\n")
    print(f"{'matchup':<34} result")
    print("-" * 50)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            aw = bw = dr = 0
            for g in range(games):
                # alternate colours for fairness; colour-swapped pair shares its
                # opening seed so per-opening comparisons are paired
                seed = None if opening_seed_base is None else opening_seed_base + g // 2
                if g % 2 == 0:
                    w = play_game(roster[a], roster[b], budget_s, opening_seed=seed)
                    if w == 1: aw += 1
                    elif w == 2: bw += 1
                    else: dr += 1
                else:
                    w = play_game(roster[b], roster[a], budget_s, opening_seed=seed)
                    if w == 1: bw += 1
                    elif w == 2: aw += 1
                    else: dr += 1
            wins[a] += aw; wins[b] += bw
            pairings.append({"a": a, "b": b, "a_wins": aw, "b_wins": bw, "draws": dr})
            print(f"{a+' vs '+b:<34} {aw}-{bw}" + (f" ({dr}d)" if dr else ""))
    print("\nLeaderboard (total decisive wins):")
    for n, w in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"  {w:>3}  {n}")
    champ = max(wins, key=wins.get)
    print(f"\nChampion: {champ}  ->  port this strategy to src/lib/hexo.ts")
    result = {"games_per_pairing": games, "budget_s": budget_s,
              "wins": wins, "pairings": pairings, "champion": champ}
    if json_out:
        import json
        from pathlib import Path
        Path(json_out).parent.mkdir(parents=True, exist_ok=True)
        Path(json_out).write_text(json.dumps(result, indent=2))
        print(f"[saved] {json_out}")
    return result


def bot_registry() -> dict[str, Bot]:
    """Every named bot the arena and the Modal bake-off can look up.

    Phase-1 (2026-07-06) and Phase-2 entrants live in one registry so
    modal_bakeoff.py's `--bots` can name any of them. The defence-weight ladder
    exists to answer the one untuned knob the champion heuristic_d1.1 has: is
    1.1 the right defence weight, or did Phase-1 just happen to test one value?
    fast_minimax is the Phase-2 retry of "spend the spare budget on search"
    with fast_tactical's passivity defect fixed (see make_fast_minimax)."""
    return {
        # Phase-1 roster
        "random": random_bot(seed=1),
        "greedy_offence": greedy_offence(),
        "heuristic_d1.1": make_heuristic(1.1),       # the garden's current shipped bot
        "fork_aware_d1.2": make_fork_aware(1.2),     # theory-informed (tau pressure)
        "fast_tactical": make_fast_tactical(1.2),    # candidates B+D: vectorized + naive depth-2
        "residue_bias": make_residue_bias(1.2),      # candidate E: covering tie-break
        "residue_static": make_residue_static(),     # candidate E falsifier: no potential
        # Phase-2 entrants
        "heuristic_d1.0": make_heuristic(1.0),       # defence-weight ladder ...
        "heuristic_d1.3": make_heuristic(1.3),
        "heuristic_d1.6": make_heuristic(1.6),
        "heuristic_d2.0": make_heuristic(2.0),
        "fast_minimax_d1.1": make_fast_minimax(1.1),  # true turn-minimax over the vectorized eval
        "fast_minimax_d1.4": make_fast_minimax(1.4),
    }


def default_roster() -> dict[str, Bot]:
    """Phase-1 screen roster (kept as the 7-bot set for reproducibility)."""
    reg = bot_registry()
    return {n: reg[n] for n in ("random", "greedy_offence", "heuristic_d1.1",
                                "fork_aware_d1.2", "fast_tactical",
                                "residue_bias", "residue_static")}


def main() -> None:
    ap = argparse.ArgumentParser(description="HeXO bot competition arena")
    ap.add_argument("--quick", action="store_true", help="fast smoke run")
    ap.add_argument("--budget", type=float, default=1.0, help="per-move seconds")
    ap.add_argument("--json", default="", help="write results JSON here")
    ap.add_argument("--openings", type=int, default=None,
                    help="randomize openings from this seed base (decisive stats)")
    ap.add_argument("--games", type=int, default=None, help="games per pairing")
    ap.add_argument("--selftest", action="store_true",
                    help="verify fast maps match cell_score/threat_count, then exit")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return
    games = args.games or (2 if args.quick else 6)
    budget = 0.25 if args.quick else args.budget
    round_robin(default_roster(), games=games, budget_s=budget, json_out=args.json,
                opening_seed_base=args.openings)


if __name__ == "__main__":
    main()
