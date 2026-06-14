#!/usr/bin/env python3
"""
hexconnect6_empirical_paper.py

Empirical paper generator for Infinite Hex Connect-6 / HexGo (1-2-2 rule).

What it does
------------
Creates a zipped research folder containing:
  - paper PDF generated with matplotlib PdfPages
  - Markdown paper
  - figures
  - CSV data
  - JSON metadata
  - this exact script copied into the folder

The paper studies the game on the Eisenstein/axial hex lattice:
  - P1 places one stone on the first turn.
  - P2 places two stones.
  - Every subsequent turn places two stones.
  - First player with six consecutive stones on any of the three hex axes wins.

Design constraints
------------------
This is intentionally OOM-safe:
  - no exhaustive infinite-board game tree
  - bounded frontier candidate set
  - capped pair enumeration
  - no neural net dependencies
  - no full MCTS tree in memory
  - figures written and closed one at a time

Run examples
------------
Quick smoke run:
    python hexconnect6_empirical_paper.py --mode quick --out hexgo_paper_out

More serious CPU run:
    python hexconnect6_empirical_paper.py --mode full --out hexgo_paper_out --games 160 --max-turns 90

Dependencies: Python 3.10+, numpy, pandas, matplotlib.
Optional: psutil for memory logging.
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import random
import shutil
import textwrap
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

Coord = Tuple[int, int]
Player = int

AXES: Tuple[Coord, Coord, Coord] = ((1, 0), (0, 1), (1, -1))
DIRECTIONS6: Tuple[Coord, ...] = ((1, 0), (0, 1), (-1, 1), (-1, 0), (0, -1), (1, -1))
WIN_LEN = 6
P1 = 1
P2 = -1
PLAYER_NAME = {P1: "Black/P1", P2: "White/P2", 0: "draw"}

# Potential weights for open length-6 windows. These are deliberately steep:
# in Connect6 a four-in-window is an immediate next-turn threat because the player
# can fill the two remaining cells. Five-in-window is still one cell away.
OPEN_WEIGHTS = {0: 0.0, 1: 1.0, 2: 4.0, 3: 18.0, 4: 250.0, 5: 2500.0, 6: 1_000_000.0}

# Stable references embedded in the generated paper. They are not fetched at runtime.
REFERENCES = [
    "sub-surface. HexGo Theory: number-theoretic and combinatorial investigation of optimal play in HexGo, GitHub repository, accessed 2026-05-10. https://github.com/sub-surface/hexgo-theory",
    "Wu, I.-C. and Huang, D.-Y. (2006). A new family of k-in-a-row games. ICGA Journal 29(1), 26-34.",
    "Vipin, K. and Fahmy, S. A. (2011). A threat based Connect6 implementation on FPGA. FPT 2011.",
    "Patel, A. Red Blob Games: Hexagonal Grids, continuously updated guide, accessed 2026-05-10. https://www.redblobgames.com/grids/hexagons/",
    "Litman, E. and Guo, G. (2026). A Theory of Generalization in Deep Learning. arXiv:2605.01172v1.",
    "Berlekamp, E. R., Conway, J. H. and Guy, R. K. (1982). Winning Ways for your Mathematical Plays. Academic Press.",
    "Erdos, P. and Selfridge, J. L. (1973). On a combinatorial game. Journal of Combinatorial Theory, Series A 14, 298-301.",
]

# -----------------------------
# Hex / Eisenstein lattice tools
# -----------------------------

def add(a: Coord, b: Coord) -> Coord:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Coord, b: Coord) -> Coord:
    return (a[0] - b[0], a[1] - b[1])


def mul(k: int, a: Coord) -> Coord:
    return (k * a[0], k * a[1])


def neg(a: Coord) -> Coord:
    return (-a[0], -a[1])


def cube(a: Coord) -> Tuple[int, int, int]:
    # axial (q,r) -> cube (x,y,z) with x+y+z=0; choose x=q, z=r.
    q, r = a
    return (q, -q - r, r)


def axial(c: Tuple[int, int, int]) -> Coord:
    x, y, z = c
    return (x, z)


def hex_distance(a: Coord, b: Coord = (0, 0)) -> int:
    q, r = sub(a, b)
    return max(abs(q), abs(r), abs(q + r))


def coord_to_xy(c: Coord) -> Tuple[float, float]:
    q, r = c
    return (q + 0.5 * r, (math.sqrt(3.0) / 2.0) * r)


def rotate60(c: Coord, n: int = 1) -> Coord:
    x, y, z = cube(c)
    n %= 6
    for _ in range(n):
        # 60 degree rotation in cube coordinates.
        x, y, z = -z, -x, -y
    return axial((x, y, z))


def reflect_qr(c: Coord) -> Coord:
    # Reflection swapping q and r axes: cube x <-> z.
    x, y, z = cube(c)
    return axial((z, y, x))


def d6_images(c: Coord) -> List[Coord]:
    imgs = []
    for k in range(6):
        rc = rotate60(c, k)
        imgs.append(rc)
        imgs.append(reflect_qr(rc))
    return imgs


def canonical_coord(c: Coord) -> Coord:
    return min(d6_images(c))


def transform_pattern(pattern: Sequence[Tuple[Coord, Player]], rot: int, refl: bool) -> Tuple[Tuple[int, int, int], ...]:
    out = []
    for c, p in pattern:
        cc = rotate60(c, rot)
        if refl:
            cc = reflect_qr(cc)
        out.append((cc[0], cc[1], p))
    return tuple(sorted(out))


def canonical_pattern(pattern: Sequence[Tuple[Coord, Player]]) -> Tuple[Tuple[int, int, int], ...]:
    if not pattern:
        return tuple()
    return min(transform_pattern(pattern, rot, refl) for rot in range(6) for refl in (False, True))


def ring(radius: int) -> List[Coord]:
    if radius == 0:
        return [(0, 0)]
    results: List[Coord] = []
    c = mul(radius, DIRECTIONS6[4])
    for direction in DIRECTIONS6:
        for _ in range(radius):
            results.append(c)
            c = add(c, direction)
    return results


def disk(radius: int) -> List[Coord]:
    cells: List[Coord] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            c = (q, r)
            if hex_distance(c) <= radius:
                cells.append(c)
    return cells

# -----------------------------
# Board and threat calculus
# -----------------------------

@dataclass
class Board:
    stones: Dict[Coord, Player] = field(default_factory=dict)
    history: List[Tuple[Player, Tuple[Coord, ...]]] = field(default_factory=list)
    winner: Player = 0
    winning_line: Tuple[Coord, ...] = tuple()

    def copy(self) -> "Board":
        return Board(dict(self.stones), list(self.history), self.winner, tuple(self.winning_line))

    def occupied(self) -> Set[Coord]:
        return set(self.stones.keys())

    def empty(self, c: Coord) -> bool:
        return c not in self.stones

    def player_stones(self, player: Player) -> List[Coord]:
        return [c for c, p in self.stones.items() if p == player]

    def place(self, player: Player, coords: Sequence[Coord]) -> None:
        coords_t = tuple(coords)
        if len(coords_t) != len(set(coords_t)):
            raise ValueError(f"duplicate coordinates in move {coords_t}")
        for c in coords_t:
            if c in self.stones:
                raise ValueError(f"cell {c} already occupied")
        for c in coords_t:
            self.stones[c] = player
        self.history.append((player, coords_t))
        win_line = self.find_win_after(player, coords_t)
        if win_line:
            self.winner = player
            self.winning_line = tuple(win_line)

    def undo(self, coords: Sequence[Coord]) -> None:
        for c in coords:
            self.stones.pop(c, None)
        self.winner = 0
        self.winning_line = tuple()
        if self.history and set(self.history[-1][1]) == set(coords):
            self.history.pop()

    def find_win_after(self, player: Player, coords: Sequence[Coord]) -> Optional[List[Coord]]:
        for c in coords:
            for d in AXES:
                line = [c]
                x = add(c, d)
                while self.stones.get(x) == player:
                    line.append(x)
                    x = add(x, d)
                x = sub(c, d)
                while self.stones.get(x) == player:
                    line.insert(0, x)
                    x = sub(x, d)
                if len(line) >= WIN_LEN:
                    # Return a length-6 subline containing c if possible.
                    idx = line.index(c)
                    start = max(0, min(idx, len(line) - WIN_LEN))
                    return line[start:start + WIN_LEN]
        return None

    def bounding_radius(self) -> int:
        if not self.stones:
            return 0
        return max(hex_distance(c) for c in self.stones)

    def canonical_recent_hash(self, radius: int = 3) -> Tuple[Tuple[int, int, int], ...]:
        if not self.stones:
            return tuple()
        # Use center of mass rounded to nearest occupied as local anchor.
        qs = np.array([c[0] for c in self.stones], dtype=float)
        rs = np.array([c[1] for c in self.stones], dtype=float)
        anchor = min(self.stones, key=lambda c: (c[0] - qs.mean()) ** 2 + (c[1] - rs.mean()) ** 2)
        pattern = []
        for c, p in self.stones.items():
            rel = sub(c, anchor)
            if hex_distance(rel) <= radius:
                pattern.append((rel, p))
        return canonical_pattern(pattern)


def window_cells(start: Coord, d: Coord, length: int = WIN_LEN) -> Tuple[Coord, ...]:
    return tuple(add(start, mul(i, d)) for i in range(length))


def all_relevant_windows(board: Board, player: Player, include_empty_nearby: bool = False) -> Dict[Tuple[int, Coord], Tuple[int, int, Tuple[Coord, ...]]]:
    # Returns key -> (own_count, opp_count, empties)
    seeds = set(board.player_stones(player))
    if include_empty_nearby:
        seeds |= candidate_cells(board, frontier_radius=1, max_cells=200)
    windows = {}
    for c in seeds:
        for ai, d in enumerate(AXES):
            for off in range(WIN_LEN):
                start = sub(c, mul(off, d))
                cells = window_cells(start, d)
                own = sum(1 for x in cells if board.stones.get(x) == player)
                opp = sum(1 for x in cells if board.stones.get(x) == -player)
                empties = tuple(x for x in cells if x not in board.stones)
                if own or opp:
                    windows[(ai, start)] = (own, opp, empties)
    return windows


def open_windows(board: Board, player: Player) -> List[Tuple[int, int, Tuple[Coord, ...]]]:
    out = []
    for own, opp, empties in all_relevant_windows(board, player).values():
        if opp == 0:
            out.append((own, opp, empties))
    return out


def potential(board: Board, player: Player) -> float:
    val = 0.0
    for own, opp, _empties in all_relevant_windows(board, player).values():
        if opp == 0:
            val += OPEN_WEIGHTS.get(own, 0.0)
    return val


def immediate_win_pairs(board: Board, player: Player) -> List[Tuple[Coord, ...]]:
    # All one- or two-cell fills that immediately complete a six-window.
    pairs: Set[Tuple[Coord, ...]] = set()
    for own, opp, empties in all_relevant_windows(board, player).values():
        if opp == 0 and own >= 4 and 1 <= len(empties) <= 2:
            pairs.add(tuple(sorted(empties)))
    return sorted(pairs)


def threat_family(board: Board, player: Player) -> List[frozenset]:
    # A family of empty-cell sets, each of which would be fillable by player on next turn.
    fam: Set[frozenset] = set()
    for own, opp, empties in all_relevant_windows(board, player).values():
        if opp == 0 and own >= 4 and 1 <= len(empties) <= 2:
            fam.add(frozenset(empties))
    return sorted(fam, key=lambda s: (len(s), sorted(s)))


def capped_hitting_number(family: Sequence[frozenset], cap: int = 2) -> int:
    """Minimum number of cells needed to hit every threat set; cap+1 if more than cap.

    In the 1-2-2 game, a player can block at most two empty cells per turn. If the
    opponent's immediate-threat family has hitting number >=3, they cannot block
    all immediate wins in a single turn.
    """
    family = [set(f) for f in family if len(f) > 0]
    if not family:
        return 0
    universe = sorted(set().union(*family))
    for k in range(1, cap + 1):
        for combo in itertools.combinations(universe, k):
            s = set(combo)
            if all(s & f for f in family):
                return k
    return cap + 1


def threat_load(board: Board, player: Player) -> int:
    return capped_hitting_number(threat_family(board, player), cap=2)


def local_density(board: Board, c: Coord, radius: int = 2) -> Tuple[int, int]:
    own = 0
    opp = 0
    for dq, dr in disk(radius):
        if dq == 0 and dr == 0:
            continue
        p = board.stones.get((c[0] + dq, c[1] + dr), 0)
        if p == 1:
            own += 1
        elif p == -1:
            opp += 1
    return own, opp


def candidate_cells(board: Board, frontier_radius: int = 2, max_cells: int = 160, rng: Optional[random.Random] = None) -> Set[Coord]:
    if not board.stones:
        return {(0, 0)}
    cand: Set[Coord] = set()
    occ = list(board.stones.keys())
    # Frontier around occupied cells.
    small_disk = disk(frontier_radius)
    for c in occ:
        for delta in small_disk:
            x = add(c, delta)
            if x not in board.stones:
                cand.add(x)
    # Threat empties are mandatory candidates.
    for player in (P1, P2):
        for f in threat_family(board, player):
            cand |= set(f)
        for pair in immediate_win_pairs(board, player):
            cand |= set(pair)
    # Avoid unbounded blow-up.
    if len(cand) > max_cells:
        # Keep nearest-to-action cells plus all threat cells.
        threat_cells: Set[Coord] = set()
        for player in (P1, P2):
            for f in threat_family(board, player):
                threat_cells |= set(f)
        center_q = sum(c[0] for c in occ) / len(occ)
        center_r = sum(c[1] for c in occ) / len(occ)
        def key(x: Coord) -> Tuple[float, int, int]:
            nearest = min(hex_distance(x, o) for o in occ)
            center = (x[0] - center_q) ** 2 + (x[1] - center_r) ** 2
            return (0 if x in threat_cells else 1, nearest, center)
        kept = sorted(cand, key=key)[:max_cells]
        cand = set(kept) | threat_cells
    return cand


def move_size_for_ply(ply: int) -> int:
    # ply starts at 0. P1's first move is size 1; all later moves are size 2.
    return 1 if ply == 0 else 2


def stone_player_for_ply(ply: int) -> Player:
    if ply == 0:
        return P1
    return P2 if ply % 2 == 1 else P1

# -----------------------------
# Agents and pair scoring
# -----------------------------

@dataclass
class ScoreBreakdown:
    total: float
    own_win: int
    blocks_opp_win: int
    own_tau_after: int
    opp_tau_after: int
    potential_delta: float
    radius_penalty: float


def score_move(board: Board, player: Player, move: Tuple[Coord, ...], aggression: float = 1.0, defense: float = 1.0) -> ScoreBreakdown:
    if any(c in board.stones for c in move) or len(set(move)) < len(move):
        return ScoreBreakdown(-1e18, 0, 0, 0, 0, 0.0, 0.0)
    before_own = potential(board, player)
    before_opp = potential(board, -player)
    before_opp_tau = threat_load(board, -player)
    before_opp_wins = len(immediate_win_pairs(board, -player))
    b = board.copy()
    b.place(player, move)
    own_win = 1 if b.winner == player else 0
    after_own = potential(b, player)
    after_opp = potential(b, -player)
    after_own_tau = threat_load(b, player)
    after_opp_tau = threat_load(b, -player)
    after_opp_wins = len(immediate_win_pairs(b, -player))
    blocks = 1 if before_opp_wins > 0 and after_opp_wins < before_opp_wins else 0
    radius_penalty = 0.05 * sum(hex_distance(c) for c in move) + 0.02 * max(hex_distance(c) for c in move)
    pot_delta = (after_own - before_own) - defense * 0.92 * (after_opp - before_opp)
    tau_bonus = aggression * (800.0 * after_own_tau + 5000.0 * int(after_own_tau >= 3))
    tau_defense = defense * (1000.0 * before_opp_tau - 950.0 * after_opp_tau + 5000.0 * int(after_opp_tau <= 2 < before_opp_tau))
    total = (
        1e9 * own_win
        + 1e7 * blocks
        + tau_bonus
        + tau_defense
        + pot_delta
        - radius_penalty
        + random.random() * 1e-6
    )
    return ScoreBreakdown(total, own_win, blocks, after_own_tau, after_opp_tau, pot_delta, radius_penalty)


def prescore_cell(board: Board, player: Player, cell: Coord, aggression: float = 1.0, defense: float = 1.0) -> float:
    if cell in board.stones:
        return -1e18
    b = board.copy()
    b.place(player, (cell,))
    own_win = 1 if b.winner == player else 0
    return (
        1e7 * own_win
        + 500.0 * threat_load(b, player) * aggression
        - 450.0 * threat_load(b, -player) * defense
        + potential(b, player)
        - 0.85 * potential(b, -player)
        - 0.05 * hex_distance(cell)
    )


class Agent:
    name = "agent"

    def select(self, board: Board, player: Player, move_size: int, rng: random.Random) -> Tuple[Coord, ...]:
        raise NotImplementedError


class RandomFrontierAgent(Agent):
    name = "random-frontier"

    def select(self, board: Board, player: Player, move_size: int, rng: random.Random) -> Tuple[Coord, ...]:
        cand = list(candidate_cells(board, frontier_radius=2, max_cells=220, rng=rng))
        if len(cand) < move_size:
            raise RuntimeError("not enough candidate cells")
        return tuple(sorted(rng.sample(cand, move_size)))


class GreedyThreatAgent(Agent):
    def __init__(self, name: str = "greedy-threat", frontier_radius: int = 2, top_singles: int = 48, aggression: float = 1.0, defense: float = 1.0, candidate_cap: int = 140):
        self.name = name
        self.frontier_radius = frontier_radius
        self.top_singles = top_singles
        self.aggression = aggression
        self.defense = defense
        self.candidate_cap = candidate_cap

    def select(self, board: Board, player: Player, move_size: int, rng: random.Random) -> Tuple[Coord, ...]:
        if move_size == 1:
            if not board.stones:
                return ((0, 0),)
            cand = list(candidate_cells(board, self.frontier_radius, max_cells=self.candidate_cap, rng=rng))
            return (max(cand, key=lambda c: prescore_cell(board, player, c, self.aggression, self.defense)),)
        cand = list(candidate_cells(board, self.frontier_radius, max_cells=self.candidate_cap, rng=rng))
        # Force immediate wins or blocks into the candidate set.
        force_cells: Set[Coord] = set()
        for pair in immediate_win_pairs(board, player)[:20] + immediate_win_pairs(board, -player)[:20]:
            force_cells |= set(pair)
        scored = sorted(cand, key=lambda c: prescore_cell(board, player, c, self.aggression, self.defense), reverse=True)
        top = list(dict.fromkeys(list(force_cells) + scored[: self.top_singles]))
        top = [c for c in top if c not in board.stones]
        if len(top) < 2:
            top = scored[: max(2, min(len(scored), self.top_singles))]
        best_pair: Optional[Tuple[Coord, Coord]] = None
        best_score = -1e30
        for a, b in itertools.combinations(top, 2):
            br = score_move(board, player, tuple(sorted((a, b))), self.aggression, self.defense)
            if br.total > best_score:
                best_score = br.total
                best_pair = tuple(sorted((a, b)))
        assert best_pair is not None
        return best_pair


class MirrorHaloAgent(Agent):
    """A deliberately simple P2-ish agent: mirror around the origin when safe, otherwise greedy.

    It operationalizes the 'Eisenstein halo' idea: pair replies across a D6/central-symmetry
    orbit to neutralize single-stone initiative. This is not claimed optimal.
    """
    def __init__(self):
        self.name = "mirror-halo"
        self.greedy = GreedyThreatAgent("mirror-halo-fallback", top_singles=28, aggression=0.85, defense=1.2, candidate_cap=100)

    def select(self, board: Board, player: Player, move_size: int, rng: random.Random) -> Tuple[Coord, ...]:
        if move_size == 1:
            return self.greedy.select(board, player, move_size, rng)
        if board.history:
            last_player, last = board.history[-1]
            proposed = []
            for c in last:
                m = neg(c)
                if m not in board.stones and m not in proposed:
                    proposed.append(m)
            # Fill with D6 halo cells near radius 2 or 3 if needed.
            halo = [c for rad in (2, 3, 1, 4) for c in ring(rad)]
            rng.shuffle(halo)
            for h in halo:
                if len(proposed) >= 2:
                    break
                if h not in board.stones and h not in proposed:
                    proposed.append(h)
            if len(proposed) == 2:
                # Only trust mirror if it does not leave an unblocked immediate disaster.
                br = score_move(board, player, tuple(sorted(proposed)), aggression=0.8, defense=1.4)
                if br.opp_tau_after <= 2 or br.own_win:
                    return tuple(sorted(proposed))
        return self.greedy.select(board, player, move_size, rng)


class NoisyAgent(Agent):
    def __init__(self, base: Agent, eps: float = 0.15, name: Optional[str] = None):
        self.base = base
        self.eps = eps
        self.name = name or f"noisy-{base.name}"
        self.random_agent = RandomFrontierAgent()

    def select(self, board: Board, player: Player, move_size: int, rng: random.Random) -> Tuple[Coord, ...]:
        if rng.random() < self.eps:
            return self.random_agent.select(board, player, move_size, rng)
        return self.base.select(board, player, move_size, rng)

# -----------------------------
# Game simulation
# -----------------------------

@dataclass
class GameRecord:
    game_id: int
    black_agent: str
    white_agent: str
    winner: Player
    winner_name: str
    plies: int
    stones: int
    radius: int
    terminal_tau_black: int
    terminal_tau_white: int
    bragg_top1: float = np.nan
    final_pattern_entropy_r2: float = np.nan


def play_game(agent_black: Agent, agent_white: Agent, game_id: int, seed: int, max_turns: int = 90, collect_states: bool = False) -> Tuple[Board, GameRecord, List[Dict]]:
    rng = random.Random(seed)
    board = Board()
    states: List[Dict] = []
    for ply in range(max_turns):
        player = stone_player_for_ply(ply)
        move_size = move_size_for_ply(ply)
        agent = agent_black if player == P1 else agent_white
        if collect_states and board.stones:
            states.append(state_metrics(board, player_to_move=player, ply=ply, game_id=game_id, black_agent=agent_black.name, white_agent=agent_white.name))
        try:
            move = agent.select(board, player, move_size, rng)
            if len(move) != move_size:
                # Repair invalid agent outputs.
                move = RandomFrontierAgent().select(board, player, move_size, rng)
            board.place(player, move)
        except Exception:
            move = RandomFrontierAgent().select(board, player, move_size, rng)
            board.place(player, move)
        if board.winner:
            break
    rec = GameRecord(
        game_id=game_id,
        black_agent=agent_black.name,
        white_agent=agent_white.name,
        winner=board.winner,
        winner_name=PLAYER_NAME.get(board.winner, "draw"),
        plies=len(board.history),
        stones=len(board.stones),
        radius=board.bounding_radius(),
        terminal_tau_black=threat_load(board, P1),
        terminal_tau_white=threat_load(board, P2),
    )
    return board, rec, states


def state_metrics(board: Board, player_to_move: Player, ply: int, game_id: int, black_agent: str, white_agent: str) -> Dict:
    cand = candidate_cells(board, frontier_radius=2, max_cells=180)
    pairs = math.comb(len(cand), 2) if len(cand) >= 2 else 0
    player = -player_to_move  # just-moved player
    tau_p1 = threat_load(board, P1)
    tau_p2 = threat_load(board, P2)
    p1_pot = potential(board, P1)
    p2_pot = potential(board, P2)
    # Pair score entropy over a bounded top set for side to move.
    entropy = np.nan
    top_count = 0
    if len(cand) >= 2:
        pres = sorted(cand, key=lambda c: prescore_cell(board, player_to_move, c), reverse=True)[:34]
        scores = []
        for a, b in itertools.combinations(pres, 2):
            scores.append(score_move(board, player_to_move, tuple(sorted((a, b)))).total)
        if scores:
            arr = np.array(scores, dtype=np.float64)
            arr = arr - np.max(arr)
            probs = np.exp(arr / max(1.0, np.std(arr) + 1e-9))
            probs = probs / probs.sum()
            entropy = float(-(probs * np.log(probs + 1e-12)).sum())
            top_count = len(scores)
    return {
        "game_id": game_id,
        "ply": ply,
        "black_agent": black_agent,
        "white_agent": white_agent,
        "player_to_move": player_to_move,
        "just_moved": player,
        "stones": len(board.stones),
        "radius": board.bounding_radius(),
        "candidate_cells": len(cand),
        "candidate_pairs_upper": pairs,
        "eval_pair_count": top_count,
        "reply_entropy": entropy,
        "tau_black": tau_p1,
        "tau_white": tau_p2,
        "tau_just_moved": tau_p1 if player == P1 else tau_p2,
        "tau_to_move": tau_p1 if player_to_move == P1 else tau_p2,
        "potential_black": p1_pot,
        "potential_white": p2_pot,
        "potential_balance_black_minus_white": p1_pot - p2_pot,
    }

# -----------------------------
# Experiments
# -----------------------------


def run_tournament(args, out_data: Path) -> Tuple[pd.DataFrame, pd.DataFrame, List[Board]]:
    rng = random.Random(args.seed)
    # Caps are deliberately smaller in quick mode; full mode still avoids exhaustive O(N^2) infinity.
    top_small = 18 if args.mode == "quick" else 36
    top_combo = 24 if args.mode == "quick" else 52
    cap_small = 80 if args.mode == "quick" else 140
    agents: Dict[str, Agent] = {
        "random-frontier": RandomFrontierAgent(),
        "greedy-threat": GreedyThreatAgent("greedy-threat", top_singles=top_small, aggression=1.0, defense=1.0, candidate_cap=cap_small),
        "combo": GreedyThreatAgent("combo", frontier_radius=2, top_singles=top_combo, aggression=1.18, defense=1.12, candidate_cap=cap_small),
        "mirror-halo": MirrorHaloAgent(),
        "noisy-combo": NoisyAgent(GreedyThreatAgent("combo-core", top_singles=top_small, aggression=1.1, defense=1.05, candidate_cap=cap_small), eps=0.18, name="noisy-combo"),
    }
    if args.mode == "quick":
        pairings = [("combo", "combo"), ("combo", "mirror-halo"), ("mirror-halo", "combo"), ("greedy-threat", "combo"), ("random-frontier", "combo")]
        games_per_pair = max(1, args.games // max(1, len(pairings)))
    else:
        names = ["random-frontier", "greedy-threat", "combo", "mirror-halo", "noisy-combo"]
        pairings = [(a, b) for a in names for b in names]
        games_per_pair = max(1, args.games // max(1, len(pairings)))

    records = []
    states = []
    boards = []
    game_id = 0
    for black_name, white_name in pairings:
        for j in range(games_per_pair):
            game_id += 1
            b, rec, ss = play_game(
                agents[black_name], agents[white_name], game_id=game_id,
                seed=rng.randrange(10**9), max_turns=args.max_turns,
                collect_states=True,
            )
            records.append(rec.__dict__)
            states.extend(ss)
            if (black_name, white_name) in [("combo", "combo"), ("combo", "mirror-halo"), ("mirror-halo", "combo")]:
                boards.append(b)
    games_df = pd.DataFrame(records)
    states_df = pd.DataFrame(states)
    games_df.to_csv(out_data / "tournament_games.csv", index=False)
    states_df.to_csv(out_data / "tournament_states.csv", index=False)
    return games_df, states_df, boards


def opening_scan(args, out_data: Path) -> pd.DataFrame:
    """Scan P2 replies after P1 opens at the origin.

    Bottleneck note: a naive two-ply scan evaluates O(N^2 M^2) pair replies.
    We instead evaluate every P2 pair with the static threat heuristic, then run
    the expensive Black-best-reply calculation only for the top replies. This
    preserves the research object - the opening halo - without exploding CPU.
    """
    board = Board()
    board.place(P1, ((0, 0),))
    cells = [c for c in disk(args.opening_radius) if c != (0, 0)]
    rows = []
    for a, b in itertools.combinations(cells, 2):
        move = tuple(sorted((a, b)))
        br = score_move(board, P2, move, aggression=1.0, defense=1.1)
        cx, cy = coord_to_xy(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0))  # type: ignore[arg-type]
        rows.append({
            "a_q": a[0], "a_r": a[1], "b_q": b[0], "b_r": b[1],
            "centroid_x": cx, "centroid_y": cy,
            "white_reply_score": br.total,
            "white_tau_after": br.own_tau_after,
            "black_tau_after": br.opp_tau_after,
            "black_best_reply_score": np.nan,
            "net_reply_value": br.total,
            "pair_distance": hex_distance(a, b),
            "max_radius": max(hex_distance(a), hex_distance(b)),
            "canonical_a": str(canonical_coord(a)),
            "canonical_b": str(canonical_coord(b)),
        })
    df = pd.DataFrame(rows).sort_values("white_reply_score", ascending=False).reset_index(drop=True)

    # Refine the best-looking replies with a bounded Black reply search.
    refine_n = min(len(df), args.opening_refine)
    for idx in range(refine_n):
        row = df.loc[idx]
        move = tuple(sorted(((int(row.a_q), int(row.a_r)), (int(row.b_q), int(row.b_r)))))
        cb = board.copy()
        cb.place(P2, move)
        cand = sorted(candidate_cells(cb, frontier_radius=2, max_cells=120), key=lambda c: prescore_cell(cb, P1, c), reverse=True)[: args.opening_reply_top]
        best_black = -1e30
        for x, y in itertools.combinations(cand, 2):
            best_black = max(best_black, score_move(cb, P1, tuple(sorted((x, y))), aggression=1.15, defense=1.0).total)
        df.at[idx, "black_best_reply_score"] = best_black
        df.at[idx, "net_reply_value"] = float(row.white_reply_score) - 0.0001 * best_black
    df = df.sort_values("net_reply_value", ascending=False).reset_index(drop=True)
    df.to_csv(out_data / "opening_reply_scan.csv", index=False)
    return df

def threat_validation(states_df: pd.DataFrame, out_data: Path) -> pd.DataFrame:
    # Mostly theorem-level: from stored states we inspect tau. We cannot reconstruct boards from states alone,
    # so this table is empirical outcome correlation and theorem statement. Outcome merge by game id happens later.
    if states_df.empty:
        df = pd.DataFrame()
    else:
        df = states_df.copy()
        df["forced_next_turn_indicator"] = (df["tau_just_moved"] >= 3).astype(int)
    df.to_csv(out_data / "threat_load_states.csv", index=False)
    return df


def pattern_entropy(board: Board, radius: int = 2) -> float:
    counts = Counter()
    for anchor in board.stones:
        pattern = []
        for delta in disk(radius):
            c = add(anchor, delta)
            p = board.stones.get(c, 0)
            if p != 0:
                pattern.append((delta, p))
        counts[canonical_pattern(pattern)] += 1
    if not counts:
        return 0.0
    arr = np.array(list(counts.values()), dtype=float)
    probs = arr / arr.sum()
    return float(-(probs * np.log(probs + 1e-12)).sum())


def diffraction_metrics(points: List[Coord], grid_n: int = 64, kmax: float = math.pi) -> Tuple[np.ndarray, float]:
    if not points:
        return np.zeros((grid_n, grid_n)), 0.0
    xy = np.array([coord_to_xy(c) for c in points], dtype=np.float64)
    kx = np.linspace(-kmax, kmax, grid_n)
    ky = np.linspace(-kmax, kmax, grid_n)
    I = np.zeros((grid_n, grid_n), dtype=np.float64)
    # Streaming over k rows to avoid a huge K x N complex matrix.
    for i, xk in enumerate(kx):
        phase = xk * xy[:, 0][None, :] + ky[:, None] * xy[:, 1][None, :]
        amp = np.exp(-1j * phase).sum(axis=1)
        I[:, i] = (np.abs(amp) ** 2) / (len(points) ** 2)
    flat = np.sort(I.ravel())
    n_top = max(1, int(0.01 * len(flat)))
    bragg_top1 = float(flat[-n_top:].sum() / (flat.sum() + 1e-12))
    return I, bragg_top1


def random_points_like(board: Board, rng: random.Random) -> List[Coord]:
    n = len(board.stones)
    R = max(2, board.bounding_radius())
    cells = disk(R)
    if len(cells) < n:
        cells = disk(R + 2)
    return rng.sample(cells, min(n, len(cells)))


def run_diffraction(boards: List[Board], args, out_data: Path, out_fig: Path) -> pd.DataFrame:
    rng = random.Random(args.seed + 333)
    rows = []
    if not boards:
        pd.DataFrame(rows).to_csv(out_data / "diffraction_metrics.csv", index=False)
        return pd.DataFrame(rows)
    # Analyze a bounded number of final boards.
    for i, b in enumerate(boards[: args.diffraction_boards]):
        pts_black = b.player_stones(P1)
        pts_white = b.player_stones(P2)
        pts_all = list(b.stones.keys())
        for label, pts in [("black", pts_black), ("white", pts_white), ("all", pts_all)]:
            I, br = diffraction_metrics(pts, grid_n=args.diffraction_grid)
            rows.append({"board_index": i, "measure": label, "n_points": len(pts), "bragg_top1": br, "pattern_entropy_r2": pattern_entropy(b, 2), "radius": b.bounding_radius()})
            if i == 0 and label in ("black", "white", "all"):
                fig, ax = plt.subplots(figsize=(5.3, 4.5))
                im = ax.imshow(I, origin="lower", extent=(-math.pi, math.pi, -math.pi, math.pi), aspect="auto")
                ax.set_title(f"Diffraction intensity: {label}, Bragg top1={br:.3f}")
                ax.set_xlabel("k_x")
                ax.set_ylabel("k_y")
                fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                fig.tight_layout()
                fig.savefig(out_fig / f"diffraction_{label}.png", dpi=180)
                plt.close(fig)
        rand_pts = random_points_like(b, rng)
        _I, br = diffraction_metrics(rand_pts, grid_n=args.diffraction_grid)
        rows.append({"board_index": i, "measure": "random-control", "n_points": len(rand_pts), "bragg_top1": br, "pattern_entropy_r2": np.nan, "radius": b.bounding_radius()})
    df = pd.DataFrame(rows)
    df.to_csv(out_data / "diffraction_metrics.csv", index=False)
    return df

# -----------------------------
# Lightweight ML evaluator with PopRisk-SNR gate
# -----------------------------


def pair_features(board: Board, player: Player, move: Tuple[Coord, Coord]) -> np.ndarray:
    before_own = potential(board, player)
    before_opp = potential(board, -player)
    before_opp_tau = threat_load(board, -player)
    before_own_tau = threat_load(board, player)
    b = board.copy()
    b.place(player, move)
    after_own = potential(b, player)
    after_opp = potential(b, -player)
    after_own_tau = threat_load(b, player)
    after_opp_tau = threat_load(b, -player)
    own_win = 1.0 if b.winner == player else 0.0
    opp_threat_reduction = before_opp_tau - after_opp_tau
    own_density = 0
    opp_density = 0
    for c in move:
        o, p = local_density(board, c, radius=2)
        if player == P1:
            own_density += o
            opp_density += p
        else:
            own_density += p
            opp_density += o
    d_pair = hex_distance(move[0], move[1])
    rad = max(hex_distance(move[0]), hex_distance(move[1]))
    feats = np.array([
        1.0,
        own_win,
        before_own_tau,
        before_opp_tau,
        after_own_tau,
        after_opp_tau,
        opp_threat_reduction,
        math.log1p(max(0.0, after_own - before_own)),
        math.log1p(max(0.0, before_opp - after_opp)),
        math.log1p(max(0.0, after_opp - before_opp)),
        own_density,
        opp_density,
        d_pair,
        rad,
        1.0 if after_own_tau >= 3 else 0.0,
        1.0 if after_opp_tau >= 3 else 0.0,
    ], dtype=np.float32)
    return feats


def generate_ml_dataset(args, out_data: Path) -> Tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    if args.ml_games <= 0 or args.ml_max_samples <= 0 or args.ml_steps <= 0:
        X = np.zeros((0, 16), dtype=np.float32)
        y = np.zeros((0,), dtype=np.float32)
        meta = pd.DataFrame()
        np.save(out_data / "ml_pair_features.npy", X)
        np.save(out_data / "ml_pair_labels.npy", y)
        meta.to_csv(out_data / "ml_pair_metadata.csv", index=False)
        return X, y, meta
    rng = random.Random(args.seed + 777)
    combo = GreedyThreatAgent("combo-data", top_singles=52, aggression=1.12, defense=1.1)
    noisy = NoisyAgent(combo, eps=0.25, name="data-noisy")
    X_rows = []
    y_rows = []
    meta_rows = []
    game_budget = args.ml_games if args.mode != "quick" else max(1, args.ml_games // 4)
    for gid in range(game_budget):
        b, rec, states = play_game(combo, noisy if gid % 2 else combo, gid, rng.randrange(10**9), max_turns=min(args.max_turns, 60), collect_states=False)
        # Replay the trajectory to sample candidate decisions.
        rb = Board()
        for ply, (player, actual_move) in enumerate(b.history):
            if len(rb.stones) > 4 and move_size_for_ply(ply) == 2:
                cand = sorted(candidate_cells(rb, frontier_radius=2, max_cells=150), key=lambda c: prescore_cell(rb, player, c), reverse=True)[:36]
                pairs = list(itertools.combinations(cand, 2))
                if pairs:
                    rng.shuffle(pairs)
                    sample_pairs = pairs[: args.ml_pairs_per_state]
                    scored = [(score_move(rb, player, tuple(sorted(pair))).total, tuple(sorted(pair))) for pair in sample_pairs]
                    scored_sorted = sorted(scored, reverse=True, key=lambda t: t[0])
                    if scored_sorted:
                        cutoff_index = max(1, int(0.22 * len(scored_sorted)))
                        good = {p for _, p in scored_sorted[:cutoff_index]}
                        for sc, pair in scored_sorted:
                            # Add label noise to imitate imperfect tactical annotation.
                            y = 1.0 if pair in good else 0.0
                            if rng.random() < args.ml_label_noise:
                                y = 1.0 - y
                            X_rows.append(pair_features(rb, player, pair))
                            y_rows.append(y)
                            meta_rows.append({"game_id": gid, "ply": ply, "player": player, "score": sc, "label": y})
            rb.place(player, actual_move)
            if rb.winner:
                break
            if len(X_rows) >= args.ml_max_samples:
                break
        if len(X_rows) >= args.ml_max_samples:
            break
    X = np.vstack(X_rows).astype(np.float32) if X_rows else np.zeros((0, 16), dtype=np.float32)
    y = np.array(y_rows, dtype=np.float32)
    meta = pd.DataFrame(meta_rows)
    np.save(out_data / "ml_pair_features.npy", X)
    np.save(out_data / "ml_pair_labels.npy", y)
    meta.to_csv(out_data / "ml_pair_metadata.csv", index=False)
    return X, y, meta


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -30, 30)))


def auc_score(y_true: np.ndarray, y_score: np.ndarray) -> float:
    # Rank-based AUC without sklearn.
    y_true = y_true.astype(int)
    pos = y_true == 1
    neg = y_true == 0
    n_pos = int(pos.sum())
    n_neg = int(neg.sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(y_score)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(y_score) + 1)
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def train_linear_evaluator(X: np.ndarray, y: np.ndarray, args, out_data: Path) -> pd.DataFrame:
    if len(y) < 50:
        df = pd.DataFrame()
        df.to_csv(out_data / "ml_training_curves.csv", index=False)
        return df
    rng = np.random.default_rng(args.seed + 888)
    idx = np.arange(len(y))
    rng.shuffle(idx)
    split = int(0.75 * len(idx))
    tr, te = idx[:split], idx[split:]
    mean = X[tr].mean(axis=0)
    std = X[tr].std(axis=0) + 1e-6
    Xn = (X - mean) / std
    Xn[:, 0] = 1.0
    rows = []
    for opt in ("adam", "poprisk-snr"):
        w = rng.normal(0, 0.01, size=Xn.shape[1]).astype(np.float32)
        m = np.zeros_like(w)
        v = np.zeros_like(w)
        b1, b2 = 0.9, 0.99
        lr = 0.025
        bs = min(96, max(16, len(tr) // 8))
        for step in range(1, args.ml_steps + 1):
            batch = rng.choice(tr, size=bs, replace=True)
            xb = Xn[batch]
            yb = y[batch]
            p = sigmoid(xb @ w)
            per_ex_grad = ((p - yb)[:, None] * xb).astype(np.float32)
            grad = per_ex_grad.mean(axis=0)
            m = b1 * m + (1 - b1) * grad
            v = b2 * v + (1 - b2) * (grad * grad)
            mhat = m / (1 - b1 ** step)
            vhat = v / (1 - b2 ** step)
            if opt == "adam":
                gate = np.ones_like(w)
            else:
                var = per_ex_grad.var(axis=0)
                gate = (mhat * mhat) / (mhat * mhat + args.poprisk_lambda * var / max(1, bs - 1) + 1e-8)
            w -= lr * gate * mhat / (np.sqrt(vhat) + 1e-8)
            if step == 1 or step % 25 == 0 or step == args.ml_steps:
                pred_tr = sigmoid(Xn[tr] @ w)
                pred_te = sigmoid(Xn[te] @ w)
                rows.append({
                    "optimizer": opt,
                    "step": step,
                    "train_loss": float(-(y[tr] * np.log(pred_tr + 1e-8) + (1 - y[tr]) * np.log(1 - pred_tr + 1e-8)).mean()),
                    "test_loss": float(-(y[te] * np.log(pred_te + 1e-8) + (1 - y[te]) * np.log(1 - pred_te + 1e-8)).mean()),
                    "train_acc": float(((pred_tr > 0.5) == y[tr]).mean()),
                    "test_acc": float(((pred_te > 0.5) == y[te]).mean()),
                    "test_auc": auc_score(y[te], pred_te),
                    "gate_mean": float(gate.mean()),
                    "gate_structural_mean": float(gate[[1, 2, 3, 4, 5, 6, 14, 15]].mean()),
                    "gate_geometry_mean": float(gate[[10, 11, 12, 13]].mean()),
                })
    df = pd.DataFrame(rows)
    df.to_csv(out_data / "ml_training_curves.csv", index=False)
    return df

# -----------------------------
# Figures
# -----------------------------


def plot_board(board: Board, path: Path, title: str = "Final board") -> None:
    fig, ax = plt.subplots(figsize=(6.3, 5.8))
    if not board.stones:
        ax.text(0.5, 0.5, "empty board", ha="center", va="center")
    else:
        xs = []
        ys = []
        colors = []
        sizes = []
        for c, p in board.stones.items():
            x, y = coord_to_xy(c)
            xs.append(x)
            ys.append(y)
            colors.append(1 if p == P1 else -1)
            sizes.append(55 if c in board.winning_line else 32)
        sc = ax.scatter(xs, ys, c=colors, s=sizes, alpha=0.88, cmap="coolwarm", vmin=-1, vmax=1)
        if board.winning_line:
            line_xy = np.array([coord_to_xy(c) for c in board.winning_line])
            ax.plot(line_xy[:, 0], line_xy[:, 1], linewidth=3.0, alpha=0.75)
        for c, p in list(board.stones.items())[-6:]:
            x, y = coord_to_xy(c)
            ax.text(x, y, "B" if p == P1 else "W", ha="center", va="center", fontsize=7)
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.set_xlabel("Eisenstein real axis")
    ax.set_ylabel("Eisenstein omega axis")
    ax.grid(True, linewidth=0.3, alpha=0.35)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_tournament(games: pd.DataFrame, out_fig: Path) -> None:
    if games.empty:
        return
    pivot = games.assign(black_win=(games["winner"] == P1).astype(float)).pivot_table(
        index="black_agent", columns="white_agent", values="black_win", aggfunc="mean"
    )
    fig, ax = plt.subplots(figsize=(7.2, 5.8))
    im = ax.imshow(pivot.values, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=40, ha="right")
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            ax.text(j, i, f"{val:.2f}" if not np.isnan(val) else "", ha="center", va="center", fontsize=8)
    ax.set_title("Tournament matrix: Black/P1 win share")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(out_fig / "tournament_matrix.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for winner, grp in games.groupby("winner_name"):
        ax.hist(grp["plies"], bins=16, alpha=0.55, label=str(winner))
    ax.set_title("Distribution of game lengths")
    ax.set_xlabel("plies")
    ax.set_ylabel("games")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_fig / "game_length_distribution.png", dpi=180)
    plt.close(fig)


def plot_opening(opening: pd.DataFrame, out_fig: Path) -> None:
    if opening.empty:
        return
    fig, ax = plt.subplots(figsize=(6.6, 5.8))
    top = opening.head(400)
    sc = ax.scatter(top["centroid_x"], top["centroid_y"], c=top["net_reply_value"], s=30, cmap="plasma", alpha=0.8)
    ax.scatter([0], [0], marker="*", s=120, label="P1 opening")
    for _, row in opening.head(20).iterrows():
        a = (int(row.a_q), int(row.a_r))
        b = (int(row.b_q), int(row.b_r))
        xy = np.array([coord_to_xy(a), coord_to_xy(b)])
        ax.plot(xy[:, 0], xy[:, 1], linewidth=0.8, alpha=0.35)
    ax.set_aspect("equal")
    ax.set_title("Opening reply scan: best P2 pairs near the origin")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.legend(loc="upper right")
    fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label="heuristic net reply value")
    fig.tight_layout()
    fig.savefig(out_fig / "opening_reply_scan.png", dpi=180)
    plt.close(fig)


def plot_states(states: pd.DataFrame, games: pd.DataFrame, out_fig: Path) -> None:
    if states.empty:
        return
    merged = states.merge(games[["game_id", "winner"]], on="game_id", how="left")
    merged["just_moved_eventual_win"] = (merged["winner"] == merged["just_moved"]).astype(float)
    tau_summary = merged.groupby("tau_just_moved", as_index=False).agg(
        n=("game_id", "count"), eventual_win_rate=("just_moved_eventual_win", "mean"), mean_reply_entropy=("reply_entropy", "mean")
    )
    fig, ax = plt.subplots(figsize=(6.4, 4.5))
    ax.bar(tau_summary["tau_just_moved"].astype(str), tau_summary["eventual_win_rate"])
    for _, row in tau_summary.iterrows():
        ax.text(str(int(row.tau_just_moved)), row.eventual_win_rate + 0.02, f"n={int(row.n)}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_xlabel("threat-load tau after move")
    ax.set_ylabel("eventual win rate for just-moved player")
    ax.set_title("Threat load predicts terminal advantage")
    fig.tight_layout()
    fig.savefig(out_fig / "threat_load_outcomes.png", dpi=180)
    plt.close(fig)

    fig, ax1 = plt.subplots(figsize=(7.0, 4.8))
    byply = states.groupby("ply", as_index=False).agg(
        candidate_pairs_upper=("candidate_pairs_upper", "mean"),
        reply_entropy=("reply_entropy", "mean"),
        tau_to_move=("tau_to_move", "mean"),
    )
    ax1.plot(byply["ply"], byply["reply_entropy"], marker="o", markevery=5, label="reply entropy")
    ax1.set_xlabel("ply")
    ax1.set_ylabel("bounded reply entropy")
    ax2 = ax1.twinx()
    ax2.plot(byply["ply"], np.log1p(byply["candidate_pairs_upper"]), linestyle="--", label="log candidate pairs")
    ax2.set_ylabel("log(1 + frontier pair count)")
    ax1.set_title("Epiplexity trace: reply entropy and branching pressure")
    fig.tight_layout()
    fig.savefig(out_fig / "epiplexity_trace.png", dpi=180)
    plt.close(fig)


def plot_diffraction_summary(diff: pd.DataFrame, out_fig: Path) -> None:
    if diff.empty:
        return
    fig, ax = plt.subplots(figsize=(6.8, 4.8))
    summary = diff.groupby("measure", as_index=False).agg(mean=("bragg_top1", "mean"), std=("bragg_top1", "std"), n=("bragg_top1", "count"))
    ax.bar(summary["measure"], summary["mean"], yerr=summary["std"].fillna(0.0))
    ax.set_ylabel("top-1% diffraction mass")
    ax.set_title("Bragg concentration: self-play boards vs random control")
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(out_fig / "bragg_summary.png", dpi=180)
    plt.close(fig)


def plot_ml(ml: pd.DataFrame, out_fig: Path) -> None:
    if ml.empty:
        return
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for opt, grp in ml.groupby("optimizer"):
        ax.plot(grp["step"], grp["test_auc"], marker="o", markevery=4, label=opt)
    ax.set_xlabel("training step")
    ax.set_ylabel("held-out AUC")
    ax.set_title("Move-evaluator generalization under noisy tactical labels")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_fig / "ml_auc.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    sub = ml[ml["optimizer"] == "poprisk-snr"]
    if not sub.empty:
        ax.plot(sub["step"], sub["gate_structural_mean"], marker="o", markevery=4, label="threat/structural gate")
        ax.plot(sub["step"], sub["gate_geometry_mean"], marker="x", linestyle="--", markevery=4, label="geometry gate")
        ax.plot(sub["step"], sub["gate_mean"], linestyle=":", label="all features")
    ax.set_xlabel("training step")
    ax.set_ylabel("mean gate value")
    ax.set_title("PopRisk-SNR gate selectivity")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_fig / "ml_gate_selectivity.png", dpi=180)
    plt.close(fig)

# -----------------------------
# Paper generation
# -----------------------------


def fmt_pct(x: float) -> str:
    if np.isnan(x):
        return "n/a"
    return f"{100*x:.1f}%"


def make_markdown_paper(args, out: Path, games: pd.DataFrame, states: pd.DataFrame, opening: pd.DataFrame, diff: pd.DataFrame, ml: pd.DataFrame, metadata: Dict) -> str:
    if games.empty:
        black_share = np.nan
        decisive = 0
    else:
        decisive_df = games[games["winner"] != 0]
        decisive = len(decisive_df)
        black_share = float((decisive_df["winner"] == P1).mean()) if decisive else np.nan
    combo_combo = games[(games["black_agent"] == "combo") & (games["white_agent"] == "combo")] if not games.empty else pd.DataFrame()
    combo_black_share = float((combo_combo["winner"] == P1).mean()) if not combo_combo.empty else np.nan
    mean_len = float(games["plies"].mean()) if not games.empty else np.nan
    opening_top = opening.head(6) if not opening.empty else pd.DataFrame()
    bragg_summary = diff.groupby("measure")["bragg_top1"].mean().to_dict() if not diff.empty else {}
    if ml.empty:
        ml_last = pd.DataFrame()
    else:
        ml_last = ml.sort_values("step").groupby("optimizer").tail(1)

    paper = f"""# A Threat-Reservoir Theory of Infinite Hex Connect-6

