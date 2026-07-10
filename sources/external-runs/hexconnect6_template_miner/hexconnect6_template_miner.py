"""Hex Connect-6 primitive forcing template miner.

The central statistic is the transversal number of the urgent obligation
hypergraph induced by a candidate two-stone move.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Set, Tuple


Cell = Tuple[int, int]
Edge = Tuple[Cell, ...]
Board = Dict[Cell, int]

ATTACKER = 1
DEFENDER = -1
WIN_LEN = 6

DIRECTIONS6: Tuple[Cell, ...] = (
    (1, 0),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (0, -1),
    (1, -1),
)
SEGMENT_AXES: Tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))


class Evaluation(NamedTuple):
    exact_edges: Tuple[Edge, ...]
    proto_only_edges: Tuple[Edge, ...]
    proto_edges: Tuple[Edge, ...]
    terminal_segments: Tuple[Tuple[Cell, ...], ...]
    exact_source_segments: Tuple[Tuple[Cell, ...], ...]
    proto_source_segments: Tuple[Tuple[Cell, ...], ...]
    tau_exact: int
    tau_proto: int
    pressure_exact: int
    pressure_proto: int


class Template(NamedTuple):
    template_id: str
    source_event_id: str
    kind: str
    attacker: Tuple[Cell, ...]
    defender: Tuple[Cell, ...]
    move: Tuple[Cell, Cell]
    obligations: Tuple[Edge, ...]
    tau: int
    pressure: int
    terminal: bool
    source_type: str
    pair_shape: Cell


def add(a: Cell, b: Cell) -> Cell:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Cell, b: Cell) -> Cell:
    return (a[0] - b[0], a[1] - b[1])


def mul(k: int, a: Cell) -> Cell:
    return (k * a[0], k * a[1])


def neg(a: Cell) -> Cell:
    return (-a[0], -a[1])


def hex_dist(a: Cell, b: Cell = (0, 0)) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def axial_to_xy(c: Cell) -> Tuple[float, float]:
    q, r = c
    return (q + 0.5 * r, (math.sqrt(3.0) / 2.0) * r)


def cells_in_radius(radius: int) -> List[Cell]:
    cells: List[Cell] = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            c = (q, r)
            if hex_dist(c) <= radius:
                cells.append(c)
    return sorted(cells)


def rotate60(c: Cell, n: int = 1) -> Cell:
    q, r = c
    for _ in range(n % 6):
        q, r = -r, q + r
    return (q, r)


def reflect_axial(c: Cell) -> Cell:
    q, r = c
    return (q + r, -r)


def transform_cell(c: Cell, rot: int = 0, reflect: bool = False) -> Cell:
    out = reflect_axial(c) if reflect else c
    return rotate60(out, rot)


def d6_images(c: Cell) -> List[Cell]:
    return [transform_cell(c, rot, refl) for refl in (False, True) for rot in range(6)]


def translate_cells(cells: Iterable[Cell], delta: Cell) -> Tuple[Cell, ...]:
    return tuple(sorted(add(c, delta) for c in cells))


def normalise_translated(cells: Iterable[Cell]) -> Tuple[Cell, ...]:
    cells_tuple = tuple(sorted(cells))
    if not cells_tuple:
        return tuple()
    anchor = min(cells_tuple)
    return translate_cells(cells_tuple, neg(anchor))


def canonical_pair_shape(move: Tuple[Cell, Cell]) -> Cell:
    a, b = move
    delta = sub(b, a)
    candidates = d6_images(delta) + d6_images(neg(delta))
    return min(candidates)


def all_segments(radius: int, pad: int = 2) -> List[Tuple[Cell, ...]]:
    window = radius + pad
    segments: Set[Tuple[Cell, ...]] = set()
    for start in cells_in_radius(window):
        for axis in SEGMENT_AXES:
            seg = tuple(add(start, mul(k, axis)) for k in range(WIN_LEN))
            if all(hex_dist(c) <= window for c in seg):
                segments.add(seg)
    return sorted(segments)


_SEGMENT_CACHE: Dict[Tuple[int, int], List[Tuple[Cell, ...]]] = {}


def cached_segments(radius: int, pad: int = 2) -> List[Tuple[Cell, ...]]:
    key = (radius, pad)
    if key not in _SEGMENT_CACHE:
        _SEGMENT_CACHE[key] = all_segments(radius, pad=pad)
    return _SEGMENT_CACHE[key]


def normalise_edges(edges: Iterable[Iterable[Cell]]) -> Tuple[Edge, ...]:
    unique = sorted(
        {tuple(sorted(edge)) for edge in edges if tuple(edge)},
        key=lambda e: (len(e), e),
    )
    minimal: List[Edge] = []
    minimal_sets: List[Set[Cell]] = []
    for edge in unique:
        edge_set = set(edge)
        if any(existing.issubset(edge_set) for existing in minimal_sets):
            continue
        minimal.append(edge)
        minimal_sets.append(edge_set)
    return tuple(sorted(minimal, key=lambda e: (len(e), e)))


def hitting_number(edges: Sequence[Edge], max_k: Optional[int] = None) -> int:
    """Return the minimum number of vertices hitting every hyperedge."""
    normalised = normalise_edges(edges)
    if not normalised:
        return 0

    memo: Dict[Tuple[Edge, ...], int] = {}

    def solve(remaining: Tuple[Edge, ...]) -> int:
        remaining = normalise_edges(remaining)
        if not remaining:
            return 0
        if remaining in memo:
            return memo[remaining]

        forced = tuple(edge[0] for edge in remaining if len(edge) == 1)
        if forced:
            forced_set = set(forced)
            next_remaining = tuple(
                edge for edge in remaining if not any(v in forced_set for v in edge)
            )
            value = len(forced_set) + solve(next_remaining)
            memo[remaining] = value
            return value

        branch_edge = min(remaining, key=lambda edge: (len(edge), edge))
        best = len({v for edge in remaining for v in edge})
        if max_k is not None:
            best = min(best, max_k + 1)
        for vertex in branch_edge:
            next_remaining = tuple(edge for edge in remaining if vertex not in edge)
            value = 1 + solve(next_remaining)
            if value < best:
                best = value
            if best == 1:
                break
        memo[remaining] = best
        return best

    return solve(normalised)


def critical_obligation_core(
    edges: Sequence[Edge],
    mode: str = "same-pressure",
    max_combo: int = 2,
) -> Tuple[Edge, ...]:
    target_edges = normalise_edges(edges)
    target_tau = hitting_number(target_edges)
    target_pressure = max(0, target_tau - 2)
    current = list(target_edges)

    def acceptable(candidate_edges: Sequence[Edge]) -> bool:
        tau = hitting_number(candidate_edges)
        pressure = max(0, tau - 2)
        if mode == "positive":
            return pressure > 0
        if mode == "same-tau":
            return tau == target_tau
        return pressure == target_pressure

    changed = True
    while changed:
        changed = False
        for edge in list(current):
            trial = list(current)
            trial.remove(edge)
            if acceptable(trial):
                current = trial
                changed = True
                break

    for combo_size in range(2, max_combo + 1):
        changed = True
        while changed:
            changed = False
            if len(current) < combo_size:
                break
            for combo in itertools.combinations(list(current), combo_size):
                trial = list(current)
                for edge in combo:
                    trial.remove(edge)
                if acceptable(trial):
                    current = trial
                    changed = True
                    break

    return normalise_edges(current)


def count_minimum_transversals(
    edges: Sequence[Edge],
    tau: int,
    cap: int = 100000,
    max_combinations: int = 200000,
) -> int:
    if tau < 0:
        return 0
    edges = normalise_edges(edges)
    if tau == 0:
        return 1 if not edges else 0
    vertices = sorted({v for edge in edges for v in edge})
    if len(vertices) > 28:
        return -1
    if math.comb(len(vertices), tau) > max_combinations:
        return -1
    count = 0
    for combo in itertools.combinations(vertices, tau):
        combo_set = set(combo)
        if all(any(v in combo_set for v in edge) for edge in edges):
            count += 1
            if count >= cap:
                return cap
    return count


def apply_move(board: Board, move: Tuple[Cell, Cell], player: int) -> Board:
    a, b = move
    if a == b:
        raise ValueError("Connect-6 two-stone moves must use two distinct cells")
    if a in board or b in board:
        raise ValueError("candidate move intersects an occupied cell")
    out = dict(board)
    out[a] = player
    out[b] = player
    return out


def extract_obligations(
    board: Board,
    player: int,
    segments: Sequence[Tuple[Cell, ...]],
    include_proto: bool = True,
) -> Evaluation:
    exact_raw: List[Edge] = []
    proto_raw: List[Edge] = []
    exact_sources: List[Tuple[Cell, ...]] = []
    proto_sources: List[Tuple[Cell, ...]] = []
    terminal_segments: List[Tuple[Cell, ...]] = []

    for segment in segments:
        values = [board.get(c, 0) for c in segment]
        if any(v == -player for v in values):
            continue
        attackers = sum(1 for v in values if v == player)
        empties = tuple(c for c, v in zip(segment, values) if v == 0)
        if attackers >= WIN_LEN:
            terminal_segments.append(segment)
        elif attackers == 5 and len(empties) == 1:
            exact_raw.append(empties)
            exact_sources.append(segment)
        elif attackers == 4 and len(empties) == 2:
            exact_raw.append(empties)
            exact_sources.append(segment)
        elif include_proto and attackers == 3 and len(empties) == 3:
            proto_raw.append(empties)
            proto_sources.append(segment)

    exact_edges = normalise_edges(exact_raw)
    proto_only_edges = normalise_edges(proto_raw)
    proto_edges = normalise_edges(tuple(exact_edges) + tuple(proto_only_edges))
    tau_exact = hitting_number(exact_edges)
    tau_proto = hitting_number(proto_edges)
    return Evaluation(
        exact_edges=exact_edges,
        proto_only_edges=proto_only_edges,
        proto_edges=proto_edges,
        terminal_segments=tuple(sorted(set(terminal_segments))),
        exact_source_segments=tuple(sorted(set(exact_sources))),
        proto_source_segments=tuple(sorted(set(proto_sources))),
        tau_exact=tau_exact,
        tau_proto=tau_proto,
        pressure_exact=max(0, tau_exact - 2),
        pressure_proto=max(0, tau_proto - 2),
    )


def evaluate_move(
    board: Board,
    move: Tuple[Cell, Cell],
    player: int,
    radius: int,
    include_proto: bool = True,
    segments: Optional[Sequence[Tuple[Cell, ...]]] = None,
) -> Evaluation:
    next_board = apply_move(board, move, player)
    if segments is None:
        segments = cached_segments(radius, pad=2)
    return extract_obligations(next_board, player, segments, include_proto=include_proto)


def transform_edge(edge: Edge, rot: int, reflect: bool) -> Edge:
    return tuple(sorted(transform_cell(c, rot, reflect) for c in edge))


def transform_template(template: Template, rot: int = 0, reflect: bool = False) -> Template:
    move = tuple(transform_cell(c, rot, reflect) for c in template.move)
    obligations = tuple(sorted(transform_edge(edge, rot, reflect) for edge in template.obligations))
    return Template(
        template_id=template.template_id,
        source_event_id=template.source_event_id,
        kind=template.kind,
        attacker=tuple(sorted(transform_cell(c, rot, reflect) for c in template.attacker)),
        defender=tuple(sorted(transform_cell(c, rot, reflect) for c in template.defender)),
        move=(move[0], move[1]),
        obligations=obligations,
        tau=template.tau,
        pressure=template.pressure,
        terminal=template.terminal,
        source_type=template.source_type,
        pair_shape=canonical_pair_shape((move[0], move[1])),
    )


def template_payload(template: Template) -> Tuple:
    occupied = set(template.attacker) | set(template.defender) | set(template.move)
    obligation_vertices = {v for edge in template.obligations for v in edge}
    all_cells = sorted(occupied | obligation_vertices)
    anchor = min(all_cells) if all_cells else (0, 0)
    delta = neg(anchor)

    def shift(c: Cell) -> Cell:
        return add(c, delta)

    shifted_edges = tuple(
        sorted(tuple(sorted(shift(v) for v in edge)) for edge in template.obligations)
    )
    return (
        template.kind,
        tuple(sorted(shift(c) for c in template.attacker)),
        tuple(sorted(shift(c) for c in template.defender)),
        tuple(sorted(shift(c) for c in template.move)),
        shifted_edges,
    )


def canonical_template_signature(template: Template) -> str:
    payloads = []
    for reflect in (False, True):
        for rot in range(6):
            payloads.append(template_payload(transform_template(template, rot=rot, reflect=reflect)))
    canonical = min(payloads)
    return hashlib.sha1(repr(canonical).encode("utf-8")).hexdigest()


def canonical_template_payload(template: Template) -> Tuple:
    payloads = []
    for reflect in (False, True):
        for rot in range(6):
            payloads.append(template_payload(transform_template(template, rot=rot, reflect=reflect)))
    return min(payloads)


def automorphism_count(template: Template) -> int:
    canonical = canonical_template_payload(template)
    count = 0
    for reflect in (False, True):
        for rot in range(6):
            if template_payload(transform_template(template, rot=rot, reflect=reflect)) == canonical:
                count += 1
    return count


def relative_board(attacker: Iterable[Cell], defender: Iterable[Cell]) -> Board:
    board: Board = {}
    for c in attacker:
        board[c] = ATTACKER
    for c in defender:
        board[c] = DEFENDER
    return board


def update_template_from_eval(template: Template, evaluation: Evaluation) -> Template:
    if template.kind == "exact":
        obligations = evaluation.exact_edges
        tau = evaluation.tau_exact
        pressure = evaluation.pressure_exact
    else:
        obligations = evaluation.proto_edges
        tau = evaluation.tau_proto
        pressure = evaluation.pressure_proto
    return Template(
        template_id=template.template_id,
        source_event_id=template.source_event_id,
        kind=template.kind,
        attacker=tuple(sorted(template.attacker)),
        defender=tuple(sorted(template.defender)),
        move=tuple(sorted(template.move)),  # type: ignore[arg-type]
        obligations=obligations,
        tau=tau,
        pressure=pressure,
        terminal=bool(evaluation.terminal_segments),
        source_type=template.source_type,
        pair_shape=canonical_pair_shape(tuple(sorted(template.move))),  # type: ignore[arg-type]
    )


def recompute_template(template: Template, radius: int) -> Template:
    evaluation = evaluate_move(
        relative_board(template.attacker, template.defender),
        template.move,
        ATTACKER,
        radius=radius,
        include_proto=True,
    )
    return update_template_from_eval(template, evaluation)


def template_is_acceptable(
    candidate: Template,
    target: Template,
    mode: str,
) -> bool:
    if candidate.terminal != target.terminal:
        return False
    if mode == "positive":
        return candidate.pressure > 0
    if mode == "same-tau":
        return candidate.tau == target.tau
    return candidate.pressure == target.pressure


def apply_critical_core(
    template: Template,
    mode: str = "same-pressure",
    max_combo: int = 2,
) -> Template:
    core = critical_obligation_core(template.obligations, mode=mode, max_combo=max_combo)
    tau = hitting_number(core)
    return template._replace(
        obligations=core,
        tau=tau,
        pressure=max(0, tau - 2),
    )


def minimise_template(
    template: Template,
    radius: int,
    mode: str = "same-pressure",
    max_combo: int = 3,
) -> Template:
    target = recompute_template(template, radius)
    current = target

    def try_remove(cells_to_remove: Sequence[Tuple[str, Cell]]) -> Optional[Template]:
        attackers = set(current.attacker)
        defenders = set(current.defender)
        for role, cell in cells_to_remove:
            if role == "A":
                attackers.discard(cell)
            else:
                defenders.discard(cell)
        trial = Template(
            template_id=current.template_id,
            source_event_id=current.source_event_id,
            kind=current.kind,
            attacker=tuple(sorted(attackers)),
            defender=tuple(sorted(defenders)),
            move=current.move,
            obligations=current.obligations,
            tau=current.tau,
            pressure=current.pressure,
            terminal=current.terminal,
            source_type=current.source_type,
            pair_shape=current.pair_shape,
        )
        try:
            recomputed = recompute_template(trial, radius)
        except ValueError:
            return None
        if template_is_acceptable(recomputed, target, mode):
            return recomputed
        return None

    changed = True
    while changed:
        changed = False
        removable = [("A", c) for c in current.attacker] + [("D", c) for c in current.defender]
        for item in removable:
            trial = try_remove([item])
            if trial is not None:
                current = trial
                changed = True
                break

    for combo_size in range(2, max_combo + 1):
        changed = True
        while changed:
            changed = False
            removable = [("A", c) for c in current.attacker] + [("D", c) for c in current.defender]
            if len(removable) < combo_size:
                break
            for combo in itertools.combinations(removable, combo_size):
                trial = try_remove(combo)
                if trial is not None:
                    current = trial
                    changed = True
                    break

    return current._replace(
        template_id=template.template_id,
        pair_shape=canonical_pair_shape(current.move),
    )


def edge_vertices(edges: Sequence[Edge]) -> Tuple[Cell, ...]:
    return tuple(sorted({v for edge in edges for v in edge}))


def cell_json(c: Cell) -> List[int]:
    return [int(c[0]), int(c[1])]


def cells_json(cells: Iterable[Cell]) -> List[List[int]]:
    return [cell_json(c) for c in cells]


def edges_json(edges: Sequence[Edge]) -> List[List[List[int]]]:
    return [cells_json(edge) for edge in edges]


def json_dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def stable_hash(obj) -> str:
    return hashlib.sha1(json_dumps(obj).encode("utf-8")).hexdigest()[:20]


def board_hash(board: Board) -> str:
    return stable_hash([(q, r, v) for (q, r), v in sorted(board.items())])


def template_to_json(template: Template, signature: Optional[str] = None, family: str = "") -> Dict:
    return {
        "template_id": template.template_id,
        "type": template.kind,
        "tau": template.tau,
        "pressure": template.pressure,
        "attacker": cells_json(template.attacker),
        "defender": cells_json(template.defender),
        "move": cells_json(template.move),
        "obligations": edges_json(template.obligations),
        "canonical_signature": signature or canonical_template_signature(template),
        "pair_shape": str(template.pair_shape),
        "family": family or classify_template_family(template),
        "terminal": template.terminal,
        "source_type": template.source_type,
    }


def shape_kind(shape: Cell) -> str:
    q, r = shape
    dist = hex_dist(shape)
    on_axis = q == 0 or r == 0 or q + r == 0
    if on_axis:
        return "rail" if dist > 1 else "adjacent"
    if dist <= 2:
        return "bridge"
    return "kink"


def line_axis_support(edges: Sequence[Edge]) -> str:
    vertices = edge_vertices(edges)
    axes = 0
    if len({q for q, _ in vertices}) > 1:
        axes += 1
    if len({r for _, r in vertices}) > 1:
        axes += 1
    if len({q + r for q, r in vertices}) > 1:
        axes += 1
    return {0: "empty", 1: "one-axis", 2: "two-axis", 3: "three-axis"}[axes]


def classify_template_family(template: Template) -> str:
    kind = shape_kind(template.pair_shape)
    singletons = sum(1 for edge in template.obligations if len(edge) == 1)
    pair_edges = sum(1 for edge in template.obligations if len(edge) == 2)
    if kind == "rail" and singletons >= 3:
        return "rail_fork"
    if kind == "rail" and pair_edges >= singletons:
        return "rail_ladder"
    if kind == "bridge":
        return "bridge_fork"
    if kind == "kink":
        return "kink_bridge"
    return kind


def hypergraph_features(edges: Sequence[Edge], tau: int) -> Dict:
    vertices = edge_vertices(edges)
    edge_sizes = Counter(len(edge) for edge in edges)
    intersections = 0
    total_pairs = 0
    for a, b in itertools.combinations(edges, 2):
        total_pairs += 1
        if set(a) & set(b):
            intersections += 1
    density = intersections / total_pairs if total_pairs else 0.0
    spectrum = ""
    try:
        import numpy as np

        if vertices:
            index = {v: i for i, v in enumerate(vertices)}
            adjacency = np.zeros((len(vertices), len(vertices)), dtype=float)
            for edge in edges:
                for u, v in itertools.combinations(edge, 2):
                    i, j = index[u], index[v]
                    adjacency[i, j] += 1.0
                    adjacency[j, i] += 1.0
            degree = np.diag(adjacency.sum(axis=1))
            eigs = np.linalg.eigvalsh(degree - adjacency)
            spectrum = ",".join(f"{x:.4g}" for x in eigs[:8])
    except Exception:
        spectrum = ""
    return {
        "number_of_vertices": len(vertices),
        "number_of_edges": len(edges),
        "edge_size_histogram": json_dumps(dict(sorted(edge_sizes.items()))),
        "singleton_count": edge_sizes.get(1, 0),
        "pair_edge_count": edge_sizes.get(2, 0),
        "transversal_number_tau": tau,
        "number_of_minimum_transversals": count_minimum_transversals(edges, tau),
        "intersection_graph_density": density,
        "laplacian_spectrum": spectrum,
    }


def extract_raw_template(
    board: Board,
    move: Tuple[Cell, Cell],
    player: int,
    evaluation: Evaluation,
    kind: str,
    event_id: str,
    source_type: str,
    template_id: str,
    padding: int = 1,
) -> Template:
    if kind == "exact":
        obligations = evaluation.exact_edges
        source_segments = evaluation.exact_source_segments
        tau = evaluation.tau_exact
        pressure = evaluation.pressure_exact
    else:
        obligations = evaluation.proto_edges
        source_segments = evaluation.exact_source_segments + evaluation.proto_source_segments
        tau = evaluation.tau_proto
        pressure = evaluation.pressure_proto

    footprint: Set[Cell] = set(move) | set(edge_vertices(obligations))
    for segment in source_segments:
        footprint.update(segment)
    if not footprint:
        footprint.update(move)

    attacker: Set[Cell] = set()
    defender: Set[Cell] = set()
    for cell, value in board.items():
        if cell in move:
            continue
        if min(hex_dist(cell, f) for f in footprint) > padding:
            continue
        if value == player:
            attacker.add(cell)
        elif value == -player:
            defender.add(cell)

    return Template(
        template_id=template_id,
        source_event_id=event_id,
        kind=kind,
        attacker=tuple(sorted(attacker)),
        defender=tuple(sorted(defender)),
        move=tuple(sorted(move)),  # type: ignore[arg-type]
        obligations=obligations,
        tau=tau,
        pressure=pressure,
        terminal=bool(evaluation.terminal_segments),
        source_type=source_type,
        pair_shape=canonical_pair_shape(tuple(sorted(move))),  # type: ignore[arg-type]
    )


def candidate_cell_score(board: Board, cell: Cell, player: int) -> float:
    if cell in board:
        return -1e9
    score = 0.0
    occupied = list(board.keys())
    if occupied:
        score -= 0.05 * min(hex_dist(cell, occ) for occ in occupied)
    for axis in SEGMENT_AXES:
        line_score = 0
        for sign in (-1, 1):
            d = mul(sign, axis)
            for k in range(1, WIN_LEN):
                value = board.get(add(cell, mul(k, d)), 0)
                if value == player:
                    line_score += 2
                elif value == -player:
                    line_score += 1
                    break
                else:
                    break
        score += line_score * line_score
    score -= 0.01 * hex_dist(cell)
    return score


def candidate_cells(board: Board, radius: int, frontier: int = 2) -> List[Cell]:
    cells = [c for c in cells_in_radius(radius) if c not in board]
    if not board:
        return cells
    occupied = list(board.keys())
    frontier_cells = [
        c for c in cells if min(hex_dist(c, occ) for occ in occupied) <= frontier
    ]
    return frontier_cells or cells


def enumerate_candidate_pairs(
    board: Board,
    player: int,
    radius: int,
    frontier: int,
    max_pairs: int,
    rng: random.Random,
) -> List[Tuple[Cell, Cell]]:
    cells = candidate_cells(board, radius, frontier=frontier)
    pairs = [tuple(sorted(pair)) for pair in itertools.combinations(cells, 2)]
    pairs = sorted(set(pairs))
    if not max_pairs or len(pairs) <= max_pairs:
        return pairs
    scored = [
        (
            candidate_cell_score(board, a, player)
            + candidate_cell_score(board, b, player)
            - 0.03 * hex_dist(a, b),
            rng.random(),
            (a, b),
        )
        for a, b in pairs
    ]
    scored.sort(reverse=True)
    return [pair for _, _, pair in scored[:max_pairs]]


def place_if_empty(board: Board, cell: Cell, player: int, radius: int) -> bool:
    if hex_dist(cell) > radius or cell in board:
        return False
    board[cell] = player
    return True


def fill_random(board: Board, radius: int, target: int, rng: random.Random) -> None:
    cells = [c for c in cells_in_radius(radius) if c not in board]
    rng.shuffle(cells)
    for cell in cells:
        if len(board) >= target:
            break
        board[cell] = ATTACKER if rng.random() < 0.52 else DEFENDER


def generate_random_sparse(radius: int, max_stones: int, rng: random.Random) -> Tuple[Board, int, int]:
    density = rng.randint(max(4, min(8, max_stones)), max_stones)
    cells = cells_in_radius(radius)
    rng.shuffle(cells)
    board: Board = {}
    for cell in cells[:density]:
        board[cell] = ATTACKER if rng.random() < 0.5 else DEFENDER
    return board, ATTACKER, 0


def generate_rail_biased(radius: int, max_stones: int, rng: random.Random) -> Tuple[Board, int, int]:
    board: Board = {}
    axis = rng.choice(SEGMENT_AXES)
    bridge = rng.choice([d for d in DIRECTIONS6 if d not in (axis, neg(axis))])
    start = mul(-rng.randint(2, 4), axis)
    length = rng.randint(3, 5)
    gap = rng.randrange(length) if rng.random() < 0.45 else None
    for k in range(length):
        if k == gap:
            continue
        place_if_empty(board, add(start, mul(k, axis)), ATTACKER, radius)
    for k in range(max(1, length - 2)):
        if rng.random() < 0.75:
            place_if_empty(board, add(add(start, bridge), mul(k, axis)), ATTACKER, radius)
    for k in range(length + 1):
        if rng.random() < 0.45:
            place_if_empty(board, add(add(start, mul(k, axis)), neg(bridge)), DEFENDER, radius)
    fill_random(board, radius, rng.randint(min(len(board) + 2, max_stones), max_stones), rng)
    return board, ATTACKER, 0


def generate_adversarial(radius: int, max_stones: int, rng: random.Random) -> Tuple[Board, int, int]:
    board: Board = {}
    for _ in range(rng.randint(2, 4)):
        axis = rng.choice(SEGMENT_AXES)
        offset = rng.choice(cells_in_radius(max(1, radius - 5)))
        segment = [add(offset, mul(k - 3, axis)) for k in range(WIN_LEN)]
        if not all(hex_dist(c) <= radius for c in segment):
            continue
        stones = rng.sample(segment, rng.randint(3, 5))
        for cell in stones:
            place_if_empty(board, cell, ATTACKER, radius)
        for cell in segment:
            if cell not in board and rng.random() < 0.15:
                place_if_empty(board, cell, DEFENDER, radius)
    fill_random(board, radius, rng.randint(min(len(board) + 2, max_stones), max_stones), rng)
    return board, ATTACKER, 0


def random_frontier_pair(board: Board, player: int, radius: int, rng: random.Random) -> Optional[Tuple[Cell, Cell]]:
    pairs = enumerate_candidate_pairs(board, player, radius, frontier=2, max_pairs=48, rng=rng)
    return rng.choice(pairs) if pairs else None


def generate_opening(radius: int, max_stones: int, rng: random.Random) -> Tuple[Board, int, int]:
    board: Board = {(0, 0): ATTACKER}
    player = DEFENDER
    plies = rng.randint(2, 6)
    for ply in range(1, plies + 1):
        pair = random_frontier_pair(board, player, radius, rng)
        if pair is None:
            break
        board[pair[0]] = player
        board[pair[1]] = player
        player = -player
        if len(board) >= max_stones:
            break
    return board, player, plies


def generate_selfplay(radius: int, max_stones: int, rng: random.Random) -> Tuple[Board, int, int]:
    board: Board = {(0, 0): ATTACKER}
    player = DEFENDER
    plies = rng.randint(3, 9)
    segments = cached_segments(radius, pad=2)
    for ply in range(1, plies + 1):
        pairs = enumerate_candidate_pairs(board, player, radius, frontier=2, max_pairs=64, rng=rng)
        if not pairs:
            break
        scored = []
        for pair in pairs[:64]:
            try:
                ev = evaluate_move(board, pair, player, radius, include_proto=True, segments=segments)
            except ValueError:
                continue
            score = 8 * ev.pressure_exact + 3 * ev.pressure_proto + ev.tau_exact + 0.2 * ev.tau_proto
            score += 0.05 * rng.random()
            scored.append((score, pair))
        if not scored:
            break
        scored.sort(reverse=True)
        top = scored[: max(1, min(6, len(scored)))]
        pair = rng.choice(top)[1]
        board[pair[0]] = player
        board[pair[1]] = player
        player = -player
        if len(board) >= max_stones:
            break
    return board, player, plies


GENERATOR_ALIASES = {
    "random": generate_random_sparse,
    "sparse": generate_random_sparse,
    "rail": generate_rail_biased,
    "rail-biased": generate_rail_biased,
    "opening": generate_opening,
    "selfplay": generate_selfplay,
    "self-play": generate_selfplay,
    "adversarial": generate_adversarial,
    "near-threat": generate_adversarial,
}


def generate_position(
    source_type: str,
    radius: int,
    max_stones: int,
    rng: random.Random,
) -> Tuple[Board, int, int]:
    if source_type not in GENERATOR_ALIASES:
        raise ValueError(f"unknown generator {source_type!r}")
    return GENERATOR_ALIASES[source_type](radius, max_stones, rng)


def active_source_types(source_types: Sequence[str], positive_counts: Dict[str, int], cap: int) -> List[str]:
    if cap <= 0:
        return list(source_types)
    return [source_type for source_type in source_types if positive_counts.get(source_type, 0) < cap]


def csv_writer(path: Path, fieldnames: Sequence[str]):
    handle = path.open("w", newline="", encoding="utf-8")
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    return handle, writer


def write_rows(path: Path, fieldnames: Sequence[str], rows: Sequence[Dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def template_row(template: Template, template_id: str, signature: str = "", count: int = 1) -> Dict:
    features = hypergraph_features(template.obligations, template.tau)
    return {
        "template_id": template_id,
        "source_event_id": template.source_event_id,
        "kind": template.kind,
        "tau": template.tau,
        "pressure": template.pressure,
        "terminal": int(template.terminal),
        "attacker_stones": json_dumps(cells_json(template.attacker)),
        "defender_stones": json_dumps(cells_json(template.defender)),
        "move_stones": json_dumps(cells_json(template.move)),
        "obligation_edges": json_dumps(edges_json(template.obligations)),
        "num_attacker_stones": len(template.attacker),
        "num_defender_stones": len(template.defender),
        "num_obligations": len(template.obligations),
        "num_obligation_vertices": len(edge_vertices(template.obligations)),
        "pair_shape": str(template.pair_shape),
        "shape_kind": shape_kind(template.pair_shape),
        "family": classify_template_family(template),
        "line_axis_support": line_axis_support(template.obligations),
        "canonical_signature": signature,
        "frequency": count,
        "automorphism_group_size": automorphism_count(template),
        **features,
    }


def ensure_plotting():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    return plt, PdfPages


def plot_tau_vs_obligations(points: Sequence[Dict], path: Path) -> None:
    plt, _ = ensure_plotting()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if points:
        xs = [p["num_obligations"] for p in points]
        ys = [p["tau"] for p in points]
        colors = [p.get("pressure", 0) for p in points]
        ax.scatter(xs, ys, c=colors, s=12, alpha=0.45, cmap="viridis")
    ax.set_xlabel("number of obligation hyperedges")
    ax.set_ylabel("exact transversal number tau")
    ax.set_title("Obligation count vs exact hitting number")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_frequency_rank(frequencies: Sequence[Tuple[str, int]], path: Path) -> None:
    plt, _ = ensure_plotting()
    counts = [count for _, count in frequencies]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    if counts:
        ax.plot(range(1, len(counts) + 1), counts, marker="o", linewidth=1)
        ax.set_yscale("log")
    ax.set_xlabel("canonical primitive template rank")
    ax.set_ylabel("frequency")
    ax.set_title("Primitive template frequency rank")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_shape_spectrum(shape_counts: Counter, path: Path) -> None:
    plt, _ = ensure_plotting()
    items = shape_counts.most_common(18)
    fig, ax = plt.subplots(figsize=(8, 4.8))
    if items:
        labels = [str(k) for k, _ in items]
        counts = [v for _, v in items]
        ax.bar(range(len(items)), counts, color="#4c78a8")
        ax.set_xticks(range(len(items)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.set_xlabel("D6 canonical pair shape")
    ax.set_ylabel("positive event count")
    ax.set_title("Template shape spectrum")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_template(ax, template: Template, title: str) -> None:
    cells = set(template.attacker) | set(template.defender) | set(template.move) | set(edge_vertices(template.obligations))
    if not cells:
        ax.axis("off")
        return
    xs = []
    ys = []
    for cell in cells:
        x, y = axial_to_xy(cell)
        xs.append(x)
        ys.append(y)
        ax.scatter([x], [y], s=130, facecolor="#f7f7f7", edgecolor="#cccccc", linewidth=0.8)
    if template.attacker:
        pts = [axial_to_xy(c) for c in template.attacker]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=70, c="#222222", label="attacker")
    if template.defender:
        pts = [axial_to_xy(c) for c in template.defender]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=70, facecolor="#ffffff", edgecolor="#222222", label="defender")
    if template.move:
        pts = [axial_to_xy(c) for c in template.move]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=95, c="#d95f02", marker="s", label="move")
    vertices = edge_vertices(template.obligations)
    if vertices:
        pts = [axial_to_xy(c) for c in vertices]
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=95, c="#1f77b4", marker="x", label="obligation")
    for edge in template.obligations:
        if len(edge) > 1:
            pts = [axial_to_xy(c) for c in edge]
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color="#1f77b4", alpha=0.35, linewidth=1)
    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    pad = 0.8
    ax.set_xlim(min(xs) - pad, max(xs) + pad)
    ax.set_ylim(min(ys) - pad, max(ys) + pad)


def write_top_templates_pdf(templates: Sequence[Template], path: Path, limit: int = 12) -> None:
    plt, PdfPages = ensure_plotting()
    with PdfPages(path) as pdf:
        for offset in range(0, min(limit, len(templates)), 4):
            fig, axes = plt.subplots(2, 2, figsize=(8, 8))
            for ax, template in zip(axes.ravel(), templates[offset : offset + 4]):
                title = f"{template.template_id} {template.kind} tau={template.tau} p={template.pressure}"
                draw_template(ax, template, title)
            for ax in axes.ravel()[len(templates[offset : offset + 4]) :]:
                ax.axis("off")
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


def write_template_pngs(templates: Sequence[Template], folder: Path, limit: int = 24) -> None:
    plt, _ = ensure_plotting()
    folder.mkdir(parents=True, exist_ok=True)
    for i, template in enumerate(templates[:limit], start=1):
        fig, ax = plt.subplots(figsize=(4.2, 4.2))
        draw_template(ax, template, f"{template.template_id} tau={template.tau}")
        fig.tight_layout()
        fig.savefig(folder / f"{i:02d}_{template.template_id}.png", dpi=180)
        plt.close(fig)


def copy_public_artifact_aliases(out: Path, data: Path, figures: Path) -> None:
    aliases = [
        (data / "primitive_templates.csv", out / "primitive_templates.csv"),
        (data / "template_examples.json", out / "template_examples.json"),
        (figures / "template_frequency_rank.png", out / "template_frequency_rank.png"),
        (figures / "tau_vs_obligations.png", out / "tau_vs_obligations.png"),
        (figures / "template_shape_spectrum.png", out / "template_shape_spectrum.png"),
        (figures / "top_templates_diagram.pdf", out / "top_templates_diagram.pdf"),
    ]
    for src, dst in aliases:
        if src.exists():
            shutil.copyfile(src, dst)


def run_mining(args: argparse.Namespace) -> Dict:
    out = Path(args.out)
    data = out / "data"
    figures = out / "figures"
    diagrams = out / "template_diagrams"
    data.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    diagrams.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    source_types = [g.strip() for g in args.generators.split(",") if g.strip()]
    pressure_modes = [p.strip() for p in args.pressure.split(",") if p.strip()]
    for source_type in source_types:
        if source_type not in GENERATOR_ALIASES:
            raise ValueError(f"unknown generator {source_type!r}; choose from {sorted(GENERATOR_ALIASES)}")
    for mode in pressure_modes:
        if mode not in {"exact", "proto"}:
            raise ValueError("--pressure must contain exact and/or proto")

    candidate_radius = args.candidate_radius if args.candidate_radius is not None else min(args.radius, 4)
    segments = cached_segments(args.radius, pad=2)

    position_fields = [
        "position_id",
        "source_type",
        "radius",
        "density",
        "ply",
        "attacker",
        "board_hash",
        "generator_seed",
        "board_json",
    ]
    candidate_fields = [
        "position_id",
        "move_a",
        "move_b",
        "pair_shape_D6",
        "num_obligations",
        "num_proto_obligations",
        "num_obligation_vertices",
        "tau_exact",
        "pressure_exact",
        "tau_proto",
        "pressure_proto",
        "terminal",
        "obligation_edges",
        "proto_obligation_edges",
    ]
    positive_fields = [
        "event_id",
        "position_id",
        "kind",
        "source_type",
        "move_a",
        "move_b",
        "pair_shape_D6",
        "tau",
        "pressure",
        "terminal",
        "num_obligations",
        "num_obligation_vertices",
        "obligation_edges",
    ]

    position_handle, position_writer = csv_writer(data / "positions.csv", position_fields)
    candidate_handle, candidate_writer = csv_writer(data / "candidate_moves.csv", candidate_fields)
    positive_handle, positive_writer = csv_writer(data / "positive_pressure_events.csv", positive_fields)

    raw_rows: List[Dict] = []
    minimal_rows: List[Dict] = []
    canonical_templates: Dict[str, Template] = {}
    canonical_counts: Counter = Counter()
    canonical_sources: Dict[str, Counter] = defaultdict(Counter)
    shape_counts: Counter = Counter()
    tau_points: List[Dict] = []
    source_positive_counts: Counter = Counter()

    positions_sampled = 0
    candidates_evaluated = 0
    positive_events = 0
    raw_template_count = 0
    minimal_template_count = 0

    try:
        for sample_idx in range(args.samples):
            active_sources = active_source_types(source_types, source_positive_counts, args.max_positive_events_per_source)
            if not active_sources:
                break
            source_type = active_sources[sample_idx % len(active_sources)]
            sample_seed = rng.randrange(2**31)
            sample_rng = random.Random(sample_seed)
            board, attacker, ply = generate_position(source_type, args.radius, args.max_stones, sample_rng)
            position_id = f"P{sample_idx:07d}"
            positions_sampled += 1
            position_writer.writerow(
                {
                    "position_id": position_id,
                    "source_type": source_type,
                    "radius": args.radius,
                    "density": len(board),
                    "ply": ply,
                    "attacker": attacker,
                    "board_hash": board_hash(board),
                    "generator_seed": sample_seed,
                    "board_json": json_dumps([[q, r, v] for (q, r), v in sorted(board.items())]),
                }
            )

            pairs = enumerate_candidate_pairs(
                board,
                attacker,
                candidate_radius,
                frontier=args.candidate_frontier,
                max_pairs=args.max_candidate_pairs,
                rng=sample_rng,
            )
            for pair_idx, move in enumerate(pairs):
                try:
                    ev = evaluate_move(board, move, attacker, args.radius, include_proto=True, segments=segments)
                except ValueError:
                    continue
                candidates_evaluated += 1
                shape = canonical_pair_shape(move)
                exact_vertices = edge_vertices(ev.exact_edges)
                candidate_writer.writerow(
                    {
                        "position_id": position_id,
                        "move_a": str(move[0]),
                        "move_b": str(move[1]),
                        "pair_shape_D6": str(shape),
                        "num_obligations": len(ev.exact_edges),
                        "num_proto_obligations": len(ev.proto_edges),
                        "num_obligation_vertices": len(exact_vertices),
                        "tau_exact": ev.tau_exact,
                        "pressure_exact": ev.pressure_exact,
                        "tau_proto": ev.tau_proto,
                        "pressure_proto": ev.pressure_proto,
                        "terminal": int(bool(ev.terminal_segments)),
                        "obligation_edges": json_dumps(edges_json(ev.exact_edges)),
                        "proto_obligation_edges": json_dumps(edges_json(ev.proto_edges)),
                    }
                )
                if len(tau_points) < args.plot_point_limit:
                    tau_points.append(
                        {
                            "num_obligations": len(ev.exact_edges),
                            "tau": ev.tau_exact,
                            "pressure": ev.pressure_exact,
                        }
                    )

                positive_kinds: List[str] = []
                if "exact" in pressure_modes and ev.tau_exact > 2:
                    positive_kinds.append("exact")
                if "proto" in pressure_modes and ev.tau_proto > 2:
                    positive_kinds.append("proto")
                for kind in positive_kinds:
                    if args.max_positive_events_per_source and source_positive_counts[source_type] >= args.max_positive_events_per_source:
                        break
                    event_id = f"E{positive_events:09d}"
                    positive_events += 1
                    source_positive_counts[source_type] += 1
                    if kind == "exact":
                        obligations = ev.exact_edges
                        tau = ev.tau_exact
                        pressure = ev.pressure_exact
                    else:
                        obligations = ev.proto_edges
                        tau = ev.tau_proto
                        pressure = ev.pressure_proto
                    positive_writer.writerow(
                        {
                            "event_id": event_id,
                            "position_id": position_id,
                            "kind": kind,
                            "source_type": source_type,
                            "move_a": str(move[0]),
                            "move_b": str(move[1]),
                            "pair_shape_D6": str(shape),
                            "tau": tau,
                            "pressure": pressure,
                            "terminal": int(bool(ev.terminal_segments)),
                            "num_obligations": len(obligations),
                            "num_obligation_vertices": len(edge_vertices(obligations)),
                            "obligation_edges": json_dumps(edges_json(obligations)),
                        }
                    )
                    shape_counts[shape] += 1
                    raw_template_count += 1
                    raw_template = extract_raw_template(
                        board,
                        move,
                        attacker,
                        ev,
                        kind=kind,
                        event_id=event_id,
                        source_type=source_type,
                        template_id=f"R{raw_template_count:09d}",
                        padding=args.template_padding,
                    )
                    raw_rows.append(template_row(raw_template, raw_template.template_id))

                    if args.minimize:
                        minimal_template = minimise_template(
                            raw_template,
                            radius=args.radius,
                            mode=args.minimize_mode,
                            max_combo=args.max_combo_delete,
                        )
                    else:
                        minimal_template = raw_template
                    if args.critical_core:
                        minimal_template = apply_critical_core(
                            minimal_template,
                            mode=args.core_mode,
                            max_combo=args.max_core_combo_delete,
                        )
                    minimal_template_count += 1
                    minimal_template = minimal_template._replace(template_id=f"M{minimal_template_count:09d}")
                    signature = canonical_template_signature(minimal_template) if args.canonicalize else stable_hash(template_to_json(minimal_template))
                    minimal_rows.append(template_row(minimal_template, minimal_template.template_id, signature=signature))
                    canonical_counts[signature] += 1
                    canonical_sources[signature][source_type] += 1
                    if signature not in canonical_templates:
                        canonical_templates[signature] = minimal_template._replace(template_id=f"T_{len(canonical_templates) + 1:04d}")

                    if args.max_positive_events and positive_events >= args.max_positive_events:
                        break
                if args.max_positive_events and positive_events >= args.max_positive_events:
                    break
                if args.max_positive_events_per_source and source_positive_counts[source_type] >= args.max_positive_events_per_source:
                    break
            if args.max_positive_events and positive_events >= args.max_positive_events:
                break
    finally:
        position_handle.close()
        candidate_handle.close()
        positive_handle.close()

    template_fields = [
        "template_id",
        "source_event_id",
        "kind",
        "tau",
        "pressure",
        "terminal",
        "attacker_stones",
        "defender_stones",
        "move_stones",
        "obligation_edges",
        "num_attacker_stones",
        "num_defender_stones",
        "num_obligations",
        "num_obligation_vertices",
        "pair_shape",
        "shape_kind",
        "family",
        "line_axis_support",
        "canonical_signature",
        "frequency",
        "automorphism_group_size",
        "number_of_vertices",
        "number_of_edges",
        "edge_size_histogram",
        "singleton_count",
        "pair_edge_count",
        "transversal_number_tau",
        "number_of_minimum_transversals",
        "intersection_graph_density",
        "laplacian_spectrum",
    ]
    write_rows(data / "raw_templates.csv", template_fields, raw_rows)
    write_rows(data / "minimal_templates.csv", template_fields, minimal_rows)

    frequency_rank = canonical_counts.most_common()
    canonical_rows: List[Dict] = []
    top_templates: List[Template] = []
    examples: List[Dict] = []
    for rank, (signature, count) in enumerate(frequency_rank, start=1):
        template = canonical_templates[signature]._replace(template_id=f"T_{rank:04d}")
        top_templates.append(template)
        row = template_row(template, template.template_id, signature=signature, count=count)
        row["source_counts"] = json_dumps(dict(canonical_sources[signature]))
        canonical_rows.append(row)
        examples.append(template_to_json(template, signature=signature))

    canonical_fields = template_fields + ["source_counts"]
    write_rows(data / "canonical_templates.csv", canonical_fields, canonical_rows)
    write_rows(data / "primitive_templates.csv", canonical_fields, canonical_rows)
    write_rows(
        data / "template_frequencies.csv",
        ["rank", "canonical_signature", "template_id", "frequency", "kind", "tau", "pressure", "family", "source_counts"],
        [
            {
                "rank": i,
                "canonical_signature": signature,
                "template_id": f"T_{i:04d}",
                "frequency": count,
                "kind": canonical_templates[signature].kind,
                "tau": canonical_templates[signature].tau,
                "pressure": canonical_templates[signature].pressure,
                "family": classify_template_family(canonical_templates[signature]),
                "source_counts": json_dumps(dict(canonical_sources[signature])),
            }
            for i, (signature, count) in enumerate(frequency_rank, start=1)
        ],
    )
    (data / "template_examples.json").write_text(json.dumps(examples[: args.top_templates], indent=2), encoding="utf-8")

    try:
        plot_tau_vs_obligations(tau_points, figures / "tau_vs_obligations.png")
        plot_frequency_rank(frequency_rank, figures / "template_frequency_rank.png")
        plot_shape_spectrum(shape_counts, figures / "template_shape_spectrum.png")
        write_top_templates_pdf(top_templates, figures / "top_templates_diagram.pdf", limit=args.top_templates)
        write_template_pngs(top_templates, diagrams, limit=args.top_templates)
    except Exception as exc:
        (figures / "PLOTTING_FAILED.txt").write_text(str(exc), encoding="utf-8")
    copy_public_artifact_aliases(out, data, figures)

    summary = {
        "positions_sampled": positions_sampled,
        "candidate_pairs_evaluated": candidates_evaluated,
        "positive_pressure_events": positive_events,
        "raw_templates": raw_template_count,
        "minimal_templates": minimal_template_count,
        "canonical_primitive_templates": len(canonical_templates),
        "radius": args.radius,
        "candidate_radius": candidate_radius,
        "max_candidate_pairs": args.max_candidate_pairs,
        "generators": source_types,
        "pressure_modes": pressure_modes,
        "minimize": bool(args.minimize),
        "critical_core": bool(args.critical_core),
        "core_mode": args.core_mode,
        "canonicalize": bool(args.canonicalize),
        "seed": args.seed,
        "positive_events_by_source": dict(source_positive_counts),
        "top_templates": examples[: min(5, len(examples))],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_readme(out, summary)
    return summary


def write_readme(out: Path, summary: Dict) -> None:
    text = f"""# Hex Connect-6 Primitive Template Miner

