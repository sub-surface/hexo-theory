#!/usr/bin/env python3
"""
wolfram_hexconnect6_hypergraphs.py

Wolfram-inspired hypergraph/multiway experiment for infinite Hex Connect-6.

Core ideas borrowed into the game setting:
  - Hypergraph state: urgent obligations after a move are hyperedges over empty cells.
  - Updating event: a two-stone move rewrites the board and changes the obligation hypergraph.
  - Multiway graph: all retained near-best futures under a scoring rule.
  - Branchial graph: states at the same ply connected by similarity of their obligation hypergraphs.
  - Causal graph: updating events connected when later events reuse/intersect earlier obligation vertices.
  - Rulial scan: compare nearby scoring rules as a tiny "rule space" over pressure/heuristic weights.

This is not a proof of optimal play. It is a compact empirical instrument for the conjecture:
  Tactical completion in Hex Connect-6 is governed by low-dimensional hypergraph pressure
  rather than by raw legal-move abundance.

Outputs:
  figures/*.png
  data/*.csv
  data/metrics.json
  README.md
  zip archive containing everything

Run:
  python wolfram_hexconnect6_hypergraphs.py --out wolfram_hex_out --radius 7 --candidate-radius 5 --plies 5 --beam 24 --branch 3
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Sequence, Set

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


Cell = Tuple[int, int]
Board = Dict[Cell, int]
DIRS = ((1, 0), (0, 1), (1, -1))


def hex_dist(a: Cell, b: Cell = (0, 0)) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def add(a: Cell, d: Cell, k: int = 1) -> Cell:
    return (a[0] + d[0] * k, a[1] + d[1] * k)


def axial_to_xy(c: Tuple[float, float]) -> Tuple[float, float]:
    q, r = c
    return (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)


def cells_in_radius(radius: int) -> List[Cell]:
    out = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                out.append((q, r))
    return out


def rotate60(c: Cell) -> Cell:
    q, r = c
    return (-r, q + r)


def reflect(c: Cell) -> Cell:
    q, r = c
    return (r, q)


def d6_orbit(c: Cell) -> List[Cell]:
    out = []
    x = c
    for _ in range(6):
        out.append(x)
        out.append(reflect(x))
        x = rotate60(x)
    return out


def canonical_delta(d: Cell) -> Cell:
    return sorted(set(d6_orbit(d)))[0]


def all_segments(radius: int, pad: int = 2) -> List[Tuple[Cell, ...]]:
    cells = set(cells_in_radius(radius + pad))
    segs = set()
    for c in cells:
        for d in DIRS:
            seg = tuple(add(c, d, k) for k in range(6))
            if all(x in cells for x in seg):
                segs.add(seg)
    return sorted(segs)


def ladder_trap_pattern() -> Board:
    black = [(-2,0),(-1,0),(0,0),(1,0),(0,-1),(1,-2),(2,-3),(-1,1),(1,1),(3,-1)]
    white = [(-2,1),(-1,-1),(2,0),(3,-2),(0,1),(2,-1),(-3,2),(1,-3),(3,0)]
    b: Board = {}
    for c in black:
        b[c] = 1
    for c in white:
        b[c] = -1
    return b


def seeded_fork_pattern() -> Board:
    black = [(0,0),(1,0),(2,0),(3,0),(1,-1),(2,-2),(-1,1),(0,1),(2,-1)]
    white = [(0,-1),(1,1),(3,-1),(-1,0),(2,1),(4,-2),(-2,2),(0,2)]
    b: Board = {}
    for c in black:
        b[c] = 1
    for c in white:
        b[c] = -1
    return b


def count_run(board: Board, cell: Cell, direction: Cell, player: int) -> Tuple[int, int]:
    count = 1
    open_ends = 0
    for sgn in (1, -1):
        for k in range(1, 6):
            c = add(cell, direction, sgn * k)
            v = board.get(c, 0)
            if v == player:
                count += 1
            else:
                if v == 0:
                    open_ends += 1
                break
    return count, open_ends


def immediate_win_if_placed(board: Board, cell: Cell, player: int) -> bool:
    return any(count_run(board, cell, d, player)[0] >= 6 for d in DIRS)


def obligations_after_move(board: Board, move: Tuple[Cell, Cell], player: int, segments: Sequence[Tuple[Cell, ...]]):
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    obligations: List[Tuple[Cell, ...]] = []
    terminal_segments: List[Tuple[Cell, ...]] = []
    for seg in segments:
        vals = [nb.get(c, 0) for c in seg]
        if any(v == -player for v in vals):
            continue
        empties = tuple(c for c, v in zip(seg, vals) if v == 0)
        mine = 6 - len(empties)
        if mine >= 6:
            terminal_segments.append(seg)
        elif mine >= 4 and 1 <= len(empties) <= 2:
            obligations.append(tuple(sorted(empties)))
    return sorted(set(obligations)), sorted(set(terminal_segments))


def hitting_number(obligations: Sequence[Tuple[Cell, ...]], max_k: int = 7) -> int:
    if not obligations:
        return 0
    universe = sorted(set(c for edge in obligations for c in edge))
    singletons = {e[0] for e in obligations if len(e) == 1}
    if len(singletons) > max_k:
        return max_k + 1
    for k in range(1, min(max_k, len(universe)) + 1):
        for combo in itertools.combinations(universe, k):
            S = set(combo)
            if all(any(c in S for c in edge) for edge in obligations):
                return k
    return max_k + 1


def heuristic_pair_value(board: Board, move: Tuple[Cell, Cell], player: int) -> float:
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    v = 0.0
    for c in move:
        for d in DIRS:
            mine, _ = count_run(nb, c, d, player)
            theirs, _ = count_run(board, c, d, -player)
            v += mine * mine + (6 if theirs >= 5 else 2 if theirs >= 4 else 0)
    v += max(0, 6 - hex_dist(move[0], move[1])) * 0.2
    return float(v)


def candidate_moves(board: Board, cells: Sequence[Cell], player: int, candidate_radius: int, max_spread: int, prefilter: int):
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    rows = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                h = heuristic_pair_value(board, (a, b), player)
                rows.append((h, a, b))
    rows.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in rows[:prefilter]]


def move_evaluation(board: Board, move: Tuple[Cell, Cell], player: int, segments, heuristic: float):
    obligations, terminal_segments = obligations_after_move(board, move, player, segments)
    tau = hitting_number(obligations)
    pressure = max(0, tau - 2)
    terminal = 1 if terminal_segments else 0
    shape = canonical_delta((move[1][0] - move[0][0], move[1][1] - move[0][1]))
    verts = sorted(set(c for e in obligations for c in e))
    return dict(
        move=move,
        heuristic=float(heuristic),
        obligations=obligations,
        obligation_vertices=verts,
        terminal_segments=terminal_segments,
        tau=int(tau),
        pressure=int(pressure),
        terminal=int(terminal),
        shape=shape,
    )


def board_signature(board: Board) -> Tuple[Tuple[int, int, int], ...]:
    return tuple(sorted((q, r, v) for (q, r), v in board.items()))


def obligation_signature(obligations: Sequence[Tuple[Cell, ...]]) -> Tuple[Tuple[Cell, ...], ...]:
    return tuple(sorted(tuple(sorted(e)) for e in obligations))


def hypergraph_feature_vector(obligations: Sequence[Tuple[Cell, ...]], radius: int) -> np.ndarray:
    # Compact state vector: radial histogram of obligation vertices + size counts + tau-ish surrogates.
    radial = np.zeros(radius + 1, dtype=float)
    edge_sizes = np.zeros(3, dtype=float)
    vertices = set()
    for e in obligations:
        if len(e) <= 2:
            edge_sizes[len(e)] += 1
        for c in e:
            if hex_dist(c) <= radius:
                radial[hex_dist(c)] += 1
                vertices.add(c)
    if radial.sum():
        radial /= radial.sum()
    density = np.array([len(obligations), len(vertices), edge_sizes[1], edge_sizes[2]], dtype=float)
    return np.concatenate([radial, density])


def hypergraph_spectrum(obligations: Sequence[Tuple[Cell, ...]]):
    vertices = sorted(set(c for e in obligations for c in e))
    if not vertices or not obligations:
        return np.array([0.0]), vertices, np.zeros((0, 0))
    idx = {v: i for i, v in enumerate(vertices)}
    B = np.zeros((len(vertices), len(obligations)), dtype=float)
    for j, e in enumerate(obligations):
        for c in e:
            B[idx[c], j] = 1.0 / math.sqrt(len(e))
    A = B @ B.T
    np.fill_diagonal(A, 0.0)
    D = np.diag(A.sum(axis=1))
    L = D - A
    eigs = np.linalg.eigvalsh(L)
    return eigs, vertices, A


def state_similarity(sig_a: Tuple[Tuple[Cell, ...], ...], sig_b: Tuple[Tuple[Cell, ...], ...]) -> float:
    A = set(sig_a)
    B = set(sig_b)
    if not A and not B:
        return 1.0
    return len(A & B) / max(1, len(A | B))


@dataclass
class State:
    id: int
    ply: int
    board: Board
    side: int
    parent_state: int | None
    event_id: int | None
    score: float
    mass: float
    obligations: Tuple[Tuple[Cell, ...], ...]
    obligation_vertices: Tuple[Cell, ...]


@dataclass
class Event:
    id: int
    ply: int
    parent_state: int
    child_state: int
    side: int
    move: Tuple[Cell, Cell]
    tau: int
    pressure: int
    terminal: int
    heuristic: float
    shape: Cell
    obligations: Tuple[Tuple[Cell, ...], ...]
    obligation_vertices: Tuple[Cell, ...]
    parent_event: int | None


def build_multiway(args, pressure_weight=1.0, heuristic_weight=0.15, terminal_weight=2.0):
    cells = cells_in_radius(args.radius)
    segments = all_segments(args.radius, pad=2)
    board0 = ladder_trap_pattern() if args.pattern == "ladder" else seeded_fork_pattern()

    states: List[State] = []
    events: List[Event] = []
    seen_by_ply: Dict[Tuple[int, Tuple[Tuple[int, int, int], ...]], int] = {}

    root = State(
        id=0, ply=0, board=board0, side=args.player, parent_state=None, event_id=None,
        score=0.0, mass=1.0, obligations=tuple(), obligation_vertices=tuple()
    )
    states.append(root)
    frontier = [root]
    seen_by_ply[(0, board_signature(board0))] = 0

    for ply in range(args.plies):
        candidates: List[State] = []
        for st in frontier:
            moves = candidate_moves(st.board, cells, st.side, args.candidate_radius, args.max_spread, args.prefilter)
            evals = []
            for a, b, h in moves:
                ev = move_evaluation(st.board, (a, b), st.side, segments, h)
                # Wolfram-like "updating rule" score: different rule weights give different multiway slices.
                rule_score = (
                    pressure_weight * ev["pressure"]
                    + 0.35 * ev["tau"]
                    + terminal_weight * ev["terminal"]
                    + heuristic_weight * np.tanh(ev["heuristic"] / 40.0)
                    + 0.05 * len(ev["obligations"])
                )
                ev["rule_score"] = float(rule_score)
                evals.append(ev)
            evals.sort(key=lambda e: e["rule_score"], reverse=True)

            # Branch from this state using the local top-N rules.
            chosen = evals[:args.branch]
            denom = sum(math.exp(e["rule_score"]) for e in chosen) or 1.0
            for ev in chosen:
                nb = dict(st.board)
                nb[ev["move"][0]] = st.side
                nb[ev["move"][1]] = st.side
                sig = board_signature(nb)
                # Keep duplicate board states if they arise from different causal histories? For a multiway graph,
                # merging by state supports a causal-invariance/reconvergence diagnostic.
                key_sig = (ply + 1, sig)
                child_id = seen_by_ply.get(key_sig)
                if child_id is None:
                    child_id = len(states)
                    seen_by_ply[key_sig] = child_id
                    child_state = State(
                        id=child_id,
                        ply=ply + 1,
                        board=nb,
                        side=-st.side,
                        parent_state=st.id,
                        event_id=None,
                        score=st.score + ev["rule_score"] * (1 if st.side == args.player else 0.85),
                        mass=st.mass * math.exp(ev["rule_score"]) / denom,
                        obligations=obligation_signature(ev["obligations"]),
                        obligation_vertices=tuple(ev["obligation_vertices"]),
                    )
                    states.append(child_state)
                else:
                    old = states[child_id]
                    old.mass += st.mass * math.exp(ev["rule_score"]) / denom
                    old.score = max(old.score, st.score + ev["rule_score"])
                    child_state = old

                event_id = len(events)
                event = Event(
                    id=event_id,
                    ply=ply + 1,
                    parent_state=st.id,
                    child_state=child_id,
                    side=st.side,
                    move=ev["move"],
                    tau=ev["tau"],
                    pressure=ev["pressure"],
                    terminal=ev["terminal"],
                    heuristic=ev["heuristic"],
                    shape=ev["shape"],
                    obligations=obligation_signature(ev["obligations"]),
                    obligation_vertices=tuple(ev["obligation_vertices"]),
                    parent_event=st.event_id,
                )
                events.append(event)
                states[child_id].event_id = event_id
                candidates.append(states[child_id])

        # Beam foliation: retain high mass/score states at this ply.
        candidates.sort(key=lambda s: s.mass * (1 + max(0.0, s.score)), reverse=True)
        frontier = candidates[:args.beam]

    return states, events


def build_branchial_edges(states: Sequence[State], min_similarity=0.15):
    edges = []
    by_ply: Dict[int, List[State]] = {}
    for s in states:
        by_ply.setdefault(s.ply, []).append(s)
    for ply, layer in by_ply.items():
        for i, a in enumerate(layer):
            for b in layer[i + 1:]:
                sim = state_similarity(a.obligations, b.obligations)
                if sim >= min_similarity:
                    edges.append((a.id, b.id, ply, sim))
    return edges


def build_causal_edges(events: Sequence[Event]):
    edges = []
    for e in events:
        if e.parent_event is not None:
            parent = events[e.parent_event]
            overlap = len(set(parent.obligation_vertices) & set(e.move))
            obligation_overlap = len(set(parent.obligation_vertices) & set(e.obligation_vertices))
            if overlap or obligation_overlap:
                edges.append((parent.id, e.id, overlap + obligation_overlap))
        # Extra cross-branch causal edges: same/overlapping obligation vertices at later ply.
    for i, a in enumerate(events):
        A = set(a.obligation_vertices)
        if not A:
            continue
        for b in events[i + 1:]:
            if b.ply <= a.ply:
                continue
            B = set(b.move) | set(b.obligation_vertices)
            ov = len(A & B)
            if ov >= 2:
                edges.append((a.id, b.id, ov))
    return edges


def pca2(X):
    X = np.asarray(X, dtype=float)
    if X.ndim != 2 or X.shape[0] == 0:
        return np.zeros((0, 2))
    X = X - X.mean(axis=0, keepdims=True)
    if X.shape[0] == 1:
        return np.zeros((1, 2))
    U, S, Vt = np.linalg.svd(X, full_matrices=False)
    coords = X @ Vt[:2].T if Vt.shape[0] >= 2 else np.column_stack([X @ Vt[0], np.zeros(X.shape[0])])
    return coords


def force_layout(n, edges, seed=0, steps=250):
    rng = np.random.default_rng(seed)
    pos = rng.normal(size=(n, 2))
    if n == 0:
        return pos
    for _ in range(steps):
        disp = np.zeros_like(pos)
        # Repulsion
        for i in range(n):
            delta = pos[i] - pos
            dist2 = np.sum(delta * delta, axis=1) + 0.04
            disp[i] += np.sum(delta / dist2[:, None], axis=0) * 0.012
        # Attraction
        for a, b, w in edges:
            if a >= n or b >= n:
                continue
            delta = pos[b] - pos[a]
            disp[a] += 0.012 * w * delta
            disp[b] -= 0.012 * w * delta
        pos += np.clip(disp, -0.05, 0.05)
    return pos


def state_table(states: Sequence[State]):
    return pd.DataFrame([dict(
        state_id=s.id, ply=s.ply, side=s.side, parent_state=-1 if s.parent_state is None else s.parent_state,
        event_id=-1 if s.event_id is None else s.event_id, score=s.score, mass=s.mass,
        num_stones=len(s.board), num_obligations=len(s.obligations), num_obligation_vertices=len(s.obligation_vertices),
    ) for s in states])


def event_table(events: Sequence[Event]):
    return pd.DataFrame([dict(
        event_id=e.id, ply=e.ply, parent_state=e.parent_state, child_state=e.child_state, side=e.side,
        a_q=e.move[0][0], a_r=e.move[0][1], b_q=e.move[1][0], b_r=e.move[1][1],
        tau=e.tau, pressure=e.pressure, terminal=e.terminal, heuristic=e.heuristic,
        shape=str(e.shape), num_obligations=len(e.obligations), num_obligation_vertices=len(e.obligation_vertices),
        parent_event=-1 if e.parent_event is None else e.parent_event,
    ) for e in events])


def layer_metrics(states: Sequence[State], events: Sequence[Event], branchial_edges, causal_edges):
    rows = []
    max_ply = max(s.ply for s in states)
    for ply in range(max_ply + 1):
        layer_states = [s for s in states if s.ply == ply]
        layer_events = [e for e in events if e.ply == ply]
        masses = np.array([s.mass for s in layer_states], dtype=float)
        probs = masses / masses.sum() if masses.sum() else np.ones(len(masses)) / max(1, len(masses))
        entropy = float(-(probs[probs > 0] * np.log(probs[probs > 0])).sum()) if probs.size else 0.0
        participation = float(1.0 / max(float((probs * probs).sum()), 1e-12)) if probs.size else 0.0
        rows.append(dict(
            ply=ply,
            states=len(layer_states),
            events=len(layer_events),
            mean_pressure=float(np.mean([e.pressure for e in layer_events])) if layer_events else 0.0,
            max_pressure=int(max([e.pressure for e in layer_events], default=0)),
            terminals=int(sum(e.terminal for e in layer_events)),
            branchial_edges=sum(1 for _, _, p, _ in branchial_edges if p == ply),
            causal_edges_to_date=sum(1 for a, b, _ in causal_edges if events[b].ply <= ply) if events else 0,
            branchial_entropy=entropy,
            branchial_participation=participation,
        ))
    return pd.DataFrame(rows)


def incidence_spectrum_for_top_event(events: Sequence[Event]):
    if not events:
        return np.array([0.0]), [], np.zeros((0, 0)), None
    top = max(events, key=lambda e: (e.pressure, e.tau, e.terminal, len(e.obligations)))
    eigs, vertices, A = hypergraph_spectrum(top.obligations)
    return eigs, vertices, A, top


def rulial_scan(args):
    rows = []
    pressure_weights = np.linspace(0.0, 2.0, 7)
    heuristic_weights = np.linspace(0.0, 0.45, 7)
    # Smaller scan settings for speed.
    class Tmp: pass
    tmp = Tmp()
    tmp.radius = args.radius
    tmp.candidate_radius = args.candidate_radius
    tmp.max_spread = args.max_spread
    tmp.prefilter = min(args.prefilter, 18)
    tmp.branch = min(args.branch, 2)
    tmp.beam = min(args.beam, 12)
    tmp.plies = min(args.plies, 4)
    tmp.pattern = args.pattern
    tmp.player = args.player
    for wp in pressure_weights:
        for wh in heuristic_weights:
            states, events = build_multiway(tmp, pressure_weight=float(wp), heuristic_weight=float(wh), terminal_weight=2.0)
            terminals = sum(e.terminal for e in events)
            max_pressure = max([e.pressure for e in events], default=0)
            mean_pressure = float(np.mean([e.pressure for e in events])) if events else 0.0
            rows.append(dict(
                pressure_weight=float(wp),
                heuristic_weight=float(wh),
                states=len(states),
                events=len(events),
                terminals=terminals,
                max_pressure=max_pressure,
                mean_pressure=mean_pressure,
                final_mass=sum(s.mass for s in states if s.ply == max(st.ply for st in states)),
            ))
    return pd.DataFrame(rows)


def save_multiway_graph(states, events, path):
    plt.figure(figsize=(9, 6))
    by_id = {s.id: s for s in states}
    max_ply = max(s.ply for s in states)
    y_offsets = {ply: 0 for ply in range(max_ply + 1)}
    coords = {}
    for ply in range(max_ply + 1):
        layer = [s for s in states if s.ply == ply]
        layer = sorted(layer, key=lambda s: s.score)
        n = len(layer)
        for i, s in enumerate(layer):
            coords[s.id] = (ply, i - (n - 1) / 2.0)
    for e in events:
        if e.parent_state in coords and e.child_state in coords:
            x1, y1 = coords[e.parent_state]
            x2, y2 = coords[e.child_state]
            plt.plot([x1, x2], [y1, y2], linewidth=0.5 + 0.45 * e.pressure, alpha=0.45)
    xs = [coords[s.id][0] for s in states]
    ys = [coords[s.id][1] for s in states]
    cs = [s.mass for s in states]
    plt.scatter(xs, ys, c=cs, s=35 + 30 * np.array(cs))
    plt.xlabel("ply")
    plt.ylabel("multiway branch index")
    plt.title("Multiway state graph of retained Hex Connect-6 futures")
    plt.colorbar(label="state mass")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def save_branchial_space(states, branchial_edges, args, path):
    feats = [hypergraph_feature_vector(s.obligations, args.radius) for s in states]
    coords = pca2(np.vstack(feats)) if feats else np.zeros((0, 2))
    id_to_i = {s.id: i for i, s in enumerate(states)}
    plt.figure(figsize=(8, 6))
    for a, b, ply, sim in branchial_edges:
        ia = id_to_i.get(a)
        ib = id_to_i.get(b)
        if ia is not None and ib is not None:
            plt.plot([coords[ia, 0], coords[ib, 0]], [coords[ia, 1], coords[ib, 1]], linewidth=0.4 + sim, alpha=0.22)
    plt.scatter(coords[:, 0], coords[:, 1], c=[s.ply for s in states], s=[25 + 15 * s.mass for s in states])
    plt.xlabel("branchial PC1")
    plt.ylabel("branchial PC2")
    plt.title("Branchial space from obligation-hypergraph similarity")
    plt.colorbar(label="ply")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def save_causal_graph(events, causal_edges, path):
    n = len(events)
    # Local event ids are 0..n-1.
    pos = force_layout(n, causal_edges, seed=42, steps=260)
    plt.figure(figsize=(8, 6))
    for a, b, w in causal_edges:
        if a < n and b < n:
            plt.plot([pos[a, 0], pos[b, 0]], [pos[a, 1], pos[b, 1]], linewidth=0.3 + 0.25 * w, alpha=0.25)
    if events:
        plt.scatter(pos[:, 0], pos[:, 1], c=[e.pressure + 0.5 * e.terminal for e in events], s=[30 + 18 * e.tau for e in events])
        plt.colorbar(label="pressure + terminal")
    plt.xlabel("causal layout x")
    plt.ylabel("causal layout y")
    plt.title("Multiway causal graph of move events")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def save_layer_metrics(df, path):
    plt.figure(figsize=(8, 5))
    plt.plot(df["ply"], df["states"], marker="o", label="states")
    plt.plot(df["ply"], df["events"], marker="o", label="events")
    plt.plot(df["ply"], df["branchial_edges"], marker="o", label="branchial edges")
    plt.xlabel("ply")
    plt.ylabel("count")
    plt.title("Multiway growth and branchial connectivity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(df["ply"], df["mean_pressure"], marker="o", label="mean pressure")
    plt.plot(df["ply"], df["max_pressure"], marker="o", label="max pressure")
    plt.plot(df["ply"], df["branchial_entropy"], marker="o", label="branchial entropy")
    plt.xlabel("ply")
    plt.ylabel("value")
    plt.title("Pressure and branchial entropy over evolution")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path.with_name("pressure_entropy_over_ply.png"), dpi=190)
    plt.close()


def save_hypergraph_spectrum(eigs, path):
    plt.figure(figsize=(7, 4.8))
    plt.plot(np.arange(len(eigs)), np.sort(eigs), marker="o")
    plt.xlabel("eigenvalue index")
    plt.ylabel("hypergraph Laplacian eigenvalue")
    plt.title("Obligation-hypergraph spectral signature of top event")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def save_obligation_overlap_matrix(A, vertices, path):
    plt.figure(figsize=(6.5, 5.8))
    if A.size:
        plt.imshow(A)
        plt.colorbar(label="shared hyperedge weight")
    else:
        plt.imshow(np.zeros((1, 1)))
    plt.title("2-section overlap matrix of top obligation hypergraph")
    plt.xlabel("obligation vertex")
    plt.ylabel("obligation vertex")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def save_rulial_scan(df, path):
    pivot = df.pivot(index="pressure_weight", columns="heuristic_weight", values="mean_pressure")
    plt.figure(figsize=(7, 5.7))
    plt.imshow(pivot.values, origin="lower", aspect="auto", extent=[pivot.columns.min(), pivot.columns.max(), pivot.index.min(), pivot.index.max()])
    plt.xlabel("heuristic rule weight")
    plt.ylabel("pressure rule weight")
    plt.title("Tiny rulial scan: mean pressure reached by rule weights")
    plt.colorbar(label="mean pressure")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    pivot2 = df.pivot(index="pressure_weight", columns="heuristic_weight", values="states")
    plt.figure(figsize=(7, 5.7))
    plt.imshow(pivot2.values, origin="lower", aspect="auto", extent=[pivot2.columns.min(), pivot2.columns.max(), pivot2.index.min(), pivot2.index.max()])
    plt.xlabel("heuristic rule weight")
    plt.ylabel("pressure rule weight")
    plt.title("Tiny rulial scan: retained state count")
    plt.colorbar(label="states")
    plt.tight_layout()
    plt.savefig(path.with_name("rulial_scan_state_count.png"), dpi=190)
    plt.close()


def save_shape_pressure_spectrum(events, path):
    df = event_table(events)
    if df.empty:
        spec = pd.DataFrame(columns=["shape", "pressure", "count", "tau"])
    else:
        spec = (df.groupby("shape", as_index=False)
                  .agg(pressure=("pressure", "sum"), count=("shape", "size"), tau=("tau", "mean"), terminal=("terminal", "sum"))
                  .sort_values(["pressure", "terminal", "count"], ascending=False)
                  .head(18))
    plt.figure(figsize=(8, 4.8))
    x = np.arange(len(spec))
    plt.bar(x, spec["pressure"])
    plt.xticks(x, spec["shape"], rotation=45, ha="right")
    plt.ylabel("total pressure")
    plt.title("D6 quotient pair-shape pressure spectrum across multiway events")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return spec


def save_event_pressure_scatter(events, path):
    df = event_table(events)
    plt.figure(figsize=(7, 5))
    if not df.empty:
        plt.scatter(df["num_obligations"], df["tau"], s=28 + 30 * df["terminal"], c=df["pressure"])
        plt.colorbar(label="pressure")
    plt.xlabel("urgent obligation hyperedges")
    plt.ylabel("hitting number tau")
    plt.title("Event obligation count vs exact hypergraph hitting number")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="wolfram_hexconnect6_hypergraphs_out")
    parser.add_argument("--radius", type=int, default=7)
    parser.add_argument("--candidate-radius", type=int, default=5)
    parser.add_argument("--max-spread", type=int, default=7)
    parser.add_argument("--plies", type=int, default=5)
    parser.add_argument("--beam", type=int, default=24)
    parser.add_argument("--branch", type=int, default=3)
    parser.add_argument("--prefilter", type=int, default=28)
    parser.add_argument("--pattern", choices=["ladder", "seeded"], default="ladder")
    parser.add_argument("--player", type=int, default=1)
    args = parser.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    states, events = build_multiway(args)
    branchial_edges = build_branchial_edges(states)
    causal_edges = build_causal_edges(events)
    layers = layer_metrics(states, events, branchial_edges, causal_edges)
    eigs, vertices, A, top_event = incidence_spectrum_for_top_event(events)
    rulial = rulial_scan(args)

    states_df = state_table(states)
    events_df = event_table(events)
    branchial_df = pd.DataFrame(branchial_edges, columns=["state_a", "state_b", "ply", "similarity"])
    causal_df = pd.DataFrame(causal_edges, columns=["event_a", "event_b", "overlap_weight"])
    spectrum_df = pd.DataFrame({"eigenvalue": np.sort(eigs)})
    shape_df = save_shape_pressure_spectrum(events, fig / "shape_pressure_spectrum.png")

    states_df.to_csv(data / "multiway_states.csv", index=False)
    events_df.to_csv(data / "multiway_events.csv", index=False)
    branchial_df.to_csv(data / "branchial_edges.csv", index=False)
    causal_df.to_csv(data / "causal_edges.csv", index=False)
    layers.to_csv(data / "layer_metrics.csv", index=False)
    spectrum_df.to_csv(data / "top_event_hypergraph_spectrum.csv", index=False)
    rulial.to_csv(data / "rulial_scan.csv", index=False)
    shape_df.to_csv(data / "shape_pressure_spectrum.csv", index=False)

    save_multiway_graph(states, events, fig / "multiway_state_graph.png")
    save_branchial_space(states, branchial_edges, args, fig / "branchial_space.png")
    save_causal_graph(events, causal_edges, fig / "multiway_causal_graph.png")
    save_layer_metrics(layers, fig / "multiway_growth.png")
    save_hypergraph_spectrum(eigs, fig / "top_event_hypergraph_spectrum.png")
    save_obligation_overlap_matrix(A, vertices, fig / "top_event_obligation_overlap_matrix.png")
    save_rulial_scan(rulial, fig / "rulial_scan_mean_pressure.png")
    save_event_pressure_scatter(events, fig / "event_tau_vs_obligations.png")

    # Simple "causal invariance" proxy: reconvergence = duplicate states by board signature at same ply.
    total_signatures = len(set((s.ply, board_signature(s.board)) for s in states))
    reconvergence = 1.0 - total_signatures / max(1, len(states))
    pressure_values = [e.pressure for e in events]
    metrics = {
        "parameters": vars(args),
        "states": len(states),
        "events": len(events),
        "branchial_edges": len(branchial_edges),
        "causal_edges": len(causal_edges),
        "terminal_events": int(sum(e.terminal for e in events)),
        "max_pressure": int(max(pressure_values, default=0)),
        "mean_pressure": float(np.mean(pressure_values)) if pressure_values else 0.0,
        "top_event": None if top_event is None else {
            "event_id": top_event.id,
            "ply": top_event.ply,
            "move": [list(top_event.move[0]), list(top_event.move[1])],
            "tau": top_event.tau,
            "pressure": top_event.pressure,
            "terminal": top_event.terminal,
            "shape": str(top_event.shape),
            "num_obligations": len(top_event.obligations),
            "num_obligation_vertices": len(top_event.obligation_vertices),
        },
        "branchial_final_entropy": float(layers["branchial_entropy"].iloc[-1]) if len(layers) else 0.0,
        "branchial_final_participation": float(layers["branchial_participation"].iloc[-1]) if len(layers) else 0.0,
        "reconvergence_proxy": float(reconvergence),
        "interpretation": "This Wolfram-inspired probe treats two-stone moves as hypergraph update events and obligation families as local hypergraph states. Branchial clustering and causal graph structure measure whether tactical play compresses into a small causal cone.",
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = f"""# Wolfram-inspired Hex Connect-6 hypergraph experiment

This folder contains a Wolfram-style multiway/hypergraph analysis of a finite-window
Hex Connect-6 position.

Objects:
- `multiway_states.csv`: retained board states by ply
- `multiway_events.csv`: two-stone update events
- `branchial_edges.csv`: same-ply state similarity edges based on obligation hypergraphs
- `causal_edges.csv`: event-event causal overlaps
- `rulial_scan.csv`: small rule-space scan over pressure/heuristic scoring weights

Key definition:
    pressure(move) = max(0, tau(obligation_hypergraph_after_move) - 2)

where tau is the hitting number required to block urgent threats.

Main figures are in `figures/`.
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob("*"):
            z.write(p, p.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "wolfram_hexconnect6_hypergraphs.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