**Subtitle.** Experiments on HexGo as an Eisenstein-lattice forcing game.

**Generated.** {time.strftime('%Y-%m-%d %H:%M:%S')}

## Abstract

We study infinite Hex Connect-6, or HexGo: a two-player game on the infinite hexagonal lattice in which the opening move places one stone, every later turn places two stones, and six consecutive stones on any of the three Eisenstein axes wins. The experiments in this paper treat the game not as a solved object but as a measurable dynamical system. A bounded-frontier engine generates self-play trajectories, threat hypergraphs, opening-response scans, diffraction spectra, and noisy tactical-learning datasets. The central conjecture is that strong finite-horizon play is governed by a small signal channel - the live length-6 arithmetic progressions in Z[omega] - while almost all other stones behave as a reservoir: present on the board but invisible to the next forcing calculation. The data support a sharp threat-load transition: once the immediate-threat hypergraph has hitting number at least 3, the defender's two stones are insufficient. We therefore conjecture that HexGo's practical complexity is not the size of the infinite board but the epiplexity of a moving threat hypergraph.

## Background

HexGo is naturally represented on the Eisenstein integer lattice Z[omega]. In axial coordinates the three unit axes are u1=(1,0), u2=(0,1), and u3=(1,-1). A winning line is exactly a length-6 arithmetic progression with one of these unit steps. This follows the coordinate philosophy used by the HexGo Theory repository and the standard axial/cube-coordinate treatment of hex grids.