This run mines local forcing events for infinite Hex Connect-6 by evaluating the
urgent obligation hypergraph induced by candidate two-stone moves.

For each candidate move, exact pressure is:

```text
pressure = max(0, tau(O(P,m)) - 2)
```

where `tau` is the minimum hitting-set size of the urgent obligation hypergraph.
Positive pressure means the defender's two-stone reply capacity is exceeded.

## Run Summary

```json
{json.dumps(summary, indent=2)}
```

## Main Outputs

- `data/positions.csv`
- `data/candidate_moves.csv`
- `data/positive_pressure_events.csv`
- `data/raw_templates.csv`
- `data/minimal_templates.csv`
- `data/canonical_templates.csv`
- `data/primitive_templates.csv`
- `data/template_frequencies.csv`
- `data/template_examples.json`
- `figures/tau_vs_obligations.png`
- `figures/template_frequency_rank.png`
- `figures/template_shape_spectrum.png`
- `figures/top_templates_diagram.pdf`
- `template_diagrams/`

The headline files are also copied to the run root:

- `primitive_templates.csv`
- `template_examples.json`
- `template_frequency_rank.png`
- `tau_vs_obligations.png`
- `template_shape_spectrum.png`
- `top_templates_diagram.pdf`

## Notes

The default candidate policy ranks local frontier pairs and caps them with
`--max-candidate-pairs` so exploratory runs can scale. Set
`--max-candidate-pairs 0` for exhaustive pair enumeration inside
`--candidate-radius`.
"""
    (out / "README.md").write_text(text, encoding="utf-8")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="template_mining_run")
    parser.add_argument("--radius", type=int, default=6)
    parser.add_argument("--samples", type=int, default=500)
    parser.add_argument("--generators", default="random,rail,opening,selfplay,adversarial")
    parser.add_argument("--max-stones", type=int, default=22)
    parser.add_argument("--pressure", default="exact,proto")
    parser.add_argument("--minimize", action="store_true")
    parser.add_argument("--canonicalize", action="store_true")
    parser.add_argument("--seed", type=int, default=20260510)
    parser.add_argument("--candidate-radius", type=int, default=None)
    parser.add_argument("--candidate-frontier", type=int, default=2)
    parser.add_argument("--max-candidate-pairs", type=int, default=512)
    parser.add_argument("--template-padding", type=int, default=1)
    parser.add_argument("--minimize-mode", choices=["same-pressure", "same-tau", "positive"], default="same-pressure")
    parser.add_argument("--max-combo-delete", type=int, default=3)
    parser.add_argument("--critical-core", action="store_true")
    parser.add_argument("--core-mode", choices=["same-pressure", "same-tau", "positive"], default="same-pressure")
    parser.add_argument("--max-core-combo-delete", type=int, default=2)
    parser.add_argument("--max-positive-events", type=int, default=0)
    parser.add_argument("--max-positive-events-per-source", type=int, default=0)
    parser.add_argument("--plot-point-limit", type=int, default=200000)
    parser.add_argument("--top-templates", type=int, default=12)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    summary = run_mining(args)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
