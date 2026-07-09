"""
Standalone HeXO tournament bot v2 -- pure Python, stdlib only, no repo
dependency. Drop-in replacement for hexo_bot.py (same choose_move signature).

RULE ASSUMPTIONS (verify against the opponent's engine before a real match):
  - Infinite hex board, axial (q, r) integer coordinates, unbounded.
  - Win lines along exactly 3 axes: (1,0), (0,1), (1,-1).
  - Win = 6 in an unbroken row along one axis.
  - Turn rule 1-2-2: P1 places 1 stone on the game's first move; every turn
    thereafter (both players) places exactly 2 stones.
  - No captures; any unoccupied cell is legal.

DESIGN (2026-07-09 fresh-start rebuild -- see
competition/2026-07-08-fresh-start-bot-brief.md for the empirical facts this
is built on):

  The defender answers with at most 2 stones per turn, so all exact tactics
  reduce to hitting-set arithmetic over "brink" windows (live 6-windows with
  >= 4 of the attacker's stones, i.e. completable within one turn):
    - mover with any brink window -> unconditional win this turn;
    - mover facing opponent brink windows whose empties admit no hitting set
      of <= remaining stones -> proven loss, regardless of anything else.
  Both checks run at EVERY search node (the 24-0 pathology in the brief came
  from a search that could silently prune forced continuations).

  On top of the exact layer:
  1. THREAT-SPACE SEARCH (the new lever, absent from both hexo_bot.py and
     SealBot): attacker moves restricted to brink-creating pairs, defender
     restricted to exact covering replies (enumerated from the hitting-set
     structure, plus a bounded "free stone" set when one cell covers all).
     Finds forced wins several turns out -- e.g. two open-3s doubled into
     two open-4s in one turn is threat-cost 4 > 2 = proven win, invisible
     to a beam search until the brinks already exist.
  2. Joint-pair iterative-deepening alpha-beta over full 2-stone turns,
     with threat-only quiescence at the leaves (never statically evaluates
     a position where either side holds a brink).
  3. Incremental window-count board (18 windows per stone, make/unmake with
     an undo stack, no dict copies) -- node cost ~100x below a global
     re-evaluation, which is where the search depth actually comes from.

  Threat/blocking cells are enumerated directly from window empties, never
  from a radius-limited candidate ring: a cell completing a live-3 can sit
  3 steps from the nearest stone, outside any ring-1 neighbourhood.

Usage:
    from hexo_bot2 import choose_move
    q, r = choose_move(stones, turn, placed_this_turn, stones_per_turn)

choose_move computes the full 2-stone turn on the first call and caches the
second stone (keyed on the expected intermediate board), so a turn costs one
time budget, not two. A cache miss just recomputes a 1-stone decision.
"""
from __future__ import annotations

import time
from itertools import combinations
from typing import Optional

Cell = tuple[int, int]

WIN_LENGTH = 6
AXES = ((1, 0), (0, 1), (1, -1))
RING = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))
# candidate offsets: ring-1 plus 2 steps along each axis (still only a
# positional-search narrowing; exact tactics never depend on this set)
CAND_OFFS = RING + tuple((2 * dq, 2 * dr) for dq, dr in RING)

# live-window value by own-stone count (index = stones in window, up to 6 =
# completed); V[4]/V[5] are backstops -- quiescence resolves loud leaves, so
# these mostly matter when qdepth runs out
V = (0.0, 1.0, 7.0, 55.0, 4000.0, 200000.0, 10000000.0)
DEF_W = 1.1
WIN_SCORE = 1e12

# integer twin of V for the incrementally-maintained per-cell move deltas
# (units of 0.1 so DEF_W=1.1 stays integral) -- integers make place/unplace
# delta updates exactly reversible, no float drift across make/unmake
_IV = tuple(int(v) for v in V)


def _gain(nq: int, nother: int) -> int:
    """0.1-units gain for player q placing one more stone into a live window
    currently holding (nq, nother): own growth if live, kill value if the
    window is the opponent's, 0 if mixed or full."""
    if nq + nother >= WIN_LENGTH:
        return 0
    if nother == 0:
        return 10 * (_IV[nq + 1] - _IV[nq])
    if nq == 0:
        return 11 * _IV[nother]
    return 0