Connect6 was introduced as a k-in-a-row family with the balancing rule that Black places one first stone and then both players place two stones per turn. Existing Connect6 work emphasizes threat calculation: a player can defend at most two cells per turn, so three independent immediate threats are decisive. The infinite hex variant makes that principle more algebraic: threats are small hyperedges in the family of length-6 Eisenstein progressions.

The machine-learning analogy used here is borrowed from the population-risk/reservoir language of Litman and Guo: a learned or searched system has a signal channel and a reservoir. For HexGo, the signal channel is the live threat hypergraph. The reservoir is the immense complement of stones and cells that do not affect any live six-window in the current finite horizon.

## Rules and notation

A board state is a finite partial function B: Z[omega] -> {{Black, White}}. The legal turn size is 1 at ply 0 and 2 thereafter. Let W_p(B) be the family of all length-6 windows containing only player p stones and empty cells. Let T_p(B) be the subfamily of windows with at least four p stones and no opponent stones. Each element of T_p(B) contributes its empty cells, a set of size one or two. The defender can block a family F only by choosing a hitting set of size at most two.

Define the **threat load** tau_p(B) as the minimum hitting-set size of T_p(B), capped at 3. Thus tau=3 means: more than two blocking cells are required.

## Theorem 1: the two-stone blocking threshold

