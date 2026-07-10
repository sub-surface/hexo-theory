#!/usr/bin/env python3
"""
hexconnect6_pressure_landscape.py

Exact-ish transversal pressure landscape for infinite Hex Connect-6 in a finite Eisenstein window.

A two-stone candidate move m induces an obligation hypergraph O(P,m):
  - vertices are empty cells that could be used to block urgent future wins;
  - hyperedges are the empty cells in any live length-6 segment that the attacker can
    complete on their next two-stone turn, i.e. segments with no opponent stones and
    one or two empty cells.

The defender has capacity 2. We compute the exact small hitting number tau(O) by brute
force over the union of obligation vertices, and define

    pressure(m) = max(0, tau(O(P,m)) - 2)

This script evaluates that pressure over all legal two-stone candidates in a bounded
local window and produces scientific figures/data.

Run:
    python hexconnect6_pressure_landscape.py --out pressure_out --radius 7 --candidate-radius 5
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DIRS = ((1, 0), (0, 1), (1, -1))
Cell = Tuple[int, int]
Board = Dict[Cell, int]


def hex_dist(a: Cell, b: Cell = (0, 0)) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def add(a: Cell, d: Cell, k: int = 1) -> Cell:
    return (a[0] + d[0] * k, a[1] + d[1] * k)


def axial_to_xy(c: Cell) -> Tuple[float, float]:
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


def all_segments(radius: int, pad: int = 2) -> List[Tuple[Cell, ...]]:
    # Include a slightly padded window because six-lines can cross the candidate region boundary.
    cells = set(cells_in_radius(radius + pad))
    segments = set()
    for c in cells:
        for d in DIRS:
            seg = tuple(add(c, d, k) for k in range(6))
            if all(x in cells for x in seg):
                segments.add(seg)
    return sorted(segments)


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
            # Defender must hit at least one vertex in this set before the attacker gets another pair.
            obligations.append(tuple(sorted(empties)))
    # Deduplicate identical obligations.
    obligations = sorted(set(obligations))
    terminal_segments = sorted(set(terminal_segments))
    return obligations, terminal_segments


def hitting_number(obligations: Sequence[Tuple[Cell, ...]], max_k: int = 7) -> int:
    if not obligations:
        return 0
    universe = sorted(set(c for edge in obligations for c in edge))
    # Fast lower bound: number of singleton edges with distinct cells.
    singleton_cells = {edge[0] for edge in obligations if len(edge) == 1}
    if len(singleton_cells) > max_k:
        return max_k + 1
    for k in range(1, min(max_k, len(universe)) + 1):
        for combo in itertools.combinations(universe, k):
            S = set(combo)
            if all(any(c in S for c in edge) for edge in obligations):
                return k
    return max_k + 1


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
    # Lightweight ordering proxy only; pressure/tau below are exact for the derived obligation game.
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    value = 0.0
    for c in move:
        for d in DIRS:
            mine, op = count_run(nb, c, d, player)
            theirs, _ = count_run(board, c, d, -player)
            value += mine * mine + (6 if theirs >= 5 else 2 if theirs >= 4 else 0)
    value += max(0, 6 - hex_dist(move[0], move[1])) * 0.2
    return value


def evaluate_landscape(board: Board, radius: int, candidate_radius: int, player: int, max_spread: int):
    cells = cells_in_radius(radius)
    segments = all_segments(radius, pad=2)
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    rows = []
    obligation_records = []
    top_obligations = None
    top_key = None

    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) > max_spread:
                continue
            obligations, terminal_segments = obligations_after_move(board, (a, b), player, segments)
            tau = hitting_number(obligations, max_k=7)
            pressure = max(0, tau - 2)
            terminal = int(len(terminal_segments) > 0)
            shape = canonical_delta((b[0] - a[0], b[1] - a[1]))
            naive_deficit = max(0, len(obligations) - 2)
            center_q = (a[0] + b[0]) / 2
            center_r = (a[1] + b[1]) / 2
            x, y = axial_to_xy((center_q, center_r))
            row = dict(
                a_q=a[0], a_r=a[1], b_q=b[0], b_r=b[1],
                center_q=center_q, center_r=center_r, x=x, y=y,
                spread=hex_dist(a, b),
                shape=str(shape),
                obligations=len(obligations),
                singleton_obligations=sum(1 for e in obligations if len(e) == 1),
                tau=tau,
                pressure=pressure,
                terminal=terminal,
                terminal_segments=len(terminal_segments),
                naive_deficit=naive_deficit,
                heuristic_value=heuristic_pair_value(board, (a, b), player),
            )
            rows.append(row)
            score = pressure * 1000 + terminal * 100 + tau * 10 + len(obligations)
            if top_key is None or score > top_key:
                top_key = score
                top_obligations = (a, b, obligations, terminal_segments)

    df = pd.DataFrame(rows)
    if top_obligations is not None:
        a, b, obligations, terminal_segments = top_obligations
        for j, edge in enumerate(obligations):
            obligation_records.append({
                "kind": "obligation",
                "index": j,
                "a_q": a[0], "a_r": a[1], "b_q": b[0], "b_r": b[1],
                "edge": str(edge),
                "edge_size": len(edge),
            })
        for j, seg in enumerate(terminal_segments):
            obligation_records.append({
                "kind": "terminal_segment",
                "index": j,
                "a_q": a[0], "a_r": a[1], "b_q": b[0], "b_r": b[1],
                "edge": str(seg),
                "edge_size": len(seg),
            })
    return df, pd.DataFrame(obligation_records), cells


def deposit_cell_heat(df: pd.DataFrame, cells: List[Cell]):
    heat = {c: dict(pressure=0.0, tau=0.0, terminal=0.0, obligations=0.0) for c in cells}
    for _, row in df.iterrows():
        for c in ((int(row.a_q), int(row.a_r)), (int(row.b_q), int(row.b_r))):
            if c in heat:
                heat[c]["pressure"] += float(row.pressure)
                heat[c]["tau"] += float(row.tau)
                heat[c]["terminal"] += float(row.terminal)
                heat[c]["obligations"] += float(row.obligations)
    rows = []
    for c in cells:
        x, y = axial_to_xy(c)
        rows.append(dict(q=c[0], r=c[1], x=x, y=y, radius=hex_dist(c), **heat[c]))
    return pd.DataFrame(rows)


def shape_spectrum(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame()
    return (df.groupby("shape", as_index=False)
              .agg(pressure=("pressure", "sum"), tau=("tau", "mean"), count=("shape", "size"), terminal=("terminal", "sum"))
              .sort_values(["pressure", "terminal", "count"], ascending=False)
              .head(20))


def plot_hex_heat(cell_df: pd.DataFrame, value_col: str, title: str, path: Path):
    plt.figure(figsize=(7, 6))
    plt.scatter(cell_df["x"], cell_df["y"], c=cell_df[value_col], marker="h", s=270)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title(title)
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.colorbar(label=value_col)
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_pair_centers(df: pd.DataFrame, path: Path):
    plt.figure(figsize=(7, 6))
    plt.scatter(df["x"], df["y"], c=df["pressure"] + 0.25 * df["terminal"], s=18 + 18 * np.minimum(df["tau"], 8))
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title("Pair-center transversal pressure landscape")
    plt.xlabel("pair-center Eisenstein x")
    plt.ylabel("pair-center Eisenstein y")
    plt.colorbar(label="pressure + terminal")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_tau_vs_obligations(df: pd.DataFrame, path: Path):
    plt.figure(figsize=(7, 5))
    plt.scatter(df["obligations"], df["tau"], s=20 + 30 * df["terminal"])
    plt.xlabel("number of urgent obligation hyperedges")
    plt.ylabel("exact hitting number tau")
    plt.title("Obligations vs exact defender hitting number")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_proxy_vs_pressure(df: pd.DataFrame, path: Path):
    plt.figure(figsize=(7, 5))
    plt.scatter(df["naive_deficit"], df["pressure"], s=18 + 25 * df["terminal"])
    plt.xlabel("naive deficit = max(0, #obligations - 2)")
    plt.ylabel("exact pressure = max(0, tau - 2)")
    plt.title("Proxy threat count vs exact transversal pressure")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_shape_spectrum(spec: pd.DataFrame, path: Path):
    plt.figure(figsize=(8, 4.8))
    x = np.arange(len(spec))
    plt.bar(x, spec["pressure"])
    plt.xticks(x, spec["shape"], rotation=45, ha="right")
    plt.ylabel("total exact pressure")
    plt.title("D6 pair-shape pressure spectrum")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_top_obligation_board(board: Board, cell_df: pd.DataFrame, obligations_df: pd.DataFrame, path: Path):
    plt.figure(figsize=(7, 6))
    # Base grid by exact pressure heat.
    plt.scatter(cell_df["x"], cell_df["y"], c=cell_df["pressure"], marker="h", s=230, alpha=0.75)

    if not obligations_df.empty:
        first = obligations_df.iloc[0]
        move = [(int(first.a_q), int(first.a_r)), (int(first.b_q), int(first.b_r))]
        move_xy = np.array([axial_to_xy(c) for c in move])
        plt.scatter(move_xy[:, 0], move_xy[:, 1], marker="o", s=420, facecolors="none", linewidths=2.5, label="top pressure move")

        edge_cells = []
        for _, row in obligations_df[obligations_df["kind"] == "obligation"].iterrows():
            # Safe parsing because edge is tuple repr from our own script.
            cells = eval(row["edge"], {"__builtins__": {}})
            for c in cells:
                edge_cells.append(c)
        if edge_cells:
            exy = np.array([axial_to_xy(c) for c in edge_cells])
            plt.scatter(exy[:, 0], exy[:, 1], marker="x", s=120, label="obligation vertices")

    stones = list(board.items())
    if stones:
        xy = np.array([axial_to_xy(c) for c, _ in stones])
        vals = np.array([v for _, v in stones])
        plt.scatter(xy[:, 0], xy[:, 1], c=vals, marker="o", s=80, label="existing stones")
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title("Top pressure move and induced obligation vertices")
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="hexconnect6_pressure_landscape_out")
    parser.add_argument("--radius", type=int, default=7)
    parser.add_argument("--candidate-radius", type=int, default=5)
    parser.add_argument("--player", type=int, default=1)
    parser.add_argument("--max-spread", type=int, default=7)
    parser.add_argument("--pattern", choices=["ladder", "seeded"], default="ladder")
    args = parser.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    board = ladder_trap_pattern() if args.pattern == "ladder" else seeded_fork_pattern()
    df, obligations_df, cells = evaluate_landscape(board, args.radius, args.candidate_radius, args.player, args.max_spread)
    cell_df = deposit_cell_heat(df, cells)
    spec = shape_spectrum(df)

    df.to_csv(data / "candidate_pressure_landscape.csv", index=False)
    cell_df.to_csv(data / "cell_pressure_heatmap.csv", index=False)
    spec.to_csv(data / "shape_pressure_spectrum.csv", index=False)
    obligations_df.to_csv(data / "top_move_obligations.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "num_candidates": int(len(df)),
        "num_pressure_positive": int((df["pressure"] > 0).sum()),
        "num_terminal": int((df["terminal"] > 0).sum()),
        "max_tau": int(df["tau"].max()) if len(df) else 0,
        "max_pressure": int(df["pressure"].max()) if len(df) else 0,
        "mean_tau": float(df["tau"].mean()) if len(df) else 0,
        "mean_pressure": float(df["pressure"].mean()) if len(df) else 0,
        "correlation_naive_exact": float(df[["naive_deficit", "pressure"]].corr().iloc[0, 1]) if len(df) and df["pressure"].std() > 0 else None,
        "top_candidates": df.sort_values(["pressure", "terminal", "tau", "obligations", "heuristic_value"], ascending=False).head(12).to_dict(orient="records"),
        "interpretation": "pressure=max(0,tau-2), where tau is the exact hitting number of the urgent obligation hypergraph induced by a two-stone move.",
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    plot_hex_heat(cell_df, "pressure", "Cell-deposited exact transversal pressure", fig / "cell_transversal_pressure_heatmap.png")
    plot_hex_heat(cell_df, "tau", "Cell-deposited hitting number tau", fig / "cell_tau_heatmap.png")
    plot_hex_heat(cell_df, "terminal", "Cell-deposited terminal pressure", fig / "cell_terminal_heatmap.png")
    plot_pair_centers(df, fig / "pair_center_pressure_landscape.png")
    plot_tau_vs_obligations(df, fig / "tau_vs_obligations.png")
    plot_proxy_vs_pressure(df, fig / "proxy_vs_exact_pressure.png")
    plot_shape_spectrum(spec, fig / "shape_pressure_spectrum.png")
    plot_top_obligation_board(board, cell_df, obligations_df, fig / "top_move_obligation_hypergraph.png")

    readme = f"""# Hex Connect-6 exact transversal pressure landscape

This run computes the derived obligation hypergraph for every candidate two-stone move
in a finite axial/Eisenstein window, then computes exact hitting number tau by brute force.

Core definition:

    pressure(m) = max(0, tau(O(P,m)) - 2)

where O(P,m) is the family of urgent one- or two-cell obligations created by move m.

A positive pressure means that, in this derived local hypergraph game, a defender with
two stones cannot hit every urgent obligation in one reply.

See data/metrics.json and figures/.
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob("*"):
            z.write(p, p.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_pressure_landscape.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