TIME_BUDGET_S = 0.70
TSS_FRACTION = 0.20      # slice of the budget given to threat-space search
TSS_MAX_DEPTH = 4        # in turns
Q_DEPTH = 4              # quiescence extension, in turns
TOP_CELLS = 10           # positional candidates per node


def other(p: int) -> int:
    return 2 if p == 1 else 1


class TimeUp(Exception):
    pass


class Board:
    """Incremental window-count board. wc[(axis, sq, sr)] = [n1, n2];
    hot[p] = brink windows (live, >= 4 own), warm[p] = live with >= 2 own."""

    def __init__(self, stones: dict[Cell, int]):
        self.stones: dict[Cell, int] = {}
        self.wc: dict[tuple, list[int]] = {}
        self.hot = ({}, {})      # wkey -> True (dict as ordered set)
        self.warm = ({}, {})
        self.score = [0.0, 0.0]
        # per-player incrementally-maintained move deltas (0.1-units, int):
        # delta[pi][cell] = sum of _gain over that cell's existing windows.
        # Maintained for every cell of every touched window (occupied cells
        # included, so entries are never stale when a cell re-empties).
        self.delta: tuple[dict, dict] = ({}, {})
        self.wcells: dict[tuple, tuple[Cell, ...]] = {}  # wkey -> its 6 cells
        self.cand: dict[Cell, bool] = {}
        self.winner = 0
        self._undo: list = []
        for c, p in stones.items():
            self.place(c, p)
        self._undo.clear()

    def place(self, cell: Cell, p: int) -> None:
        q, r = cell
        pi = p - 1
        oi = 1 - pi
        wc = self.wc
        hot_p, warm_p = self.hot[pi], self.warm[pi]
        hot_o, warm_o = self.hot[oi], self.warm[oi]
        score = self.score
        d_p, d_o = self.delta[pi], self.delta[oi]
        rec_sets = []            # (which, wkey) reversals for set membership
        for d in range(3):
            dq, dr = AXES[d]
            for j in range(WIN_LENGTH):
                sq, sr = q - j * dq, r - j * dr
                wkey = (d, sq, sr)
                cnt = wc.get(wkey)
                if cnt is None:
                    cnt = wc[wkey] = [0, 0]
                    self.wcells[wkey] = tuple(
                        (sq + i * dq, sr + i * dr) for i in range(WIN_LENGTH))
                nm, no = cnt[pi], cnt[oi]
                if no == 0:
                    score[pi] += V[nm + 1] - V[nm]
                    if nm + 1 == 2:
                        warm_p[wkey] = True
                    elif nm + 1 == 4:
                        hot_p[wkey] = True
                    if nm + 1 >= WIN_LENGTH:
                        self.winner = p
                elif nm == 0:
                    # window just died for the opponent
                    score[oi] -= V[no]
                    if wkey in warm_o:
                        del warm_o[wkey]
                        rec_sets.append((2 + oi, wkey))
                    if wkey in hot_o:
                        del hot_o[wkey]
                        rec_sets.append((4 + oi, wkey))
                cnt[pi] = nm + 1
                dg_p = _gain(nm + 1, no) - _gain(nm, no)
                dg_o = _gain(no, nm + 1) - _gain(no, nm)
                if dg_p or dg_o:
                    for c2 in self.wcells[wkey]:
                        if dg_p:
                            d_p[c2] = d_p.get(c2, 0) + dg_p
                        if dg_o:
                            d_o[c2] = d_o.get(c2, 0) + dg_o
        self.stones[cell] = p
        was_cand = cell in self.cand
        if was_cand:
            del self.cand[cell]
        added = []
        for dq, dr in CAND_OFFS:
            c2 = (q + dq, r + dr)
            if c2 not in self.stones and c2 not in self.cand:
                self.cand[c2] = True
                added.append(c2)
        self._undo.append((cell, p, was_cand, added, rec_sets, self.winner))

    def unplace(self) -> None:
        cell, p, was_cand, added, rec_sets, _ = self._undo.pop()
        q, r = cell
        pi = p - 1
        oi = 1 - pi
        wc = self.wc
        hot_p, warm_p = self.hot[pi], self.warm[pi]
        score = self.score
        d_p, d_o = self.delta[pi], self.delta[oi]
        del self.stones[cell]
        for c2 in added:
            del self.cand[c2]
        if was_cand:
            self.cand[cell] = True
        for d in range(3):
            dq, dr = AXES[d]
            for j in range(WIN_LENGTH):
                sq, sr = q - j * dq, r - j * dr
                wkey = (d, sq, sr)
                cnt = wc[wkey]
                nm = cnt[pi] - 1
                no = cnt[oi]
                cnt[pi] = nm
                if no == 0:
                    score[pi] -= V[nm + 1] - V[nm]
                    if nm + 1 == 2 and wkey in warm_p:
                        del warm_p[wkey]
                    elif nm + 1 == 4 and wkey in hot_p:
                        del hot_p[wkey]
                elif nm == 0:
                    score[oi] += V[no]
                dg_p = _gain(nm, no) - _gain(nm + 1, no)
                dg_o = _gain(no, nm) - _gain(no, nm + 1)
                if dg_p or dg_o:
                    for c2 in self.wcells[wkey]:
                        if dg_p:
                            d_p[c2] = d_p.get(c2, 0) + dg_p
                        if dg_o:
                            d_o[c2] = d_o.get(c2, 0) + dg_o
        for which, wkey in rec_sets:
            if which >= 4:
                self.hot[which - 4][wkey] = True
            else:
                self.warm[which - 2][wkey] = True
        self.winner = 0
        # re-derive winner only if undo stack says a previous placement won
        if self._undo:
            self.winner = self._undo[-1][5]

    def eval_for(self, p: int) -> float:
        pi = p - 1
        return self.score[pi] - DEF_W * self.score[1 - pi]

    def window_empties(self, wkey: tuple) -> tuple[Cell, ...]:
        d, sq, sr = wkey
        dq, dr = AXES[d]
        stones = self.stones
        return tuple((sq + j * dq, sr + j * dr) for j in range(WIN_LENGTH)
                     if (sq + j * dq, sr + j * dr) not in stones)

    def brink_empties(self, p: int) -> list[tuple[Cell, ...]]:
        """Empty-cell sets of p's brink windows (each has <= 2 empties)."""
        return [self.window_empties(w) for w in self.hot[p - 1]]

    def instant_win_cells(self, p: int, remaining: int) -> Optional[tuple[Cell, ...]]:
        """Cells completing some live window within `remaining` placements."""
        pi = p - 1
        wc = self.wc
        for wkey in self.hot[pi]:
            if wc[wkey][pi] >= WIN_LENGTH - remaining:
                e = self.window_empties(wkey)
                if len(e) <= remaining:
                    return e
        return None

    def move_delta(self, cell: Cell, p: int) -> int:
        """Reference (slow) recomputation of delta[p-1][cell]: static gain of
        placing p at cell over the cell's EXISTING windows, in the same
        0.1-units as the incremental dicts. Kept only to cross-check the
        incremental maintenance in the selftest."""
        q, r = cell
        pi = p - 1
        oi = 1 - pi
        wc = self.wc
        gain = 0
        base = _gain(0, 0)
        for d in range(3):
            dq, dr = AXES[d]
            for j in range(WIN_LENGTH):
                cnt = wc.get((d, q - j * dq, r - j * dr))
                if cnt is None:
                    continue
                # the incremental dicts telescope from each window's (0,0)
                # creation state, i.e. they measure gain RELATIVE to an empty
                # window (dead windows contribute negatively -- fresh space
                # outranks dead zones); mirror that here
                gain += _gain(cnt[pi], cnt[oi]) - base
        return gain