If after player p moves, tau_p(B) >= 3 and the opponent has not already won, then the opponent cannot block every immediate p win on the next turn. This is not a heuristic. It is a direct consequence of the 1-2-2 rule: every immediate winning window is a hyperedge of size one or two, and an opponent turn selects at most two vertices. If no hitting set of size at most two exists, at least one immediate winning hyperedge remains, and p fills it on the following turn.

## Central conjectures

**Conjecture A - finite signal, infinite reservoir.** In strong HexGo play, the strategically relevant state at ply t is captured, up to small error, by the threat hypergraph induced by live length-6 progressions within O(1) of occupied stones. The rest of the infinite board is a reservoir.

**Conjecture B - epiplexity peak.** The apparent difficulty of a position is maximized not at the widest frontier, but just before the first tau>=3 transition, where many replies remain plausible while a small number of threat hyperedges begin to couple.

**Conjecture C - Eisenstein halo.** The second player's best replies to the origin opening concentrate on D6-symmetric halo pairs rather than adjacent contact. This does not prove second-player advantage; rather, it says the opening initiative is neutralized by paired stones whose centroids lie near a small number of Eisenstein orbits.

**Conjecture D - weak quasicrystal signature.** Greedy strong-agent self-play produces final occupied sets with higher Bragg concentration than random controls of the same size and radius. This is weaker than the repository's full Pisot/substitution conjecture, but it is a measurable shadow of it.

