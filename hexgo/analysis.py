"""
Board analysis functions for HexGame states.

All pure functions — no side effects, no UI deps.

  live_lines(game)           → [(cells, axis_idx), ...]
  threat_cells(game, p)      → {cell: count}
  fork_cells(game, p)        → {cell: axes_hit}
  potential_map(game)        → {cell: float}
  axis_chain_lengths(game,p) → {cell: [cq, cr, cd]}
  pair_correlation(moves)    → {r: g(r)}
  live_ap_count(game)        → (p1_live, p2_live)
  pattern_fingerprint(game)  → {cell: str}
"""
from __future__ import annotations
import math
from collections import defaultdict
from hexgo.game import HexGame, AXES, WIN_LENGTH


def _windows(game: HexGame):
    """Yield (cells, axis_idx) for every WIN_LENGTH window touching a stone."""
    seen: set = set()
    for (sq, sr) in game.board:
        for ai, (dq, dr) in enumerate(AXES):
            for off in range(WIN_LENGTH):
                key = (ai, sq - off*dq, sr - off*dr)
                if key in seen: continue
                seen.add(key)
                oq, or_ = key[1], key[2]
                yield [(oq+i*dq, or_+i*dr) for i in range(WIN_LENGTH)], ai


def live_lines(game):
    return [(c, a) for c, a in _windows(game)
            if len({game.board[x] for x in c if x in game.board}) <= 1]


def threat_cells(game, player):
    out = defaultdict(int)
    for cells, _ in _windows(game):
        ps = {game.board[c] for c in cells if c in game.board}
        if ps != {player}: continue
        empty = [c for c in cells if c not in game.board]
        if len(empty) == 1:
            out[empty[0]] += 1
    return dict(out)


def fork_cells(game, player, min_chain=2):
    out = defaultdict(int)
    for cand in game.candidates:
        if cand in game.board: continue
        q, r = cand
        axes = 0
        for dq, dr in AXES:
            n = 1
            for s in (1, -1):
                nq, nr = q+s*dq, r+s*dr
                while game.board.get((nq, nr)) == player:
                    n += 1; nq += s*dq; nr += s*dr
            if n >= min_chain: axes += 1
        if axes >= 2:
            out[cand] = axes
    return dict(out)


def potential_map(game):
    out = defaultdict(float)
    for cells, _ in _windows(game):
        ps = {game.board[c] for c in cells if c in game.board}
        if len(ps) > 1: continue
        k = sum(1 for c in cells if c in game.board)
        w = 0.5**k
        for c in cells:
            out[c] += w
    return dict(out)


def axis_chain_lengths(game, player):
    out = {}
    for (q, r), p in game.board.items():
        if p != player: continue
        chains = []
        for dq, dr in AXES:
            n = 1
            for s in (1, -1):
                nq, nr = q+s*dq, r+s*dr
                while game.board.get((nq, nr)) == player:
                    n += 1; nq += s*dq; nr += s*dr
            chains.append(n)
        out[(q, r)] = chains
    return out


def pair_correlation(moves, max_r=20):
    if len(moves) < 2: return {}
    dist = defaultdict(int)
    for i, (q1, r1) in enumerate(moves):
        for q2, r2 in moves[i+1:]:
            d = (abs(q1-q2) + abs(r1-r2) + abs((q1+r1)-(q2+r2))) // 2
            if d <= max_r: dist[d] += 1
    n = len(moves)
    total = n*(n-1)/2
    shell_sum = sum(6*r for r in range(1, max_r+1))
    return {r: dist.get(r, 0) / max(1.0, total * 6*r / shell_sum)
            for r in range(1, max_r+1)}


def live_ap_count(game):
    p1 = p2 = 0
    for cells, _ in _windows(game):
        ps = {game.board[c] for c in cells if c in game.board}
        if ps in ({1}, set()): p1 += 1
        if ps in ({2}, set()): p2 += 1
    return p1, p2


def pattern_fingerprint(game, radius=2):
    def _enc(cq, cr):
        tokens = []
        for dq in range(-radius, radius+1):
            for dr in range(max(-radius, -dq-radius), min(radius, -dq+radius)+1):
                tokens.append(str(game.board.get((cq+dq, cr+dr), 0)))
        return "".join(tokens)
    return {(q, r): _enc(q, r) for (q, r) in game.board}
