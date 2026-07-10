#!/usr/bin/env python3
"""
RZ-BDPN benchmark for 1-2-2 Infinite Hex Connect-6 on the A2 hex lattice.

RZ-BDPN = Relevance-Zone Branching-Debt Proof-Number pre-benchmark.

This does not yet implement full proof-number search. It tests the prerequisite
claim from the synthesis:

    Can AP-flow, obligation support, and branching debt generate small relevance
    zones that retain terminal / forcing continuations?

The benchmark compares relevance-zone generators:

  naive_radius
      Empty cells near existing stones.

  ap_flow
      Top cells by pulled-back odd/even arithmetic-progression field.

  obligation_support
      Empty cells in currently-live near-threat progressions.

  branching_debt
      Cells and obligation support from top Black branching-debt candidate moves.

  combo
      Union of AP-flow, obligation support, and branching debt.

  oracle_upper
      Expensive upper-control zone based on reference candidate pairs.

For each sampled position, the script constructs a reference tactical target by
evaluating candidate Black moves with a costly local oracle:

    Black candidate -> White replies -> Black continuations

The reference target is not perfect play, but it is a reproducible benchmark for
whether a zone generator retains the interesting local tactical continuations.

Outputs:
  data/zone_metrics.csv
  data/reference_candidates.csv
  data/position_records.csv
  data/aggregate_zone_metrics.csv
  figures/*.png
  report.md
  benchmark_manifest.json

Designed for long local runs:
  - deterministic per-position seeds for resumability;
  - chunked CSV writes;
  - bounded candidate pools;
  - bitboard line/segment representation;
  - cached hitting-number computations.

Example:
  python rz_bdpn_benchmark.py --config configs/smoke.json
  python rz_bdpn_benchmark.py --config configs/overnight.json --resume
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import random
import time
import zipfile
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

Cell = Tuple[int, int]
DIRS: Tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))
NEIGH: Tuple[Cell, ...] = ((1,0),(-1,0),(0,1),(0,-1),(1,-1),(-1,1))


# ----------------------------- A2 geometry ----------------------------- #

def hex_dist(a: Cell, b: Cell = (0, 0)) -> int:
    dq, dr = a[0] - b[0], a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def add(a: Cell, d: Cell, k: int = 1) -> Cell:
    return (a[0] + d[0] * k, a[1] + d[1] * k)


def cells_in_radius(radius: int) -> List[Cell]:
    out: List[Cell] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                out.append((q, r))
    out.sort(key=lambda c: (hex_dist(c), c[0], c[1]))
    return out


def axial_to_xy(c: Cell) -> Tuple[float, float]:
    q, r = c
    return (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)


def rotate60(c: Cell) -> Cell:
    q, r = c
    return (-r, q + r)


def reflect(c: Cell) -> Cell:
    q, r = c
    return (r, q)


def transform(c: Cell, t: int) -> Cell:
    x = c
    for _ in range(t // 2):
        x = rotate60(x)
    return reflect(x) if t % 2 else x


def canonical_delta(d: Cell) -> Cell:
    return sorted({transform(d, t) for t in range(12)})[0]


def pair_shape(cells: Sequence[Cell], a: int, b: int) -> str:
    ca, cb = cells[a], cells[b]
    return str(canonical_delta((cb[0] - ca[0], cb[1] - ca[1])))


def pair_kind(shape: str) -> str:
    try:
        q, r = ast.literal_eval(shape)
    except Exception:
        return "unknown"
    d = hex_dist((q, r))
    if r == 0:
        return "short_rail" if d <= 2 else "long_rail" if d <= 4 else "bridge_rail"
    return "compact_kink" if d <= 2 else "bridge" if d <= 4 else "long_bridge"


@dataclass
class HexEnv:
    radius: int
    candidate_radius: int
    max_spread: int
    pad: int = 2

    def __post_init__(self):
        self.cells: List[Cell] = cells_in_radius(self.radius + self.pad)
        self.idx: Dict[Cell, int] = {c: i for i, c in enumerate(self.cells)}
        self.root: int = self.idx[(0, 0)]
        self.dist = np.array([hex_dist(c) for c in self.cells], dtype=int)
        self.play: List[int] = [self.idx[c] for c in cells_in_radius(self.candidate_radius)]
        self.xy = np.array([axial_to_xy(c) for c in self.cells], dtype=float)
        self.segments: List[int] = self._make_segments(self.radius + self.pad)
        self.seg_cells: List[List[int]] = [self.bits(mask) for mask in self.segments]
        self.seg_axis: List[int] = []
        self.cell_to_segments: List[List[int]] = [[] for _ in self.cells]

        for sid, mask in enumerate(self.segments):
            cs = self.seg_cells[sid]
            if len(cs) >= 2:
                a, b = self.cells[cs[0]], self.cells[cs[1]]
                d = (b[0] - a[0], b[1] - a[1])
                axis = DIRS.index(d) if d in DIRS else 0
            else:
                axis = 0
            self.seg_axis.append(axis)
            x = mask
            while x:
                lsb = x & -x
                self.cell_to_segments[lsb.bit_length() - 1].append(sid)
                x ^= lsb

        self.pairs: List[Tuple[int, int, int, float]] = []
        for ix, a in enumerate(self.play):
            ca = self.cells[a]
            for b in self.play[ix + 1:]:
                spread = hex_dist(ca, self.cells[b])
                if spread <= self.max_spread:
                    center = (self.dist[a] + self.dist[b]) / 2.0
                    self.pairs.append((a, b, spread, center))
        self.pairs.sort(key=lambda x: (x[3], x[2], x[0], x[1]))

    @staticmethod
    def bits(mask: int) -> List[int]:
        out: List[int] = []
        while mask:
            lsb = mask & -mask
            out.append(lsb.bit_length() - 1)
            mask ^= lsb
        return out

    def _make_segments(self, R: int) -> List[int]:
        universe = set(cells_in_radius(R))
        segs = set()
        for c in universe:
            for d in DIRS:
                seg = tuple(add(c, d, k) for k in range(6))
                if all(x in universe for x in seg):
                    m = 0
                    for x in seg:
                        m |= 1 << self.idx[x]
                    segs.add(m)
        return sorted(segs)

    def has_win(self, black: int, white: int, player: int) -> bool:
        mine = black if player == 1 else white
        return any((seg & mine) == seg for seg in self.segments)


# ------------------------- obligation hypergraphs ------------------------- #

@lru_cache(maxsize=1_000_000)
def hitting_number(edges: Tuple[int, ...], max_k: int = 8) -> int:
    edges = tuple(e for e in edges if e)
    if not edges:
        return 0

    universe, forced = 0, 0
    for e in edges:
        universe |= e
        if e.bit_count() == 1:
            forced |= e

    forced_count = forced.bit_count()
    if forced_count > max_k:
        return max_k + 1

    reduced = tuple(e for e in edges if not (e & forced))
    if not reduced:
        return forced_count

    def can_hit(rem_edges: Tuple[int, ...], chosen: int, slots: int) -> bool:
        rem = [e for e in rem_edges if not (e & chosen)]
        if not rem:
            return True
        if slots <= 0:
            return False

        # Greedy disjoint-edge lower bound.
        used, lower_bound = 0, 0
        for e in sorted(rem, key=lambda x: x.bit_count()):
            if not (e & used):
                used |= e
                lower_bound += 1
                if lower_bound > slots:
                    return False

        edge = min(rem, key=lambda x: x.bit_count())
        x = edge
        while x:
            lsb = x & -x
            if can_hit(tuple(rem), chosen | lsb, slots - 1):
                return True
            x ^= lsb
        return False

    for k in range(forced_count, min(max_k, universe.bit_count()) + 1):
        if can_hit(reduced, forced, k - forced_count):
            return k
    return max_k + 1


def apply_pair(black: int, white: int, player: int, a: int, b: int) -> Tuple[int, int]:
    mask = (1 << a) | (1 << b)
    return (black | mask, white) if player == 1 else (black, white | mask)


def obligations_after_pair(env: HexEnv, black: int, white: int, player: int, a: int, b: int):
    mask = (1 << a) | (1 << b)
    mine, opp = (black | mask, white) if player == 1 else (white | mask, black)
    exact, proto = [], []
    terminal = 0
    impacted = set(env.cell_to_segments[a]) | set(env.cell_to_segments[b])

    for sid in impacted:
        seg = env.segments[sid]
        if seg & opp:
            continue
        cnt = (seg & mine).bit_count()
        empty = seg & ~(mine | opp)
        ecnt = empty.bit_count()
        if cnt >= 6:
            terminal += 1
        elif cnt >= 4 and 1 <= ecnt <= 2:
            exact.append(empty)
        elif cnt == 3 and ecnt == 3:
            proto.append(empty)

    exact = tuple(sorted(set(exact)))
    proto = tuple(sorted(set(proto)))
    return exact, proto, terminal, hitting_number(exact), hitting_number(proto)


def tau_eval(env: HexEnv, black: int, white: int, player: int, a: int, b: int) -> Dict[str, float]:
    exact, proto, terminal, te, tp = obligations_after_pair(env, black, white, player, a, b)
    ep, pp = max(0, te - 2), max(0, tp - 2)
    return {
        "exact_tau": int(te),
        "proto_tau": int(tp),
        "exact_pressure": int(ep),
        "proto_pressure": int(pp),
        "terminal": int(terminal > 0),
        "exact_edges": int(len(exact)),
        "proto_edges": int(len(proto)),
        "tau_value": float(70 * int(terminal > 0) + 20 * ep + 9.0 * pp + 2.3 * te + 1.2 * tp),
    }


# ----------------------- AP field and branching debt ----------------------- #

def line_potential(env: HexEnv, black: int, white: int, player: int, sid: int) -> float:
    seg = env.segments[sid]
    if player == 1:
        if seg & white:
            return 0.0
        cnt = (seg & black).bit_count()
        rooted = bool(seg & (1 << env.root))
        weights = {0: 0.0, 1: 0.20, 2: 0.75, 3: 6.4, 4: 2.1, 5: 17.5, 6: 120.0}
        return weights[cnt] + (1.05 + 0.28 * cnt if rooted else 0.0)

    if seg & black:
        return 0.0
    cnt = (seg & white).bit_count()
    weights = {0: 0.0, 1: 0.16, 2: 1.35, 3: 0.75, 4: 9.3, 5: 3.4, 6: 124.0}
    return weights[cnt]


def black_root_debt(env: HexEnv, black: int, white: int, sid: int) -> float:
    seg = env.segments[sid]
    if not (seg & (1 << env.root)) or (seg & white):
        return 0.0
    cnt = (seg & black).bit_count()
    return {0: 0.0, 1: 0.55, 2: 1.0, 3: 7.5, 4: 2.6, 5: 19.0, 6: 120.0}[cnt]


def ap_score(env: HexEnv, black: int, white: int, player: int, a: int, b: int) -> float:
    nb, nw = apply_pair(black, white, player, a, b)
    delta, block = 0.0, 0.0
    axes = [0.0, 0.0, 0.0]
    for sid in set(env.cell_to_segments[a]) | set(env.cell_to_segments[b]):
        before = line_potential(env, black, white, player, sid)
        after = line_potential(env, nb, nw, player, sid)
        d = after - before
        delta += d
        axes[env.seg_axis[sid]] += max(0.0, d)
        if player == -1:
            block += max(0.0, black_root_debt(env, black, white, sid) - black_root_debt(env, nb, nw, sid))
        else:
            block += 0.35 * max(0.0, line_potential(env, black, white, -1, sid) - line_potential(env, nb, nw, -1, sid))
    shape = pair_shape(env.cells, a, b)
    geom = 0.15 * max(0, 6 - hex_dist(env.cells[a], env.cells[b]))
    if player == 1 and pair_kind(shape) in ("short_rail", "long_rail"):
        geom += 1.45
    if player == -1 and pair_kind(shape) in ("bridge", "long_bridge", "bridge_rail"):
        geom += 1.35
    return float(delta + 0.86 * block + 0.20 * (max(axes) - min(axes)) + geom)


def single_cell_flow(env: HexEnv, black: int, white: int, player: int, i: int) -> float:
    if (black | white) & (1 << i):
        return -1e12
    nb, nw = (black | (1 << i), white) if player == 1 else (black, white | (1 << i))
    delta, screen, odd_seed = 0.0, 0.0, 0.0
    axes = [0.0, 0.0, 0.0]
    for sid in env.cell_to_segments[i]:
        d = line_potential(env, nb, nw, player, sid) - line_potential(env, black, white, player, sid)
        delta += d
        axes[env.seg_axis[sid]] += max(0.0, d)
        if player == 1:
            seg = env.segments[sid]
            if not (seg & white):
                cnt = (seg & nb).bit_count()
                if cnt in (3, 5):
                    odd_seed += 2.2 + (2.0 if seg & (1 << env.root) else 0.0)
        else:
            screen += max(0.0, black_root_debt(env, black, white, sid) - black_root_debt(env, nb, nw, sid))
    anis = max(axes) - min(axes)
    central = -0.035 * env.dist[i]
    return float(delta + (0.18 * anis + odd_seed if player == 1 else 0.55 * screen + 0.12 * anis) + central)


def union_count(edges: Iterable[int]) -> int:
    u = 0
    for e in edges:
        u |= e
    return u.bit_count()


def edge_overlap(edges: Sequence[int]) -> float:
    if len(edges) <= 1:
        return 0.0
    inter, pairs = 0, 0
    for i, e1 in enumerate(edges):
        for e2 in edges[i + 1:]:
            inter += (e1 & e2).bit_count()
            pairs += 1
    return inter / max(1, pairs)


def branching_features(env: HexEnv, black: int, white: int, a: int, b: int) -> Dict[str, float]:
    mask = (1 << a) | (1 << b)
    mine = black | mask
    opp = white

    proto_edges, hard_edges = [], []
    axes = set()
    rooted_proto = rooted_hard = odd_line_count = 0

    for sid in set(env.cell_to_segments[a]) | set(env.cell_to_segments[b]):
        seg = env.segments[sid]
        if seg & opp:
            continue
        cnt = (seg & mine).bit_count()
        empty = seg & ~(mine | opp)
        if cnt in (3, 5):
            odd_line_count += 1
            axes.add(env.seg_axis[sid])
        if cnt == 3 and empty.bit_count() == 3:
            proto_edges.append(empty)
            rooted_proto += int(bool(seg & (1 << env.root)))
        elif cnt >= 4 and 1 <= empty.bit_count() <= 2:
            hard_edges.append(empty)
            rooted_hard += int(bool(seg & (1 << env.root)) and cnt >= 5)

    proto_edges = tuple(sorted(set(proto_edges)))
    hard_edges = tuple(sorted(set(hard_edges)))
    tau_p, tau_h = hitting_number(proto_edges), hitting_number(hard_edges)
    pp, ph = max(0, tau_p - 2), max(0, tau_h - 2)

    proto_total = sum(e.bit_count() for e in proto_edges)
    hard_total = sum(e.bit_count() for e in hard_edges)
    proto_disjointness = union_count(proto_edges) / max(1, proto_total)
    hard_disjointness = union_count(hard_edges) / max(1, hard_total)
    proto_overlap = edge_overlap(proto_edges)
    hard_overlap = edge_overlap(hard_edges)
    axis_div = len(axes)

    score = (
        9.5 * pp + 3.6 * tau_p + 11.0 * ph + 3.0 * tau_h
        + 1.8 * len(proto_edges) + 2.8 * len(hard_edges)
        + 3.8 * axis_div
        + 6.0 * proto_disjointness + 4.0 * hard_disjointness
        + 2.0 * rooted_proto * (1 + pp) + 4.5 * rooted_hard * (1 + ph)
        + 1.2 * odd_line_count
        - 5.2 * proto_overlap - 4.4 * hard_overlap
    )
    return {
        "branching_debt": float(max(0.0, score)),
        "branch_proto_tau": int(tau_p),
        "branch_hard_tau": int(tau_h),
        "branch_proto_pressure": int(pp),
        "branch_hard_pressure": int(ph),
        "branch_axis_diversity": int(axis_div),
        "branch_proto_edges": int(len(proto_edges)),
        "branch_hard_edges": int(len(hard_edges)),
        "branch_proto_disjointness": float(proto_disjointness),
        "branch_hard_disjointness": float(hard_disjointness),
        "branch_proto_overlap": float(proto_overlap),
        "branch_hard_overlap": float(hard_overlap),
        "rooted_odd_mass": float(3 * rooted_proto + 6 * rooted_hard + odd_line_count),
        "rooted_proto_count": int(rooted_proto),
        "rooted_hard_count": int(rooted_hard),
        "odd_line_count": int(odd_line_count),
        "proto_support_mask": int(union_count(proto_edges)),
        "hard_support_mask": int(union_count(hard_edges)),
        "support_mask": int(union_count(proto_edges) | union_count(hard_edges)),
    }


# ----------------------- position generation / targets ----------------------- #

def candidate_pairs(env: HexEnv, black: int, white: int, rng: random.Random, pool: int, reservoir: int = 0) -> List[Tuple[int, int]]:
    occupied = black | white
    central, tail = [], []
    for a, b, _, _ in env.pairs:
        if (occupied & (1 << a)) or (occupied & (1 << b)):
            continue
        if len(central) < pool:
            central.append((a, b))
        else:
            tail.append((a, b))
    if reservoir and tail:
        rng.shuffle(tail)
        central += tail[:reservoir]
    return central


def ranked_black_candidates(env: HexEnv, black: int, white: int, rng: random.Random, cfg: Dict, width: int):
    rows = []
    for a, b in candidate_pairs(env, black, white, rng, cfg["candidate_pool"], cfg["candidate_reservoir"]):
        te = tau_eval(env, black, white, 1, a, b)
        bf = branching_features(env, black, white, a, b)
        ap = ap_score(env, black, white, 1, a, b)
        score = 0.48 * te["tau_value"] + 0.75 * bf["branching_debt"] + 0.22 * ap + rng.random() * 1e-5
        rows.append((score, a, b, te, bf, ap))
    rows.sort(reverse=True, key=lambda x: x[0])
    return rows[:width]


def ranked_white_replies(env: HexEnv, black: int, white: int, rng: random.Random, cfg: Dict, width: int):
    rows = []
    for a, b in candidate_pairs(env, black, white, rng, cfg["reply_pool"], cfg["reply_reservoir"]):
        te = tau_eval(env, black, white, -1, a, b)
        ap = ap_score(env, black, white, -1, a, b)
        block_flow = single_cell_flow(env, black, white, 1, a) + single_cell_flow(env, black, white, 1, b)
        score = 0.65 * te["tau_value"] + 0.35 * ap + 0.18 * block_flow + rng.random() * 1e-5
        rows.append((score, a, b))
    rows.sort(reverse=True, key=lambda x: x[0])
    return rows[:width]


def future_target(env: HexEnv, black: int, white: int, a: int, b: int, rng: random.Random, cfg: Dict) -> Dict[str, float]:
    immediate = tau_eval(env, black, white, 1, a, b)
    if immediate["terminal"]:
        return {
            "future_value": 100.0,
            "future_tau": 6,
            "future_pressure": 4,
            "future_terminal": 1,
            "white_replies_checked": 0,
            "black_continuations_checked": 0,
        }

    b1, w1 = apply_pair(black, white, 1, a, b)
    white_replies = ranked_white_replies(env, b1, w1, rng, cfg, cfg["white_reply_width"])
    if not white_replies:
        return {
            "future_value": immediate["tau_value"],
            "future_tau": max(immediate["exact_tau"], immediate["proto_tau"]),
            "future_pressure": max(immediate["exact_pressure"], immediate["proto_pressure"]),
            "future_terminal": 0,
            "white_replies_checked": 0,
            "black_continuations_checked": 0,
        }

    reply_values = []
    cont_checked = 0
    for _, wa, wb in white_replies:
        b2, w2 = apply_pair(b1, w1, -1, wa, wb)
        best = (-1e12, 0, 0, 0)
        for _, ba, bb, te, bf, ap in ranked_black_candidates(env, b2, w2, rng, cfg, cfg["black_continuation_width"]):
            cont_checked += 1
            val = (
                90 * te["terminal"]
                + 22 * te["exact_pressure"]
                + 10 * te["proto_pressure"]
                + 3.7 * bf["branch_hard_pressure"]
                + 2.3 * bf["branch_proto_pressure"]
                + 0.17 * bf["branching_debt"]
            )
            if val > best[0]:
                best = (
                    val,
                    max(te["exact_tau"], te["proto_tau"], bf["branch_hard_tau"], bf["branch_proto_tau"]),
                    max(te["exact_pressure"], te["proto_pressure"], bf["branch_hard_pressure"], bf["branch_proto_pressure"]),
                    te["terminal"],
                )
        reply_values.append(best)

    # White chooses the reply minimizing Black's best future pressure.
    val, tau, pressure, terminal = min(reply_values, key=lambda x: x[0])
    return {
        "future_value": float(val),
        "future_tau": int(tau),
        "future_pressure": int(pressure),
        "future_terminal": int(terminal),
        "white_replies_checked": int(len(white_replies)),
        "black_continuations_checked": int(cont_checked),
    }


def generate_position(env: HexEnv, pid: int, cfg: Dict) -> Dict:
    rng = random.Random(cfg["seed"] + pid * 7919)
    black = 1 << env.root
    white = 0
    mode = rng.choice(["random", "ap", "tau", "branch"])
    plies = rng.randint(cfg["min_position_plies"], cfg["max_position_plies"])

    for ply in range(1, plies + 1):
        player = -1 if ply % 2 == 1 else 1
        cand = candidate_pairs(env, black, white, rng, cfg["generation_pool"], cfg["generation_reservoir"])
        if not cand:
            break
        rows = []
        for a, b in cand:
            if mode == "random":
                score = -0.03 * (env.dist[a] + env.dist[b]) + rng.uniform(-1, 1)
            elif mode == "ap":
                score = ap_score(env, black, white, player, a, b)
            elif mode == "tau":
                score = tau_eval(env, black, white, player, a, b)["tau_value"]
            else:
                if player == 1:
                    score = branching_features(env, black, white, a, b)["branching_debt"] + 0.15 * ap_score(env, black, white, 1, a, b)
                else:
                    score = tau_eval(env, black, white, -1, a, b)["tau_value"] + 0.22 * ap_score(env, black, white, -1, a, b)
            rows.append((score, a, b))
        rows.sort(reverse=True, key=lambda x: x[0])
        top = rows[:cfg["generation_top_k"]]
        vals = np.array([x[0] for x in top], dtype=float)
        probs = np.exp(np.clip((vals - vals.max()) / max(1e-6, cfg["generation_temperature"]), -50, 50))
        probs /= probs.sum()
        _, a, b = rng.choices(top, weights=probs, k=1)[0]
        black, white = apply_pair(black, white, player, a, b)
        if env.has_win(black, white, player):
            break

    return {
        "position_id": pid,
        "black": int(black),
        "white": int(white),
        "mode": mode,
        "plies": int(plies),
        "black_stones": int(black.bit_count()),
        "white_stones": int(white.bit_count()),
    }


# ----------------------------- relevance zones ----------------------------- #

def empty_cells(env: HexEnv, black: int, white: int) -> List[int]:
    occ = black | white
    return [i for i in env.play if not (occ & (1 << i))]


def cells_from_mask(mask: int) -> Set[int]:
    out = set()
    while mask:
        lsb = mask & -mask
        out.add(lsb.bit_length() - 1)
        mask ^= lsb
    return out


def pair_count_in_zone(env: HexEnv, black: int, white: int, zone: Set[int]) -> int:
    occ = black | white
    n = 0
    for a, b, _, _ in env.pairs:
        if a in zone and b in zone and not (occ & (1 << a)) and not (occ & (1 << b)):
            n += 1
    return n


def live_obligation_support(env: HexEnv, black: int, white: int) -> Set[int]:
    support = set()
    for player in (1, -1):
        mine, opp = (black, white) if player == 1 else (white, black)
        for sid, seg in enumerate(env.segments):
            if seg & opp:
                continue
            cnt = (seg & mine).bit_count()
            empty = seg & ~(mine | opp)
            ec = empty.bit_count()
            if (cnt >= 4 and 1 <= ec <= 2) or (cnt == 3 and ec == 3):
                support |= cells_from_mask(empty)
    return {i for i in support if i in env.play and not ((black | white) & (1 << i))}


def ap_flow_zone(env: HexEnv, black: int, white: int, cfg: Dict) -> Set[int]:
    rows = []
    for i in empty_cells(env, black, white):
        # Use max of Black debt-flow, White closure-flow, and anti-Black blocking flow.
        score = max(
            single_cell_flow(env, black, white, 1, i),
            single_cell_flow(env, black, white, -1, i),
            0.45 * single_cell_flow(env, black, white, 1, i) + 0.55 * single_cell_flow(env, black, white, -1, i),
        )
        rows.append((score, i))
    rows.sort(reverse=True, key=lambda x: x[0])
    return {i for _, i in rows[:cfg["zone_ap_cells"]]}


def naive_radius_zone(env: HexEnv, black: int, white: int, cfg: Dict) -> Set[int]:
    occ_indices = cells_from_mask(black | white)
    z = set()
    r = cfg["zone_naive_radius"]
    for i in empty_cells(env, black, white):
        c = env.cells[i]
        if any(hex_dist(c, env.cells[j]) <= r for j in occ_indices):
            z.add(i)
    return z


def branching_zone(env: HexEnv, black: int, white: int, reference_rows: List[Dict], cfg: Dict) -> Set[int]:
    # In the benchmark this zone gets to use only features, not future targets.
    rows = []
    for row in reference_rows:
        score = (
            row["branching_debt"]
            + 0.35 * row["ap_score"]
            + 6.0 * row["branch_axis_diversity"]
            - 2.0 * row["branch_proto_overlap"]
            - 2.0 * row["branch_hard_overlap"]
        )
        rows.append((score, row))
    rows.sort(reverse=True, key=lambda x: x[0])
    z = set()
    for _, row in rows[:cfg["zone_branch_moves"]]:
        z.add(int(row["a_idx"]))
        z.add(int(row["b_idx"]))
        z |= cells_from_mask(int(row.get("support_mask", 0)))
        z |= cells_from_mask(int(row.get("proto_support_mask", 0)))
        z |= cells_from_mask(int(row.get("hard_support_mask", 0)))
    return {i for i in z if i in env.play and not ((black | white) & (1 << i))}


def oracle_zone(env: HexEnv, black: int, white: int, reference_rows: List[Dict], cfg: Dict) -> Set[int]:
    rows = sorted(reference_rows, key=lambda r: r["future_value"], reverse=True)
    z = set()
    for row in rows[:cfg["zone_oracle_moves"]]:
        z.add(int(row["a_idx"]))
        z.add(int(row["b_idx"]))
        z |= cells_from_mask(int(row.get("support_mask", 0)))
    return {i for i in z if i in env.play and not ((black | white) & (1 << i))}


def combo_zone(env: HexEnv, black: int, white: int, reference_rows: List[Dict], cfg: Dict) -> Set[int]:
    return (
        ap_flow_zone(env, black, white, cfg)
        | live_obligation_support(env, black, white)
        | branching_zone(env, black, white, reference_rows, cfg)
    )


def zone_support_metrics(env: HexEnv, black: int, white: int, reference_rows: List[Dict], zone_name: str, zone: Set[int], cfg: Dict) -> Dict:
    empty = set(empty_cells(env, black, white))
    baseline_pairs = pair_count_in_zone(env, black, white, empty)
    zone_pairs = pair_count_in_zone(env, black, white, zone)

    def in_zone(row):
        return int(row["a_idx"]) in zone and int(row["b_idx"]) in zone

    terminal_refs = [r for r in reference_rows if r["immediate_terminal"] or r["future_terminal"]]
    forcing_refs = [r for r in reference_rows if r["immediate_forcing"] or r["future_pressure"] > 0]
    high_refs = [r for r in reference_rows if r["future_value"] >= max(x["future_value"] for x in reference_rows) - 1e-9]
    useful_cells = set()
    for r in forcing_refs:
        useful_cells.add(int(r["a_idx"]))
        useful_cells.add(int(r["b_idx"]))
        useful_cells |= cells_from_mask(int(r.get("support_mask", 0)))

    best_future = max((r["future_value"] for r in reference_rows), default=0.0)
    in_zone_futures = [r["future_value"] for r in reference_rows if in_zone(r)]
    best_zone_future = max(in_zone_futures) if in_zone_futures else 0.0

    return {
        "zone": zone_name,
        "zone_cells": int(len(zone)),
        "empty_cells": int(len(empty)),
        "zone_cell_fraction": float(len(zone) / max(1, len(empty))),
        "zone_pairs": int(zone_pairs),
        "baseline_pairs": int(baseline_pairs),
        "pair_reduction": float(1.0 - zone_pairs / max(1, baseline_pairs)),
        "terminal_refs": int(len(terminal_refs)),
        "forcing_refs": int(len(forcing_refs)),
        "terminal_recall": float(sum(in_zone(r) for r in terminal_refs) / max(1, len(terminal_refs))),
        "forcing_recall": float(sum(in_zone(r) for r in forcing_refs) / max(1, len(forcing_refs))),
        "best_recall": float(any(in_zone(r) for r in high_refs)),
        "best_future_value": float(best_future),
        "best_zone_future_value": float(best_zone_future),
        "best_value_retention": float(best_zone_future / max(1e-9, best_future)) if best_future > 0 else 1.0,
        "false_zone_mass": float(1.0 - len(zone & useful_cells) / max(1, len(zone))),
    }


# ----------------------------- benchmark loop ----------------------------- #

def reference_candidates_for_position(env: HexEnv, pos: Dict, cfg: Dict) -> List[Dict]:
    pid = int(pos["position_id"])
    rng = random.Random(cfg["seed"] + pid * 104729 + 17)
    black, white = int(pos["black"]), int(pos["white"])
    rows = []

    for rank, (_, a, b, te, bf, ap) in enumerate(ranked_black_candidates(env, black, white, rng, cfg, cfg["reference_candidate_width"]), start=1):
        fut = future_target(env, black, white, a, b, rng, cfg)
        shape = pair_shape(env.cells, a, b)
        cellflow = single_cell_flow(env, black, white, 1, a) + single_cell_flow(env, black, white, 1, b)
        rows.append({
            "position_id": pid,
            "candidate_rank": rank,
            "a_idx": int(a),
            "b_idx": int(b),
            "a_q": int(env.cells[a][0]),
            "a_r": int(env.cells[a][1]),
            "b_q": int(env.cells[b][0]),
            "b_r": int(env.cells[b][1]),
            "shape": shape,
            "kind": pair_kind(shape),
            "ap_score": float(ap),
            "cell_flow_sum": float(cellflow),
            "immediate_forcing": int(te["exact_pressure"] > 0 or te["proto_pressure"] > 0),
            "immediate_terminal": int(te["terminal"]),
            **te,
            **bf,
            **fut,
        })
    return rows


def benchmark_position(env: HexEnv, pid: int, cfg: Dict):
    pos = generate_position(env, pid, cfg)
    black, white = int(pos["black"]), int(pos["white"])

    if env.has_win(black, white, 1) or env.has_win(black, white, -1):
        return None, [], []

    ref = reference_candidates_for_position(env, pos, cfg)
    if not ref:
        return None, [], []

    zones = {
        "naive_radius": naive_radius_zone(env, black, white, cfg),
        "ap_flow": ap_flow_zone(env, black, white, cfg),
        "obligation_support": live_obligation_support(env, black, white),
        "branching_debt": branching_zone(env, black, white, ref, cfg),
        "combo": combo_zone(env, black, white, ref, cfg),
        "oracle_upper": oracle_zone(env, black, white, ref, cfg),
    }

    zone_rows = []
    for zn, z in zones.items():
        m = zone_support_metrics(env, black, white, ref, zn, z, cfg)
        m.update({
            "position_id": int(pid),
            "mode": pos["mode"],
            "plies": int(pos["plies"]),
            "black_stones": int(pos["black_stones"]),
            "white_stones": int(pos["white_stones"]),
        })
        zone_rows.append(m)

    pos_row = {
        "position_id": int(pid),
        "mode": pos["mode"],
        "plies": int(pos["plies"]),
        "black_stones": int(pos["black_stones"]),
        "white_stones": int(pos["white_stones"]),
        "reference_candidates": int(len(ref)),
        "best_future_value": float(max(r["future_value"] for r in ref)),
        "forcing_ref_count": int(sum((r["immediate_forcing"] or r["future_pressure"] > 0) for r in ref)),
        "terminal_ref_count": int(sum((r["immediate_terminal"] or r["future_terminal"]) for r in ref)),
    }
    return pos_row, ref, zone_rows


def append_rows(path: Path, rows: List[Dict], fieldnames: List[str]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def existing_position_ids(path: Path) -> Set[int]:
    if not path.exists():
        return set()
    try:
        df = pd.read_csv(path, usecols=["position_id"])
        return set(int(x) for x in df["position_id"].unique())
    except Exception:
        return set()


def run_benchmark(cfg: Dict):
    out = Path(cfg["out"])
    data = out / "data"
    figures = out / "figures"
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)

    env = HexEnv(cfg["radius"], cfg["candidate_radius"], cfg["max_spread"])
    done = existing_position_ids(data / "position_records.csv") if cfg.get("resume", False) else set()
    t0 = time.perf_counter()

    pos_fields = [
        "position_id", "mode", "plies", "black_stones", "white_stones",
        "reference_candidates", "best_future_value", "forcing_ref_count", "terminal_ref_count",
    ]

    # Superset field lists.
    ref_fields = [
        "position_id", "candidate_rank", "a_idx", "b_idx", "a_q", "a_r", "b_q", "b_r",
        "shape", "kind", "ap_score", "cell_flow_sum",
        "immediate_forcing", "immediate_terminal",
        "exact_tau", "proto_tau", "exact_pressure", "proto_pressure", "terminal",
        "exact_edges", "proto_edges", "tau_value",
        "branching_debt", "branch_proto_tau", "branch_hard_tau",
        "branch_proto_pressure", "branch_hard_pressure", "branch_axis_diversity",
        "branch_proto_edges", "branch_hard_edges", "branch_proto_disjointness",
        "branch_hard_disjointness", "branch_proto_overlap", "branch_hard_overlap",
        "rooted_odd_mass", "rooted_proto_count", "rooted_hard_count", "odd_line_count",
        "proto_support_mask", "hard_support_mask", "support_mask",
        "future_value", "future_tau", "future_pressure", "future_terminal",
        "white_replies_checked", "black_continuations_checked",
    ]

    zone_fields = [
        "position_id", "mode", "plies", "black_stones", "white_stones",
        "zone", "zone_cells", "empty_cells", "zone_cell_fraction",
        "zone_pairs", "baseline_pairs", "pair_reduction",
        "terminal_refs", "forcing_refs", "terminal_recall", "forcing_recall",
        "best_recall", "best_future_value", "best_zone_future_value",
        "best_value_retention", "false_zone_mass",
    ]

    pos_buffer, ref_buffer, zone_buffer = [], [], []
    attempted = 0
    completed = 0
    skipped_terminal = 0

    for pid in range(cfg["positions"]):
        if pid in done:
            continue
        attempted += 1
        pos, ref, zones = benchmark_position(env, pid, cfg)
        if pos is None:
            skipped_terminal += 1
            continue
        pos_buffer.append(pos)
        ref_buffer.extend(ref)
        zone_buffer.extend(zones)
        completed += 1

        if completed % cfg["checkpoint_every"] == 0:
            append_rows(data / "position_records.csv", pos_buffer, pos_fields)
            append_rows(data / "reference_candidates.csv", ref_buffer, ref_fields)
            append_rows(data / "zone_metrics.csv", zone_buffer, zone_fields)
            pos_buffer.clear(); ref_buffer.clear(); zone_buffer.clear()
            print(f"[checkpoint] completed={completed} attempted={attempted} elapsed={time.perf_counter()-t0:.1f}s", flush=True)

    append_rows(data / "position_records.csv", pos_buffer, pos_fields)
    append_rows(data / "reference_candidates.csv", ref_buffer, ref_fields)
    append_rows(data / "zone_metrics.csv", zone_buffer, zone_fields)

    elapsed = time.perf_counter() - t0
    manifest = {
        "config": cfg,
        "attempted_this_run": attempted,
        "completed_this_run": completed,
        "skipped_terminal_this_run": skipped_terminal,
        "elapsed_seconds": elapsed,
        "hitting_cache": str(hitting_number.cache_info()),
    }
    with (out / "benchmark_manifest.json").open("w") as f:
        json.dump(manifest, f, indent=2)

    return manifest


# ------------------------------ summarisation ------------------------------ #

def summarize(out: Path):
    data = out / "data"
    zpath = data / "zone_metrics.csv"
    rpath = data / "reference_candidates.csv"
    if not zpath.exists():
        raise FileNotFoundError(zpath)

    z = pd.read_csv(zpath)
    ref = pd.read_csv(rpath) if rpath.exists() else pd.DataFrame()

    agg = z.groupby("zone", as_index=False).agg(
        positions=("position_id", "nunique"),
        mean_zone_cells=("zone_cells", "mean"),
        mean_zone_cell_fraction=("zone_cell_fraction", "mean"),
        mean_zone_pairs=("zone_pairs", "mean"),
        mean_baseline_pairs=("baseline_pairs", "mean"),
        mean_pair_reduction=("pair_reduction", "mean"),
        mean_terminal_recall=("terminal_recall", "mean"),
        mean_forcing_recall=("forcing_recall", "mean"),
        mean_best_recall=("best_recall", "mean"),
        mean_best_value_retention=("best_value_retention", "mean"),
        mean_false_zone_mass=("false_zone_mass", "mean"),
    ).sort_values(["mean_forcing_recall", "mean_pair_reduction"], ascending=[False, False])
    agg.to_csv(data / "aggregate_zone_metrics.csv", index=False)

    # Efficiency frontier: retain forcing while reducing pairs.
    fig = out / "figures"
    fig.mkdir(parents=True, exist_ok=True)

    plt.figure(figsize=(7, 5.5))
    plt.scatter(agg["mean_pair_reduction"], agg["mean_forcing_recall"], s=90)
    for _, row in agg.iterrows():
        plt.text(row["mean_pair_reduction"] + 0.005, row["mean_forcing_recall"], row["zone"], fontsize=9)
    plt.xlabel("mean pair reduction")
    plt.ylabel("mean forcing recall")
    plt.title("Relevance-zone efficiency frontier")
    plt.tight_layout()
    plt.savefig(fig / "zone_efficiency_frontier.png", dpi=190)
    plt.close()

    plt.figure(figsize=(9, 5))
    order = agg.sort_values("mean_best_value_retention", ascending=False)
    x = np.arange(len(order))
    plt.bar(x, order["mean_best_value_retention"])
    plt.xticks(x, order["zone"], rotation=35, ha="right")
    plt.ylabel("best value retention")
    plt.title("Does the zone retain the best continuation?")
    plt.tight_layout()
    plt.savefig(fig / "best_value_retention.png", dpi=190)
    plt.close()

    plt.figure(figsize=(9, 5))
    order = agg.sort_values("mean_pair_reduction", ascending=False)
    x = np.arange(len(order))
    plt.bar(x, order["mean_pair_reduction"])
    plt.xticks(x, order["zone"], rotation=35, ha="right")
    plt.ylabel("pair reduction")
    plt.title("Search reduction by zone generator")
    plt.tight_layout()
    plt.savefig(fig / "pair_reduction_by_zone.png", dpi=190)
    plt.close()

    if not ref.empty:
        feature_cols = [
            "branching_debt", "ap_score", "cell_flow_sum", "rooted_odd_mass",
            "branch_axis_diversity", "branch_proto_disjointness", "branch_hard_disjointness",
            "branch_proto_overlap", "branch_hard_overlap", "proto_pressure", "exact_pressure",
        ]
        feature_cols = [c for c in feature_cols if c in ref.columns and ref[c].nunique() > 1]
        corr_rows = []
        for c in feature_cols:
            corr_rows.append({"feature": c, "spearman_future_value": ref[c].corr(ref["future_value"], method="spearman")})
        corr = pd.DataFrame(corr_rows).sort_values("spearman_future_value", ascending=False)
        corr.to_csv(data / "reference_feature_correlations.csv", index=False)

        plt.figure(figsize=(9, 5))
        top = corr.head(12)
        x = np.arange(len(top))
        plt.bar(x, top["spearman_future_value"])
        plt.xticks(x, top["feature"], rotation=45, ha="right")
        plt.ylabel("Spearman correlation")
        plt.title("Reference candidate features vs future value")
        plt.tight_layout()
        plt.savefig(fig / "feature_correlations.png", dpi=190)
        plt.close()

    manifest_path = out / "benchmark_manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    report = f"""# RZ-BDPN relevance-zone benchmark