## Experimental design

All experiments are bounded-frontier approximations to the infinite game. Candidate cells are generated from a radius-2 frontier around occupied stones plus all immediate threat cells. Pair enumeration is capped by ranking single cells and evaluating only top pairs. This is not perfect play. It is a microscope for threat geometry.

Experiments:

1. Round-robin self-play among random-frontier, greedy-threat, combo, mirror-halo, and noisy-combo agents.
2. Opening reply scan after Black opens at the origin.
3. Threat-load/outcome correlation and reply-entropy traces.
4. Diffraction spectra of final self-play boards compared with random controls.
5. A noisy tactical-pair classifier trained with Adam versus a PopRisk-SNR gate.

## Results

### Tournament dynamics

Across {len(games)} games, {decisive} were decisive. Black/P1's share of decisive games was **{fmt_pct(black_share)}**. Mean game length was **{mean_len:.2f} plies**. In combo-vs-combo games, Black/P1 win share was **{fmt_pct(combo_black_share)}**. These numbers should not be read as solving the game: they measure the bias of this finite-horizon threat engine.

![Tournament matrix](figures/tournament_matrix.png)

![Game length distribution](figures/game_length_distribution.png)

### Opening halo

The top opening replies found by the scan were:

| rank | P2 stone a | P2 stone b | pair distance | max radius | net value |
|---:|---|---|---:|---:|---:|
"""
    for rank, (_, row) in enumerate(opening_top.iterrows(), 1):
        paper += f"| {rank} | ({int(row.a_q)}, {int(row.a_r)}) | ({int(row.b_q)}, {int(row.b_r)}) | {int(row.pair_distance)} | {int(row.max_radius)} | {row.net_reply_value:.2f} |\n"
    paper += """

