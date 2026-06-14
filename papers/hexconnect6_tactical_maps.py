#!/usr/bin/env python3
"""
hexconnect6_tactical_maps.py

OOM-safe NumPy/Matplotlib experiment for infinite Hex Connect-6 on an axial/Eisenstein grid.

The experiment tests a concrete version of the threat-manifold conjecture:

    Paths that lead the game toward tactical completion concentrate mass into a
    low-dimensional heatmap of response-deficit cells, rather than diffusing over
    the legal move reservoir.

Outputs:
  - figures/opening_attractor_heatmap.png
  - figures/tactical_completion_heatmap.png
  - figures/response_deficit_heatmap.png
  - figures/terminal_pressure_heatmap.png
  - figures/radial_signature.png
  - figures/pair_shape_spectrum.png
  - data/cell_heatmap.csv
  - data/radial_signature.csv
  - data/pair_shape_spectrum.csv
  - data/best_line.csv
  - data/metrics.json

Run:
  python hexconnect6_tactical_maps.py --out hexconnect6_maps --radius 7 --candidate-radius 5 --plies 12 --beam 8 --branch 3
"""

from __future__ import annotations

import argparse
import json
import math
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DIRS = ((1, 0), (0, 1), (1, -1))


def key(q: int, r: int) -> Tuple[int, int]:
    return (int(q), int(r))


def opp(player: int) -> int:
    return -player


def hex_dist(a: Tuple[int, int], b: Tuple[int, int] = (0, 0)) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def cells_in_radius(radius: int) -> List[Tuple[int, int]]:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                cells.append((q, r))
    return cells


def axial_to_xy(q: int, r: int) -> Tuple[float, float]:
    return (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)


def add(a: Tuple[int, int], d: Tuple[int, int], m: int = 1) -> Tuple[int, int]:
    return (a[0] + d[0] * m, a[1] + d[1] * m)


def rotate60(c: Tuple[int, int]) -> Tuple[int, int]:
    q, r = c
    return (-r, q + r)


def reflect(c: Tuple[int, int]) -> Tuple[int, int]:
    q, r = c
    return (r, q)


def d6_orbit(c: Tuple[int, int]) -> List[Tuple[int, int]]:
    out = []
    x = c
    for _ in range(6):
        out.append(x)
        out.append(reflect(x))
        x = rotate60(x)
    return out


def canonical_delta(d: Tuple[int, int]) -> Tuple[int, int]:
    return sorted(set(d6_orbit(d)))[0]


def count_run(board: Dict[Tuple[int, int], int], cell: Tuple[int, int], direction: Tuple[int, int], player: int) -> Tuple[int, int]:
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


def immediate_win_if_placed(board: Dict[Tuple[int, int], int], cell: Tuple[int, int], player: int) -> bool:
    return any(count_run(board, cell, d, player)[0] >= 6 for d in DIRS)


def local_signed_field(board: Dict[Tuple[int, int], int], cell: Tuple[int, int], player: int, kernel_width: float) -> float:
    if not board:
        return 0.0
    s = 0.0
    mass = 0.0
    sig = kernel_width + 0.8
    for c, v in board.items():
        d = hex_dist(cell, c)
        w = math.exp(-(d * d) / (2.0 * sig * sig))
        s += (1.0 if v == player else -1.0) * w
        mass += w
    return s / mass if mass else 0.0


def cell_threat(board: Dict[Tuple[int, int], int], cell: Tuple[int, int], player: int, kernel_width: float, layers: int):
    axis = []
    for d in DIRS:
        mine_count, mine_open = count_run(board, cell, d, player)
        their_count, _ = count_run(board, cell, d, opp(player))
        live = mine_count if mine_open >= 1 else max(0, mine_count - 1)
        block = 8 if their_count >= 5 else 3 if their_count >= 4 else 1 if their_count >= 3 else 0
        axis.append(live * live + block)

    vec = np.array(axis, dtype=np.float64)
    anis = np.array([1.0, 0.82, 0.92])
    for _ in range(layers):
        vec = np.tanh((vec * anis) / (4.5 + kernel_width)) * 6.0

    win = 1 if immediate_win_if_placed(board, cell, player) else 0
    fork = int(np.sum(vec >= 3.0))
    signed = local_signed_field(board, cell, player, kernel_width)
    total = float(vec.sum() + 20 * win + 2 * fork + max(0.0, signed))
    return dict(axis=vec, total=total, win=win, fork=fork, signed=signed)


