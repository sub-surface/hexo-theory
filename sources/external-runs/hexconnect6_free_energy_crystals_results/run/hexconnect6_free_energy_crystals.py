#!/usr/bin/env python3
"""
hexconnect6_free_energy_crystals.py

Adaptive free-energy / crystal-tiling search for infinite Hex Connect-6.

This is an experimental search instrument, not a proof engine. It combines:

1. Active-inference style expected free energy:
      G(move) = complexity/surprise - tactical value - crystal/tiling coherence

2. Hypergraph pressure:
      exact_pressure = max(0, tau(exact obligations) - 2)
      proto_pressure = max(0, tau(proto obligations) - 2)

3. Crystal/tiling observables:
      - D6 pair-shape spectrum
      - rail/bridge pair classes
      - line-order parameter across the three hex axes
      - radial entropy / fractal participation
      - structure-factor-like axial Fourier energy

4. Adaptive depth:
      expand while policy entropy is high, proto/exact pressure is present, or
      a minimum ply count has not been reached; stop early in settled/low-energy leaves.

Outputs:
  figures/*.png
  data/*.csv
  data/metrics.json
  README.md
  zip package

Run:
  python hexconnect6_free_energy_crystals.py --out fep_hex_out --radius 7 --plies 16 --beam 18 --branch 3
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Sequence

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


def transforms_d6(c: Cell) -> List[Cell]:
    return d6_orbit(c)


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
    forced = sorted({e[0] for e in edges if len(e) == 1})
    if len(forced) > max_k:
        return max_k + 1
    remaining = [u for u in universe if u not in forced]
    for k in range(len(forced), min(max_k, len(universe)) + 1):
        for rest in itertools.combinations(remaining, k - len(forced)):
            S = set(forced) | set(rest)
            if all(any(c in S for c in e) for e in edges):
                return k
    return max_k + 1


def make_move(board: Board, move: Tuple[Cell, Cell], player: int) -> Board:
    nb = dict(board)
    nb[move[0]] = player
    nb[move[1]] = player
    return nb


def stones(board: Board, player: int) -> List[Cell]:
    return [c for c, v in board.items() if v == player]


def line_order(board: Board, player: int) -> float:
    ps = stones(board, player)
    if len(ps) <= 1:
        return 0.0
    counts = []
    for d in DIRS:
        # projection invariant perpendicular-ish to direction
        if d == (1, 0):
            vals = [r for q, r in ps]
        elif d == (0, 1):
            vals = [q for q, r in ps]
        else:
            vals = [q + r for q, r in ps]
        ctr = Counter(vals)
        counts.append(max(ctr.values()) / len(ps))
    return float(max(counts))


def radial_entropy(board: Board, player: int, radius: int) -> float:
    ps = stones(board, player)
    if not ps:
        return 0.0
    hist = np.zeros(radius + 1)
    for c in ps:
        d = min(radius, hex_dist(c))
        hist[d] += 1
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def structure_factor(board: Board, player: int, radius: int) -> float:
    # A tiny crystal-order proxy: Fourier energy at low axial wave-vectors.
    ps = stones(board, player)
    if not ps:
        return 0.0
    qs = [(1, 0), (0, 1), (1, -1), (2, 0), (0, 2), (2, -2)]
    energy = 0.0
    for kq, kr in qs:
        z = 0j
        for q, r in ps:
            phase = 2 * math.pi * (kq * q + kr * r) / max(3, radius)
            z += complex(math.cos(phase), math.sin(phase))
        energy += abs(z / len(ps)) ** 2
    return float(energy / len(qs))


def pair_shape_kind(shape: Cell) -> str:
    d = hex_dist(shape)
    # canonical collinear rails show up as (-n,0) under our canonicalization.
    if shape[1] == 0:
        if d <= 2:
            return "short_rail"
        if d <= 4:
            return "long_rail"
        return "bridge_rail"
    if d <= 2:
        return "compact_kink"
    if d <= 4:
        return "bridge"
    return "long_bridge"


def candidate_moves(board: Board, cells: Sequence[Cell], player: int, candidate_radius: int, max_spread: int, prefilter: int):
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    arr = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                arr.append((heuristic_pair_value(board, (a, b), player), a, b))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in arr[:prefilter]]


def move_features(board: Board, move: Tuple[Cell, Cell], player: int, segments, args, heuristic=None):
    heuristic = heuristic_pair_value(board, move, player) if heuristic is None else heuristic
    nb = make_move(board, move, player)
    exact, proto, terminal = obligations(nb, player, segments)
    tau_exact = hitting_number(exact, max_k=7)
    tau_proto = hitting_number(proto, max_k=7)
    pressure_exact = max(0, tau_exact - 2)
    pressure_proto = max(0, tau_proto - 2)
    shape = canonical_delta((move[1][0] - move[0][0], move[1][1] - move[0][1]))
    kind = pair_shape_kind(shape)
    order_before = line_order(board, player)
    order_after = line_order(nb, player)
    sf_before = structure_factor(board, player, args.radius)
    sf_after = structure_factor(nb, player, args.radius)
    re_after = radial_entropy(nb, player, args.radius)
    spread = hex_dist(move[0], move[1])
    center = ((move[0][0] + move[1][0]) / 2, (move[0][1] + move[1][1]) / 2)
    center_dist = max(abs(center[0]), abs(center[1]), abs(center[0] + center[1]))

    tactical_value = (
        args.terminal_weight * min(1, len(terminal))
        + args.exact_weight * pressure_exact
        + 0.55 * args.exact_weight * tau_exact
        + args.proto_weight * pressure_proto
        + 0.35 * args.proto_weight * tau_proto
        + 0.08 * len(proto)
        + 0.02 * heuristic
    )
    crystal_gain = (order_after - order_before) + 0.65 * (sf_after - sf_before)
    # Complexity is a prior cost: long jumps and off-lattice "surprise" should be paid for unless tactically justified.
    shape_complexity = {
        "short_rail": 0.15,
        "long_rail": 0.42,
        "bridge_rail": 0.75,
        "compact_kink": 0.32,
        "bridge": 0.55,
        "long_bridge": 0.9,
    }[kind]
    spatial_cost = 0.08 * spread + 0.035 * center_dist + 0.15 * re_after
    surprise = shape_complexity + spatial_cost

    # Expected free energy: minimize this.
    G = (
        args.complexity_weight * surprise
        - tactical_value
        - args.crystal_weight * crystal_gain
    )
    return dict(
        board=nb, move=move, shape=shape, kind=kind, heuristic=heuristic,
        exact_count=len(exact), proto_count=len(proto), terminal_count=len(terminal),
        tau_exact=tau_exact, tau_proto=tau_proto,
        pressure_exact=pressure_exact, pressure_proto=pressure_proto,
        line_order=order_after, structure_factor=sf_after, radial_entropy=re_after,
        crystal_gain=crystal_gain, surprise=surprise, tactical_value=tactical_value,
        G=float(G), spread=spread, center_dist=float(center_dist),
    )


def policy_distribution(evals: List[dict], temperature: float):
    if not evals:
        return np.array([])
    G = np.array([e["G"] for e in evals], dtype=float)
    logits = -(G - G.min()) / max(1e-6, temperature)
    logits = np.clip(logits, -60, 60)
    p = np.exp(logits)
    p /= p.sum()
    return p


def entropy(p):
    p = np.asarray(p, dtype=float)
    p = p[p > 1e-12]
    return float(-(p * np.log(p)).sum()) if p.size else 0.0


def should_expand(node, evals, p, ply, args):
    if ply < args.min_plies:
        return True
    if ply >= args.plies:
        return False
    if any(e["terminal_count"] for e in evals):
        return False
    H = entropy(p)
    best = min(e["G"] for e in evals) if evals else 0
    pressure = max([e["pressure_exact"] + 0.5 * e["pressure_proto"] for e in evals], default=0)
    # Adaptive rule: grow uncertain or tactically charged regions, stop settled reservoirs.
    return (H > args.entropy_stop) or (pressure > 0) or (best < -args.energy_continue)


def adaptive_search(args, complexity_weight=None, crystal_weight=None, phase_mode=False):
    if complexity_weight is not None:
        args = argparse.Namespace(**vars(args))
        args.complexity_weight = complexity_weight
    if crystal_weight is not None:
        args = argparse.Namespace(**vars(args))
        args.crystal_weight = crystal_weight

    cells = cells_in_radius(args.radius)
    segments = all_segments(args.radius, pad=2)
    start_board = {(0, 0): 1}
    frontier = [dict(id=0, board=start_board, side=-1, ply=0, mass=1.0, parent=-1, event=-1, cumulative_G=0.0)]
    states = [frontier[0]]
    events = []
    heat = defaultdict(float)
    signed_heat = defaultdict(float)
    shape_mass = Counter()
    kind_mass = Counter()
    layer_rows = []
    next_state_id = 1

    for ply in range(args.plies):
        expanded = []
        layer_evals = []
        for node in frontier:
            raw = candidate_moves(node["board"], cells, node["side"], args.candidate_radius, args.max_spread, args.prefilter)
            evals = [move_features(node["board"], (a, b), node["side"], segments, args, h) for a, b, h in raw]
            evals.sort(key=lambda e: e["G"])
            evals = evals[:max(args.branch * 3, args.branch)]
            p = policy_distribution(evals, args.temperature)
            H = entropy(p)
            expand = should_expand(node, evals, p, ply, args)
            layer_evals.extend(evals[:args.branch])

            for rank, (ev, prob) in enumerate(zip(evals[:args.branch], p[:args.branch])):
                eid = len(events)
                mass = node["mass"] * float(prob)
                for c in ev["move"]:
                    heat[c] += abs(mass) * (1 + ev["pressure_exact"] + 0.35 * ev["pressure_proto"])
                    signed_heat[c] += mass * (1 if node["side"] == 1 else -1)
                shape_mass[str(ev["shape"])] += mass * (1 + ev["pressure_exact"] + 0.35 * ev["pressure_proto"])
                kind_mass[ev["kind"]] += mass

                child = dict(
                    id=next_state_id, board=ev["board"], side=-node["side"], ply=ply + 1,
                    mass=mass, parent=node["id"], event=eid, cumulative_G=node["cumulative_G"] + ev["G"],
                )
                next_state_id += 1
                events.append(dict(
                    event_id=eid, parent=node["id"], child=child["id"], ply=ply + 1,
                    side=node["side"], mass=mass, policy_prob=float(prob), policy_entropy=H,
                    a_q=ev["move"][0][0], a_r=ev["move"][0][1],
                    b_q=ev["move"][1][0], b_r=ev["move"][1][1],
                    shape=str(ev["shape"]), kind=ev["kind"],
                    G=ev["G"], tactical_value=ev["tactical_value"], surprise=ev["surprise"],
                    crystal_gain=ev["crystal_gain"], line_order=ev["line_order"],
                    structure_factor=ev["structure_factor"], radial_entropy=ev["radial_entropy"],
                    tau_exact=ev["tau_exact"], tau_proto=ev["tau_proto"],
                    pressure_exact=ev["pressure_exact"], pressure_proto=ev["pressure_proto"],
                    terminal=ev["terminal_count"], exact_count=ev["exact_count"], proto_count=ev["proto_count"],
                    expanded=bool(expand),
                ))
                states.append(child)
                if expand:
                    expanded.append(child)

        if layer_evals:
            layer_rows.append(dict(
                ply=ply + 1,
                events=len(layer_evals),
                frontier=len(frontier),
                next_frontier=len(expanded),
                mean_G=float(np.mean([e["G"] for e in layer_evals])),
                min_G=float(np.min([e["G"] for e in layer_evals])),
                mean_pressure_exact=float(np.mean([e["pressure_exact"] for e in layer_evals])),
                mean_pressure_proto=float(np.mean([e["pressure_proto"] for e in layer_evals])),
                max_pressure_exact=int(max(e["pressure_exact"] for e in layer_evals)),
                max_pressure_proto=int(max(e["pressure_proto"] for e in layer_evals)),
                terminal_events=int(sum(1 for e in layer_evals if e["terminal_count"])),
                mean_line_order=float(np.mean([e["line_order"] for e in layer_evals])),
                mean_structure_factor=float(np.mean([e["structure_factor"] for e in layer_evals])),
                mean_radial_entropy=float(np.mean([e["radial_entropy"] for e in layer_evals])),
            ))

        expanded.sort(key=lambda n: n["mass"] * math.exp(-0.1 * n["cumulative_G"]), reverse=True)
        frontier = expanded[:args.beam]
        if not frontier:
            break

    events_df = pd.DataFrame(events)
    states_df = pd.DataFrame([{k: v for k, v in s.items() if k != "board"} for s in states])
    layers_df = pd.DataFrame(layer_rows)

    heat_df = []
    all_cells = cells_in_radius(args.radius)
    max_heat = max([abs(v) for v in heat.values()] + [1e-9])
    for c in all_cells:
        x, y = axial_to_xy(c)
        heat_df.append(dict(
            q=c[0], r=c[1], x=x, y=y, radius=hex_dist(c),
            heat=heat.get(c, 0.0), signed=signed_heat.get(c, 0.0),
            normalized=heat.get(c, 0.0) / max_heat,
        ))
    heat_df = pd.DataFrame(heat_df)

    shape_df = pd.DataFrame([{"shape": k, "mass": v} for k, v in shape_mass.items()]).sort_values("mass", ascending=False)
    kind_df = pd.DataFrame([{"kind": k, "mass": v} for k, v in kind_mass.items()]).sort_values("mass", ascending=False)

    metrics = dict(
        events=int(len(events_df)),
        states=int(len(states_df)),
        final_frontier=int(len(frontier)),
        max_ply=int(events_df["ply"].max()) if len(events_df) else 0,
        terminal_events=int(events_df["terminal"].sum()) if len(events_df) else 0,
        mean_G=float(events_df["G"].mean()) if len(events_df) else 0.0,
        min_G=float(events_df["G"].min()) if len(events_df) else 0.0,
        max_exact_pressure=int(events_df["pressure_exact"].max()) if len(events_df) else 0,
        max_proto_pressure=int(events_df["pressure_proto"].max()) if len(events_df) else 0,
        mean_line_order=float(events_df["line_order"].mean()) if len(events_df) else 0.0,
        mean_structure_factor=float(events_df["structure_factor"].mean()) if len(events_df) else 0.0,
        top_shape=shape_df.iloc[0].to_dict() if len(shape_df) else None,
        top_kind=kind_df.iloc[0].to_dict() if len(kind_df) else None,
    )
    return states_df, events_df, layers_df, heat_df, shape_df, kind_df, metrics


def phase_scan(args):
    rows = []
    cws = np.linspace(0.2, 2.2, args.phase_n)
    kws = np.linspace(0.0, 2.4, args.phase_n)
    # Smaller settings for grid search.
    base = argparse.Namespace(**vars(args))
    base.plies = min(args.plies, 10)
    base.beam = min(args.beam, 10)
    base.branch = min(args.branch, 2)
    base.prefilter = min(args.prefilter, 18)
    base.min_plies = min(args.min_plies, 4)
    for cw in cws:
        for kw in kws:
            _, events, layers, _, shape, kind, metrics = adaptive_search(base, complexity_weight=float(cw), crystal_weight=float(kw), phase_mode=True)
            rows.append(dict(
                complexity_weight=float(cw), crystal_weight=float(kw),
                events=metrics["events"], terminal_events=metrics["terminal_events"],
                mean_G=metrics["mean_G"], min_G=metrics["min_G"],
                max_exact_pressure=metrics["max_exact_pressure"],
                max_proto_pressure=metrics["max_proto_pressure"],
                mean_line_order=metrics["mean_line_order"],
                mean_structure_factor=metrics["mean_structure_factor"],
                top_kind=metrics["top_kind"]["kind"] if metrics["top_kind"] else "",
                top_shape=metrics["top_shape"]["shape"] if metrics["top_shape"] else "",
            ))
    return pd.DataFrame(rows)


def plot_hex_heat(df, col, title, path):
    plt.figure(figsize=(7, 6))
    plt.scatter(df["x"], df["y"], c=df[col], marker="h", s=270)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title(title)
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.colorbar(label=col)
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_pair_landscape(events, path):
    if events.empty:
        return
    centers = []
    for _, e in events.iterrows():
        cq = (e.a_q + e.b_q) / 2
        cr = (e.a_r + e.b_r) / 2
        x, y = axial_to_xy((cq, cr))
        centers.append((x, y))
    C = np.array(centers)
    plt.figure(figsize=(7, 6))
    plt.scatter(C[:, 0], C[:, 1], c=-events["G"], s=16 + 12 * (events["pressure_exact"] + events["pressure_proto"] + events["terminal"]))
    plt.gca().set_aspect("equal", adjustable="box")
    plt.title("Free-energy move landscape: low G / high value pair centers")
    plt.xlabel("pair-center x")
    plt.ylabel("pair-center y")
    plt.colorbar(label="-G")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_layers(layers, path):
    if layers.empty:
        return
    plt.figure(figsize=(8, 5))
    plt.plot(layers["ply"], layers["mean_G"], marker="o", label="mean G")
    plt.plot(layers["ply"], layers["min_G"], marker="o", label="min G")
    plt.xlabel("ply")
    plt.ylabel("free energy")
    plt.title("Adaptive free-energy descent")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(layers["ply"], layers["mean_line_order"], marker="o", label="line order")
    plt.plot(layers["ply"], layers["mean_structure_factor"], marker="o", label="structure factor")
    plt.plot(layers["ply"], layers["mean_radial_entropy"], marker="o", label="radial entropy")
    plt.xlabel("ply")
    plt.ylabel("order statistic")
    plt.title("Crystal/tiling order over adaptive search")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path.with_name("crystal_order_over_ply.png"), dpi=190)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(layers["ply"], layers["max_pressure_exact"], marker="o", label="max exact pressure")
    plt.plot(layers["ply"], layers["max_pressure_proto"], marker="o", label="max proto pressure")
    plt.plot(layers["ply"], layers["terminal_events"], marker="o", label="terminal events")
    plt.xlabel("ply")
    plt.ylabel("count")
    plt.title("Pressure emergence over adaptive search")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path.with_name("pressure_emergence_over_ply.png"), dpi=190)
    plt.close()


def plot_shape_spectrum(shape, path):
    top = shape.head(18)
    plt.figure(figsize=(8, 4.8))
    x = np.arange(len(top))
    plt.bar(x, top["mass"])
    plt.xticks(x, top["shape"], rotation=45, ha="right")
    plt.ylabel("free-energy path mass")
    plt.title("D6 quotient shape spectrum under FEP search")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_kind_spectrum(kind, path):
    plt.figure(figsize=(7, 4.6))
    x = np.arange(len(kind))
    plt.bar(x, kind["mass"])
    plt.xticks(x, kind["kind"], rotation=30, ha="right")
    plt.ylabel("path mass")
    plt.title("Rail / bridge / kink phase spectrum")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_phase(phase, path):
    if phase.empty:
        return
    piv = phase.pivot(index="complexity_weight", columns="crystal_weight", values="terminal_events")
    plt.figure(figsize=(7, 5.8))
    plt.imshow(piv.values, origin="lower", aspect="auto", extent=[piv.columns.min(), piv.columns.max(), piv.index.min(), piv.index.max()])
    plt.xlabel("crystal coherence weight")
    plt.ylabel("complexity/surprise weight")
    plt.title("Phase diagram: terminal events under FEP constraints")
    plt.colorbar(label="terminal events")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    piv2 = phase.pivot(index="complexity_weight", columns="crystal_weight", values="mean_line_order")
    plt.figure(figsize=(7, 5.8))
    plt.imshow(piv2.values, origin="lower", aspect="auto", extent=[piv2.columns.min(), piv2.columns.max(), piv2.index.min(), piv2.index.max()])
    plt.xlabel("crystal coherence weight")
    plt.ylabel("complexity/surprise weight")
    plt.title("Phase diagram: mean line/crystal order")
    plt.colorbar(label="line order")
    plt.tight_layout()
    plt.savefig(path.with_name("phase_diagram_line_order.png"), dpi=190)
    plt.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="hexconnect6_free_energy_crystals_out")
    p.add_argument("--radius", type=int, default=7)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--max-spread", type=int, default=7)
    p.add_argument("--plies", type=int, default=16)
    p.add_argument("--min-plies", type=int, default=5)
    p.add_argument("--beam", type=int, default=18)
    p.add_argument("--branch", type=int, default=3)
    p.add_argument("--prefilter", type=int, default=30)
    p.add_argument("--temperature", type=float, default=0.75)
    p.add_argument("--entropy-stop", type=float, default=0.55)
    p.add_argument("--energy-continue", type=float, default=3.0)
    p.add_argument("--complexity-weight", type=float, default=1.05)
    p.add_argument("--crystal-weight", type=float, default=1.15)
    p.add_argument("--terminal-weight", type=float, default=9.0)
    p.add_argument("--exact-weight", type=float, default=4.5)
    p.add_argument("--proto-weight", type=float, default=1.4)
    p.add_argument("--phase-n", type=int, default=6)
    args = p.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    states, events, layers, heat, shape, kind, metrics = adaptive_search(args)
    phase = phase_scan(args)

    states.to_csv(data / "adaptive_states.csv", index=False)
    events.to_csv(data / "adaptive_events.csv", index=False)
    layers.to_csv(data / "layer_metrics.csv", index=False)
    heat.to_csv(data / "cell_free_energy_heat.csv", index=False)
    shape.to_csv(data / "shape_spectrum.csv", index=False)
    kind.to_csv(data / "kind_spectrum.csv", index=False)
    phase.to_csv(data / "phase_scan.csv", index=False)

    plot_hex_heat(heat, "heat", "Free-energy constrained path heatmap", fig / "free_energy_path_heatmap.png")
    plot_hex_heat(heat, "signed", "Signed free-energy path heatmap", fig / "signed_path_heatmap.png")
    plot_pair_landscape(events, fig / "free_energy_pair_landscape.png")
    plot_layers(layers, fig / "free_energy_over_ply.png")
    plot_shape_spectrum(shape, fig / "shape_spectrum.png")
    plot_kind_spectrum(kind, fig / "rail_bridge_kind_spectrum.png")
    plot_phase(phase, fig / "phase_diagram_terminal_events.png")

    metrics["parameters"] = vars(args)
    metrics["phase_best_terminal"] = phase.sort_values(["terminal_events","mean_line_order"], ascending=False).head(8).to_dict(orient="records")
    metrics["phase_low_energy"] = phase.sort_values(["mean_G","terminal_events"], ascending=[True, False]).head(8).to_dict(orient="records")
    metrics["conjecture"] = {
        "name": "Free-energy crystallisation conjecture",
        "statement": (
            "Optimal-looking Hex Connect-6 search can be constrained by an expected free energy "
            "that trades tactical pressure against complexity/surprise while rewarding crystalline "
            "line order. Under this constraint, tactical play should not diffuse across the reservoir: "
            "it should crystallise into a small D6 quotient spectrum of rails, bridges, and kinks, "
            "with adaptive depth spent only where policy entropy or proto-pressure remains high."
        )
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = """# Hex Connect-6 free-energy crystal search

This package tests a free-energy/crystal constraint for adaptive Hex Connect-6 search.

Core free energy:

    G(move) = complexity/surprise - tactical_value - crystal_coherence

where tactical_value includes exact/proto obligation-hypergraph pressure, and crystal
coherence includes line-order and low-frequency axial structure-factor gains.

Key figures:
- free_energy_path_heatmap.png
- free_energy_pair_landscape.png
- free_energy_over_ply.png
- crystal_order_over_ply.png
- pressure_emergence_over_ply.png
- shape_spectrum.png
- rail_bridge_kind_spectrum.png
- phase_diagram_terminal_events.png
- phase_diagram_line_order.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_free_energy_crystals.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
