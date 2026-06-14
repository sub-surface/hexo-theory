"""
Matplotlib visualisation helpers — torch-free, marimo-compatible.

  draw_board(game, ax)         full board with potential heatmap, threats, forks
  draw_trail(game, ax)         same + move-number labels
  replay_fig(moves, step)      single figure at a given step of a game
  d6_panel(game)               4×3 grid of all D6 orbit images
  hex_xy(q, r)                 axial → cartesian (flat-top)
"""
from __future__ import annotations
import math
from typing import Callable, Sequence

import matplotlib.pyplot as plt
import matplotlib.patches as mp
import numpy as np

from hexgo.game   import HexGame, DIRS
from hexgo.analysis import threat_cells, fork_cells, potential_map

_S3 = math.sqrt(3)


# ── geometry ─────────────────────────────────────────────────────────────────

def hex_xy(q: int, r: int, size: float = 1.0) -> tuple[float, float]:
    return size * 1.5 * q, size * _S3 * (r + q/2)


def _poly(q, r, size=1.0):
    cx, cy = hex_xy(q, r, size)
    return np.array([(cx + size*math.cos(math.radians(60*k)),
                      cy + size*math.sin(math.radians(60*k))) for k in range(6)])


def _region(cells, pad=2):
    if not cells:
        cells = [(0, 0)]
    qs, rs = [c[0] for c in cells], [c[1] for c in cells]
    for q in range(min(qs)-pad, max(qs)+pad+1):
        for r in range(min(rs)-pad, max(rs)+pad+1):
            yield q, r


# ── board drawing ─────────────────────────────────────────────────────────────

_P1 = "#2a4a8a"   # deep blue
_P2 = "#b8392b"   # deep red
_BG = "#1a1a2e"   # dark navy


def draw_board(game: HexGame, ax=None, size=1.0,
               show_potential=True, show_threats=True,
               show_forks=True, title=None):
    """Render a HexGame state onto `ax` (created if None)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 7))
        ax.set_facecolor(_BG)

    pot = potential_map(game) if show_potential else {}
    vmax = max(pot.values(), default=1.0) or 1.0

    # background — candidate cells + potential heatmap
    for q, r in _region(list(game.board)):
        if (q, r) in game.board: continue
        poly = _poly(q, r, size)
        if show_potential and (q, r) in pot:
            shade = plt.cm.YlOrRd(min(1.0, pot[(q,r)] / vmax * 0.85))
            ax.fill(poly[:,0], poly[:,1], color=shade, alpha=0.65,
                    edgecolor="none", zorder=1)
        ax.plot(np.append(poly[:,0], poly[0,0]),
                np.append(poly[:,1], poly[0,1]),
                color="#303060", lw=0.5, zorder=2)

    # stones
    for (q, r), p in game.board.items():
        poly = _poly(q, r, size)
        col = _P1 if p == 1 else _P2
        ax.fill(poly[:,0], poly[:,1], color=col, alpha=0.92,
                edgecolor="#000", lw=0.9, zorder=3)

    # last-move dot
    if game.move_history:
        q, r = game.move_history[-1]
        cx, cy = hex_xy(q, r, size)
        ax.plot(cx, cy, "o", ms=7, mfc="white", mec="black", mew=1.2, zorder=5)

    # threats
    if show_threats:
        for p, col in ((1, _P1), (2, _P2)):
            for (q, r) in threat_cells(game, p):
                cx, cy = hex_xy(q, r, size)
                ax.plot(cx, cy, "X", ms=13, mfc=col, mec="white", mew=1.2, zorder=6)

    # forks
    if show_forks:
        for p, col in ((1, _P1), (2, _P2)):
            for (q, r) in fork_cells(game, p):
                cx, cy = hex_xy(q, r, size)
                ax.plot(cx, cy, "D", ms=7, mfc="none", mec=col, mew=1.5, zorder=6)

    ax.set_aspect("equal"); ax.axis("off")
    if title: ax.set_title(title, color="white")
    return ax


def draw_trail(game: HexGame, ax=None, size=1.0):
    ax = draw_board(game, ax, size, show_potential=False,
                    show_threats=False, show_forks=False)
    for i, ((q, r), p) in enumerate(zip(game.move_history, game.player_history)):
        cx, cy = hex_xy(q, r, size)
        ax.text(cx, cy, str(i+1), ha="center", va="center",
                fontsize=7, color="white", fontweight="bold", zorder=7)
    return ax


def replay_fig(moves: Sequence[tuple[int,int]], step: int,
               agents=None, size=1.0) -> plt.Figure:
    g = HexGame()
    for mv in moves[:step]:
        if mv in set(g.legal_moves()): g.make(*mv)
    fig, ax = plt.subplots(figsize=(7, 6.5))
    ax.set_facecolor(_BG); fig.patch.set_facecolor(_BG)
    draw_board(g, ax, size, title=f"move {step} / {len(moves)}")
    plt.tight_layout()
    return fig


# ── D6 orbit panel ────────────────────────────────────────────────────────────

_D6 = [
    ("id",    lambda q,r: (q, r)),
    ("r60",   lambda q,r: (-r, q+r)),
    ("r120",  lambda q,r: (-q-r, q)),
    ("r180",  lambda q,r: (-q, -r)),
    ("r240",  lambda q,r: (r, -q-r)),
    ("r300",  lambda q,r: (q+r, -q)),
    ("s0",    lambda q,r: (q+r, -r)),
    ("s60",   lambda q,r: (-q, q+r)),
    ("s120",  lambda q,r: (-q-r, r)),
    ("s180",  lambda q,r: (r, q)),
    ("s240",  lambda q,r: (-r, -q)),
    ("s300",  lambda q,r: (q, -q-r)),
]


def d6_panel(game: HexGame, size=0.85) -> plt.Figure:
    fig, axs = plt.subplots(3, 4, figsize=(14, 9.5))
    fig.patch.set_facecolor(_BG)
    for ax, (name, op) in zip(axs.flatten(), _D6):
        ax.set_facecolor(_BG)
        g2 = HexGame()
        g2.board = {op(q,r): p for (q,r),p in game.board.items()}
        g2.move_history  = [op(q,r) for q,r in game.move_history]
        g2.player_history = list(game.player_history)
        draw_board(g2, ax, size, show_potential=False,
                   show_threats=False, show_forks=False, title=name)
    plt.tight_layout()
    return fig


# ── quick game sampler ────────────────────────────────────────────────────────

def play(factory_a: Callable, factory_b: Callable,
         max_moves=150, seed=None) -> HexGame:
    import random
    if seed is not None: random.seed(seed)
    a, b = factory_a(), factory_b()
    g = HexGame()
    m = 0
    while g.winner is None and m < max_moves:
        ag = a if g.current_player == 1 else b
        legal = g.legal_moves()
        if not legal: break
        mv = ag.choose_move(g)
        if mv not in set(legal): mv = random.choice(legal)
        g.make(*mv); m += 1
    return g