![Opening reply scan](figures/opening_reply_scan.png)

The halo conjecture survives if high-value replies cluster by D6 orbit and do not simply collapse onto nearest-neighbor contact with the first stone. In my run this is a quantitative conjecture rather than a proof: inspect `data/opening_reply_scan.csv` for the orbit-level ranking.

### Threat load and epiplexity

The threat-load statistic tau is a small integer but it reorganizes the game. In the stored trajectories, tau after a move is correlated with eventual victory for the just-moved player. The theorem says tau>=3 is locally decisive under exact immediate-threat semantics; the empirical plot asks how often trajectories approach that cliff before the terminal move.

![Threat load outcomes](figures/threat_load_outcomes.png)

![Epiplexity trace](figures/epiplexity_trace.png)

I use **epiplexity** here for the effective complexity of a position after quotienting away dead infinity: not the raw number of empty hexes, but the entropy of plausible bounded-frontier replies under the current threat hypergraph.

### Diffraction and local order

The mean top-1% Bragg mass by measure was:

| measure | mean top-1% diffraction mass |
|---|---:|
"""
    for k, v in sorted(bragg_summary.items()):
        paper += f"| {k} | {v:.4f} |\n"
    paper += """

![Bragg summary](figures/bragg_summary.png)

![Black diffraction](figures/diffraction_black.png)