# --- exact hitting-set layer --------------------------------------------------

def covering_placements(win_emps: list[tuple[Cell, ...]], max_stones: int
                        ) -> list[tuple[Cell, ...]]:
    """All minimal placements (size <= max_stones) hitting every window's
    empty set. Empty list == unstoppable (proven loss for the defender).
    Exact: each window's empty set has <= 2 cells, so a 2-cover's second
    cell must lie in the intersection of the windows the first cell misses."""
    if not win_emps:
        return [()]
    sets = [frozenset(w) for w in win_emps]
    universe = []
    seen = set()
    for w in win_emps:
        for c in w:
            if c not in seen:
                seen.add(c)
                universe.append(c)
    singles = [c for c in universe if all(c in s for s in sets)]
    out: list[tuple[Cell, ...]] = [(c,) for c in singles]
    if max_stones >= 2:
        got = set()
        for c1 in universe:
            rest = [s for s in sets if c1 not in s]
            if not rest:
                continue
            inter = frozenset.intersection(*rest)
            for c2 in inter:
                if c2 != c1:
                    key = (c1, c2) if c1 <= c2 else (c2, c1)
                    if key not in got:
                        got.add(key)
                        out.append(key)
    return out


# --- search -------------------------------------------------------------------

class Searcher:
    def __init__(self, board: Board, me: int, deadline: float):
        self.b = board
        self.me = me
        self.deadline = deadline
        self.nodes = 0

    def _tick(self) -> None:
        self.nodes += 1
        if self.nodes % 16 == 0 and time.perf_counter() > self.deadline:
            raise TimeUp()

    def make_turn(self, cells: tuple[Cell, ...], p: int) -> int:
        n = 0
        for c in cells:
            self.b.place(c, p)
            n += 1
            if self.b.winner:
                break
        return n

    def undo_turn(self, n: int) -> None:
        for _ in range(n):
            self.b.unplace()

    def top_cells(self, p: int, k: int) -> list[Cell]:
        b = self.b
        d = b.delta[p - 1]
        scored = sorted(b.cand, key=lambda c: -d.get(c, 0))
        return scored[:k]

    def gen_turns(self, p: int, remaining: int) -> list[tuple[Cell, ...]]:
        """Legal-and-not-immediately-losing turns: if the opponent holds
        brink windows they MUST be covered (exact); otherwise pairs from the
        top positional candidates plus own threat pairs."""
        b = self.b
        win = b.instant_win_cells(p, remaining)
        if win is not None:
            return [win]
        opp_brinks = b.brink_empties(other(p))
        if opp_brinks:
            covers = covering_placements(opp_brinks, remaining)
            if not covers:
                return []          # proven loss; caller scores it
            turns = []
            tops = self.top_cells(p, 6)
            for cv in covers:
                if len(cv) == remaining:
                    turns.append(cv)
                else:              # one cover cell + one free stone
                    for t in tops:
                        if t != cv[0]:
                            turns.append((cv[0], t))
            return turns[:24]
        if remaining == 1:
            return [(c,) for c in self.top_cells(p, TOP_CELLS)]
        tops = self.top_cells(p, TOP_CELLS)
        turns = []
        n = len(tops)
        for i in range(min(4, n)):
            for j in range(i + 1, n):
                turns.append((tops[i], tops[j]))
        return turns

    # --- threat-space search ---

    def threat_pairs(self, p: int) -> list[tuple[tuple[Cell, ...], int]]:
        """Pairs creating >= 1 brink, ranked by resulting defender cost
        (number of stones the opponent must spend; > 2 = proven win).
        Enumerated from warm-window empties directly."""
        b = self.b
        pi = p - 1
        wc = b.wc
        # cells that alone raise a live-3 window to a brink
        cells3: dict[Cell, bool] = {}
        # (window, empties) for live-2 windows: any 2 of its empties -> brink
        two_windows = []
        for wkey in b.warm[pi]:
            n = wc[wkey][pi]
            if n >= 3:
                for c in b.window_empties(wkey):
                    cells3[c] = True
            elif n == 2:
                two_windows.append(b.window_empties(wkey))
        cand_pairs: dict[tuple, bool] = {}
        dd = b.delta[pi]
        c3 = list(cells3)
        c3.sort(key=lambda c: -dd.get(c, 0))
        c3 = c3[:12]
        for i in range(len(c3)):
            for j in range(i + 1, len(c3)):
                cand_pairs[(c3[i], c3[j])] = True
        for emp in two_windows[:20]:
            for a, c in combinations(emp, 2):
                cand_pairs[(a, c)] = True
        # threat + build: one stone makes a brink, the other grows a live-2
        # window -- feeds the NEXT turn of a forcing sequence
        for c in c3[:4]:
            for emp in two_windows[:4]:
                for e in emp[:2]:
                    if e != c:
                        cand_pairs[(c, e)] = True
        # score each pair by exact resulting defender cost
        out = []
        opp = other(p)
        for pair in list(cand_pairs)[:40]:
            self._tick()
            n = self.make_turn(pair, p)
            if self.b.winner == p:
                self.undo_turn(n)
                return [(pair, 99)]
            my_brinks = b.brink_empties(p)
            if not my_brinks or b.hot[opp - 1]:
                # not forcing, or lets the opponent win first
                cost = -1
            else:
                covers = covering_placements(my_brinks, 2)
                cost = 3 if not covers else (1 if len(covers[0]) == 1 else 2)
                # covers is mixed sizes; recompute properly
                if covers and any(len(c) == 1 for c in covers):
                    cost = 1
                elif covers:
                    cost = 2
            self.undo_turn(n)
            if cost >= 1:
                out.append((pair, cost))
        out.sort(key=lambda pc: -pc[1])
        return out[:16]

    def tss(self, p: int, depth: int) -> Optional[tuple[Cell, ...]]:
        """Forced-win turn for p (to move, 2 stones) via continuous DOUBLE
        threats, or None. STRICTLY SOUND: a line only counts as forcing if
        every defender reply must spend both stones covering (any 1-cell
        cover means a free stone exists -- line treated as refuted), and the
        full cover set is enumerated, never truncated. The 2026-07-09 v2
        bake-off measured the earlier bounded-optimism defender model
        (free-stone replies from a top-k set) as ACTIVELY harmful: 2-22
        head-to-head against the no-TSS ablation arm -- phantom 'forced
        wins' committed stones to fizzling attacks. A sound detector can
        only find real wins, so its only cost is its time slice."""
        self._tick()
        b = self.b
        win = b.instant_win_cells(p, 2)
        if win is not None:
            return win if len(win) == 2 else (win[0], self._companion(p, win[0]))
        if depth == 0:
            return None
        opp = other(p)
        opp_brinks = b.brink_empties(opp)
        for pair, cost in self.threat_pairs(p):
            if cost < 2 and cost != 99:
                continue           # defender keeps a free stone: not forcing
            if opp_brinks and not all(
                    any(c in w for c in pair) for w in opp_brinks):
                continue           # must cover while threatening
            n = self.make_turn(pair, p)
            if b.winner == p:
                self.undo_turn(n)
                return pair
            my_brinks = b.brink_empties(p)
            covers = covering_placements(my_brinks, 2)
            if not covers and not b.hot[opp - 1]:
                self.undo_turn(n)
                return pair        # cost > 2: proven unstoppable
            refuted = False
            for cv in covers:
                if len(cv) < 2:
                    refuted = True  # 1-cell cover -> defender has a free stone
                    break
                m = self.make_turn(cv, opp)
                if b.winner == opp:
                    self.undo_turn(m)
                    refuted = True
                    break
                ok = self.tss(p, depth - 1)
                self.undo_turn(m)
                if ok is None:
                    refuted = True
                    break
            self.undo_turn(n)
            if not refuted and covers:
                return pair
        return None

    def _companion(self, p: int, first: Cell) -> Cell:
        for c in self.top_cells(p, 4):
            if c != first:
                return c
        for c in self.b.cand:
            if c != first:
                return c
        return (first[0] + 1, first[1])

    # --- main alpha-beta over joint turns ---

    def quiesce(self, p: int, alpha: float, beta: float, qdepth: int,
                ply: int) -> float:
        """Brink-resolution quiescence: never statically evaluates while
        either side holds a brink window. Deliberately does NOT extend on
        mere threat-creation potential -- that costs too many nodes in
        Python and is TSS's job at the root; depth-2 alpha-beta plus this
        already scores one-turn double-threat swings exactly."""
        self._tick()
        b = self.b
        me = self.me
        win = b.instant_win_cells(p, 2)
        if win is not None:
            return WIN_SCORE - ply if p == me else -WIN_SCORE + ply
        opp = other(p)
        opp_brinks = b.brink_empties(opp)
        stand = b.eval_for(me)
        if not opp_brinks or qdepth <= 0:
            return stand
        maximizing = p == me
        covers = covering_placements(opp_brinks, 2)
        if not covers:
            return -WIN_SCORE + ply if maximizing else WIN_SCORE - ply
        turns = []
        for cv in covers[:8]:
            if len(cv) == 2:
                turns.append(cv)
            else:
                for t in self.top_cells(p, 3):
                    if t != cv[0]:
                        turns.append((cv[0], t))
        turns = turns[:10]
        best = -WIN_SCORE if maximizing else WIN_SCORE
        for t in turns:
            n = self.make_turn(t, p)
            if b.winner == p:
                val = WIN_SCORE - ply if maximizing else -WIN_SCORE + ply
            else:
                val = self.quiesce(opp, alpha, beta, qdepth - 1, ply + 1)
            self.undo_turn(n)
            if maximizing:
                if val > best:
                    best = val
                alpha = max(alpha, val)
            else:
                if val < best:
                    best = val
                beta = min(beta, val)
            if beta <= alpha:
                break
        return best

    def ab(self, p: int, depth: int, alpha: float, beta: float,
           ply: int) -> float:
        self._tick()
        b = self.b
        me = self.me
        if depth == 0:
            return self.quiesce(p, alpha, beta, Q_DEPTH, ply)
        turns = self.gen_turns(p, 2)
        if not turns:
            return -WIN_SCORE + ply if p == me else WIN_SCORE - ply
        maximizing = p == me
        opp = other(p)
        best = -WIN_SCORE if maximizing else WIN_SCORE
        for t in turns:
            n = self.make_turn(t, p)
            if b.winner == p:
                val = WIN_SCORE - ply if maximizing else -WIN_SCORE + ply
            else:
                val = self.ab(opp, depth - 1, alpha, beta, ply + 1)
            self.undo_turn(n)
            if maximizing:
                if val > best:
                    best = val
                alpha = max(alpha, val)
            else:
                if val < best:
                    best = val
                beta = min(beta, val)
            if beta <= alpha:
                break
        return best


