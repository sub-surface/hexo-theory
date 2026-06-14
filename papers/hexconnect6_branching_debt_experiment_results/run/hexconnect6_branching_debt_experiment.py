#!/usr/bin/env python3
"""
hexconnect6_branching_debt_experiment.py

Branching-debt experiment for the rooted odd / unrooted even breakthrough.

This extends the three-agent experiment with a genuinely side-specific hybrid:

  symmetric_tau:
      same exact/proto tau evaluator for both players.

  odd_even_ap:
      no tau; Black uses rooted odd AP debt, White uses even closure + anti-root screen.

  hybrid_shared:
      AP field screens candidates; exact tau reranks with one shared AP/tau mixture.

  hybrid_split:
      AP field screens candidates; exact tau reranks with different side-specific theories:
          Black: rooted odd debt maturation + proto/5-threshold acceleration + tau.
          White: even closure + anti-root screen + terminal/bridge conversion + tau.

  hybrid_branching:
      AP field screens candidates; exact tau reranks with a stricter Black bonus:
          Black: branching odd debt = high-transversal, low-overlap proto/hard obligation webs.
          White: even closure + anti-root screen + terminal/bridge conversion + tau.

The point is not merely to maximize win rate. The representation claim is supported if
hybrid_split approaches or improves tactical quality with fewer tau evaluations than symmetric_tau,
and if it changes Black's odd-threshold debt profile relative to the shared hybrid.

Run:
  python hexconnect6_branching_debt_experiment.py --out split_out --games-per-matchup 8
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import random
import time
import zipfile
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Tuple, List

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

Cell = Tuple[int, int]
DIRS = ((1, 0), (0, 1), (1, -1))
AGENTS = ["symmetric_tau", "odd_even_ap", "hybrid_shared", "hybrid_split", "hybrid_branching"]


def hex_dist(a: Cell, b: Cell=(0, 0)) -> int:
    dq, dr = a[0]-b[0], a[1]-b[1]
    return max(abs(dq), abs(dr), abs(dq+dr))


def add(a: Cell, d: Cell, k: int=1) -> Cell:
    return (a[0] + d[0]*k, a[1] + d[1]*k)


def axial_to_xy(c: Cell):
    q, r = c
    return (math.sqrt(3) * (q + r/2), 1.5*r)


def rotate60(c: Cell) -> Cell:
    q, r = c
    return (-r, q+r)


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


def shape_of(cells, a: int, b: int) -> str:
    ca, cb = cells[a], cells[b]
    return str(canonical_delta((cb[0]-ca[0], cb[1]-ca[1])))


def pair_kind(shape: str) -> str:
    try:
        q, r = ast.literal_eval(shape)
    except Exception:
        return "unknown"
    d = hex_dist((q, r))
    if r == 0:
        return "short_rail" if d <= 2 else "long_rail" if d <= 4 else "bridge_rail"
    return "compact_kink" if d <= 2 else "bridge" if d <= 4 else "long_bridge"


def cells_in_radius(R: int):
    out = []
    for q in range(-R, R+1):
        for r in range(-R, R+1):
            if max(abs(q), abs(r), abs(q+r)) <= R:
                out.append((q, r))
    out.sort(key=lambda c: (hex_dist(c), c[0], c[1]))
    return out


class HexEnv:
    def __init__(self, radius: int, candidate_radius: int, max_spread: int):
        self.radius = radius
        self.pad = 2
        self.cells = cells_in_radius(radius + self.pad)
        self.idx = {c: i for i, c in enumerate(self.cells)}
        self.root = self.idx[(0, 0)]
        self.dist = np.array([hex_dist(c) for c in self.cells])
        self.play = [self.idx[c] for c in cells_in_radius(candidate_radius)]
        self.segments = self.make_segments(radius + self.pad)
        self.seg_cells = [self.bits(m) for m in self.segments]
        self.seg_axis = []
        self.cell_to_segments = [[] for _ in self.cells]
        for sid, mask in enumerate(self.segments):
            cs = self.seg_cells[sid]
            if len(cs) >= 2:
                a, b = self.cells[cs[0]], self.cells[cs[1]]
                d = (b[0]-a[0], b[1]-a[1])
                axis = DIRS.index(d) if d in DIRS else 0
            else:
                axis = 0
            self.seg_axis.append(axis)
            x = mask
            while x:
                lsb = x & -x
                self.cell_to_segments[lsb.bit_length()-1].append(sid)
                x ^= lsb
        self.pairs = []
        for ix, a in enumerate(self.play):
            ca = self.cells[a]
            for b in self.play[ix+1:]:
                if hex_dist(ca, self.cells[b]) <= max_spread:
                    spread = hex_dist(ca, self.cells[b])
                    center = (hex_dist(ca) + hex_dist(self.cells[b])) / 2
                    self.pairs.append((a, b, spread, center))
        self.pairs.sort(key=lambda x: (x[3], x[2], x[0], x[1]))

    @staticmethod
    def bits(mask: int):
        out = []
        while mask:
            lsb = mask & -mask
            out.append(lsb.bit_length()-1)
            mask ^= lsb
        return out

    def make_segments(self, R):
        cs = set(cells_in_radius(R))
        segs = set()
        for c in cs:
            for d in DIRS:
                seg = tuple(add(c, d, k) for k in range(6))
                if all(x in cs for x in seg):
                    m = 0
                    for x in seg:
                        m |= 1 << self.idx[x]
                    segs.add(m)
        return sorted(segs)

    def has_win(self, black: int, white: int, player: int):
        mine = black if player == 1 else white
        return any((seg & mine) == seg for seg in self.segments)


@lru_cache(maxsize=800000)
def hitting(edges: Tuple[int, ...], max_k: int=8) -> int:
    edges = tuple(e for e in edges if e)
    if not edges:
        return 0
    universe, forced = 0, 0
    for e in edges:
        universe |= e
        if e.bit_count() == 1:
            forced |= e
    fcnt = forced.bit_count()
    if fcnt > max_k:
        return max_k + 1
    reduced = tuple(e for e in edges if not (e & forced))
    if not reduced:
        return fcnt

    def can_hit(rem_edges, chosen, slots):
        rem = [e for e in rem_edges if not (e & chosen)]
        if not rem:
            return True
        if slots <= 0:
            return False
        # lower bound: greedily pack disjoint edges
        used, lb = 0, 0
        for e in sorted(rem, key=lambda x: x.bit_count()):
            if not (e & used):
                used |= e
                lb += 1
                if lb > slots:
                    return False
        edge = min(rem, key=lambda x: x.bit_count())
        x = edge
        while x:
            lsb = x & -x
            if can_hit(tuple(rem), chosen | lsb, slots - 1):
                return True
            x ^= lsb
        return False

    for k in range(fcnt, min(max_k, universe.bit_count()) + 1):
        if can_hit(reduced, forced, k - fcnt):
            return k
    return max_k + 1


def obligations_after_pair(env: HexEnv, black: int, white: int, player: int, a: int, b: int):
    mm = (1 << a) | (1 << b)
    mine, opp = (black | mm, white) if player == 1 else (white | mm, black)
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
    return exact, proto, terminal, hitting(exact), hitting(proto)


def count_run(env, black, white, player, i, d):
    mine = black if player == 1 else white
    c = env.cells[i]
    n = 1
    for sgn in (1, -1):
        for k in range(1, 6):
            j = env.idx.get(add(c, d, sgn*k))
            if j is None or not (mine & (1 << j)):
                break
            n += 1
    return n


def rough_heuristic(env, black, white, player, a, b):
    s = 0.0
    for i in (a, b):
        for d in DIRS:
            own = count_run(env, black, white, player, i, d)
            opp = count_run(env, black, white, -player, i, d)
            s += own*own + (10 if opp >= 5 else 4 if opp >= 4 else 1.5 if opp >= 3 else 0)
    s += 0.18 * max(0, 6 - hex_dist(env.cells[a], env.cells[b]))
    s -= 0.02 * (env.dist[a] + env.dist[b])
    return s


def line_count(env, mask, seg):
    return (mask & seg).bit_count()


def line_potential(env, black, white, player, sid):
    seg = env.segments[sid]
    if player == 1:
        if seg & white:
            return 0.0
        cnt = line_count(env, black, seg)
        rooted = bool(seg & (1 << env.root))
        # Black: odd debt. 3 and 5 are highly meaningful; 4 is a passage state.
        weights = {0: 0, 1: 0.20, 2: 0.75, 3: 6.4, 4: 2.1, 5: 17.5, 6: 120.0}
        return weights[cnt] + (1.05 + 0.28*cnt if rooted else 0.0)
    else:
        if seg & black:
            return 0.0
        cnt = line_count(env, white, seg)
        # White: even closure. 4 and 6 matter; 2 is scaffold; 5 is less strategic unless terminal-ready.
        weights = {0: 0, 1: 0.16, 2: 1.35, 3: 0.75, 4: 9.3, 5: 3.4, 6: 124.0}
        return weights[cnt]


def black_root_debt(env, black, white, sid):
    seg = env.segments[sid]
    if not (seg & (1 << env.root)) or (seg & white):
        return 0.0
    cnt = (seg & black).bit_count()
    return {0: 0.0, 1: 0.55, 2: 1.0, 3: 7.5, 4: 2.6, 5: 19.0, 6: 120.0}[cnt]


def threshold_profile_after(env, black, white, player, a, b):
    mm = (1 << a) | (1 << b)
    nb, nw = (black | mm, white) if player == 1 else (black, white | mm)
    mine = nb if player == 1 else nw
    opp = nw if player == 1 else nb
    counts = Counter()
    root_counts = Counter()
    live_axes = [0, 0, 0]
    touched = set(env.cell_to_segments[a]) | set(env.cell_to_segments[b])
    for sid in touched:
        seg = env.segments[sid]
        if seg & opp:
            continue
        cnt = (seg & mine).bit_count()
        counts[cnt] += 1
        live_axes[env.seg_axis[sid]] += int(cnt > 0)
        if seg & (1 << env.root):
            root_counts[cnt] += 1
    anis = max(live_axes) - min(live_axes)
    return counts, root_counts, anis


def ap_score(env, black, white, player, a, b):
    mm = (1 << a) | (1 << b)
    nb, nw = (black | mm, white) if player == 1 else (black, white | mm)
    touched = set(env.cell_to_segments[a]) | set(env.cell_to_segments[b])
    delta, block = 0.0, 0.0
    axes = [0.0, 0.0, 0.0]
    for sid in touched:
        before = line_potential(env, black, white, player, sid)
        after = line_potential(env, nb, nw, player, sid)
        d = after - before
        delta += d
        axes[env.seg_axis[sid]] += max(0, d)
        if player == -1:
            killed = black_root_debt(env, black, white, sid) - black_root_debt(env, nb, nw, sid)
            block += max(0.0, killed)
        else:
            killed = line_potential(env, black, white, -1, sid) - line_potential(env, nb, nw, -1, sid)
            block += 0.35 * max(0.0, killed)
    anis = max(axes) - min(axes)
    sh = shape_of(env.cells, a, b)
    kind = pair_kind(sh)
    geom = 0.15 * max(0, 6 - hex_dist(env.cells[a], env.cells[b]))
    if player == 1 and kind in ("short_rail", "long_rail"):
        geom += 1.45
    if player == -1 and kind in ("bridge", "long_bridge", "bridge_rail"):
        geom += 1.35
    return delta + 0.86*block + 0.20*anis + geom



def branching_debt_bonus(env, black, white, a, b):
    """
    Black-only branching debt.

    Rooted odd debt is valuable only when it branches into a hard-to-cover
    obligation web. Rails with many overlapping blockers are penalized; disjoint
    proto/hard obligations across multiple A2 foliations are rewarded.

    This operationalises:
        Black value ≈ future transversal pressure - overlap/coverability.
    """
    mm = (1 << a) | (1 << b)
    mine = black | mm
    opp = white

    proto_edges = []
    hard_edges = []
    axes = set()
    rooted_proto = 0
    rooted_hard = 0
    odd_line_count = 0

    touched = set(env.cell_to_segments[a]) | set(env.cell_to_segments[b])
    for sid in touched:
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
            if seg & (1 << env.root):
                rooted_proto += 1
        elif cnt >= 4 and 1 <= empty.bit_count() <= 2:
            # exact/hard obligations are maturity channels; singleton 5-lines matter most.
            hard_edges.append(empty)
            if (seg & (1 << env.root)) and cnt >= 5:
                rooted_hard += 1

    proto_edges = tuple(sorted(set(proto_edges)))
    hard_edges = tuple(sorted(set(hard_edges)))
    tau_p = hitting(proto_edges)
    tau_h = hitting(hard_edges)
    pp = max(0, tau_p - 2)
    ph = max(0, tau_h - 2)

    def union_count(edges):
        u = 0
        for e in edges:
            u |= e
        return u.bit_count()

    def overlap_penalty(edges):
        if len(edges) <= 1:
            return 0.0
        inter = 0
        pairs = 0
        for i, e1 in enumerate(edges):
            for e2 in edges[i+1:]:
                inter += (e1 & e2).bit_count()
                pairs += 1
        return inter / max(1, pairs)

    proto_union = union_count(proto_edges)
    hard_union = union_count(hard_edges)
    proto_overlap = overlap_penalty(proto_edges)
    hard_overlap = overlap_penalty(hard_edges)

    # Branchiness: many distinct blockers per edge and many axes.
    proto_disjointness = proto_union / max(1, sum(e.bit_count() for e in proto_edges))
    hard_disjointness = hard_union / max(1, sum(e.bit_count() for e in hard_edges))
    axis_diversity = len(axes)

    # Strong pressure terms, but only if the web is not trivially coverable.
    score = (
        9.5 * pp +
        3.6 * tau_p +
        11.0 * ph +
        3.0 * tau_h +
        1.8 * len(proto_edges) +
        2.8 * len(hard_edges) +
        3.8 * axis_diversity +
        6.0 * proto_disjointness +
        4.0 * hard_disjointness +
        2.0 * rooted_proto * (1 + pp) +
        4.5 * rooted_hard * (1 + ph) +
        1.2 * odd_line_count
        - 5.2 * proto_overlap
        - 4.4 * hard_overlap
    )
    return float(max(0.0, score))

def split_side_bonus(env, black, white, player, a, b, ev):
    counts, root_counts, anis = threshold_profile_after(env, black, white, player, a, b)
    sh = shape_of(env.cells, a, b)
    kind = pair_kind(sh)
    if player == 1:
        # Black debt maturation: rooted 3/5 counts, proto lift, anisotropic debt rays.
        return (
            5.8 * root_counts[3] +
            9.5 * root_counts[5] +
            2.2 * counts[3] +
            3.0 * ev["pressure_proto"] +
            1.2 * anis +
            (1.8 if kind in ("short_rail", "long_rail") else 0.0)
        )
    else:
        # White closure/screen: 4/6 line access, exact pressure, bridge conversion, root screening.
        screen = 0.0
        touched = set(env.cell_to_segments[a]) | set(env.cell_to_segments[b])
        mm = (1 << a) | (1 << b)
        nb, nw = black, white | mm
        for sid in touched:
            screen += max(0.0, black_root_debt(env, black, white, sid) - black_root_debt(env, nb, nw, sid))
        return (
            5.0 * counts[4] +
            14.0 * counts[6] +
            4.2 * ev["pressure_exact"] +
            0.92 * screen +
            (2.4 if kind in ("bridge", "long_bridge", "bridge_rail") else 0.0)
        )


def tau_score(env, black, white, player, a, b):
    exact, proto, term, te, tp = obligations_after_pair(env, black, white, player, a, b)
    pe, pp = max(0, te - 2), max(0, tp - 2)
    h = rough_heuristic(env, black, white, player, a, b)
    return {
        "base_tau_score": float(75*int(term > 0) + 20*pe + 8.5*pp + 2.4*te + 1.15*tp + 0.04*h),
        "tau_exact": int(te),
        "tau_proto": int(tp),
        "pressure_exact": int(pe),
        "pressure_proto": int(pp),
        "terminal": int(term > 0),
        "exact_edges": len(exact),
        "proto_edges": len(proto),
    }


def candidate_pool(env, black, white, rng, args):
    occ = black | white
    central, tail = [], []
    for a, b, _, _ in env.pairs:
        if (occ & (1 << a)) or (occ & (1 << b)):
            continue
        if len(central) < args.max_considered:
            central.append((a, b))
        else:
            tail.append((a, b))
    rng.shuffle(tail)
    return central + tail[:args.random_reservoir]


def soft_pick(rows, rng, temp, top_k):
    rows = sorted(rows, reverse=True, key=lambda x: x[0])[:top_k]
    if not rows:
        return None
    scores = np.array([r[0] for r in rows], dtype=float)
    logits = (scores - scores.max()) / max(1e-6, temp)
    p = np.exp(np.clip(logits, -60, 60))
    p /= p.sum()
    ix = rng.choices(range(len(rows)), weights=p, k=1)[0]
    H = float(-(p[p > 1e-12] * np.log(p[p > 1e-12])).sum())
    return rows[ix], H


def choose_move(env, black, white, player, agent, rng, args):
    pool = candidate_pool(env, black, white, rng, args)
    tau_evals = 0
    ap_evals = 0
    rows = []

    if agent == "symmetric_tau":
        rough = [(rough_heuristic(env, black, white, player, a, b), a, b) for a, b in pool]
        rough.sort(reverse=True, key=lambda x: x[0])
        for _, a, b in rough[:args.tau_width]:
            ev = tau_score(env, black, white, player, a, b)
            tau_evals += 1
            score = ev["base_tau_score"]
            rows.append((score, a, b, ev, 0.0, 0.0))

    elif agent == "odd_even_ap":
        for a, b in pool:
            aps = ap_score(env, black, white, player, a, b)
            ap_evals += 1
            ev = {"base_tau_score": 0.0, "tau_exact": 0, "tau_proto": 0, "pressure_exact": 0, "pressure_proto": 0, "terminal": 0, "exact_edges": 0, "proto_edges": 0}
            rows.append((aps, a, b, ev, aps, 0.0))

    elif agent in ("hybrid_shared", "hybrid_split", "hybrid_branching"):
        ap_rows = []
        for a, b in pool:
            aps = ap_score(env, black, white, player, a, b)
            ap_evals += 1
            ap_rows.append((aps, a, b))
        ap_rows.sort(reverse=True, key=lambda x: x[0])
        width = args.hybrid_tau_width if agent == "hybrid_shared" else args.branch_tau_width if agent == "hybrid_branching" else args.split_tau_width
        for aps, a, b in ap_rows[:width]:
            ev = tau_score(env, black, white, player, a, b)
            tau_evals += 1
            if agent == "hybrid_shared":
                bonus = args.hybrid_ap_weight * aps
            elif agent == "hybrid_split":
                side_bonus = split_side_bonus(env, black, white, player, a, b, ev)
                if player == 1:
                    bonus = args.split_black_ap_weight * aps + args.split_black_bonus_weight * side_bonus
                else:
                    bonus = args.split_white_ap_weight * aps + args.split_white_bonus_weight * side_bonus
            else:
                if player == 1:
                    side_bonus = branching_debt_bonus(env, black, white, a, b)
                    bonus = args.branch_black_ap_weight * aps + args.branch_black_bonus_weight * side_bonus
                else:
                    side_bonus = split_side_bonus(env, black, white, player, a, b, ev)
                    bonus = args.branch_white_ap_weight * aps + args.branch_white_bonus_weight * side_bonus
            rows.append((ev["base_tau_score"] + bonus, a, b, ev, aps, bonus))
    else:
        raise ValueError(agent)

    picked = soft_pick(rows, rng, args.temperature, args.top_k)
    if picked is None:
        return None
    (score, a, b, ev, aps, bonus), H = picked
    ev = dict(ev)
    ev.update({
        "score": float(score),
        "ap_score": float(aps),
        "side_bonus": float(bonus),
        "tau_evals": int(tau_evals),
        "ap_evals": int(ap_evals),
        "policy_entropy": H,
        "candidates": len(pool),
        "shape": shape_of(env.cells, a, b),
        "kind": pair_kind(shape_of(env.cells, a, b)),
    })
    return a, b, ev


def play_game(env, black_agent, white_agent, gid, seed, args):
    rng = random.Random(seed)
    black = 1 << env.root
    white = 0
    moves = []
    winner = 0
    terminal_ply = -1
    for ply in range(1, args.max_plies + 1):
        player = -1 if ply % 2 == 1 else 1
        agent = white_agent if player == -1 else black_agent
        chosen = choose_move(env, black, white, player, agent, rng, args)
        if chosen is None:
            break
        a, b, ev = chosen
        mm = (1 << a) | (1 << b)
        if player == 1:
            black |= mm
        else:
            white |= mm
        won = bool(ev["terminal"]) or env.has_win(black, white, player)
        if won:
            winner = player
            terminal_ply = ply
        ca, cb = env.cells[a], env.cells[b]
        moves.append({
            "game_id": gid, "ply": ply, "player": player, "agent": agent,
            "black_agent": black_agent, "white_agent": white_agent,
            "a_q": ca[0], "a_r": ca[1], "b_q": cb[0], "b_r": cb[1],
            **ev,
        })
        if winner:
            break
    summary = {
        "game_id": gid,
        "black_agent": black_agent,
        "white_agent": white_agent,
        "winner": winner,
        "winner_agent": black_agent if winner == 1 else white_agent if winner == -1 else "draw",
        "terminal_ply": terminal_ply,
        "plies": len(moves),
        "black_stones": black.bit_count(),
        "white_stones": white.bit_count(),
        "total_tau_evals": sum(m["tau_evals"] for m in moves),
        "total_ap_evals": sum(m["ap_evals"] for m in moves),
        "black_tau_evals": sum(m["tau_evals"] for m in moves if m["player"] == 1),
        "white_tau_evals": sum(m["tau_evals"] for m in moves if m["player"] == -1),
        "max_proto_pressure": max([m["pressure_proto"] for m in moves] + [0]),
        "max_exact_pressure": max([m["pressure_exact"] for m in moves] + [0]),
        "mean_policy_entropy": float(np.mean([m["policy_entropy"] for m in moves])) if moves else 0.0,
        "black_odd_debt_mean": float(np.mean([m["tau_proto"] + 2*m["pressure_proto"] for m in moves if m["player"] == 1])) if any(m["player"] == 1 for m in moves) else 0.0,
        "white_even_closure_mean": float(np.mean([m["tau_exact"] + 2*m["pressure_exact"] + 3*m["terminal"] for m in moves if m["player"] == -1])) if any(m["player"] == -1 for m in moves) else 0.0,
    }
    return summary, moves


def run_experiment(args):
    env = HexEnv(args.radius, args.candidate_radius, args.max_spread)
    summaries, moves = [], []
    gid = 0
    t0 = time.perf_counter()
    for black_agent in AGENTS:
        for white_agent in AGENTS:
            for rep in range(args.games_per_matchup):
                s, m = play_game(env, black_agent, white_agent, gid, args.seed + 7919*gid, args)
                summaries.append(s)
                moves.extend(m)
                gid += 1
    return pd.DataFrame(summaries), pd.DataFrame(moves), time.perf_counter() - t0


def aggregate(summaries, moves):
    by_match = summaries.groupby(["black_agent", "white_agent"], as_index=False).agg(
        games=("game_id", "size"),
        black_win_rate=("winner", lambda x: float((x == 1).mean())),
        white_win_rate=("winner", lambda x: float((x == -1).mean())),
        draw_rate=("winner", lambda x: float((x == 0).mean())),
        mean_plies=("plies", "mean"),
        mean_tau_evals=("total_tau_evals", "mean"),
        mean_ap_evals=("total_ap_evals", "mean"),
        mean_black_odd_debt=("black_odd_debt_mean", "mean"),
        mean_white_even_closure=("white_even_closure_mean", "mean"),
        mean_max_proto=("max_proto_pressure", "mean"),
        mean_max_exact=("max_exact_pressure", "mean"),
    )
    rows = []
    for agent in AGENTS:
        as_black = summaries[summaries["black_agent"] == agent]
        as_white = summaries[summaries["white_agent"] == agent]
        ctrl = moves[moves["agent"] == agent]
        rows.append({
            "agent": agent,
            "games_as_black": len(as_black),
            "black_win_rate": float((as_black["winner"] == 1).mean()) if len(as_black) else 0,
            "games_as_white": len(as_white),
            "white_win_rate": float((as_white["winner"] == -1).mean()) if len(as_white) else 0,
            "overall_win_rate": float((summaries["winner_agent"] == agent).mean()),
            "mean_plies_in_games": float(pd.concat([as_black["plies"], as_white["plies"]]).mean()) if len(as_black)+len(as_white) else 0,
            "moves_controlled": int(len(ctrl)),
            "tau_evals_per_move": float(ctrl["tau_evals"].mean()) if len(ctrl) else 0,
            "ap_evals_per_move": float(ctrl["ap_evals"].mean()) if len(ctrl) else 0,
            "terminal_move_rate": float(ctrl["terminal"].mean()) if len(ctrl) else 0,
            "mean_move_proto_pressure": float(ctrl["pressure_proto"].mean()) if len(ctrl) else 0,
            "mean_move_exact_pressure": float(ctrl["pressure_exact"].mean()) if len(ctrl) else 0,
            "mean_side_bonus": float(ctrl["side_bonus"].mean()) if len(ctrl) else 0,
        })
    by_agent = pd.DataFrame(rows)
    return by_match, by_agent


def plot_results(out, summaries, moves, by_match, by_agent):
    fig = out / "figures"
    fig.mkdir(parents=True, exist_ok=True)

    mat = by_match.pivot(index="black_agent", columns="white_agent", values="black_win_rate").reindex(index=AGENTS, columns=AGENTS)
    plt.figure(figsize=(7, 6))
    plt.imshow(mat.values, vmin=0, vmax=1)
    plt.xticks(np.arange(len(AGENTS)), AGENTS, rotation=35, ha="right")
    plt.yticks(np.arange(len(AGENTS)), AGENTS)
    plt.xlabel("White agent")
    plt.ylabel("Black agent")
    plt.title("Black win rate by matchup")
    plt.colorbar(label="Black win rate")
    plt.tight_layout()
    plt.savefig(fig / "black_win_matchup_matrix.png", dpi=190)
    plt.close()

    plt.figure(figsize=(8.6, 5))
    x = np.arange(len(by_agent))
    plt.bar(x-0.2, by_agent["black_win_rate"], width=0.4, label="as Black")
    plt.bar(x+0.2, by_agent["white_win_rate"], width=0.4, label="as White")
    plt.xticks(x, by_agent["agent"], rotation=25, ha="right")
    plt.ylabel("win rate")
    plt.title("Agent win rates by side")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig / "agent_win_rates_by_side.png", dpi=190)
    plt.close()

    plt.figure(figsize=(8.6, 5))
    x = np.arange(len(by_agent))
    plt.bar(x-0.2, by_agent["tau_evals_per_move"], width=0.4, label="tau evals/move")
    plt.bar(x+0.2, by_agent["ap_evals_per_move"], width=0.4, label="AP evals/move")
    plt.xticks(x, by_agent["agent"], rotation=25, ha="right")
    plt.ylabel("evaluations")
    plt.title("Computation profile")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig / "agent_computation_profile.png", dpi=190)
    plt.close()

    plt.figure(figsize=(8.6, 5))
    x = np.arange(len(by_agent))
    plt.bar(x-0.2, by_agent["mean_move_proto_pressure"], width=0.4, label="proto pressure")
    plt.bar(x+0.2, by_agent["mean_move_exact_pressure"], width=0.4, label="exact pressure")
    plt.xticks(x, by_agent["agent"], rotation=25, ha="right")
    plt.ylabel("mean pressure per move")
    plt.title("Pressure generated by agent moves")
    plt.legend()
    plt.tight_layout()
    plt.savefig(fig / "agent_pressure_profile.png", dpi=190)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.hist(summaries["plies"], bins=range(1, int(summaries["plies"].max())+3))
    plt.xlabel("plies after Black singleton")
    plt.ylabel("games")
    plt.title("Game length distribution")
    plt.tight_layout()
    plt.savefig(fig / "game_lengths.png", dpi=190)
    plt.close()

    shape = moves.groupby(["agent", "shape"], as_index=False).agg(count=("shape", "size"), terminal=("terminal", "sum"), mean_score=("score", "mean")).sort_values("count", ascending=False)
    top = moves.groupby("shape", as_index=False).agg(count=("shape", "size"), terminal=("terminal", "sum"), mean_score=("score", "mean")).sort_values("count", ascending=False).head(18)
    plt.figure(figsize=(9, 5))
    x = np.arange(len(top))
    plt.bar(x, top["count"])
    plt.xticks(x, top["shape"], rotation=45, ha="right")
    plt.ylabel("moves")
    plt.title("Move-shape spectrum")
    plt.tight_layout()
    plt.savefig(fig / "shape_spectrum.png", dpi=190)
    plt.close()
    return shape, top


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="hexconnect6_split_hybrid_experiment_out")
    p.add_argument("--radius", type=int, default=6)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--max-spread", type=int, default=7)
    p.add_argument("--games-per-matchup", type=int, default=8)
    p.add_argument("--max-plies", type=int, default=28)
    p.add_argument("--max-considered", type=int, default=230)
    p.add_argument("--random-reservoir", type=int, default=120)
    p.add_argument("--tau-width", type=int, default=56)
    p.add_argument("--hybrid-tau-width", type=int, default=28)
    p.add_argument("--split-tau-width", type=int, default=28)
    p.add_argument("--hybrid-ap-weight", type=float, default=0.46)
    p.add_argument("--branch-tau-width", type=int, default=25)
    p.add_argument("--branch-black-ap-weight", type=float, default=0.22)
    p.add_argument("--branch-black-bonus-weight", type=float, default=1.05)
    p.add_argument("--branch-white-ap-weight", type=float, default=0.26)
    p.add_argument("--branch-white-bonus-weight", type=float, default=0.58)
    p.add_argument("--split-black-ap-weight", type=float, default=0.82)
    p.add_argument("--split-white-ap-weight", type=float, default=0.30)
    p.add_argument("--split-black-bonus-weight", type=float, default=0.72)
    p.add_argument("--split-white-bonus-weight", type=float, default=0.52)
    p.add_argument("--temperature", type=float, default=0.85)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--seed", type=int, default=260514)
    args = p.parse_args()

    out = Path(args.out)
    data = out / "data"
    fig = out / "figures"
    data.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)

    summaries, moves, elapsed = run_experiment(args)
    by_match, by_agent = aggregate(summaries, moves)
    shape_by_agent, shape_top = plot_results(out, summaries, moves, by_match, by_agent)

    summaries.to_csv(data / "game_summaries.csv", index=False)
    moves.to_csv(data / "move_records.csv", index=False)
    by_match.to_csv(data / "matchup_matrix.csv", index=False)
    by_agent.to_csv(data / "agent_aggregates.csv", index=False)
    shape_by_agent.to_csv(data / "shape_by_agent.csv", index=False)
    shape_top.to_csv(data / "shape_spectrum.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "games": int(len(summaries)),
        "moves": int(len(moves)),
        "elapsed_seconds": elapsed,
        "moves_per_second": float(len(moves) / max(elapsed, 1e-9)),
        "terminal_rate": float((summaries["winner"] != 0).mean()),
        "black_win_rate": float((summaries["winner"] == 1).mean()),
        "white_win_rate": float((summaries["winner"] == -1).mean()),
        "mean_plies": float(summaries["plies"].mean()),
        "hitting_cache": str(hitting.cache_info()),
        "agent_aggregates": by_agent.to_dict(orient="records"),
        "matchups": by_match.to_dict(orient="records"),
        "top_shapes": shape_top.head(12).to_dict(orient="records"),
        "interpretation": (
            "The split hybrid tests the rooted-threshold parity derivation: Black should use a rooted odd-debt representation, "
            "while White should use even closure plus anti-root screening. The expected positive result is improved Black debt "
            "generation or comparable tactical strength with half the tau evaluations of symmetric_tau."
        ),
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    (out / "README.md").write_text(
        "# Branching-debt Hex Connect-6 experiment\n\n"
        "Adds a branching-debt hybrid agent: Black=high-transversal low-overlap odd debt + tau; White=even closure/screen + tau.\n"
    )

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_branching_debt_experiment.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
