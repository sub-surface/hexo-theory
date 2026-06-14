"""
Hand-crafted agent hierarchy — ascending strategic depth.

  RandomAgent               uniform random legal move
  EisensteinGreedyAgent     max chain-length, greedy (from upstream elo.py)
  ForkAwareAgent            chain_score + α·fork_axes
  PotentialGradientAgent    Erdős–Selfridge potential + threat/fork bonuses
  ComboAgent                threat-first wrapper around PotentialGradientAgent
"""
from __future__ import annotations
import random
from hexgo.game import HexGame, AXES, WIN_LENGTH


class ForkAwareAgent:
    """chain_score + α·fork_axes  (α=0 → pure greedy)."""

    def __init__(self, name="fork_aware", alpha=2.0, min_chain=1,
                 defensive=True, eps=0.01):
        self.name, self.alpha = name, alpha
        self.min_chain, self.defensive, self.eps = min_chain, defensive, eps

    def choose_move(self, game: HexGame):
        player, opp = game.current_player, 3 - game.current_player
        best, bscore = None, -1.0
        for q, r in game.legal_moves():
            s = self._score(game, q, r, player)
            if self.defensive:
                s = max(s, self._score(game, q, r, opp))
            s += self.eps * random.random()
            if s > bscore or best is None:
                best, bscore = (q, r), s
        return best or random.choice(game.legal_moves())

    def _score(self, game, q, r, player):
        return self._chain(game, q, r, player) + self.alpha * self._forks(game, q, r, player)

    def _chain(self, game, q, r, player):
        best = 1
        for dq, dr in AXES:
            n = 1
            for s in (1, -1):
                nq, nr = q + s*dq, r + s*dr
                while game.board.get((nq, nr)) == player:
                    n += 1; nq += s*dq; nr += s*dr
            best = max(best, n)
        return best

    def _forks(self, game, q, r, player):
        hit = 0
        for dq, dr in AXES:
            n = 1
            for s in (1, -1):
                nq, nr = q + s*dq, r + s*dr
                while game.board.get((nq, nr)) == player:
                    n += 1; nq += s*dq; nr += s*dr
            if n >= self.min_chain:
                hit += 1
        return hit


class PotentialGradientAgent:
    """Erdős–Selfridge potential Σ(½)^k  +  threat/fork bonuses."""

    def __init__(self, name="potgrad", w_pot=1.0, w_threat_own=100.0,
                 w_threat_opp=80.0, w_fork=3.0, eps=0.001):
        self.name = name
        self.w_pot, self.w_threat_own = w_pot, w_threat_own
        self.w_threat_opp, self.w_fork, self.eps = w_threat_opp, w_fork, eps

    def choose_move(self, game: HexGame):
        player, opp = game.current_player, 3 - game.current_player
        legal = set(game.legal_moves())
        pot, th_own, th_opp = {}, {}, {}
        seen = set()

        for (sq, sr) in game.board:
            for ai, (dq, dr) in enumerate(AXES):
                for off in range(WIN_LENGTH):
                    key = (ai, sq - off*dq, sr - off*dr)
                    if key in seen: continue
                    seen.add(key)
                    oq, or_ = key[1], key[2]
                    cells = [(oq+i*dq, or_+i*dr) for i in range(WIN_LENGTH)]
                    ps = {game.board[c] for c in cells if c in game.board}
                    if len(ps) > 1: continue
                    k = sum(1 for c in cells if c in game.board)
                    contrib = 0.5**k
                    empty = [c for c in cells if c not in game.board]
                    for c in cells:
                        if c in legal:
                            pot[c] = pot.get(c, 0.0) + contrib
                    if k == WIN_LENGTH - 1 and len(empty) == 1:
                        ec = empty[0]
                        if ec in legal:
                            if ps == {player}:
                                th_own[ec] = th_own.get(ec, 0) + 1
                            elif ps == {opp}:
                                th_opp[ec] = th_opp.get(ec, 0) + 1

        if th_own: return max(th_own, key=th_own.get)
        if th_opp: return max(th_opp, key=th_opp.get)

        best, bscore = None, -1e9
        for q, r in legal:
            c = (q, r)
            score = self.w_pot * pot.get(c, 0.0)
            score += self.w_fork * self._forks(game, q, r, player)
            score += self.eps * random.random()
            if score > bscore or best is None:
                best, bscore = c, score
        return best or random.choice(list(legal))

    def _forks(self, game, q, r, player):
        hit = 0
        for dq, dr in AXES:
            n = 1
            for s in (1, -1):
                nq, nr = q + s*dq, r + s*dr
                while game.board.get((nq, nr)) == player:
                    n += 1; nq += s*dq; nr += s*dr
            if n >= 1: hit += 1
        return hit


class ComboAgent:
    """Threat-first; falls back to PotentialGradientAgent."""

    def __init__(self, name="combo", w_pot=1.0, w_fork=4.0):
        self.name = name
        self._pg = PotentialGradientAgent(name, w_pot=w_pot,
                                          w_threat_own=10000., w_threat_opp=8000.,
                                          w_fork=w_fork)

    def choose_move(self, game: HexGame):
        return self._pg.choose_move(game)
