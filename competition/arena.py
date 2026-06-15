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


# --- arena -------------------------------------------------------------------

def play_game(bot1: Bot, bot2: Bot, budget_s: float = 1.0, max_moves: int = 400) -> int:
    """Return winner (1 or 2) or 0 for draw/cutoff. Budget overruns forfeit to fallback."""
    s = State()
    bots = {1: bot1, 2: bot2}
    for _ in range(max_moves):
        if s.winner is not None:
            return s.winner
        cells = candidates(s.stones)
        if not cells:
            return 0
        t0 = time.perf_counter()
        try:
            mv = bots[s.turn](s)
        except Exception:
            mv = cells[0]
        if time.perf_counter() - t0 > budget_s or mv not in cells and mv not in s.stones:
            # over budget or illegal -> fallback to first candidate
            mv = mv if (mv in cells) else cells[0]
        s = place(s, mv[0], mv[1])
    return 0


def round_robin(roster: dict[str, Bot], games: int = 2, budget_s: float = 1.0) -> None:
    names = list(roster)
    wins = {n: 0 for n in names}
    print(f"\nRound-robin: {len(names)} bots, {games} games/pairing/side, {budget_s}s budget\n")
    print(f"{'matchup':<28} result")
    print("-" * 44)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            aw = bw = dr = 0
            for g in range(games):
                # alternate colours for fairness
                if g % 2 == 0:
                    w = play_game(roster[a], roster[b], budget_s)
                    if w == 1: aw += 1
                    elif w == 2: bw += 1
                    else: dr += 1
                else:
                    w = play_game(roster[b], roster[a], budget_s)
                    if w == 1: bw += 1
                    elif w == 2: aw += 1
                    else: dr += 1
            wins[a] += aw; wins[b] += bw
            print(f"{a+' vs '+b:<28} {aw}-{bw}" + (f" ({dr}d)" if dr else ""))
    print("\nLeaderboard (total decisive wins):")
    for n, w in sorted(wins.items(), key=lambda kv: -kv[1]):
        print(f"  {w:>3}  {n}")
    champ = max(wins, key=wins.get)
    print(f"\nChampion: {champ}  ->  port this strategy to src/lib/hexo.ts")


def main() -> None:
    ap = argparse.ArgumentParser(description="HeXO bot competition arena")
    ap.add_argument("--quick", action="store_true", help="fast smoke run")
    ap.add_argument("--budget", type=float, default=1.0, help="per-move seconds")
    args = ap.parse_args()

    roster: dict[str, Bot] = {
        "random": random_bot(seed=1),
        "greedy_offence": greedy_offence(),
        "heuristic_d1.1": make_heuristic(1.1),       # the garden's current shipped bot
        "fork_aware_d1.1": make_fork_aware(1.1),     # theory-informed (tau pressure)
        "fork_aware_d1.5": make_fork_aware(1.5),
    }
    games = 2 if args.quick else 6
    budget = 0.25 if args.quick else args.budget
    round_robin(roster, games=games, budget_s=budget)


if __name__ == "__main__":
    main()