# --- top-level orchestration ----------------------------------------------

_pending: dict = {}


def _board_key(stones: dict[Cell, int], turn: int):
    return (frozenset(stones.items()), turn)


def _choose_turn(stones: dict[Cell, int], me: int, remaining: int,
                 budget_s: float, use_tss: bool = True) -> tuple[Cell, ...]:
    t0 = time.perf_counter()
    board = Board(stones)
    if not stones:
        return ((0, 0),)

    s = Searcher(board, me, t0 + budget_s)
    # 1. exact: win now
    win = board.instant_win_cells(me, remaining)
    if win is not None:
        if len(win) < remaining:
            return (win[0], s._companion(me, win[0]))
        return win[:remaining]

    # 2. threat-space search (only with 2 stones to play and enough material)
    if use_tss and remaining == 2 and len(stones) >= 4:
        s.deadline = t0 + budget_s * TSS_FRACTION
        try:
            for d in range(1, TSS_MAX_DEPTH + 1):
                t = s.tss(me, d)
                if t is not None and len(t) == 2:
                    return t
                if time.perf_counter() > s.deadline:
                    break
        except TimeUp:
            pass

    # NOTE: a root-level DEFENSIVE threat-space check (restrict the root to
    # turns verified to defuse an opponent forced-threat win) was built and
    # measured on 2026-07-09: it took the incumbent matchup from 12-12 to
    # 6-18. Removed -- depth-2 alpha-beta plus the exact cover layer already
    # prices one-turn double-threat swings exactly, and the check's false
    # alarms narrowed the root to passive moves. Don't re-add without a
    # fresh ablation.

    # 3. iterative-deepening alpha-beta over joint turns
    s.deadline = t0 + budget_s
    root_turns = s.gen_turns(me, remaining)
    if not root_turns:
        # proven loss: maximum resistance = cover as much as possible
        opp_brinks = board.brink_empties(other(me))
        cells = [c for w in opp_brinks for c in w]
        seen: list[Cell] = []
        for c in cells:
            if c not in seen:
                seen.append(c)
        if seen:
            out = tuple(seen[:remaining])
            if len(out) == remaining:
                return out
            return (out[0], s._companion(me, out[0]))[:remaining]
        return tuple(s.top_cells(me, remaining))
    best_turn = root_turns[0]
    depth = 1
    while True:
        try:
            cur_best, cur_val = None, -WIN_SCORE * 2
            alpha, beta = -WIN_SCORE * 2, WIN_SCORE * 2
            for t in root_turns:
                n = s.make_turn(t, me)
                if board.winner == me:
                    val = WIN_SCORE
                else:
                    val = s.ab(other(me), depth - 1, alpha, beta, 1)
                s.undo_turn(n)
                if val > cur_val:
                    cur_val, cur_best = val, t
                alpha = max(alpha, val)
            if cur_best is not None:
                best_turn = cur_best
                # re-order root: best first for the next iteration
                root_turns.sort(key=lambda t: t != best_turn)
        except TimeUp:
            break
        if time.perf_counter() > s.deadline or depth >= 6:
            break
        depth += 1
    return best_turn