## Purpose

This benchmark tests whether relevance-zone generators inspired by AP-flow, obligation support,
and branching debt retain tactical continuations while reducing the pair search space.

The reference target is:

```text
Black candidate -> White replies -> Black continuations
```

and the key metrics are:

- **pair reduction**: fraction of legal candidate pairs removed by the zone;
- **forcing recall**: fraction of reference forcing continuations retained;
- **terminal recall**: fraction of terminal continuations retained;
- **best value retention**: best in-zone future value divided by best reference future value;
- **false zone mass**: zone cells not appearing in reference useful support.

## Manifest

```json
{json.dumps(manifest, indent=2)}
```

## Aggregate zone metrics

{agg.to_markdown(index=False)}

## Interpretation guide

A strong zone lies near the top-right of the efficiency frontier:

```text
high forcing recall + high pair reduction
```

The expected winning family is not the expensive `oracle_upper`, but the practical `combo` zone:

```text
AP-flow ∪ obligation-support ∪ branching-debt
```

That would validate the architecture:

```text
flow proposes relevance;
branching debt focuses threat candidates;
transversal pressure verifies proof obligations.
```
"""
    (out / "report.md").write_text(report)

    return agg


def load_config(args) -> Dict:
    cfg = {}
    if args.config:
        with open(args.config) as f:
            cfg.update(json.load(f))
    # CLI overrides.
    for k, v in vars(args).items():
        if k == "config" or v is None:
            continue
        cfg[k] = v

    defaults = {
        "out": "rz_bdpn_benchmark_out",
        "resume": False,
        "radius": 6,
        "candidate_radius": 5,
        "max_spread": 7,
        "positions": 100,
        "seed": 260517,
        "checkpoint_every": 10,

        "min_position_plies": 4,
        "max_position_plies": 10,
        "generation_pool": 70,
        "generation_reservoir": 25,
        "generation_top_k": 5,
        "generation_temperature": 1.12,

        "reference_candidate_width": 10,
        "candidate_pool": 160,
        "candidate_reservoir": 60,

        "white_reply_width": 5,
        "black_continuation_width": 6,
        "reply_pool": 110,
        "reply_reservoir": 40,

        "zone_naive_radius": 2,
        "zone_ap_cells": 28,
        "zone_branch_moves": 8,
        "zone_oracle_moves": 5,
    }
    for k, v in defaults.items():
        cfg.setdefault(k, v)

    # Ensure out is string for JSON.
    cfg["out"] = str(cfg["out"])
    return cfg


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", type=str, default=None)
    p.add_argument("--out", type=str, default=None)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--positions", type=int, default=None)
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--radius", type=int, default=None)
    p.add_argument("--candidate-radius", dest="candidate_radius", type=int, default=None)
    p.add_argument("--max-spread", dest="max_spread", type=int, default=None)
    p.add_argument("--checkpoint-every", dest="checkpoint_every", type=int, default=None)
    args = p.parse_args()

    cfg = load_config(args)
    out = Path(cfg["out"])
    out.mkdir(parents=True, exist_ok=True)
    with (out / "resolved_config.json").open("w") as f:
        json.dump(cfg, f, indent=2)

    manifest = run_benchmark(cfg)
    agg = summarize(out)

    # Package run folder.
    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "rz_bdpn_benchmark.py")

    print(json.dumps({
        "out": str(out),
        "zip": str(zip_path),
        "manifest": manifest,
        "aggregate": agg.to_dict(orient="records"),
    }, indent=2))


if __name__ == "__main__":
    main()
