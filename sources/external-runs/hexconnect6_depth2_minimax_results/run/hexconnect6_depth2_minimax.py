#!/usr/bin/env python3
"""
hexconnect6_depth2_minimax.py

Depth-2 minimax proto-pressure atlas for infinite Hex Connect-6.

Game fragment:
  B0: Black singleton at origin.
  W1: candidate White opening pair.
  B1: Black chooses a reply.
  W2: White chooses a defence.
  B2: Black chooses a continuation.

For each W1, estimate:

  V(W1) = max_B1 min_W2 max_B2 Score(B2 | B0,W1,B1,W2)

where Score combines:
  - terminal six-in-row
  - exact transversal pressure: lines with 4-5 stones, empty sets of size 1-2
  - proto transversal pressure: lines with 3 stones, empty sets of size 3

This is designed to test the "annular branchial bottleneck / rail-to-bridge" hypothesis:
  Good openings should minimize Black's depth-2 proto/exact pressure, and forcing
  continuations should concentrate into a small spectrum of D6 quotient pair-shapes.

Run:
  python hexconnect6_depth2_minimax.py --out depth2_out --opening-radius 4 --max-openings 240
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import zipfile
from collections import Counter, defaultdict
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


def axial_to_xy(c) -> Tuple[float, float]:
    q, r = c
    return (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)


def cells_in_radius(radius: int) -> List[Cell]:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                cells.append((q, r))
    return cells


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


def canonical_pair(pair: Tuple[Cell, Cell]) -> Tuple[Cell, Cell]:
    reps = []
    for a0 in d6_orbit(pair[0]):
        # Need the same transform on both cells. Reconstruct by applying 12 transforms explicitly.
        pass
    # implemented below using transform functions
    raise RuntimeError("unreachable")


def transforms_d6(c: Cell) -> List[Cell]:
    vals = []
    x = c
    for _ in range(6):
        vals.append(x)
        vals.append(reflect(x))
        x = rotate60(x)
    return vals


def transform_pair(pair: Tuple[Cell, Cell], t: int) -> Tuple[Cell, Cell]:
    a_vals = transforms_d6(pair[0])
    b_vals = transforms_d6(pair[1])
    p = tuple(sorted([a_vals[t], b_vals[t]]))
    return p


def canonical_pair_d6(pair: Tuple[Cell, Cell]) -> Tuple[Cell, Cell]:
    return min(transform_pair(pair, t) for t in range(12))


def all_segments(radius: int, pad: int = 2) -> List[Tuple[Cell, ...]]:
    cells = set(cells_in_radius(radius + pad))
    segs = set()
    for c in cells:
        for d in DIRS:
            seg = tuple(add(c, d, k) for k in range(6))
            if all(x in cells for x in seg):
                segs.add(seg)
    return sorted(segs)


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


def heuristic_pair_value(board: Board, move: Tuple[Cell, Cell], player: int) -> float:
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    v = 0.0
    for c in move:
        for d in DIRS:
            mine, _ = count_run(nb, c, d, player)
            theirs, _ = count_run(board, c, d, -player)
            v += mine * mine + (8 if theirs >= 5 else 3 if theirs >= 4 else 1 if theirs >= 3 else 0)
    v += max(0, 6 - hex_dist(move[0], move[1])) * 0.25
    return float(v)


def obligations(board: Board, player: int, segments: Sequence[Tuple[Cell, ...]]):
    exact = []
    proto = []
    terminal = []
    for seg in segments:
        vals = [board.get(c, 0) for c in seg]
        if any(v == -player for v in vals):
            continue
        empties = tuple(c for c, v in zip(seg, vals) if v == 0)
        mine = 6 - len(empties)
        if mine >= 6:
            terminal.append(seg)
        elif mine >= 4 and 1 <= len(empties) <= 2:
            exact.append(tuple(sorted(empties)))
        elif mine == 3 and len(empties) == 3:
            proto.append(tuple(sorted(empties)))
    return sorted(set(exact)), sorted(set(proto)), sorted(set(terminal))


def hitting_number(edges: Sequence[Tuple[Cell, ...]], max_k: int = 7) -> int:
    if not edges:
        return 0
    universe = sorted(set(c for e in edges for c in e))
    singletons = {e[0] for e in edges if len(e) == 1}
    if len(singletons) > max_k:
        return max_k + 1
    # Use singleton lower bound: include all singleton vertices in combos.
    forced = sorted(singletons)
    remaining = [u for u in universe if u not in singletons]
    for k in range(len(forced), min(max_k, len(universe)) + 1):
        for rest in itertools.combinations(remaining, k - len(forced)):
            S = set(forced) | set(rest)
            if all(any(c in S for c in e) for e in edges):
                return k
    return max_k + 1


def evaluate_position(board: Board, player: int, segments):
    exact, proto, terminal = obligations(board, player, segments)
    tau_exact = hitting_number(exact, max_k=7)
    tau_proto = hitting_number(proto, max_k=7)
    pressure_exact = max(0, tau_exact - 2)
    pressure_proto = max(0, tau_proto - 2)
    return dict(
        exact=exact, proto=proto, terminal=terminal,
        tau_exact=tau_exact, tau_proto=tau_proto,
        pressure_exact=pressure_exact, pressure_proto=pressure_proto,
        terminal_count=len(terminal),
        exact_count=len(exact), proto_count=len(proto),
        vertex_count=len(set(c for e in exact + proto for c in e)),
    )


def make_move(board: Board, move: Tuple[Cell, Cell], player: int) -> Board:
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    return nb


def move_eval(board: Board, move: Tuple[Cell, Cell], player: int, segments, h=None):
    nb = make_move(board, move, player)
    ev = evaluate_position(nb, player, segments)
    h = heuristic_pair_value(board, move, player) if h is None else h
    score = (
        1000.0 * min(1, ev["terminal_count"])
        + 80.0 * ev["pressure_exact"]
        + 18.0 * ev["tau_exact"]
        + 13.0 * ev["pressure_proto"]
        + 2.0 * ev["tau_proto"]
        + 0.18 * ev["proto_count"]
        + 0.025 * h
    )
    shape = canonical_delta((move[1][0] - move[0][0], move[1][1] - move[0][1]))
    return dict(move=move, h=h, score=float(score), shape=shape, **ev)


def candidate_moves(board: Board, cells: Sequence[Cell], player: int, radius: int, max_spread: int, prefilter: int):
    empty = [c for c in cells if c not in board and hex_dist(c) <= radius]
    arr = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                arr.append((heuristic_pair_value(board, (a, b), player), a, b))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in arr[:prefilter]]


def defence_candidates(board: Board, cells: Sequence[Cell], player: int, radius: int, max_spread: int, prefilter: int, opponent_edges: Sequence[Tuple[Cell, ...]]):
    # Blend high-heuristic moves with moves that hit current opponent proto/exact obligations.
    base = candidate_moves(board, cells, player, radius, max_spread, prefilter)
    cand = {(a, b): h for a, b, h in base}
    verts = sorted(set(c for e in opponent_edges for c in e if c not in board and hex_dist(c) <= radius))
    # Add pairs among obligation vertices and pairs from obligation vertices to tactically central cells.
    central = [c for c in cells if c not in board and hex_dist(c) <= min(radius, 3)]
    pool = verts[:18]
    for i, a in enumerate(pool):
        for b in pool[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                cand[(a, b)] = max(cand.get((a, b), -1e9), heuristic_pair_value(board, (a, b), player) + 20)
        for b in central[:18]:
            if a != b and hex_dist(a, b) <= max_spread:
                pair = tuple(sorted([a, b]))
                cand[pair] = max(cand.get(pair, -1e9), heuristic_pair_value(board, pair, player) + 8)
    rows = [(h, pair[0], pair[1]) for pair, h in cand.items()]
    rows.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in rows[:prefilter]]


def opening_pairs(opening_radius: int, max_spread: int, max_openings: int | None, canonical: bool = True):
    cells = [c for c in cells_in_radius(opening_radius) if c != (0, 0)]
    seen = set()
    rows = []
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            if hex_dist(a, b) > max_spread:
                continue
            pair = tuple(sorted([a, b]))
            canon = canonical_pair_d6(pair) if canonical else pair
            if canon in seen:
                continue
            seen.add(canon)
            rows.append(pair)
    # Deterministic order: closer and representative openings first, then all.
    rows.sort(key=lambda p: (min(hex_dist(p[0]), hex_dist(p[1])), hex_dist(p[0], p[1]), max(hex_dist(p[0]), hex_dist(p[1])), p))
    if max_openings:
        rows = rows[:max_openings]
    return rows


def depth2_value_for_opening(white_opening: Tuple[Cell, Cell], args, cells, segments):
    board0 = {(0, 0): 1, white_opening[0]: -1, white_opening[1]: -1}

    b1_pool_raw = candidate_moves(board0, cells, 1, args.candidate_radius, args.max_spread, args.b1_prefilter)
    b1_evals = [move_eval(board0, (a, b), 1, segments, h) for a, b, h in b1_pool_raw]
    b1_evals.sort(key=lambda e: e["score"], reverse=True)
    b1_evals = b1_evals[:args.b1_branch]

    best_for_black = None
    all_lines = []
    for b1 in b1_evals:
        board1 = make_move(board0, b1["move"], 1)
        opp_edges = b1["exact"] + b1["proto"]

        w2_pool_raw = defence_candidates(board1, cells, -1, args.candidate_radius, args.max_spread, args.w2_prefilter, opp_edges)
        w2_evals = []
        for wa, wb, wh in w2_pool_raw:
            # White defence selection proxy: evaluate how much it reduces Black's current obligations and creates counter-pressure.
            board2_candidate = make_move(board1, (wa, wb), -1)
            black_after = evaluate_position(board2_candidate, 1, segments)
            white_self = evaluate_position(board2_candidate, -1, segments)
            defence_score = (
                -90 * black_after["pressure_exact"]
                -16 * black_after["pressure_proto"]
                -2.0 * black_after["proto_count"]
                +12 * white_self["pressure_exact"]
                +3.0 * white_self["pressure_proto"]
                +0.01 * wh
            )
            w2_evals.append((defence_score, (wa, wb), board2_candidate))
        w2_evals.sort(reverse=True, key=lambda x: x[0])
        w2_evals = w2_evals[:args.w2_branch]

        best_white_defence = None
        for defence_score, w2, board2 in w2_evals:
            b2_pool_raw = candidate_moves(board2, cells, 1, args.candidate_radius, args.max_spread, args.b2_prefilter)
            b2_evals = [move_eval(board2, (a, b), 1, segments, h) for a, b, h in b2_pool_raw]
            b2_evals.sort(key=lambda e: e["score"], reverse=True)
            b2_evals = b2_evals[:args.b2_branch]
            if b2_evals:
                worst_b2 = max(b2_evals, key=lambda e: e["score"])
                value = worst_b2["score"]
            else:
                worst_b2 = None
                value = 0.0
            line = dict(b1=b1, w2=w2, b2=worst_b2, value=float(value), defence_score=float(defence_score))
            all_lines.append(line)
            # White minimizes Black continuation.
            if best_white_defence is None or value < best_white_defence["value"]:
                best_white_defence = line

        if best_white_defence is None:
            continue
        # Black chooses B1 that maximizes value after White's best defence.
        if best_for_black is None or best_white_defence["value"] > best_for_black["value"]:
            best_for_black = best_white_defence

    if best_for_black is None:
        return None, []

    return best_for_black, all_lines


def run_atlas(args):
    cells = cells_in_radius(args.radius)
    segments = all_segments(args.radius, pad=2)
    openings = opening_pairs(args.opening_radius, args.opening_spread, args.max_openings, canonical=not args.no_canonical)

    rows = []
    lines = []
    for idx, opening in enumerate(openings):
        best, all_lines = depth2_value_for_opening(opening, args, cells, segments)
        if best is None:
            continue
        b1, b2 = best["b1"], best["b2"]
        w2 = best["w2"]
        center = ((opening[0][0] + opening[1][0]) / 2, (opening[0][1] + opening[1][1]) / 2)
        x, y = axial_to_xy(center)
        shape = canonical_delta((opening[1][0] - opening[0][0], opening[1][1] - opening[0][1]))
        row = dict(
            opening_id=idx,
            w1a_q=opening[0][0], w1a_r=opening[0][1],
            w1b_q=opening[1][0], w1b_r=opening[1][1],
            center_q=center[0], center_r=center[1], x=x, y=y,
            min_radius=min(hex_dist(opening[0]), hex_dist(opening[1])),
            max_radius=max(hex_dist(opening[0]), hex_dist(opening[1])),
            spread=hex_dist(opening[0], opening[1]),
            opening_shape=str(shape),
            depth2_value=best["value"],
            b1_a_q=b1["move"][0][0], b1_a_r=b1["move"][0][1],
            b1_b_q=b1["move"][1][0], b1_b_r=b1["move"][1][1],
            b1_shape=str(b1["shape"]),
            b1_score=b1["score"],
            b1_exact_pressure=b1["pressure_exact"],
            b1_proto_pressure=b1["pressure_proto"],
            b1_tau_exact=b1["tau_exact"],
            b1_tau_proto=b1["tau_proto"],
            b1_proto_count=b1["proto_count"],
            w2_a_q=w2[0][0], w2_a_r=w2[0][1],
            w2_b_q=w2[1][0], w2_b_r=w2[1][1],
            b2_a_q=b2["move"][0][0] if b2 else np.nan,
            b2_a_r=b2["move"][0][1] if b2 else np.nan,
            b2_b_q=b2["move"][1][0] if b2 else np.nan,
            b2_b_r=b2["move"][1][1] if b2 else np.nan,
            b2_shape=str(b2["shape"]) if b2 else "",
            b2_score=b2["score"] if b2 else 0,
            b2_exact_pressure=b2["pressure_exact"] if b2 else 0,
            b2_proto_pressure=b2["pressure_proto"] if b2 else 0,
            b2_terminal=b2["terminal_count"] if b2 else 0,
            b2_tau_exact=b2["tau_exact"] if b2 else 0,
            b2_tau_proto=b2["tau_proto"] if b2 else 0,
            b2_proto_count=b2["proto_count"] if b2 else 0,
        )
        rows.append(row)
        for j, ln in enumerate(all_lines):
            if ln["b2"] is None:
                continue
            lines.append(dict(
                opening_id=idx, line_id=j, value=ln["value"],
                b1_shape=str(ln["b1"]["shape"]),
                b1_proto_pressure=ln["b1"]["pressure_proto"],
                w2_a_q=ln["w2"][0][0], w2_a_r=ln["w2"][0][1],
                w2_b_q=ln["w2"][1][0], w2_b_r=ln["w2"][1][1],
                b2_shape=str(ln["b2"]["shape"]),
                b2_exact_pressure=ln["b2"]["pressure_exact"],
                b2_proto_pressure=ln["b2"]["pressure_proto"],
                b2_terminal=ln["b2"]["terminal_count"],
                b2_tau_exact=ln["b2"]["tau_exact"],
                b2_tau_proto=ln["b2"]["tau_proto"],
            ))
    return pd.DataFrame(rows), pd.DataFrame(lines)


def pca2(X):
    X = np.asarray(X, dtype=float)
    if len(X) == 0:
        return np.zeros((0, 2))
    X = X - X.mean(axis=0, keepdims=True)
    if X.shape[0] == 1:
        return np.zeros((1, 2))
    _, _, Vt = np.linalg.svd(X, full_matrices=False)
    if Vt.shape[0] == 1:
        return np.column_stack([X @ Vt[0], np.zeros(X.shape[0])])
    return X @ Vt[:2].T


def plot_opening_surface(df, path):
    plt.figure(figsize=(7.2, 6.2))
    plt.scatter(df["x"], df["y"], c=df["depth2_value"], s=28 + 10 * df["b2_tau_proto"])
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title("Depth-2 minimax proto/exact value by White opening center")
    plt.xlabel("opening center x")
    plt.ylabel("opening center y")
    plt.colorbar(label="Black minimax value")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_radius(df, path):
    g = df.groupby("min_radius", as_index=False).agg(
        mean_value=("depth2_value", "mean"),
        min_value=("depth2_value", "min"),
        mean_b2_proto=("b2_proto_pressure", "mean"),
        terminal_rate=("b2_terminal", lambda x: np.mean(np.array(x) > 0)),
        count=("opening_id", "size"),
    )
    plt.figure(figsize=(7, 5))
    plt.plot(g["min_radius"], g["mean_value"], marker="o", label="mean value")
    plt.plot(g["min_radius"], g["min_value"], marker="o", label="best-case value")
    plt.plot(g["min_radius"], 20 * g["terminal_rate"], marker="o", label="terminal rate ×20")
    plt.xlabel("minimum White-stone opening radius")
    plt.ylabel("value")
    plt.title("Depth-2 annulus test")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return g


def plot_shape_vulnerability(df, path):
    g = (df.groupby("opening_shape", as_index=False)
           .agg(mean_value=("depth2_value", "mean"), min_value=("depth2_value", "min"),
                terminal_rate=("b2_terminal", lambda x: np.mean(np.array(x) > 0)),
                count=("opening_id", "size"))
           .sort_values("mean_value", ascending=False))
    top = g.head(20)
    plt.figure(figsize=(9, 5))
    x = np.arange(len(top))
    plt.bar(x, top["mean_value"])
    plt.xticks(x, top["opening_shape"], rotation=45, ha="right")
    plt.ylabel("mean Black depth-2 value")
    plt.title("White opening shape vulnerability spectrum")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return g


def plot_transition(lines, path):
    if lines.empty:
        return pd.DataFrame()
    trans = (lines.groupby(["b1_shape", "b2_shape"], as_index=False)
              .agg(count=("line_id", "size"), mean_value=("value", "mean"),
                   mean_b2_proto=("b2_proto_pressure", "mean"), terminal_rate=("b2_terminal", lambda x: np.mean(np.array(x) > 0))))
    shapes = sorted(set(trans["b1_shape"]) | set(trans["b2_shape"]))
    idx = {s: i for i, s in enumerate(shapes)}
    M = np.zeros((len(shapes), len(shapes)))
    for _, row in trans.iterrows():
        M[idx[row["b1_shape"]], idx[row["b2_shape"]]] += row["count"] * (1 + 0.01 * row["mean_value"])
    row_sums = M.sum(axis=1, keepdims=True)
    P = np.divide(M, row_sums, out=np.zeros_like(M), where=row_sums > 0)
    plt.figure(figsize=(8, 7))
    plt.imshow(P)
    plt.xticks(np.arange(len(shapes)), shapes, rotation=90)
    plt.yticks(np.arange(len(shapes)), shapes)
    plt.title("Rail-to-bridge D6 shape transition matrix")
    plt.xlabel("Black continuation shape")
    plt.ylabel("Black first reply shape")
    plt.colorbar(label="transition probability")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return trans.sort_values(["count", "mean_value"], ascending=False)


def plot_branchial_openings(df, path):
    features = df[[
        "min_radius","max_radius","spread","b1_proto_pressure","b1_tau_proto","b1_proto_count",
        "b2_proto_pressure","b2_tau_proto","b2_proto_count","b2_exact_pressure","depth2_value"
    ]].fillna(0).to_numpy(float)
    coords = pca2(features)
    plt.figure(figsize=(7.2, 6))
    plt.scatter(coords[:, 0], coords[:, 1], c=df["depth2_value"], s=28)
    plt.title("Opening branchial atlas: embeddings by proto/exact futures")
    plt.xlabel("branchial PC1")
    plt.ylabel("branchial PC2")
    plt.colorbar(label="Black depth-2 value")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    out = df[["opening_id"]].copy()
    out["pc1"] = coords[:, 0]
    out["pc2"] = coords[:, 1]
    return out


def plot_immediate_vs_depth(df, path):
    plt.figure(figsize=(7, 5))
    plt.scatter(df["b1_score"], df["depth2_value"], c=df["min_radius"], s=25 + 12 * df["b2_terminal"])
    plt.xlabel("Black first-reply score")
    plt.ylabel("Black depth-2 minimax value")
    plt.title("Immediate proto-pressure vs depth-2 minimax value")
    plt.colorbar(label="opening min radius")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="hexconnect6_depth2_minimax_out")
    p.add_argument("--radius", type=int, default=7)
    p.add_argument("--opening-radius", type=int, default=4)
    p.add_argument("--opening-spread", type=int, default=7)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--max-spread", type=int, default=7)
    p.add_argument("--max-openings", type=int, default=220)
    p.add_argument("--no-canonical", action="store_true")
    p.add_argument("--b1-prefilter", type=int, default=20)
    p.add_argument("--b1-branch", type=int, default=3)
    p.add_argument("--w2-prefilter", type=int, default=26)
    p.add_argument("--w2-branch", type=int, default=4)
    p.add_argument("--b2-prefilter", type=int, default=24)
    p.add_argument("--b2-branch", type=int, default=4)
    args = p.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    df, lines = run_atlas(args)
    df.to_csv(data / "depth2_opening_atlas.csv", index=False)
    lines.to_csv(data / "depth2_lines.csv", index=False)

    radius_df = plot_radius(df, fig / "depth2_annulus_test.png")
    radius_df.to_csv(data / "depth2_annulus_summary.csv", index=False)
    shape_df = plot_shape_vulnerability(df, fig / "opening_shape_vulnerability_depth2.png")
    shape_df.to_csv(data / "opening_shape_vulnerability_depth2.csv", index=False)
    trans_df = plot_transition(lines, fig / "rail_to_bridge_shape_transition.png")
    trans_df.to_csv(data / "rail_to_bridge_shape_transitions.csv", index=False)
    branchial_df = plot_branchial_openings(df, fig / "opening_branchial_atlas.png")
    branchial_df.to_csv(data / "opening_branchial_coordinates.csv", index=False)
    plot_opening_surface(df, fig / "depth2_opening_surface.png")
    plot_immediate_vs_depth(df, fig / "immediate_vs_depth2.png")

    safe = df.sort_values(["depth2_value","b2_proto_pressure","b2_exact_pressure","min_radius"], ascending=[True, True, True, False]).head(15)
    risky = df.sort_values(["depth2_value","b2_terminal","b2_proto_pressure"], ascending=False).head(15)

    # Extract shape "attractors": continuation shapes weighted by depth2 value and proto pressure.
    if not lines.empty:
        attractors = (lines.groupby("b2_shape", as_index=False)
                      .agg(count=("line_id", "size"), mean_value=("value", "mean"),
                           proto_mass=("b2_proto_pressure", "sum"), terminal_rate=("b2_terminal", lambda x: np.mean(np.array(x)>0)))
                      .sort_values(["proto_mass","mean_value","count"], ascending=False))
    else:
        attractors = pd.DataFrame()

    attractors.to_csv(data / "continuation_shape_attractors.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "openings_evaluated": int(len(df)),
        "lines_evaluated": int(len(lines)),
        "best_shell": radius_df.sort_values(["min_value","mean_value"]).head(1).to_dict(orient="records")[0] if len(radius_df) else None,
        "safest_openings": safe.to_dict(orient="records"),
        "riskiest_openings": risky.to_dict(orient="records"),
        "top_vulnerable_opening_shapes": shape_df.head(10).to_dict(orient="records"),
        "top_continuation_shape_attractors": attractors.head(10).to_dict(orient="records") if len(attractors) else [],
        "correlation_immediate_depth2": float(df[["b1_score", "depth2_value"]].corr().iloc[0,1]) if len(df)>2 else None,
        "conjecture": {
            "name": "Depth-2 rail-to-bridge minimax conjecture",
            "statement": "White openings are separated not by immediate exact threats but by their depth-2 proto-pressure after optimal defence. Good openings sit in basins that delay the transition from short rail shapes into longer bridge shapes; bad openings allow Black to convert rail pressure into bridge/terminal pressure after one defensive ply."
        }
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = """# Depth-2 minimax proto-pressure atlas

This package estimates:

    White opening -> max Black reply -> min White defence -> max Black continuation

using proto/exact obligation hypergraph pressure.

Key CSVs:
- depth2_opening_atlas.csv
- depth2_lines.csv
- depth2_annulus_summary.csv
- opening_shape_vulnerability_depth2.csv
- rail_to_bridge_shape_transitions.csv
- continuation_shape_attractors.csv
- metrics.json

Key figures:
- depth2_opening_surface.png
- depth2_annulus_test.png
- opening_shape_vulnerability_depth2.png
- rail_to_bridge_shape_transition.png
- opening_branchial_atlas.png
- immediate_vs_depth2.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in out.rglob("*"):
            z.write(path, path.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_depth2_minimax.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