def choose_move(stones: dict[Cell, int], turn: int, placed_this_turn: int = 0,
                stones_per_turn: int = 2,
                time_budget_s: float = TIME_BUDGET_S,
                use_tss: bool = True) -> Cell:
    """Return the (q, r) cell for `turn`'s next placement. Pure function of
    the board; internally caches the second stone of a planned pair."""
    me = turn
    remaining = stones_per_turn - placed_this_turn
    key = _board_key(stones, turn)
    if key in _pending:
        c = _pending.pop(key)
        if c not in stones:
            return c
    try:
        cells = _choose_turn(stones, me, remaining, time_budget_s, use_tss)
    except Exception:
        cells = ()
    if not cells:
        # never crash: greedy legal fallback
        b = Board(stones)
        if b.cand:
            d = b.delta[me - 1]
            cells = (max(b.cand, key=lambda c: d.get(c, 0)),)
        else:
            cells = ((0, 0),)
    first = cells[0]
    if len(cells) > 1 and remaining > 1:
        nxt = dict(stones)
        nxt[first] = me
        _pending.clear()
        _pending[_board_key(nxt, turn)] = cells[1]
    return first


if __name__ == "__main__":
    t_start = time.perf_counter()

    # opening
    assert choose_move({}, 1, 0, 1) == (0, 0)

    # 1-move win (5 in a row)
    w5 = {(i, 0): 1 for i in range(5)}
    mv = choose_move(w5, 1, 0, 2)
    assert mv in ((5, 0), (-1, 0)), mv

    # 2-move brink win: 4 in a row, both placements must complete ONE window
    _pending.clear()
    b4 = {(i, 0): 1 for i in range(4)}
    m1 = choose_move(b4, 1, 0, 2)
    b4b = dict(b4); b4b[m1] = 1
    m2 = choose_move(b4b, 1, 1, 2)
    b4b[m2] = 1
    bb = Board(b4b)
    assert bb.winner == 1, (m1, m2)

    # must-block: opponent has open-4; our pair must cover the hitting set
    _pending.clear()
    blk = {(i, 0): 2 for i in range(1, 5)}
    blk.update({(20, 20): 1, (21, 20): 1, (20, 21): 1})
    m1 = choose_move(blk, 1, 0, 2, time_budget_s=0.5)
    blk2 = dict(blk); blk2[m1] = 1
    m2 = choose_move(blk2, 1, 1, 2, time_budget_s=0.5)
    blk2[m2] = 1
    bb = Board(blk2)
    assert not covering_placements(bb.brink_empties(2), 2) or bb.brink_empties(2) == [] or \
        all(any(c in w for c in (m1, m2)) for w in bb.brink_empties(2)), (m1, m2)
    assert bb.brink_empties(2) == [] or covering_placements(bb.brink_empties(2), 2), \
        f"left opponent unstoppable: {m1}, {m2}"

    # proven loss detection: opponent holds 3 separate brinks
    _pending.clear()
    loss = {}
    for base in ((0, 0), (30, 0), (0, 30)):
        for i in range(4):
            loss[(base[0] + i, base[1])] = 2
    lb = Board(loss)
    assert not covering_placements(lb.brink_empties(2), 2), "should be unstoppable"

    # TSS depth-1: two open-3s -> double open-4 in one turn = proven win
    _pending.clear()
    tssp = {(1, 0): 1, (2, 0): 1, (3, 0): 1,
            (10, 10): 1, (10, 11): 1, (10, 12): 1,
            (50, 50): 2, (52, 55): 2, (55, 52): 2, (60, 60): 2, (58, 63): 2, (63, 58): 2}
    bd = Board(tssp)
    sr = Searcher(bd, 1, time.perf_counter() + 5.0)
    t = sr.tss(1, 2)
    assert t is not None, "TSS missed the double-open-4 win"
    n = sr.make_turn(t, 1)
    briks = bd.brink_empties(1)
    assert not covering_placements(briks, 2), f"TSS 'win' {t} is coverable"
    sr.undo_turn(n)

    # defensive TSS: opponent (P2) has two open-3s; our turn must defuse the
    # coming double-open-4 (verified by P2's TSS finding nothing afterwards)
    _pending.clear()
    dfs = {(1, 0): 2, (2, 0): 2, (3, 0): 2,
           (10, 10): 2, (10, 11): 2, (10, 12): 2,
           (-20, 0): 1, (-20, 3): 1, (-23, 0): 1, (-23, 3): 1, (-26, 6): 1}
    m1 = choose_move(dfs, 1, 0, 2, time_budget_s=1.5)
    dfs2 = dict(dfs); dfs2[m1] = 1
    m2 = choose_move(dfs2, 1, 1, 2, time_budget_s=1.5)
    dfs2[m2] = 1
    bdf = Board(dfs2)
    sdf = Searcher(bdf, 2, time.perf_counter() + 5.0)
    assert sdf.tss(2, 2) is None, \
        f"defense failed: P2 still has a forced threat win after {m1}, {m2}"

    # board make/unmake integrity, incl. exact delta-dict restoration
    bd2 = Board({(0, 0): 1, (1, 0): 2})
    snap = (dict(bd2.stones), dict(bd2.cand), list(bd2.score),
            {k: list(v) for k, v in bd2.wc.items()},
            dict(bd2.delta[0]), dict(bd2.delta[1]))
    sr2 = Searcher(bd2, 1, time.perf_counter() + 5.0)
    n = sr2.make_turn(((3, 3), (4, 3)), 1)
    n2 = sr2.make_turn(((5, 5), (2, 2)), 2)
    sr2.undo_turn(n2); sr2.undo_turn(n)
    assert bd2.stones == snap[0] and bd2.cand == snap[1]
    assert bd2.score == snap[2]
    assert all(bd2.wc.get(k, [0, 0]) == v or v == [0, 0] for k, v in snap[3].items())
    for pi in (0, 1):
        for c, dv in bd2.delta[pi].items():
            assert dv == snap[4 + pi].get(c, 0), (pi, c, dv)

    # incremental deltas match the reference recomputation on a random board
    import random as _rand
    _rng = _rand.Random(3)
    rpos: dict[Cell, int] = {}
    rp = 1
    for _ in range(30):
        while True:
            rc = (_rng.randint(-7, 7), _rng.randint(-7, 7))
            if rc not in rpos:
                break
        rpos[rc] = rp
        rp = other(rp)
    rbd = Board(rpos)
    for rc in list(rbd.cand)[:40]:
        for pp in (1, 2):
            assert rbd.delta[pp - 1].get(rc, 0) == rbd.move_delta(rc, pp), \
                (rc, pp, rbd.delta[pp - 1].get(rc, 0), rbd.move_delta(rc, pp))

    # timing sanity on a mid-game position
    _pending.clear()
    import random
    rng = random.Random(7)
    pos: dict[Cell, int] = {}
    p = 1
    for _ in range(20):
        while True:
            c = (rng.randint(-6, 6), rng.randint(-6, 6))
            if c not in pos:
                break
        pos[c] = p
        p = other(p)
    t1 = time.perf_counter()
    mv = choose_move(pos, 1, 0, 2, time_budget_s=0.7)
    dt = time.perf_counter() - t1
    assert mv not in pos
    assert dt < 1.0, f"overran budget: {dt:.2f}s"
    print(f"selftest OK ({time.perf_counter() - t_start:.1f}s total, "
          f"midgame move {mv} in {dt:.2f}s)")