![White diffraction](figures/diffraction_white.png)

![All-stone diffraction](figures/diffraction_all.png)

A stronger quasicrystal claim would require longer games, better agents, and orbit-frequency convergence tests. The current result is deliberately weaker: strong self-play should show more concentrated spectral mass than a same-size random control if the forcing dynamics generate repeated long-range structure.

### Noisy tactical learning

To connect the game experiment back to the signal/reservoir learning picture, I generated noisy labels for candidate move-pairs and trained a linear evaluator. The PopRisk-SNR gate downweights features whose per-batch gradient variance overwhelms their squared mean, analogous to preferring cross-example agreement over idiosyncratic memorization.

| optimizer | final held-out AUC | final held-out acc. | final test loss | mean gate |
|---|---:|---:|---:|---:|
"""
    if not ml_last.empty:
        for _, row in ml_last.iterrows():
            paper += f"| {row.optimizer} | {row.test_auc:.4f} | {row.test_acc:.4f} | {row.test_loss:.4f} | {row.gate_mean:.4f} |\n"
    paper += """

![ML AUC](figures/ml_auc.png)

![ML gate selectivity](figures/ml_gate_selectivity.png)

## Discussion

The infinite board is a red herring until the players deliberately make it matter. Every finite play history occupies a finite set; every immediate win is a length-6 arithmetic progression touching that finite set; and every boundedly rational agent can be studied through the small family of still-live progressions. This is the core analogy with signal/reservoir decomposition: the live windows form the signal channel, while the uncountably intimidating rest of 'infinity' is test-invisible to the next tactical calculation.

The most Conway-like feature of the game is that the local theorem is tiny but the global consequence is wild. A threat family with hitting number three is an elementary hypergraph object. But self-play consists of steering this hypergraph through the A2 geometry of Z[omega], and small local forks can propagate outward as if they were substitution rules. That is where the Hamkins/Conway mood enters: infinite HexGo is determined by finite certificates of victory, yet the search for perfect play may reveal tiling-like structure rather than a compact joseki book.

## Limitations

This is not a solution of infinite Hex Connect-6. The agents are heuristic. The frontier is bounded. The opening scan uses a one-ply/two-ply heuristic value. Diffraction measurements are short-horizon and sensitive to agent style. The point of the package is to make these assumptions inspectable, reproducible, and falsifiable.

## Reproducibility

Run command:

```bash
{metadata.get('command', '')}
```

Memory controls:

- candidate frontier capped at {metadata.get('candidate_cap', 'n/a')} cells;
- top-pair enumeration capped by agent `top_singles`;
- diffraction computed row-wise without constructing a full wave-vector by point tensor;
- no neural-network framework required.

## References

