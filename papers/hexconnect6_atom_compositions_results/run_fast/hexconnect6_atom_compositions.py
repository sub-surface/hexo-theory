#!/usr/bin/env python3
"""
hexconnect6_atom_compositions.py

Evaluate openings by the value of compositions of primitive forcing atoms.

Input:
  Periodic-table results zip/folder from hexconnect6_periodic_table.py.

Idea:
  A position is evaluated by the forcing elements it can compose on the next move
  and in short minimax continuations. Each move induces exact/proto obligation
  hypergraphs; their integer incidence fingerprints are looked up as "elements" in
  the periodic table. Unknown fingerprints get a small fallback value from tau.

  Opening value at horizon d:
      BlackValue(W1, d) = minimax value after Black singleton + White opening pair,
                          with d further two-stone plies.

This gives:
  - opening value surfaces by ply/horizon
  - composition heatmaps: which forcing elements appear in principal variations
  - ranking stability across depths
  - safe/risky openings under the atom-composition value model
  - element-pair transition counts from principal lines

Run:
  python hexconnect6_atom_compositions.py --input hexconnect6_periodic_table_results.zip --out comp_out
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import shutil
import zipfile
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Sequence

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


Cell = Tuple[int, int]
Board = Dict[Cell, int]
DIRS = ((1, 0), (0, 1), (1, -1))


def extract_if_zip(input_path: Path, work: Path) -> Path:
    if input_path.is_file() and input_path.suffix == ".zip":
        out = work / "extracted"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(out)
        return out
    return input_path


def find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} under {root}")
    matches.sort(key=lambda p: (0 if p.parent.name == "data" else 1, len(str(p))))
    return matches[0]


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


def transform(c: Cell, t: int) -> Cell:
    x = c
    for _ in range(t // 2):
        x = rotate60(x)
    if t % 2:
        x = reflect(x)
    return x


def d6_orbit(c: Cell) -> List[Cell]:
    return [transform(c, t) for t in range(12)]


def canonical_delta(d: Cell) -> Cell:
    return sorted(set(d6_orbit(d)))[0]


def canonical_shape(move: Tuple[Cell, Cell]) -> str:
    a, b = move
    return str(canonical_delta((b[0] - a[0], b[1] - a[1])))


def canonical_pair_d6(pair: Tuple[Cell, Cell]) -> Tuple[Cell, Cell]:
    reps = []
    for t in range(12):
        pts = [transform(pair[0], t), transform(pair[1], t)]
        for origin in pts:
            reps.append(tuple(sorted((p[0] - origin[0], p[1] - origin[1]) for p in pts)))
    return min(reps)


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


def board_key(board: Board) -> Tuple[Tuple[int, int, int], ...]:
    return tuple(sorted((q, r, v) for (q, r), v in board.items()))


def make_move(board: Board, move: Tuple[Cell, Cell], player: int) -> Board:
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    return nb


def obligations_after_move(board: Board, move: Tuple[Cell, Cell], player: int, segments: Sequence[Tuple[Cell, ...]]):
    nb = make_move(board, move, player)
    exact = []
    proto = []
    terminal = []
    for seg in segments:
        vals = [nb.get(c, 0) for c in seg]
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


def hitting_number(edges: Sequence[Tuple[Cell, ...]], max_k: int = 5) -> int:
    if not edges:
        return 0
    universe = sorted(set(c for e in edges for c in e))
    forced = sorted({e[0] for e in edges if len(e) == 1})
    if len(forced) > max_k:
        return max_k + 1
    remaining = [u for u in universe if u not in forced]
    for k in range(len(forced), min(max_k, len(universe)) + 1):
        for rest in itertools_combinations(remaining, k - len(forced)):
            S = set(forced) | set(rest)
            if all(any(c in S for c in e) for e in edges):
                return k
    return max_k + 1


# Micro-optimised combinations alias.
from itertools import combinations as itertools_combinations


def count_min_transversals(edges: Sequence[Tuple[Cell, ...]], tau: int, cap: int = 2000) -> int:
    if tau <= 0 or not edges:
        return 1
    universe = sorted(set(c for e in edges for c in e))
    forced = sorted({e[0] for e in edges if len(e) == 1})
    if len(forced) > tau:
        return 0
    remaining = [u for u in universe if u not in forced]
    cnt = 0
    for rest in itertools_combinations(remaining, tau - len(forced)):
        S = set(forced) | set(rest)
        if all(any(c in S for c in e) for e in edges):
            cnt += 1
            if cnt >= cap:
                return cap
    return cnt


def incidence_integer_fingerprint(edges: Sequence[Tuple[Cell, ...]], tau: int):
    verts = sorted(set(c for e in edges for c in e))
    deg = {}
    for e in edges:
        for c in e:
            deg[c] = deg.get(c, 0) + 1
    edge_sizes = tuple(sorted(len(e) for e in edges))
    degrees = tuple(sorted(deg.values(), reverse=True))
    intersections = []
    for i, e1 in enumerate(edges):
        s1 = set(e1)
        for e2 in edges[i + 1:]:
            intersections.append(len(s1 & set(e2)))
    intersections = tuple(sorted(intersections, reverse=True))
    min_trans = count_min_transversals(edges, tau)
    return str((len(edges), len(verts), edge_sizes, degrees, intersections, tau, min_trans))



def reduced_fingerprint_from_edges(edges: Sequence[Tuple[Cell, ...]], tau: int):
    """Fast bulk key without counting minimum transversals.

    This intentionally coarsens the periodic-table element lookup so opening search
    can evaluate many positions without the expensive min-transversal count.
    """
    verts = sorted(set(c for e in edges for c in e))
    deg = {}
    for e in edges:
        for c in e:
            deg[c] = deg.get(c, 0) + 1
    edge_sizes = tuple(sorted(len(e) for e in edges))
    degrees = tuple(sorted(deg.values(), reverse=True))
    intersections = []
    for i, e1 in enumerate(edges):
        s1 = set(e1)
        for e2 in edges[i + 1:]:
            intersections.append(len(s1 & set(e2)))
    intersections = tuple(sorted(intersections, reverse=True))
    return str((len(edges), len(verts), edge_sizes, degrees, intersections, tau))


def reduced_fingerprint_from_table(fp: str):
    try:
        v = ast.literal_eval(fp)
        return str((v[0], v[1], tuple(v[2]), tuple(v[3]), tuple(v[4]), v[5]))
    except Exception:
        return str(fp)


def parse_target_mode(symbol_or_target):
    s = str(symbol_or_target).lower()
    if s.startswith("p"):
        return "proto"
    if s.startswith("e"):
        return "exact"
    if s.startswith("t"):
        return "terminal"
    return s


def load_element_values(root: Path):
    elements_path = find_file(root, "forcing_elements.csv")
    elements = pd.read_csv(elements_path)

    # Element value is deliberately simple and inspectable. It is not learned.
    rows = []
    for _, r in elements.iterrows():
        target = parse_target_mode(r.get("target_mode", r.get("symbol", "")))
        stage_w = 0.72 if target == "proto" else 1.0
        if "Terminal" in str(r.get("family_periodic", "")):
            stage_w = 1.55
        tau = float(r["tau"])
        pressure = float(r["pressure"])
        freq = float(r.get("frequency", 1))
        emb = float(r.get("embedding_count", 1))
        min_trans = float(r.get("min_transversals_mode", 1))
        # Saturate min_trans because some runs cap it at 2000.
        degeneracy = math.log1p(min(min_trans, 2000))
        value = stage_w * (8.0 * pressure + 2.25 * tau + 0.55 * math.log1p(freq) + 0.35 * math.log1p(emb) + 0.18 * degeneracy)
        rows.append({
            "integer_fingerprint": r["integer_fingerprint"],
            "symbol": r["symbol"],
            "target": target,
            "element_number": int(r["element_number"]),
            "element_value": float(value),
            "tau": int(r["tau"]),
            "pressure": int(r["pressure"]),
            "family_periodic": r.get("family_periodic", ""),
            "frequency": int(r.get("frequency", 1)),
            "embedding_count": int(r.get("embedding_count", 1)),
            "pair_shape_mode": r.get("pair_shape_mode", ""),
        })
    val_df = pd.DataFrame(rows)
    lookup = {}
    for _, r in val_df.iterrows():
        lookup[(r["target"], reduced_fingerprint_from_table(r["integer_fingerprint"]))] = r.to_dict()
    return elements, val_df, lookup


def candidate_moves(board: Board, cells: Sequence[Cell], player: int, candidate_radius: int, max_spread: int, prefilter: int):
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    rows = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                rows.append((heuristic_pair_value(board, (a, b), player), a, b))
    rows.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in rows[:prefilter]]


def evaluate_move_atom(board: Board, move: Tuple[Cell, Cell], player: int, segments, lookup):
    exact, proto, terminal = obligations_after_move(board, move, player, segments)
    tau_e = hitting_number(exact)
    tau_p = hitting_number(proto)
    pressure_e = max(0, tau_e - 2)
    pressure_p = max(0, tau_p - 2)

    components = []
    value = 0.0

    if exact:
        fp = reduced_fingerprint_from_edges(exact, tau_e)
        elem = lookup.get(("exact", fp))
        if elem:
            value += elem["element_value"]
            components.append((elem["symbol"], elem["element_value"], "exact"))
        elif pressure_e > 0:
            fallback = 8.0 * pressure_e + 2.0 * tau_e
            value += fallback
            components.append((f"X{tau_e}", fallback, "exact_unknown"))

    if proto:
        fp = reduced_fingerprint_from_edges(proto, tau_p)
        elem = lookup.get(("proto", fp))
        if elem:
            value += 0.78 * elem["element_value"]
            components.append((elem["symbol"], 0.78 * elem["element_value"], "proto"))
        elif pressure_p > 0:
            fallback = 0.72 * (8.0 * pressure_p + 2.0 * tau_p)
            value += fallback
            components.append((f"PX{tau_p}", fallback, "proto_unknown"))

    terminal_bonus = 0.0
    if terminal:
        terminal_bonus = 65.0 + 5.0 * len(terminal)
        value += terminal_bonus
        components.append(("TERM", terminal_bonus, "terminal"))

    # Move-shape and run heuristic are weak priors.
    h = heuristic_pair_value(board, move, player)
    value += 0.018 * h

    return {
        "value": float(value),
        "components": components,
        "exact_tau": int(tau_e),
        "proto_tau": int(tau_p),
        "exact_pressure": int(pressure_e),
        "proto_pressure": int(pressure_p),
        "terminal": int(len(terminal) > 0),
        "shape": canonical_shape(move),
        "heuristic": float(h),
    }


def position_static_value(board: Board, side: int, cells, segments, lookup, args):
    # High value means favourable for "side".
    rows = []
    for a, b, h in candidate_moves(board, cells, side, args.candidate_radius, args.max_spread, min(args.prefilter, args.static_top)):
        ev = evaluate_move_atom(board, (a, b), side, segments, lookup)
        rows.append(ev["value"])
    if not rows:
        return 0.0
    vals = np.array(sorted(rows, reverse=True)[:args.static_top], dtype=float)
    # Logsumexp-like soft maximum.
    m = vals.max()
    return float(m + args.temperature * math.log(float(np.exp((vals - m) / args.temperature).sum())))


def minimax_value(board: Board, side: int, depth: int, cells, segments, lookup, args, cache):
    # Value from Black's perspective.
    bk = (board_key(board), side, depth)
    if bk in cache:
        return cache[bk]

    if depth <= 0:
        black = position_static_value(board, 1, cells, segments, lookup, args)
        white = position_static_value(board, -1, cells, segments, lookup, args)
        val = black - args.opponent_weight * white
        cache[bk] = (val, [])
        return val, []

    # First score a small candidate pool, then recurse only through the most
    # atom-relevant branch moves. This keeps the opening atlas OOM/time safe.
    pool = []
    for a, b, h in candidate_moves(board, cells, side, args.candidate_radius, args.max_spread, args.prefilter):
        move = (a, b)
        ev = evaluate_move_atom(board, move, side, segments, lookup)
        prior = ev["value"] + 0.018 * h
        pool.append((prior, move, ev))
    pool.sort(key=lambda x: x[0], reverse=True)
    pool = pool[:max(1, args.branch)]

    cand = []
    for _, move, ev in pool:
        nb = make_move(board, move, side)
        child, line = minimax_value(nb, -side, depth - 1, cells, segments, lookup, args, cache)
        signed_delta = ev["value"] if side == 1 else -args.white_attack_weight * ev["value"]
        total = signed_delta + args.gamma * child
        cand.append((total, move, ev, line))

    if not cand:
        val = position_static_value(board, 1, cells, segments, lookup, args) - args.opponent_weight * position_static_value(board, -1, cells, segments, lookup, args)
        cache[bk] = (val, [])
        return val, []

    # Black maximises, White minimises black value.
    best = max(cand, key=lambda x: x[0]) if side == 1 else min(cand, key=lambda x: x[0])
    val, move, ev, line = best
    pv = [{
        "side": side,
        "move": move,
        "shape": ev["shape"],
        "move_value": ev["value"],
        "components": ev["components"],
        "exact_tau": ev["exact_tau"],
        "proto_tau": ev["proto_tau"],
        "exact_pressure": ev["exact_pressure"],
        "proto_pressure": ev["proto_pressure"],
        "terminal": ev["terminal"],
    }] + line
    cache[bk] = (float(val), pv)
    return float(val), pv


def opening_pairs(opening_radius: int, max_spread: int, max_openings: int):
    cells = [c for c in cells_in_radius(opening_radius) if c != (0, 0)]
    seen = set()
    pairs = []
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            if hex_dist(a, b) > max_spread:
                continue
            pair = tuple(sorted([a, b]))
            canon = canonical_pair_d6(pair)
            if canon in seen:
                continue
            seen.add(canon)
            pairs.append(pair)
    pairs.sort(key=lambda p: (min(hex_dist(p[0]), hex_dist(p[1])), hex_dist(p[0], p[1]), max(hex_dist(p[0]), hex_dist(p[1])), p))
    return pairs[:max_openings]


def evaluate_openings(args, lookup):
    cells = cells_in_radius(args.radius)
    segments = all_segments(args.radius, pad=2)
    openings = opening_pairs(args.opening_radius, args.opening_spread, args.max_openings)

    rows = []
    pv_rows = []
    comp_rows = []
    for oid, wmove in enumerate(openings):
        board = {(0, 0): 1, wmove[0]: -1, wmove[1]: -1}
        center = ((wmove[0][0] + wmove[1][0]) / 2, (wmove[0][1] + wmove[1][1]) / 2)
        x, y = axial_to_xy(center)
        opening_shape = canonical_shape(wmove)
        base = {
            "opening_id": oid,
            "w1a_q": wmove[0][0], "w1a_r": wmove[0][1],
            "w1b_q": wmove[1][0], "w1b_r": wmove[1][1],
            "x": x, "y": y,
            "min_radius": min(hex_dist(wmove[0]), hex_dist(wmove[1])),
            "max_radius": max(hex_dist(wmove[0]), hex_dist(wmove[1])),
            "spread": hex_dist(wmove[0], wmove[1]),
            "opening_shape": opening_shape,
        }
        values = {}
        for depth in range(args.max_depth + 1):
            cache = {}
            val, pv = minimax_value(board, 1, depth, cells, segments, lookup, args, cache)
            values[f"value_d{depth}"] = val
            for k, step in enumerate(pv):
                mv = step["move"]
                pv_rows.append({
                    **base,
                    "depth": depth,
                    "pv_ply": k + 1,
                    "side": step["side"],
                    "a_q": mv[0][0], "a_r": mv[0][1],
                    "b_q": mv[1][0], "b_r": mv[1][1],
                    "shape": step["shape"],
                    "move_value": step["move_value"],
                    "exact_tau": step["exact_tau"],
                    "proto_tau": step["proto_tau"],
                    "exact_pressure": step["exact_pressure"],
                    "proto_pressure": step["proto_pressure"],
                    "terminal": step["terminal"],
                })
                for sym, v, typ in step["components"]:
                    comp_rows.append({
                        **base,
                        "depth": depth,
                        "pv_ply": k + 1,
                        "side": step["side"],
                        "symbol": sym,
                        "component_type": typ,
                        "component_value": v,
                    })
        rows.append({**base, **values})
    return pd.DataFrame(rows), pd.DataFrame(pv_rows), pd.DataFrame(comp_rows)


def plot_opening_surface(df, col, path, title):
    plt.figure(figsize=(7.2, 6.2))
    plt.scatter(df["x"], df["y"], c=df[col], s=28 + 5 * df["spread"])
    plt.gca().set_aspect("equal", adjustable="box")
    plt.xlabel("White opening pair center x")
    plt.ylabel("White opening pair center y")
    plt.title(title)
    plt.colorbar(label=col)
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def plot_depth_curves(df, path, max_depth):
    value_cols = [f"value_d{i}" for i in range(max_depth + 1)]
    arr = df[value_cols].to_numpy(float)
    plt.figure(figsize=(8, 5))
    for i in range(min(40, len(df))):
        plt.plot(range(max_depth + 1), arr[i], alpha=0.18)
    plt.plot(range(max_depth + 1), arr.mean(axis=0), marker="o", linewidth=3, label="mean")
    plt.plot(range(max_depth + 1), np.percentile(arr, 10, axis=0), linestyle="--", label="10%")
    plt.plot(range(max_depth + 1), np.percentile(arr, 90, axis=0), linestyle="--", label="90%")
    plt.xlabel("continuation depth after White opening")
    plt.ylabel("Black atom-composition value")
    plt.title("Opening value by composition horizon")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def plot_ranking_stability(df, path, max_depth):
    rows = []
    for a in range(max_depth + 1):
        for b in range(a + 1, max_depth + 1):
            corr = df[f"value_d{a}"].corr(df[f"value_d{b}"], method="spearman")
            rows.append({"a": a, "b": b, "spearman": corr})
    mat = np.eye(max_depth + 1)
    for r in rows:
        mat[int(r["a"]), int(r["b"])] = r["spearman"]
        mat[int(r["b"]), int(r["a"])] = r["spearman"]
    plt.figure(figsize=(6.2, 5.5))
    plt.imshow(mat, vmin=-1, vmax=1)
    plt.xticks(range(max_depth + 1))
    plt.yticks(range(max_depth + 1))
    plt.xlabel("depth")
    plt.ylabel("depth")
    plt.title("Opening ranking stability across composition horizons")
    plt.colorbar(label="Spearman rho")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return pd.DataFrame(rows)


def plot_composition_heatmap(comp, path):
    if comp.empty:
        return pd.DataFrame()
    g = (comp.groupby(["depth", "symbol"], as_index=False)
          .agg(value=("component_value", "sum"), count=("symbol", "size")))
    top_symbols = g.groupby("symbol")["value"].sum().sort_values(ascending=False).head(18).index.tolist()
    piv = g[g["symbol"].isin(top_symbols)].pivot_table(index="symbol", columns="depth", values="value", aggfunc="sum", fill_value=0)
    piv = piv.loc[top_symbols]
    plt.figure(figsize=(8, 6.5))
    plt.imshow(piv.values, aspect="auto")
    plt.yticks(np.arange(len(piv.index)), piv.index)
    plt.xticks(np.arange(len(piv.columns)), piv.columns)
    plt.xlabel("composition horizon")
    plt.ylabel("forcing element")
    plt.title("Principal-variation atom composition by opening horizon")
    plt.colorbar(label="summed component value")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return g


def plot_shape_by_ply(pv, path):
    if pv.empty:
        return pd.DataFrame()
    g = pv.groupby(["pv_ply", "shape"], as_index=False).size().rename(columns={"size": "count"})
    top = g.groupby("shape")["count"].sum().sort_values(ascending=False).head(14).index.tolist()
    piv = g[g["shape"].isin(top)].pivot_table(index="shape", columns="pv_ply", values="count", fill_value=0)
    piv = piv.loc[top]
    plt.figure(figsize=(8, 5.5))
    plt.imshow(piv.values, aspect="auto")
    plt.yticks(np.arange(len(piv.index)), piv.index)
    plt.xticks(np.arange(len(piv.columns)), piv.columns)
    plt.xlabel("principal variation ply")
    plt.ylabel("pair shape")
    plt.title("Shape compositions along principal variations")
    plt.colorbar(label="count")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return g


def plot_opening_shape_summary(df, path, max_depth):
    col = f"value_d{max_depth}"
    g = df.groupby("opening_shape", as_index=False).agg(
        openings=("opening_id", "size"),
        mean_value=(col, "mean"),
        min_value=(col, "min"),
        max_value=(col, "max"),
        mean_spread=("spread", "mean"),
    ).sort_values("mean_value", ascending=False)
    top = g.head(18)
    plt.figure(figsize=(8.5, 5))
    x = np.arange(len(top))
    plt.bar(x, top["mean_value"])
    plt.xticks(x, top["opening_shape"], rotation=45, ha="right")
    plt.ylabel(f"mean Black value d={max_depth}")
    plt.title("Opening shape vulnerability under atom-composition minimax")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()
    return g


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out", default="hexconnect6_atom_compositions_out")
    p.add_argument("--radius", type=int, default=6)
    p.add_argument("--opening-radius", type=int, default=4)
    p.add_argument("--opening-spread", type=int, default=7)
    p.add_argument("--max-openings", type=int, default=80)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--max-spread", type=int, default=7)
    p.add_argument("--prefilter", type=int, default=18)
    p.add_argument("--branch", type=int, default=3)
    p.add_argument("--max-depth", type=int, default=4)
    p.add_argument("--static-top", type=int, default=8)
    p.add_argument("--temperature", type=float, default=1.2)
    p.add_argument("--gamma", type=float, default=0.72)
    p.add_argument("--opponent-weight", type=float, default=0.72)
    p.add_argument("--white-attack-weight", type=float, default=0.95)
    args = p.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    work = out / "_work"
    for d in [fig, data, work]:
        d.mkdir(parents=True, exist_ok=True)

    root = extract_if_zip(Path(args.input), work)
    elements, element_values, lookup = load_element_values(root)
    openings, pv, comp = evaluate_openings(args, lookup)

    openings.to_csv(data / "opening_atom_values.csv", index=False)
    pv.to_csv(data / "principal_variations.csv", index=False)
    comp.to_csv(data / "atom_compositions.csv", index=False)
    elements.to_csv(data / "source_forcing_elements.csv", index=False)
    element_values.to_csv(data / "element_values.csv", index=False)

    maxd = args.max_depth
    plot_opening_surface(openings, f"value_d0", fig / "opening_value_surface_d0.png", "Immediate atom-composition value after opening")
    plot_opening_surface(openings, f"value_d{maxd}", fig / f"opening_value_surface_d{maxd}.png", f"Depth-{maxd} atom-composition opening value")
    plot_depth_curves(openings, fig / "opening_value_by_depth.png", maxd)
    rank = plot_ranking_stability(openings, fig / "opening_ranking_stability.png", maxd)
    rank.to_csv(data / "ranking_stability.csv", index=False)
    comp_summary = plot_composition_heatmap(comp, fig / "atom_composition_by_depth.png")
    comp_summary.to_csv(data / "atom_composition_by_depth.csv", index=False)
    shape_summary = plot_shape_by_ply(pv, fig / "shape_composition_by_ply.png")
    shape_summary.to_csv(data / "shape_composition_by_ply.csv", index=False)
    opening_shapes = plot_opening_shape_summary(openings, fig / "opening_shape_vulnerability.png", maxd)
    opening_shapes.to_csv(data / "opening_shape_vulnerability.csv", index=False)

    safe = openings.sort_values([f"value_d{maxd}", "min_radius", "spread"], ascending=[True, False, True]).head(15)
    risky = openings.sort_values([f"value_d{maxd}", "min_radius", "spread"], ascending=[False, True, True]).head(15)
    safe.to_csv(data / "safest_openings.csv", index=False)
    risky.to_csv(data / "riskiest_openings.csv", index=False)

    # Element transition counts in principal lines.
    trans_rows = []
    if not comp.empty:
        for (oid, depth), g in comp.sort_values(["opening_id", "depth", "pv_ply"]).groupby(["opening_id", "depth"]):
            syms = g.groupby("pv_ply")["symbol"].apply(lambda x: "+".join(sorted(set(x)))).tolist()
            for a, b in zip(syms, syms[1:]):
                trans_rows.append({"opening_id": oid, "depth": depth, "from": a, "to": b})
    trans = pd.DataFrame(trans_rows)
    if not trans.empty:
        trans_counts = trans.groupby(["from", "to"], as_index=False).size().rename(columns={"size": "count"}).sort_values("count", ascending=False)
    else:
        trans_counts = pd.DataFrame()
    trans.to_csv(data / "element_transition_rows.csv", index=False)
    trans_counts.to_csv(data / "element_transition_counts.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "openings_evaluated": int(len(openings)),
        "element_values": int(len(element_values)),
        "known_element_hits": int((comp["component_type"].isin(["exact", "proto"])).sum()) if not comp.empty else 0,
        "unknown_element_hits": int((comp["component_type"].str.contains("unknown", na=False)).sum()) if not comp.empty else 0,
        "mean_value_by_depth": {f"d{i}": float(openings[f"value_d{i}"].mean()) for i in range(maxd + 1)},
        "std_value_by_depth": {f"d{i}": float(openings[f"value_d{i}"].std()) for i in range(maxd + 1)},
        "best_white_openings_low_black_value": safe.head(10).to_dict(orient="records"),
        "worst_white_openings_high_black_value": risky.head(10).to_dict(orient="records"),
        "top_composition_symbols": comp.groupby("symbol")["component_value"].sum().sort_values(ascending=False).head(12).to_dict() if not comp.empty else {},
        "top_shape_pv": pv.groupby("shape")["shape"].count().sort_values(ascending=False).head(12).to_dict() if not pv.empty else {},
        "interpretation": (
            "Opening value is estimated by short minimax over compositions of periodic-table forcing elements. "
            "Low value means a White opening suppresses Black's accessible atom compositions; high value means it permits strong Black forcing atoms."
        ),
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = """# Atom-composition opening evaluation

This package evaluates Hex Connect-6 openings by compositions of primitive forcing atoms.

A move induces exact/proto obligation hypergraphs. Their integer incidence fingerprints
are looked up as elements in the periodic table; a short minimax search then scores
White openings at several continuation depths.

Key files:
- data/opening_atom_values.csv
- data/principal_variations.csv
- data/atom_compositions.csv
- data/element_values.csv
- data/safest_openings.csv
- data/riskiest_openings.csv

Key figures:
- opening_value_surface_d0.png
- opening_value_surface_d4.png
- opening_value_by_depth.png
- opening_ranking_stability.png
- atom_composition_by_depth.png
- shape_composition_by_ply.png
- opening_shape_vulnerability.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            if "_work" in pth.parts:
                continue
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_atom_compositions.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
