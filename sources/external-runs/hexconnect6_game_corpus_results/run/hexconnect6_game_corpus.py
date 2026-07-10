#!/usr/bin/env python3
"""
hexconnect6_game_corpus.py

Generate and analyse a corpus of finite-window games for infinite Hex Connect-6 using a
free-energy / hypergraph-pressure heuristic.

The engine:
  - Black opens with one stone at the origin.
  - Thereafter each player places two stones.
  - Candidate move-pairs are scored by expected free energy:
        G = complexity/surprise - tactical_value - crystal_coherence - block_value
  - tactical_value uses exact/proto obligation-hypergraph pressure.
  - crystal_coherence uses line order and a small axial structure-factor proxy.
  - Moves are sampled from a softmax over -G, giving a corpus rather than one line.

The analysis:
  - game outcomes, lengths, hazard curve
  - pressure/free-energy/line-order trajectories
  - D6 quotient pair-shape spectrum
  - rail/bridge/kink phase spectrum
  - shape transition matrix
  - opening pair-shape vs winner/length
  - cell occupation heatmap
  - branchial PCA of game trajectories
  - terminal motifs

Run:
  python hexconnect6_game_corpus.py --out corpus_out --games 120 --radius 7 --max-plies 28
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


def immediate_win_if_placed(board: Board, cell: Cell, player: int) -> bool:
    return any(count_run(board, cell, d, player)[0] >= 6 for d in DIRS)


def has_win(board: Board, player: int, segments: Sequence[Tuple[Cell, ...]]) -> bool:
    for seg in segments:
        if all(board.get(c, 0) == player for c in seg):
            return True
    return False


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


def obligation_stats(board: Board, player: int, segments):
    exact, proto, terminal = obligations(board, player, segments)
    tau_exact = hitting_number(exact)
    tau_proto = hitting_number(proto)
    pressure_exact = max(0, tau_exact - 2)
    pressure_proto = max(0, tau_proto - 2)
    verts = set(c for e in exact + proto for c in e)
    return dict(
        exact=exact, proto=proto, terminal=terminal,
        tau_exact=tau_exact, tau_proto=tau_proto,
        pressure_exact=pressure_exact, pressure_proto=pressure_proto,
        terminal_count=len(terminal), exact_count=len(exact), proto_count=len(proto),
        vertex_count=len(verts),
    )


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
        hist[min(radius, hex_dist(c))] += 1
    p = hist / hist.sum()
    p = p[p > 0]
    return float(-(p * np.log(p)).sum())


def structure_factor(board: Board, player: int, radius: int) -> float:
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


def heuristic_pair_value(board: Board, move: Tuple[Cell, Cell], player: int) -> float:
    nb = make_move(board, move, player)
    v = 0.0
    for c in move:
        for d in DIRS:
            mine, _ = count_run(nb, c, d, player)
            theirs, _ = count_run(board, c, d, -player)
            v += mine * mine + (8 if theirs >= 5 else 3 if theirs >= 4 else 1 if theirs >= 3 else 0)
    v += max(0, 6 - hex_dist(move[0], move[1])) * 0.25
    return float(v)


def candidate_moves(board: Board, cells: Sequence[Cell], player: int, candidate_radius: int, max_spread: int, prefilter: int):
    empty = [c for c in cells if c not in board and hex_dist(c) <= candidate_radius]
    arr = []
    for i, a in enumerate(empty):
        for b in empty[i + 1:]:
            if hex_dist(a, b) <= max_spread:
                arr.append((heuristic_pair_value(board, (a, b), player), a, b))
    arr.sort(reverse=True, key=lambda x: x[0])
    return [(a, b, h) for h, a, b in arr[:prefilter]]


def move_features(board: Board, move: Tuple[Cell, Cell], player: int, segments, radius: int, params: dict, heuristic=None):
    heuristic = heuristic_pair_value(board, move, player) if heuristic is None else heuristic
    before_own = obligation_stats(board, player, segments)
    before_opp = obligation_stats(board, -player, segments)
    nb = make_move(board, move, player)
    after_own = obligation_stats(nb, player, segments)
    after_opp = obligation_stats(nb, -player, segments)

    shape = canonical_delta((move[1][0] - move[0][0], move[1][1] - move[0][1]))
    kind = pair_shape_kind(shape)

    order_before = line_order(board, player)
    order_after = line_order(nb, player)
    sf_before = structure_factor(board, player, radius)
    sf_after = structure_factor(nb, player, radius)
    re_after = radial_entropy(nb, player, radius)

    spread = hex_dist(move[0], move[1])
    center = ((move[0][0] + move[1][0]) / 2, (move[0][1] + move[1][1]) / 2)
    center_dist = max(abs(center[0]), abs(center[1]), abs(center[0] + center[1]))

    tactical_value = (
        params["terminal_weight"] * min(1, after_own["terminal_count"])
        + params["exact_weight"] * after_own["pressure_exact"]
        + 0.55 * params["exact_weight"] * after_own["tau_exact"]
        + params["proto_weight"] * after_own["pressure_proto"]
        + 0.35 * params["proto_weight"] * after_own["tau_proto"]
        + 0.08 * after_own["proto_count"]
        + 0.02 * heuristic
    )

    # Defensive value: how much opponent pressure is reduced.
    block_value = (
        params["block_weight"] * max(0, before_opp["pressure_exact"] - after_opp["pressure_exact"])
        + 0.55 * params["block_weight"] * max(0, before_opp["pressure_proto"] - after_opp["pressure_proto"])
        + 0.04 * max(0, before_opp["proto_count"] - after_opp["proto_count"])
    )

    crystal_gain = (order_after - order_before) + 0.65 * (sf_after - sf_before)
    shape_complexity = {
        "short_rail": 0.15,
        "long_rail": 0.42,
        "bridge_rail": 0.75,
        "compact_kink": 0.32,
        "bridge": 0.55,
        "long_bridge": 0.9,
    }[kind]
    surprise = shape_complexity + 0.08 * spread + 0.035 * center_dist + 0.15 * re_after
    G = params["complexity_weight"] * surprise - tactical_value - params["crystal_weight"] * crystal_gain - block_value

    return dict(
        board=nb, move=move, shape=shape, kind=kind, heuristic=heuristic,
        G=float(G), surprise=float(surprise), tactical_value=float(tactical_value),
        block_value=float(block_value), crystal_gain=float(crystal_gain),
        line_order=float(order_after), structure_factor=float(sf_after), radial_entropy=float(re_after),
        spread=spread, center_dist=float(center_dist),
        own_tau_exact=after_own["tau_exact"], own_tau_proto=after_own["tau_proto"],
        own_pressure_exact=after_own["pressure_exact"], own_pressure_proto=after_own["pressure_proto"],
        own_exact_count=after_own["exact_count"], own_proto_count=after_own["proto_count"],
        opp_tau_exact=after_opp["tau_exact"], opp_tau_proto=after_opp["tau_proto"],
        opp_pressure_exact=after_opp["pressure_exact"], opp_pressure_proto=after_opp["pressure_proto"],
        terminal_count=after_own["terminal_count"],
    )


def softmax_from_G(evals: List[dict], temperature: float, rng: np.random.Generator, top_k: int):
    if not evals:
        return None, np.array([])
    evals = sorted(evals, key=lambda e: e["G"])[:top_k]
    G = np.array([e["G"] for e in evals], dtype=float)
    logits = -(G - G.min()) / max(1e-6, temperature)
    logits = np.clip(logits, -60, 60)
    p = np.exp(logits)
    p /= p.sum()
    idx = rng.choice(len(evals), p=p)
    return evals[int(idx)], p


def entropy(p):
    p = np.asarray(p, dtype=float)
    p = p[p > 1e-12]
    return float(-(p * np.log(p)).sum()) if p.size else 0.0


def sample_params(rng: np.random.Generator, args):
    # Corpus deliberately samples a small rule manifold.
    return dict(
        temperature=float(rng.uniform(args.temp_min, args.temp_max)),
        complexity_weight=float(rng.uniform(0.35, 1.9)),
        crystal_weight=float(rng.uniform(0.0, 1.6)),
        terminal_weight=float(rng.uniform(7.0, 11.0)),
        exact_weight=float(rng.uniform(3.6, 5.8)),
        proto_weight=float(rng.uniform(0.8, 2.1)),
        block_weight=float(rng.uniform(1.4, 3.6)),
    )


def play_game(game_id: int, rng: np.random.Generator, args, cells, segments):
    params = sample_params(rng, args)
    board: Board = {(0, 0): 1}
    moves = []
    winner = 0
    terminal_ply = None

    for ply in range(1, args.max_plies + 1):
        player = -1 if ply % 2 == 1 else 1  # W first pair, then B, W, ...
        raw = candidate_moves(board, cells, player, args.candidate_radius, args.max_spread, args.prefilter)
        evals = [move_features(board, (a, b), player, segments, args.radius, params, h) for a, b, h in raw]
        chosen, probs = softmax_from_G(evals, params["temperature"], rng, args.top_k)
        if chosen is None:
            break
        board = chosen["board"]

        if has_win(board, player, segments):
            winner = player
            terminal_ply = ply

        move_row = dict(
            game_id=game_id, ply=ply, player=player,
            a_q=chosen["move"][0][0], a_r=chosen["move"][0][1],
            b_q=chosen["move"][1][0], b_r=chosen["move"][1][1],
            shape=str(chosen["shape"]), kind=chosen["kind"],
            G=chosen["G"], surprise=chosen["surprise"], tactical_value=chosen["tactical_value"],
            block_value=chosen["block_value"], crystal_gain=chosen["crystal_gain"],
            line_order=chosen["line_order"], structure_factor=chosen["structure_factor"],
            radial_entropy=chosen["radial_entropy"], spread=chosen["spread"],
            own_tau_exact=chosen["own_tau_exact"], own_tau_proto=chosen["own_tau_proto"],
            own_pressure_exact=chosen["own_pressure_exact"], own_pressure_proto=chosen["own_pressure_proto"],
            own_exact_count=chosen["own_exact_count"], own_proto_count=chosen["own_proto_count"],
            opp_pressure_exact=chosen["opp_pressure_exact"], opp_pressure_proto=chosen["opp_pressure_proto"],
            terminal_count=chosen["terminal_count"], policy_entropy=entropy(probs),
            winner_so_far=winner,
        )
        moves.append(move_row)

        if winner:
            break

    # Summary features.
    game_len = len(moves)
    black_stones = len(stones(board, 1))
    white_stones = len(stones(board, -1))
    final_stats_black = obligation_stats(board, 1, segments)
    final_stats_white = obligation_stats(board, -1, segments)

    summary = dict(
        game_id=game_id, winner=winner, terminal_ply=terminal_ply if terminal_ply is not None else -1,
        plies=game_len, black_stones=black_stones, white_stones=white_stones,
        final_black_line_order=line_order(board, 1), final_white_line_order=line_order(board, -1),
        final_black_structure=structure_factor(board, 1, args.radius),
        final_white_structure=structure_factor(board, -1, args.radius),
        final_black_proto=final_stats_black["pressure_proto"], final_white_proto=final_stats_white["pressure_proto"],
        final_black_exact=final_stats_black["pressure_exact"], final_white_exact=final_stats_white["pressure_exact"],
        **{f"param_{k}": v for k, v in params.items()},
    )
    return summary, moves, board


def corpus(args):
    rng = np.random.default_rng(args.seed)
    cells = cells_in_radius(args.radius)
    segments = all_segments(args.radius, pad=2)
    summaries, moves, final_boards = [], [], []
    for gid in range(args.games):
        summary, game_moves, board = play_game(gid, rng, args, cells, segments)
        summaries.append(summary)
        moves.extend(game_moves)
        for (q, r), v in board.items():
            x, y = axial_to_xy((q, r))
            final_boards.append(dict(game_id=gid, q=q, r=r, x=x, y=y, value=v, radius=hex_dist((q, r))))
    return pd.DataFrame(summaries), pd.DataFrame(moves), pd.DataFrame(final_boards)


def pca2(X):
    X = np.asarray(X, dtype=float)
    if X.shape[0] == 0:
        return np.zeros((0, 2))
    X = X - X.mean(axis=0, keepdims=True)
    if X.shape[0] == 1:
        return np.zeros((1, 2))
    _, _, Vt = np.linalg.svd(X, full_matrices=False)
    if Vt.shape[0] == 1:
        return np.column_stack([X @ Vt[0], np.zeros(X.shape[0])])
    return X @ Vt[:2].T


def game_features(summaries, moves):
    rows = []
    for gid, g in moves.groupby("game_id"):
        kind_counts = g["kind"].value_counts(normalize=True).to_dict()
        shape_counts = g["shape"].value_counts(normalize=True).head(8).to_dict()
        first = g.iloc[0]
        last = g.iloc[-1]
        rows.append(dict(
            game_id=gid,
            mean_G=g["G"].mean(), min_G=g["G"].min(),
            mean_policy_entropy=g["policy_entropy"].mean(),
            mean_line_order=g["line_order"].mean(), max_line_order=g["line_order"].max(),
            mean_structure_factor=g["structure_factor"].mean(),
            mean_proto_pressure=g["own_pressure_proto"].mean(),
            max_proto_pressure=g["own_pressure_proto"].max(),
            mean_exact_pressure=g["own_pressure_exact"].mean(),
            max_exact_pressure=g["own_pressure_exact"].max(),
            terminal_count=g["terminal_count"].sum(),
            opening_shape=first["shape"], opening_kind=first["kind"],
            final_shape=last["shape"], final_kind=last["kind"],
            short_rail_frac=kind_counts.get("short_rail", 0.0),
            long_rail_frac=kind_counts.get("long_rail", 0.0),
            bridge_frac=kind_counts.get("bridge", 0.0) + kind_counts.get("long_bridge", 0.0) + kind_counts.get("bridge_rail", 0.0),
            compact_kink_frac=kind_counts.get("compact_kink", 0.0),
            top_shape=next(iter(shape_counts.keys())) if shape_counts else "",
        ))
    feat = pd.DataFrame(rows)
    return summaries.merge(feat, on="game_id", how="left")


def transition_matrix(moves):
    rows = []
    for gid, g in moves.sort_values(["game_id", "ply"]).groupby("game_id"):
        shapes = g["shape"].tolist()
        kinds = g["kind"].tolist()
        for a, b in zip(shapes, shapes[1:]):
            rows.append(dict(game_id=gid, from_shape=a, to_shape=b, type="shape"))
        for a, b in zip(kinds, kinds[1:]):
            rows.append(dict(game_id=gid, from_shape=a, to_shape=b, type="kind"))
    return pd.DataFrame(rows)


def plot_outcomes(summaries, path):
    plt.figure(figsize=(6.5, 4.5))
    counts = summaries["winner"].map({1: "Black", -1: "White", 0: "Draw/window"}).value_counts()
    plt.bar(counts.index, counts.values)
    plt.ylabel("games")
    plt.title("Corpus outcomes")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_lengths(summaries, path):
    plt.figure(figsize=(7, 4.8))
    plt.hist(summaries["plies"], bins=range(1, int(summaries["plies"].max()) + 3))
    plt.xlabel("plies after Black singleton")
    plt.ylabel("games")
    plt.title("Game length distribution")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()


def plot_hazard(moves, summaries, path):
    max_ply = int(max(moves["ply"].max(), summaries["plies"].max()))
    rows = []
    for ply in range(1, max_ply + 1):
        alive = int((summaries["plies"] >= ply).sum())
        ended = int(((summaries["terminal_ply"] == ply) & (summaries["winner"] != 0)).sum())
        rows.append(dict(ply=ply, alive=alive, ended=ended, hazard=ended / alive if alive else 0))
    df = pd.DataFrame(rows)
    plt.figure(figsize=(7, 4.8))
    plt.plot(df["ply"], df["hazard"], marker="o")
    plt.xlabel("ply")
    plt.ylabel("terminal hazard")
    plt.title("Estimated terminal hazard over ply")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return df


def plot_trajectory_means(moves, path):
    g = moves.groupby("ply", as_index=False).agg(
        G=("G", "mean"),
        policy_entropy=("policy_entropy", "mean"),
        proto=("own_pressure_proto", "mean"),
        exact=("own_pressure_exact", "mean"),
        line_order=("line_order", "mean"),
        structure=("structure_factor", "mean"),
    )
    plt.figure(figsize=(8, 5))
    plt.plot(g["ply"], g["G"], marker="o", label="free energy G")
    plt.plot(g["ply"], -g["policy_entropy"], marker="o", label="-policy entropy")
    plt.xlabel("ply")
    plt.ylabel("value")
    plt.title("Mean free energy and policy concentration")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.plot(g["ply"], g["proto"], marker="o", label="proto pressure")
    plt.plot(g["ply"], g["exact"], marker="o", label="exact pressure")
    plt.plot(g["ply"], g["line_order"], marker="o", label="line order")
    plt.plot(g["ply"], g["structure"], marker="o", label="structure factor")
    plt.xlabel("ply")
    plt.ylabel("mean")
    plt.title("Pressure and crystal order over game time")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path.with_name("pressure_crystal_over_ply.png"), dpi=190)
    plt.close()
    return g


def plot_shape_spectrum(moves, path):
    spec = moves.groupby("shape", as_index=False).agg(
        count=("shape", "size"),
        mean_G=("G", "mean"),
        win_terminal=("terminal_count", "sum"),
        proto=("own_pressure_proto", "mean"),
        exact=("own_pressure_exact", "mean"),
    ).sort_values(["count", "win_terminal"], ascending=False)
    top = spec.head(20)
    plt.figure(figsize=(8.5, 4.8))
    x = np.arange(len(top))
    plt.bar(x, top["count"])
    plt.xticks(x, top["shape"], rotation=45, ha="right")
    plt.ylabel("move count")
    plt.title("D6 quotient pair-shape spectrum in generated games")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return spec


def plot_kind_spectrum(moves, path):
    spec = moves.groupby("kind", as_index=False).agg(count=("kind", "size"), terminal=("terminal_count", "sum")).sort_values("count", ascending=False)
    plt.figure(figsize=(7, 4.8))
    x = np.arange(len(spec))
    plt.bar(x, spec["count"])
    plt.xticks(x, spec["kind"], rotation=30, ha="right")
    plt.ylabel("move count")
    plt.title("Rail / bridge / kink spectrum")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return spec


def plot_transition(trans, path, mode="shape", top_n=16):
    t = trans[trans["type"] == mode]
    if t.empty:
        return pd.DataFrame()
    counts = t.groupby(["from_shape", "to_shape"], as_index=False).size().rename(columns={"size": "count"})
    popular = pd.concat([counts.groupby("from_shape")["count"].sum(), counts.groupby("to_shape")["count"].sum()]).groupby(level=0).sum().sort_values(ascending=False).head(top_n).index.tolist()
    counts = counts[counts["from_shape"].isin(popular) & counts["to_shape"].isin(popular)]
    idx = {s: i for i, s in enumerate(popular)}
    M = np.zeros((len(popular), len(popular)))
    for _, row in counts.iterrows():
        M[idx[row["from_shape"]], idx[row["to_shape"]]] += row["count"]
    row_sums = M.sum(axis=1, keepdims=True)
    P = np.divide(M, row_sums, out=np.zeros_like(M), where=row_sums > 0)
    plt.figure(figsize=(8, 7))
    plt.imshow(P)
    plt.xticks(np.arange(len(popular)), popular, rotation=90)
    plt.yticks(np.arange(len(popular)), popular)
    plt.xlabel("next")
    plt.ylabel("previous")
    plt.title(f"{mode} transition matrix")
    plt.colorbar(label="transition probability")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return counts.sort_values("count", ascending=False)


def plot_cell_heat(final_boards, moves, path):
    # final occupation heat
    heat = final_boards.groupby(["q", "r", "x", "y"], as_index=False).agg(occupation=("value", "count"), signed=("value", "sum"))
    plt.figure(figsize=(7, 6))
    plt.scatter(heat["x"], heat["y"], c=heat["occupation"], marker="h", s=270)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.title("Final occupation heatmap across corpus")
    plt.colorbar(label="occupation")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()

    # move heat weighted by low free energy
    rows = []
    for _, r in moves.iterrows():
        for q, rr in [(r.a_q, r.a_r), (r.b_q, r.b_r)]:
            x, y = axial_to_xy((q, rr))
            rows.append(dict(q=q, r=rr, x=x, y=y, weight=math.exp(-0.08 * r.G)))
    mh = pd.DataFrame(rows).groupby(["q", "r", "x", "y"], as_index=False)["weight"].sum()
    plt.figure(figsize=(7, 6))
    plt.scatter(mh["x"], mh["y"], c=mh["weight"], marker="h", s=270)
    plt.gca().set_aspect("equal", adjustable="box")
    plt.xlabel("Eisenstein x")
    plt.ylabel("Eisenstein y")
    plt.title("Move heatmap weighted by low free energy")
    plt.colorbar(label="exp(-0.08G) mass")
    plt.tight_layout()
    plt.savefig(path.with_name("low_free_energy_move_heatmap.png"), dpi=190)
    plt.close()
    return heat, mh


def plot_branchial_games(features, path):
    cols = [
        "plies", "mean_G", "min_G", "mean_policy_entropy", "mean_line_order", "max_line_order",
        "mean_structure_factor", "mean_proto_pressure", "max_proto_pressure", "mean_exact_pressure",
        "max_exact_pressure", "short_rail_frac", "long_rail_frac", "bridge_frac", "compact_kink_frac",
    ]
    X = features[cols].fillna(0).to_numpy(float)
    coords = pca2(X)
    out = features[["game_id", "winner", "plies"]].copy()
    out["pc1"] = coords[:, 0]
    out["pc2"] = coords[:, 1]
    plt.figure(figsize=(7, 6))
    plt.scatter(out["pc1"], out["pc2"], c=out["winner"], s=25 + 2 * out["plies"])
    plt.xlabel("game PC1")
    plt.ylabel("game PC2")
    plt.title("Branchial corpus map: games embedded by trajectory features")
    plt.colorbar(label="winner")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return out


def plot_opening_effects(features, path):
    g = features.groupby("opening_shape", as_index=False).agg(
        games=("game_id", "size"),
        black_win=("winner", lambda x: np.mean(np.array(x) == 1)),
        white_win=("winner", lambda x: np.mean(np.array(x) == -1)),
        mean_len=("plies", "mean"),
        mean_G=("mean_G", "mean"),
    ).sort_values("games", ascending=False).head(18)
    plt.figure(figsize=(8.5, 4.8))
    x = np.arange(len(g))
    plt.bar(x, g["black_win"])
    plt.xticks(x, g["opening_shape"], rotation=45, ha="right")
    plt.ylabel("Black win rate")
    plt.title("Opening shape vs Black win rate in generated corpus")
    plt.tight_layout()
    plt.savefig(path, dpi=190)
    plt.close()
    return g


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="hexconnect6_game_corpus_out")
    p.add_argument("--games", type=int, default=120)
    p.add_argument("--radius", type=int, default=7)
    p.add_argument("--candidate-radius", type=int, default=5)
    p.add_argument("--max-spread", type=int, default=7)
    p.add_argument("--max-plies", type=int, default=28)
    p.add_argument("--prefilter", type=int, default=26)
    p.add_argument("--top-k", type=int, default=6)
    p.add_argument("--temp-min", type=float, default=0.25)
    p.add_argument("--temp-max", type=float, default=1.15)
    p.add_argument("--seed", type=int, default=260510)
    args = p.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    fig.mkdir(parents=True, exist_ok=True)
    data.mkdir(parents=True, exist_ok=True)

    summaries, moves, final_boards = corpus(args)
    features = game_features(summaries, moves)
    trans = transition_matrix(moves)

    summaries.to_csv(data / "game_summaries.csv", index=False)
    moves.to_csv(data / "move_records.csv", index=False)
    final_boards.to_csv(data / "final_boards.csv", index=False)
    features.to_csv(data / "game_features.csv", index=False)
    trans.to_csv(data / "transitions.csv", index=False)

    hazard = plot_hazard(moves, summaries, fig / "terminal_hazard.png")
    hazard.to_csv(data / "terminal_hazard.csv", index=False)
    trajectory = plot_trajectory_means(moves, fig / "free_energy_entropy_over_ply.png")
    trajectory.to_csv(data / "trajectory_means.csv", index=False)
    shape_spec = plot_shape_spectrum(moves, fig / "shape_spectrum.png")
    shape_spec.to_csv(data / "shape_spectrum.csv", index=False)
    kind_spec = plot_kind_spectrum(moves, fig / "kind_spectrum.png")
    kind_spec.to_csv(data / "kind_spectrum.csv", index=False)
    shape_trans = plot_transition(trans, fig / "shape_transition_matrix.png", mode="shape")
    shape_trans.to_csv(data / "shape_transition_counts.csv", index=False)
    kind_trans = plot_transition(trans, fig / "kind_transition_matrix.png", mode="kind", top_n=8)
    kind_trans.to_csv(data / "kind_transition_counts.csv", index=False)
    final_heat, move_heat = plot_cell_heat(final_boards, moves, fig / "final_occupation_heatmap.png")
    final_heat.to_csv(data / "final_occupation_heatmap.csv", index=False)
    move_heat.to_csv(data / "move_heatmap.csv", index=False)
    branchial = plot_branchial_games(features, fig / "game_branchial_map.png")
    branchial.to_csv(data / "game_branchial_coordinates.csv", index=False)
    opening = plot_opening_effects(features, fig / "opening_shape_winrate.png")
    opening.to_csv(data / "opening_shape_effects.csv", index=False)
    plot_outcomes(summaries, fig / "outcomes.png")
    plot_lengths(summaries, fig / "game_lengths.png")

    # Additional summary analyses.
    winner_counts = summaries["winner"].value_counts().to_dict()
    terminal_rate = float((summaries["winner"] != 0).mean())
    black_win_rate = float((summaries["winner"] == 1).mean())
    white_win_rate = float((summaries["winner"] == -1).mean())
    mean_len = float(summaries["plies"].mean())

    # Rail-to-bridge event: first bridge after short rails.
    rail_bridge_rows = []
    for gid, g in moves.sort_values(["game_id", "ply"]).groupby("game_id"):
        seen_rail = False
        bridge_ply = None
        for _, r in g.iterrows():
            if r.kind == "short_rail":
                seen_rail = True
            if seen_rail and r.kind in ("bridge", "long_bridge", "bridge_rail"):
                bridge_ply = int(r.ply)
                break
        rail_bridge_rows.append(dict(game_id=gid, bridge_after_rail_ply=-1 if bridge_ply is None else bridge_ply))
    rail_bridge = pd.DataFrame(rail_bridge_rows)
    rail_bridge.to_csv(data / "rail_to_bridge_times.csv", index=False)

    # Correlations: parameters vs outcomes.
    param_cols = [c for c in summaries.columns if c.startswith("param_")]
    corr_rows = []
    for c in param_cols:
        corr_rows.append(dict(
            parameter=c,
            corr_black_win=float(np.corrcoef(summaries[c], (summaries["winner"] == 1).astype(float))[0, 1]) if summaries[c].std() else 0.0,
            corr_length=float(np.corrcoef(summaries[c], summaries["plies"])[0, 1]) if summaries[c].std() else 0.0,
        ))
    param_corr = pd.DataFrame(corr_rows).sort_values("corr_black_win", ascending=False)
    param_corr.to_csv(data / "parameter_correlations.csv", index=False)

    metrics = {
        "parameters": vars(args),
        "games": int(len(summaries)),
        "moves": int(len(moves)),
        "winner_counts": {str(k): int(v) for k, v in winner_counts.items()},
        "terminal_rate": terminal_rate,
        "black_win_rate": black_win_rate,
        "white_win_rate": white_win_rate,
        "mean_length": mean_len,
        "median_length": float(summaries["plies"].median()),
        "mean_policy_entropy": float(moves["policy_entropy"].mean()),
        "mean_G": float(moves["G"].mean()),
        "min_G": float(moves["G"].min()),
        "max_proto_pressure": int(moves["own_pressure_proto"].max()),
        "max_exact_pressure": int(moves["own_pressure_exact"].max()),
        "top_shapes": shape_spec.head(10).to_dict(orient="records"),
        "top_kinds": kind_spec.to_dict(orient="records"),
        "opening_effects": opening.head(10).to_dict(orient="records"),
        "parameter_correlations": param_corr.to_dict(orient="records"),
        "rail_to_bridge_rate": float((rail_bridge["bridge_after_rail_ply"] > 0).mean()),
        "mean_rail_to_bridge_ply": float(rail_bridge.loc[rail_bridge["bridge_after_rail_ply"] > 0, "bridge_after_rail_ply"].mean()) if (rail_bridge["bridge_after_rail_ply"] > 0).any() else None,
        "conjecture_reading": (
            "The corpus tests whether free-energy play crystallises into rail motifs, "
            "then sometimes transitions into bridge motifs before terminal pressure. "
            "Strong support would look like high rail mass, low policy entropy before terminal plies, "
            "a structured shape transition matrix, and consistent opening-shape effects."
        ),
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = """# Hex Connect-6 game corpus

This package contains a generated corpus of finite-window games using a free-energy /
hypergraph-pressure heuristic.

Key CSVs:
- game_summaries.csv
- move_records.csv
- game_features.csv
- transitions.csv
- shape_spectrum.csv
- kind_spectrum.csv
- opening_shape_effects.csv
- parameter_correlations.csv

Key figures:
- outcomes.png
- game_lengths.png
- terminal_hazard.png
- free_energy_entropy_over_ply.png
- pressure_crystal_over_ply.png
- shape_spectrum.png
- kind_spectrum.png
- shape_transition_matrix.png
- kind_transition_matrix.png
- final_occupation_heatmap.png
- low_free_energy_move_heatmap.png
- game_branchial_map.png
- opening_shape_winrate.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for pth in out.rglob("*"):
            z.write(pth, pth.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_game_corpus.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