def pair_features(board: Dict[Tuple[int, int], int], a: Tuple[int, int], b: Tuple[int, int], player: int, kernel_width: float, layers: int):
    ta = cell_threat(board, a, player, kernel_width, layers)
    tb = cell_threat(board, b, player, kernel_width, layers)
    oa = cell_threat(board, a, opp(player), kernel_width, layers)
    ob = cell_threat(board, b, opp(player), kernel_width, layers)

    synergy = 0.0
    for i, d in enumerate(DIRS):
        aligned = (b[0] - a[0]) * d[1] == (b[1] - a[1]) * d[0]
        close = max(0, 6 - hex_dist(a, b)) / 6.0
        if aligned:
            synergy += close * (ta["axis"][i] + tb["axis"][i])

    nb = dict(board)
    nb[a] = player
    nb[b] = player
    win = 1 if immediate_win_if_placed(nb, a, player) or immediate_win_if_placed(nb, b, player) else 0

    axis_obligations = []
    for d in DIRS:
        ca = 1 if count_run(nb, a, d, player)[0] >= 5 else 0
        cb = 1 if count_run(nb, b, d, player)[0] >= 5 else 0
        axis_obligations.append(ca + cb)

    obligations = sum(axis_obligations)
    response_deficit = max(0, obligations - 2)
    fork = response_deficit + ta["fork"] + tb["fork"]
    spread = hex_dist(a, b)
    center = max(0.0, 1.0 - hex_dist(((a[0] + b[0]) // 2, (a[1] + b[1]) // 2)) / 10.0)
    block = oa["total"] + ob["total"]
    curvature = fork + response_deficit + 0.08 * abs(float(ta["axis"][0] - tb["axis"][1])) + 0.08 * abs(float(ta["axis"][2] - tb["axis"][0]))
    reservoir_score = 1.0 / (1.0 + ta["total"] + tb["total"] + block + synergy + 4 * win + 2 * fork)
    value = 24 * win + 4.1 * fork + 2.8 * response_deficit + 1.35 * synergy + 0.62 * (ta["total"] + tb["total"]) + 0.50 * block + center - 0.08 * spread
    shape = canonical_delta((b[0] - a[0], b[1] - a[1]))

    return dict(
        a=a,
        b=b,
        value=float(value),
        win=int(win),
        fork=float(fork),
        block=float(block),
        synergy=float(synergy),
        response_deficit=float(response_deficit),
        curvature=float(curvature),
        reservoir_score=float(reservoir_score),
        shape=shape,
        axis_obligations=axis_obligations,
    )


def candidate_pairs(board, cells, player, candidate_radius, kernel_width, layers, max_pairs=64):
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    pairs = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= 7:
                pairs.append(pair_features(board, a, b, player, kernel_width, layers))
    pairs.sort(key=lambda x: x["value"], reverse=True)
    return pairs[:max_pairs]


def add_orbit(heat: Dict[Tuple[int, int], float], cell: Tuple[int, int], amount: float):
    orbit = set(d6_orbit(cell))
    share = amount / max(1, len(orbit))
    for c in orbit:
        heat[c] = heat.get(c, 0.0) + share


def summarize_heat(abs_heat, radius):
    vals = np.array(list(abs_heat.values()), dtype=float)
    if vals.size == 0:
        return dict(active_cells=0, entropy=0.0, participation=0.0, dimension=0.0)
    max_abs = vals.max() if vals.size else 1.0
    active = int(np.sum(vals > max_abs * 0.08))
    ps = vals / max(vals.sum(), 1e-12)
    ps = ps[ps > 1e-12]
    entropy = float(-(ps * np.log(ps)).sum())
    participation = float(1.0 / max(float((ps * ps).sum()), 1e-12))
    dimension = float(math.log(active + 1) / math.log(radius + 2))
    return dict(active_cells=active, entropy=entropy, participation=participation, dimension=dimension)


def opening_attractor(args):
    cells = cells_in_radius(args.radius)
    board = {(0, 0): 1}
    signed_heat, abs_heat, shape_counts = {}, {}, {}
    radial = np.zeros(args.radius + 1)
    depth_mass = np.zeros(args.opening_depth + 1)
    branches = 0
    nodes = 0
    best_leaf = -1e9

    def deposit(cell, amount, ply, side):
        if hex_dist(cell) > args.radius:
            return
        add_orbit(signed_heat, cell, amount * (1 if side == 1 else -1))
        add_orbit(abs_heat, cell, abs(amount))
        radial[hex_dist(cell)] += abs(amount)
        depth_mass[ply] += abs(amount)

    deposit((0, 0), 1.0, 0, 1)

    def rec(board, side, ply, weight, score):
        nonlocal branches, nodes, best_leaf
        nodes += 1
        if ply >= args.opening_depth:
            branches += 1
            best_leaf = max(best_leaf, score)
            return
        moves = candidate_pairs(board, cells, side, args.candidate_radius, args.kernel_width, args.layers, max_pairs=max(8, args.opening_branch * 6))
        if not moves:
            branches += 1
            best_leaf = max(best_leaf, score)
            return
        chosen = moves[:args.opening_branch]
        denom = sum(max(0.05, m["value"]) for m in chosen) or 1.0
        for m in chosen:
            local = max(0.05, m["value"]) / denom
            next_weight = weight * local * (1 + 0.18 * m["response_deficit"] + 0.08 * m["fork"])
            nb = dict(board)
            nb[m["a"]] = side
            nb[m["b"]] = side
            deposit(m["a"], next_weight, ply + 1, side)
            deposit(m["b"], next_weight, ply + 1, side)
            shape_counts[m["shape"]] = shape_counts.get(m["shape"], 0.0) + next_weight
            rec(nb, -side, ply + 1, next_weight, score + m["value"] * (1 if side == 1 else -0.72))

    rec(board, -1, 0, 1.0, 0.0)
    metrics = summarize_heat(abs_heat, args.radius)
    metrics.update(branches=branches, nodes=nodes, best_leaf=float(best_leaf))
    return dict(signed_heat=signed_heat, abs_heat=abs_heat, shape_counts=shape_counts, radial=radial, depth_mass=depth_mass, metrics=metrics)


def tactical_completion(args):
    cells = cells_in_radius(args.radius)
    signed_heat, abs_heat, deficit_heat, terminal_heat, shape_counts = {}, {}, {}, {}, {}
    radial = np.zeros(args.radius + 1)
    depth_mass = np.zeros(args.plies + 1)
    frontier = [dict(board={(0, 0): 1}, side=-1, mass=1.0, score=0.0, line=[])]
    terminal_mass = 0.0
    nodes = 0
    best_score = -1e9
    best_line = []

    add_orbit(abs_heat, (0, 0), 1.0)
    add_orbit(signed_heat, (0, 0), 1.0)
    radial[0] += 1.0

    for ply in range(args.plies):
        expanded = []
        if not frontier:
            break
        for node in frontier:
            nodes += 1
            moves = candidate_pairs(node["board"], cells, node["side"], args.candidate_radius, args.kernel_width, args.layers, max_pairs=max(12, args.branch * 4))
            if not moves:
                continue
            chosen = moves[:args.branch]
            weights = np.exp(np.array([m["value"] for m in chosen], dtype=float) / 18.0)
            weights /= weights.sum() if weights.sum() else 1.0

            for m, local in zip(chosen, weights):
                mass = node["mass"] * float(local) * (1 + 0.25 * m["response_deficit"] + 0.1 * m["win"])
                nb = dict(node["board"])
                nb[m["a"]] = node["side"]
                nb[m["b"]] = node["side"]

                for c in (m["a"], m["b"]):
                    if hex_dist(c) <= args.radius:
                        add_orbit(abs_heat, c, abs(mass))
                        add_orbit(signed_heat, c, mass * (1 if node["side"] == 1 else -1))
                        add_orbit(deficit_heat, c, mass * (m["response_deficit"] + 0.35 * m["fork"]))
                        if m["win"]:
                            add_orbit(terminal_heat, c, mass)
                        radial[hex_dist(c)] += abs(mass)

                depth_mass[ply + 1] += abs(mass)
                shape_counts[m["shape"]] = shape_counts.get(m["shape"], 0.0) + mass * (1 + m["response_deficit"])
                score = node["score"] + m["value"] * (1 if node["side"] == 1 else -0.72) + 5 * m["response_deficit"] + 12 * m["win"]
                line = node["line"] + [m]
                if m["win"]:
                    terminal_mass += mass
                if score > best_score:
                    best_score = score
                    best_line = line
                if not m["win"]:
                    expanded.append(dict(board=nb, side=-node["side"], mass=mass, score=score, line=line))

        expanded.sort(key=lambda x: x["mass"] * (1 + max(0.0, x["score"])), reverse=True)
        frontier = expanded[:args.beam]

    metrics = summarize_heat(abs_heat, args.radius)
    metrics.update(
        terminal_mass=float(terminal_mass),
        live_mass=float(sum(x["mass"] for x in frontier)),
        nodes_expanded=nodes,
        best_score=float(best_score),
    )
    return dict(
        signed_heat=signed_heat,
        abs_heat=abs_heat,
        deficit_heat=deficit_heat,
        terminal_heat=terminal_heat,
        shape_counts=shape_counts,
        radial=radial,
        depth_mass=depth_mass,
        metrics=metrics,
        best_line=best_line,
    )


def heat_dataframe(cells, *heats):
    rows = []
    names = ["opening_abs", "opening_signed", "tactical_abs", "tactical_signed", "deficit", "terminal"]
    for c in cells:
        x, y = axial_to_xy(*c)
        row = dict(q=c[0], r=c[1], x=x, y=y, radius=hex_dist(c))
        for name, heat in zip(names, heats):
            row[name] = heat.get(c, 0.0)
        rows.append(row)
    return pd.DataFrame(rows)


def plot_hex_heat(df, value_col, title, path):
    plt.figure(figsize=(7, 6))
    plt.scatter(df["x"], df["y"], c=df[value_col], marker="h", s=260)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title(title)
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.colorbar(label=value_col)
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_radial(df, path):
    plt.figure(figsize=(7, 4.6))
    plt.plot(df["radius"], df["opening_mass"], marker="o", label="opening attractor")
    plt.plot(df["radius"], df["tactical_mass"], marker="o", label="tactical paths")
    plt.xlabel("hex radius")
    plt.ylabel("deposited mass")
    plt.title("Radial signature of attractor and tactical path mass")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def plot_shape_spectrum(df, path):
    plt.figure(figsize=(8, 4.8))
    labels = df["shape"].astype(str).tolist()
    x = np.arange(len(df))
    plt.bar(x, df["mass"])
    plt.xticks(x, labels, rotation=45, ha="right")
    plt.ylabel("weighted mass")
    plt.title("Dominant D6 quotient pair-shape classes")
    plt.tight_layout()
    plt.savefig(path, dpi=180)
    plt.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=str, default="hexconnect6_tactical_maps_out")
    p.add_argument("--radius", type=int, default=7)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--kernel-width", type=float, default=1.0)
    p.add_argument("--layers", type=int, default=2)
    p.add_argument("--opening-depth", type=int, default=4)
    p.add_argument("--opening-branch", type=int, default=2)
    p.add_argument("--plies", type=int, default=12)
    p.add_argument("--beam", type=int, default=8)
    p.add_argument("--branch", type=int, default=3)
    args = p.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    opening = opening_attractor(args)
    tactical = tactical_completion(args)

    cells = cells_in_radius(args.radius)
    df = heat_dataframe(
        cells,
        opening["abs_heat"],
        opening["signed_heat"],
        tactical["abs_heat"],
        tactical["signed_heat"],
        tactical["deficit_heat"],
        tactical["terminal_heat"],
    )
    df.to_csv(data / "cell_heatmap.csv", index=False)

    radial = pd.DataFrame({
        "radius": np.arange(args.radius + 1),
        "opening_mass": opening["radial"],
        "tactical_mass": tactical["radial"],
    })
    radial.to_csv(data / "radial_signature.csv", index=False)

    shape_counts = dict(opening["shape_counts"])
    for shape, mass in tactical["shape_counts"].items():
        shape_counts[shape] = shape_counts.get(shape, 0.0) + mass
    shape_df = pd.DataFrame([
        {"shape": str(shape), "mass": mass} for shape, mass in sorted(shape_counts.items(), key=lambda kv: kv[1], reverse=True)[:18]
    ])
    shape_df.to_csv(data / "pair_shape_spectrum.csv", index=False)

    best_line_rows = []
    for i, m in enumerate(tactical["best_line"][:20], start=1):
        best_line_rows.append({
            "ply": i,
            "a_q": m["a"][0], "a_r": m["a"][1],
            "b_q": m["b"][0], "b_r": m["b"][1],
            "value": m["value"],
            "response_deficit": m["response_deficit"],
            "fork": m["fork"],
            "win": m["win"],
            "shape": str(m["shape"]),
        })
    pd.DataFrame(best_line_rows).to_csv(data / "best_line.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "opening": opening["metrics"],
        "tactical_completion": tactical["metrics"],
        "conjecture_reading": {
            "completion_mass_fraction": tactical["metrics"]["terminal_mass"] / max(1e-12, tactical["metrics"]["terminal_mass"] + tactical["metrics"]["live_mass"]),
            "active_cell_fraction": tactical["metrics"]["active_cells"] / max(1, len(cells)),
            "participation_fraction": tactical["metrics"]["participation"] / max(1, len(cells)),
            "interpretation": "Support for the threat-cone conjecture increases when completion_mass_fraction is high while active_cell_fraction and participation_fraction remain low.",
        },
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    plot_hex_heat(df, "opening_signed", "D6-symmetrised opening attractor signed heat", fig / "opening_attractor_heatmap.png")
    plot_hex_heat(df, "tactical_abs", "Tactical completion path mass heatmap", fig / "tactical_completion_heatmap.png")
    plot_hex_heat(df, "deficit", "Response-deficit pressure heatmap", fig / "response_deficit_heatmap.png")
    plot_hex_heat(df, "terminal", "Terminal win-pressure heatmap", fig / "terminal_pressure_heatmap.png")
    plot_radial(radial, fig / "radial_signature.png")
    plot_shape_spectrum(shape_df, fig / "pair_shape_spectrum.png")

    readme = f"""# Hex Connect-6 tactical maps

This folder was generated by `hexconnect6_tactical_maps.py`.

The key test is whether tactical paths toward completion concentrate in a low-dimensional
threat cone. See `data/metrics.json` for active-cell fraction, participation fraction,
and completion mass fraction.

Generated figures:
- opening_attractor_heatmap.png
- tactical_completion_heatmap.png
- response_deficit_heatmap.png
- terminal_pressure_heatmap.png
- radial_signature.png
- pair_shape_spectrum.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in out.rglob("*"):
            z.write(path, path.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_tactical_maps.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