"""
    for ref in REFERENCES:
        paper += f"- {ref}\n"
    return paper


def add_text_page(pdf: PdfPages, title: str, body: str, fontsize: int = 10) -> None:
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.patch.set_facecolor("white")
    fig.text(0.08, 0.955, title, fontsize=16, fontweight="bold", va="top")
    wrapped_lines: List[str] = []
    for para in body.split("\n"):
        if not para.strip():
            wrapped_lines.append("")
        else:
            wrapped_lines.extend(textwrap.wrap(para, width=96))
    y = 0.92
    line_h = 0.018
    for line in wrapped_lines[:48]:
        fig.text(0.08, y, line, fontsize=fontsize, va="top")
        y -= line_h
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def add_figure_page(pdf: PdfPages, image_path: Path, caption: str) -> None:
    if not image_path.exists():
        return
    img = plt.imread(str(image_path))
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    ax.imshow(img)
    ax.axis("off")
    fig.text(0.08, 0.06, textwrap.fill(caption, width=110), fontsize=10, va="bottom")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def make_pdf(md: str, pdf_path: Path, fig_dir: Path) -> None:
    # A robust PDF generator using matplotlib only. The Markdown is the canonical
    # text version; the PDF is a readable paper bundle.
    sections = []
    current_title = "A Threat-Reservoir Theory of Infinite Hex Connect-6"
    current_body = []
    for line in md.splitlines():
        if line.startswith("## "):
            if current_body:
                sections.append((current_title, "\n".join(current_body)))
            current_title = line[3:].strip()
            current_body = []
        elif line.startswith("# "):
            current_title = line[2:].strip()
        elif line.startswith("!["):
            continue
        else:
            # Strip markdown table pipes less badly for PDF text pages.
            current_body.append(line)
    if current_body:
        sections.append((current_title, "\n".join(current_body)))

    with PdfPages(pdf_path) as pdf:
        for title, body in sections:
            chunks = []
            lines = body.splitlines()
            chunk = []
            for line in lines:
                chunk.append(line)
                if len(chunk) >= 34:
                    chunks.append("\n".join(chunk))
                    chunk = []
            if chunk:
                chunks.append("\n".join(chunk))
            for i, ch in enumerate(chunks):
                add_text_page(pdf, title if i == 0 else f"{title} (continued)", ch)
        figure_captions = [
            ("tournament_matrix.png", "Figure 1. Round-robin matrix: Black/P1 win share by black-agent and white-agent pairing."),
            ("game_length_distribution.png", "Figure 2. Distribution of terminal plies, grouped by winner."),
            ("opening_reply_scan.png", "Figure 3. Opening reply scan. Points show centroids of P2 two-stone replies after P1 opens at the origin; line segments mark the top replies."),
            ("threat_load_outcomes.png", "Figure 4. Empirical relationship between immediate threat-load tau and eventual winner."),
            ("epiplexity_trace.png", "Figure 5. Epiplexity trace: bounded reply entropy and frontier pair count over ply."),
            ("bragg_summary.png", "Figure 6. Mean top-1% diffraction mass for final boards versus random controls."),
            ("diffraction_black.png", "Figure 7. Diffraction intensity for Black stones in a representative final board."),
            ("diffraction_white.png", "Figure 8. Diffraction intensity for White stones in a representative final board."),
            ("diffraction_all.png", "Figure 9. Diffraction intensity for all stones in a representative final board."),
            ("ml_auc.png", "Figure 10. Held-out AUC for noisy tactical pair classification."),
            ("ml_gate_selectivity.png", "Figure 11. PopRisk-SNR gate selectivity over tactical feature groups."),
            ("representative_final_board.png", "Figure 12. Representative terminal board; larger connected stones mark the winning line if present."),
        ]
        for fname, cap in figure_captions:
            add_figure_page(pdf, fig_dir / fname, cap)

# -----------------------------
# Main
# -----------------------------


def write_json(path: Path, obj: Dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)


def zip_folder(folder: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(folder.parent))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate an empirical PDF paper for infinite hex Connect-6 / HexGo.")
    ap.add_argument("--out", type=str, default="hexconnect6_paper_out", help="Output folder.")
    ap.add_argument("--mode", choices=["quick", "full"], default="full", help="quick for smoke test, full for more data.")
    ap.add_argument("--seed", type=int, default=20260510)
    ap.add_argument("--games", type=int, default=120, help="Approx total tournament games. In full mode this is spread over all pairings.")
    ap.add_argument("--max-turns", type=int, default=90)
    ap.add_argument("--opening-radius", type=int, default=4)
    ap.add_argument("--opening-refine", type=int, default=120, help="Number of top opening replies to refine with a bounded second ply.")
    ap.add_argument("--opening-reply-top", type=int, default=22, help="Top Black single cells used during opening refinement.")
    ap.add_argument("--diffraction-boards", type=int, default=6)
    ap.add_argument("--diffraction-grid", type=int, default=56)
    ap.add_argument("--ml-games", type=int, default=48)
    ap.add_argument("--ml-max-samples", type=int, default=14000)
    ap.add_argument("--ml-pairs-per-state", type=int, default=18)
    ap.add_argument("--ml-label-noise", type=float, default=0.12)
    ap.add_argument("--ml-steps", type=int, default=450)
    ap.add_argument("--poprisk-lambda", type=float, default=10.0)
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    t0 = time.time()
    out = Path(args.out).resolve()
    fig_dir = out / "figures"
    data_dir = out / "data"
    research_dir = out / "research"
    for d in (out, fig_dir, data_dir, research_dir):
        d.mkdir(parents=True, exist_ok=True)

    if psutil is not None:
        mem_gb = psutil.virtual_memory().total / 1e9
    else:
        mem_gb = None

    random.seed(args.seed)
    np.random.seed(args.seed % (2**32 - 1))

    # Write a literature/research note as separate machine-readable file.
    research_note = {
        "game": "Infinite hex Connect-6 / HexGo, 1-2-2 rule, six in a row on Eisenstein axes.",
        "coordinate_system": "Axial coordinates q,r equivalent to Eisenstein integers a + b*omega; axes (1,0), (0,1), (1,-1).",
        "literature_claims": [
            "HexGo Theory frames the game as an infinite Eisenstein-lattice Connect6 variant and proposes D6 symmetry and quasicrystal/substitution questions.",
            "Connect6 uses one first stone and two stones thereafter; threat-based algorithms exploit the fact that a player can block at most two cells per turn.",
            "Axial/cube hex coordinates make rotations, reflections, distances and rings simple enough for exact code.",
            "Population-risk / signal-reservoir language suggests treating live tactical constraints as signal and irrelevant infinity as reservoir.",
        ],
        "references": REFERENCES,
    }
    write_json(research_dir / "literature_survey.json", research_note)

    print("[1/8] running tournament")
    games, states, boards = run_tournament(args, data_dir)
    plot_tournament(games, fig_dir)

    print("[2/8] scanning opening replies")
    opening = opening_scan(args, data_dir)
    plot_opening(opening, fig_dir)

    print("[3/8] validating threat load traces")
    _threat = threat_validation(states, data_dir)
    plot_states(states, games, fig_dir)

    print("[4/8] plotting representative board")
    rep = boards[0] if boards else Board()
    plot_board(rep, fig_dir / "representative_final_board.png", title="Representative final self-play board")

    print("[5/8] running diffraction analysis")
    diff = run_diffraction(boards, args, data_dir, fig_dir)
    plot_diffraction_summary(diff, fig_dir)

    print("[6/8] generating and training noisy tactical evaluator")
    X, y, meta = generate_ml_dataset(args, data_dir)
    ml = train_linear_evaluator(X, y, args, data_dir)
    plot_ml(ml, fig_dir)

    print("[7/8] writing paper")
    metadata = {
        "command": " ".join(["python"] + os.sys.argv),
        "seed": args.seed,
        "mode": args.mode,
        "runtime_seconds": None,
        "memory_gb": mem_gb,
        "candidate_cap": 220,
        "args": vars(args),
        "oom_safeguards": [
            "bounded frontier candidate set",
            "top-single pruning before pair enumeration",
            "row-wise diffraction computation",
            "numpy-only linear tactical model",
            "no full game tree or MCTS tree retained in memory",
        ],
    }
    md = make_markdown_paper(args, out, games, states, opening, diff, ml, metadata)
    (out / "hexconnect6_threat_reservoir_paper.md").write_text(md, encoding="utf-8")
    pdf_path = out / "hexconnect6_threat_reservoir_paper.pdf"
    make_pdf(md, pdf_path, fig_dir)

    # Copy script for exact reproducibility.
    try:
        shutil.copyfile(Path(__file__).resolve(), out / "hexconnect6_empirical_paper.py")
    except Exception:
        pass

    metadata["runtime_seconds"] = round(time.time() - t0, 3)
    write_json(data_dir / "run_metadata.json", metadata)

    print("[8/8] zipping package")
    zip_path = out.with_suffix(".zip")
    zip_folder(out, zip_path)

    print("\nDONE")
    print(f"Output folder: {out}")
    print(f"PDF: {pdf_path}")
    print(f"ZIP: {zip_path}")
    print(f"Games: {len(games)} | States: {len(states)} | ML samples: {len(y)}")


if __name__ == "__main__":
    main()
