"""Atlas analysis for Hex Connect-6 primitive forcing template runs.

This script treats a miner run as a population of local tactical molecules and
asks which ones recur across sources, compress under D6 canonicalisation, and
look like signal rather than generator-specific reservoir noise.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


Cell = Tuple[int, int]
RoleCell = Tuple[str, int, int]
Edge = Tuple[Cell, ...]
AbstractHypergraph = Tuple[Tuple[str, ...], Tuple[Tuple[int, ...], ...]]


PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "green_3": "#8BCF8B",
    "red_strong": "#B64342",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "gold": "#D8A102",
    "neutral_light": "#CFCECE",
    "neutral_mid": "#767676",
    "neutral_dark": "#4D4D4D",
    "neutral_black": "#272727",
}

ROLE_ORDER = ("A", "D", "M", "O")
HEX_DIRECTIONS: Tuple[Cell, ...] = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def parse_json_dict(value: str) -> Dict[str, int]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return {str(k): int(v) for k, v in data.items()}


def parse_cells(value: str) -> Tuple[Cell, ...]:
    if not value:
        return tuple()
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return tuple()
    return tuple(sorted((int(q), int(r)) for q, r in data))


def parse_edges(value: str) -> Tuple[Edge, ...]:
    if not value:
        return tuple()
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return tuple()
    return tuple(
        sorted(
            tuple(sorted((int(q), int(r)) for q, r in edge))
            for edge in data
        )
    )


def as_int(row: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def as_float(row: Dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


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


def add_cell(a: Cell, b: Cell) -> Cell:
    return (a[0] + b[0], a[1] + b[1])


def sub_cell(a: Cell, b: Cell) -> Cell:
    return (a[0] - b[0], a[1] - b[1])


def row_colored_cells(row: Dict[str, str]) -> Tuple[RoleCell, ...]:
    cells: List[RoleCell] = []
    for role, field in (("A", "attacker_stones"), ("D", "defender_stones"), ("M", "move_stones")):
        for q, r in parse_cells(row.get(field, "")):
            cells.append((role, q, r))
    return tuple(sorted(cells))


def row_cell_roles(row: Dict[str, str]) -> Dict[Cell, Set[str]]:
    roles: Dict[Cell, Set[str]] = defaultdict(set)
    for role, field in (("A", "attacker_stones"), ("D", "defender_stones"), ("M", "move_stones")):
        for cell in parse_cells(row.get(field, "")):
            roles[cell].add(role)
    for edge in parse_edges(row.get("obligation_edges", "")):
        for cell in edge:
            roles[cell].add("O")
    return dict(roles)


def role_color(role_set: Iterable[str]) -> str:
    present = set(role_set)
    return "".join(role for role in ROLE_ORDER if role in present) or "empty"


def abstract_hypergraph(row: Dict[str, str]) -> AbstractHypergraph:
    """Return a coordinate-free colored obligation hypergraph.

    Cell colors preserve attacker/defender/move/obligation roles; coordinates
    and hex-lattice geometry are deliberately forgotten.
    """
    roles = row_cell_roles(row)
    cells = sorted(roles, key=lambda cell: (role_color(roles[cell]), cell[0], cell[1]))
    index = {cell: i for i, cell in enumerate(cells)}
    colors = tuple(role_color(roles[cell]) for cell in cells)
    edge_set = {
        tuple(sorted(index[cell] for cell in edge if cell in index))
        for edge in parse_edges(row.get("obligation_edges", ""))
    }
    edges = tuple(sorted(edge for edge in edge_set if edge))
    return colors, edges


def _normalise_labels(signatures: Sequence[Tuple], prefix: str) -> Tuple[str, ...]:
    keys = [repr(signature) for signature in signatures]
    mapping = {key: f"{prefix}{i}" for i, key in enumerate(sorted(set(keys)))}
    return tuple(mapping[key] for key in keys)


def incidence_wl_labels(graph: AbstractHypergraph, rounds: int = 8) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    colors, edges = graph
    incident: List[List[int]] = [[] for _ in colors]
    for edge_index, edge in enumerate(edges):
        for cell_index in edge:
            incident[cell_index].append(edge_index)

    cell_labels = tuple(f"C:{color}" for color in colors)
    edge_labels = tuple(f"E:{len(edge)}" for edge in edges)
    for _ in range(rounds):
        next_cell = [
            (cell_labels[i], tuple(sorted(edge_labels[e] for e in incident[i])))
            for i in range(len(colors))
        ]
        next_edge = [
            (edge_labels[j], tuple(sorted(cell_labels[i] for i in edge)))
            for j, edge in enumerate(edges)
        ]
        new_cell_labels = _normalise_labels(next_cell, "c")
        new_edge_labels = _normalise_labels(next_edge, "e")
        if new_cell_labels == cell_labels and new_edge_labels == edge_labels:
            break
        cell_labels, edge_labels = new_cell_labels, new_edge_labels
    return cell_labels, edge_labels


def _permutation_budget(groups: Sequence[Sequence[int]]) -> int:
    budget = 1
    for group in groups:
        budget *= math.factorial(len(group))
    return budget


def _canonical_hypergraph_payload_flat(
    graph: AbstractHypergraph,
    exact_limit: int,
) -> Tuple[Tuple, bool]:
    colors, edges = graph
    if not colors:
        return (tuple(), tuple()), True

    cell_labels, _ = incidence_wl_labels(graph)
    label_groups: Dict[str, List[int]] = defaultdict(list)
    for index, label in enumerate(cell_labels):
        label_groups[label].append(index)
    groups = [label_groups[label] for label in sorted(label_groups)]

    exact = _permutation_budget(groups) <= exact_limit
    if exact:
        candidates = []
        group_permutations = [tuple(itertools.permutations(group)) for group in groups]
        for selected in itertools.product(*group_permutations):
            order = tuple(index for group_order in selected for index in group_order)
            relabel = {old: new for new, old in enumerate(order)}
            relabelled_edges = tuple(
                sorted(tuple(sorted(relabel[i] for i in edge)) for edge in edges)
            )
            candidates.append((tuple(colors[i] for i in order), relabelled_edges))
        return min(candidates), True

    order = tuple(sorted(range(len(colors)), key=lambda i: (cell_labels[i], colors[i], i)))
    relabel = {old: new for new, old in enumerate(order)}
    relabelled_edges = tuple(sorted(tuple(sorted(relabel[i] for i in edge)) for edge in edges))
    return (tuple(colors[i] for i in order), relabelled_edges), False


def incidence_components(graph: AbstractHypergraph) -> List[AbstractHypergraph]:
    colors, edges = graph
    if not colors:
        return []

    cell_to_edges: List[List[int]] = [[] for _ in colors]
    for edge_index, edge in enumerate(edges):
        for cell_index in edge:
            cell_to_edges[cell_index].append(edge_index)

    unseen_cells: Set[int] = set(range(len(colors)))
    unseen_edges: Set[int] = set(range(len(edges)))
    components: List[AbstractHypergraph] = []

    while unseen_cells or unseen_edges:
        if unseen_cells:
            start = ("c", next(iter(unseen_cells)))
        else:
            start = ("e", next(iter(unseen_edges)))
        stack = [start]
        comp_cells: Set[int] = set()
        comp_edges: Set[int] = set()

        while stack:
            kind, index = stack.pop()
            if kind == "c":
                if index in comp_cells:
                    continue
                comp_cells.add(index)
                unseen_cells.discard(index)
                for edge_index in cell_to_edges[index]:
                    if edge_index not in comp_edges:
                        stack.append(("e", edge_index))
            else:
                if index in comp_edges:
                    continue
                comp_edges.add(index)
                unseen_edges.discard(index)
                for cell_index in edges[index]:
                    if cell_index not in comp_cells:
                        stack.append(("c", cell_index))

        ordered_cells = sorted(comp_cells, key=lambda i: (colors[i], i))
        relabel = {old: new for new, old in enumerate(ordered_cells)}
        component_colors = tuple(colors[i] for i in ordered_cells)
        component_edges = tuple(
            sorted(tuple(sorted(relabel[i] for i in edges[edge_index])) for edge_index in comp_edges)
        )
        components.append((component_colors, component_edges))

    return components


def abstract_incidence_payload(
    row: Dict[str, str],
    exact_limit: int = 200_000,
) -> Tuple[Tuple, bool]:
    graph = abstract_hypergraph(row)
    components = incidence_components(graph)
    if not components:
        return tuple(), True

    payloads = []
    exact = True
    for component in components:
        component_payload, component_exact = _canonical_hypergraph_payload_flat(component, exact_limit)
        payloads.append(component_payload)
        exact = exact and component_exact
    return tuple(sorted(payloads, key=repr)), exact


def abstract_incidence_signature(
    row: Dict[str, str],
    exact_limit: int = 200_000,
) -> Tuple[str, bool]:
    payload, exact = abstract_incidence_payload(row, exact_limit=exact_limit)
    signature = hashlib.sha1(repr(payload).encode("utf-8")).hexdigest()
    return signature, exact


def colored_hypergraph_isomorphic(
    left: Dict[str, str],
    right: Dict[str, str],
    exact_limit: int = 200_000,
) -> bool:
    left_sig, left_exact = abstract_incidence_signature(left, exact_limit=exact_limit)
    right_sig, right_exact = abstract_incidence_signature(right, exact_limit=exact_limit)
    return bool(left_exact and right_exact and left_sig == right_sig)


def _edge_matching_exists(
    mapped_atom_edges: Sequence[Set[int]],
    container_edges: Sequence[Set[int]],
    mode: str,
) -> bool:
    candidate_lists: List[List[int]] = []
    for mapped in mapped_atom_edges:
        if mode == "exact":
            candidates = [i for i, edge in enumerate(container_edges) if mapped == edge]
        elif mode == "minor":
            candidates = [i for i, edge in enumerate(container_edges) if mapped.issubset(edge)]
        else:
            raise ValueError(f"unknown containment mode: {mode}")
        if not candidates:
            return False
        candidate_lists.append(candidates)

    order = sorted(range(len(candidate_lists)), key=lambda i: len(candidate_lists[i]))
    used: Set[int] = set()

    def backtrack(pos: int) -> bool:
        if pos == len(order):
            return True
        edge_index = order[pos]
        for candidate in candidate_lists[edge_index]:
            if candidate in used:
                continue
            used.add(candidate)
            if backtrack(pos + 1):
                return True
            used.remove(candidate)
        return False

    return backtrack(0)


def _edge_color_counter(colors: Sequence[str], edge: Iterable[int]) -> Counter:
    return Counter(colors[i] for i in edge)


def _contains_by_edge_mapping(
    container_graph: AbstractHypergraph,
    atom_graph: AbstractHypergraph,
    mode: str,
    max_edge_assignments: int,
) -> bool:
    atom_colors, atom_edges = atom_graph
    container_colors, container_edges_tuple = container_graph
    if not atom_edges:
        return True

    container_edges = [set(edge) for edge in container_edges_tuple]
    edge_candidates: List[List[int]] = []
    for atom_edge in atom_edges:
        atom_color_counts = _edge_color_counter(atom_colors, atom_edge)
        candidates = []
        for j, container_edge in enumerate(container_edges_tuple):
            container_color_counts = _edge_color_counter(container_colors, container_edge)
            if mode == "exact":
                size_ok = len(atom_edge) == len(container_edge)
                color_ok = atom_color_counts == container_color_counts
            elif mode == "minor":
                size_ok = len(atom_edge) <= len(container_edge)
                color_ok = all(container_color_counts[color] >= count for color, count in atom_color_counts.items())
            else:
                raise ValueError(f"unknown containment mode: {mode}")
            if size_ok and color_ok:
                candidates.append(j)
        if not candidates:
            return False
        edge_candidates.append(candidates)

    atom_incidence: Dict[int, Set[int]] = defaultdict(set)
    for edge_index, edge in enumerate(atom_edges):
        for vertex in edge:
            atom_incidence[vertex].add(edge_index)

    edge_order = sorted(range(len(atom_edges)), key=lambda i: len(edge_candidates[i]))
    edge_mapping: Dict[int, int] = {}
    used_edges: Set[int] = set()
    assignments = 0

    def vertex_mapping_works() -> bool:
        active_vertices = sorted(
            atom_incidence,
            key=lambda vertex: (-len(atom_incidence[vertex]), atom_colors[vertex], vertex),
        )
        vertex_candidates: Dict[int, List[int]] = {}
        for vertex in active_vertices:
            incident_edges = [edge_mapping[edge_index] for edge_index in atom_incidence[vertex]]
            possible = set(container_edges[incident_edges[0]])
            for edge_index in incident_edges[1:]:
                possible &= container_edges[edge_index]
            filtered = [i for i in possible if container_colors[i] == atom_colors[vertex]]
            if not filtered:
                return False
            vertex_candidates[vertex] = filtered

        ordered_vertices = sorted(active_vertices, key=lambda vertex: len(vertex_candidates[vertex]))
        vertex_mapping: Dict[int, int] = {}
        used_vertices: Set[int] = set()

        def backtrack_vertex(pos: int) -> bool:
            if pos == len(ordered_vertices):
                if mode == "exact":
                    for atom_edge_index, atom_edge in enumerate(atom_edges):
                        mapped = {vertex_mapping[v] for v in atom_edge}
                        if mapped != container_edges[edge_mapping[atom_edge_index]]:
                            return False
                return True
            vertex = ordered_vertices[pos]
            for candidate in vertex_candidates[vertex]:
                if candidate in used_vertices:
                    continue
                vertex_mapping[vertex] = candidate
                used_vertices.add(candidate)
                if backtrack_vertex(pos + 1):
                    return True
                used_vertices.remove(candidate)
                del vertex_mapping[vertex]
            return False

        return backtrack_vertex(0)

    def backtrack_edge(pos: int) -> bool:
        nonlocal assignments
        if assignments > max_edge_assignments:
            return False
        if pos == len(edge_order):
            assignments += 1
            return vertex_mapping_works()
        atom_edge_index = edge_order[pos]
        for candidate in edge_candidates[atom_edge_index]:
            if candidate in used_edges:
                continue
            edge_mapping[atom_edge_index] = candidate
            used_edges.add(candidate)
            if backtrack_edge(pos + 1):
                return True
            used_edges.remove(candidate)
            del edge_mapping[atom_edge_index]
        return False

    return backtrack_edge(0)


def contains_abstract_incidence_minor(
    container: Dict[str, str],
    atom: Dict[str, str],
    mode: str = "minor",
    max_assignments: int = 50_000,
) -> bool:
    """Color-preserving abstract incidence subgraph/minor containment.

    `exact` requires each atom obligation edge to map to an equal container
    edge. `minor` allows the mapped atom edge to be a subset of a larger
    container edge, corresponding to deleting extra obligation vertices.
    """
    atom_graph = abstract_hypergraph(atom)
    container_graph = abstract_hypergraph(container)
    atom_colors, atom_edges = atom_graph
    container_colors, container_edges_tuple = container_graph
    if not atom_colors or len(atom_colors) > len(container_colors):
        return False
    if len(atom_edges) > len(container_edges_tuple):
        return False

    atom_color_counts = Counter(atom_colors)
    container_color_counts = Counter(container_colors)
    if any(container_color_counts[color] < count for color, count in atom_color_counts.items()):
        return False

    return _contains_by_edge_mapping(container_graph, atom_graph, mode, max_assignments)


def d6_orbit_features(row: Dict[str, str]) -> Dict[str, float]:
    stabilizer = max(1, as_int(row, "automorphism_group_size", 1))
    orbit_size = 12 / stabilizer
    return {
        "d6_stabilizer_order": stabilizer,
        "d6_orbit_size": int(orbit_size) if orbit_size.is_integer() else orbit_size,
        "burnside_fixed_fraction": stabilizer / 12,
    }


def all_template_cells(row: Dict[str, str]) -> Tuple[Cell, ...]:
    cells = set(row_cell_roles(row).keys())
    return tuple(sorted(cells))


def a2_coordinates(cell: Cell) -> Tuple[int, int, int]:
    q, r = cell
    return (q, r, -q - r)


def a2_support_signature(row: Dict[str, str]) -> str:
    cells = all_template_cells(row)
    if not cells:
        return "(0,0,0)"
    coords = [a2_coordinates(cell) for cell in cells]
    spans = []
    for axis in range(3):
        values = [coord[axis] for coord in coords]
        spans.append(max(values) - min(values))
    return str(tuple(sorted(spans, reverse=True)))


def a2_coxeter_diameter(row: Dict[str, str]) -> int:
    cells = all_template_cells(row)
    if len(cells) < 2:
        return 0
    diameter = 0
    for i, left in enumerate(cells):
        lq, lr, ls = a2_coordinates(left)
        for right in cells[i + 1:]:
            rq, rr, rs = a2_coordinates(right)
            diameter = max(diameter, max(abs(lq - rq), abs(lr - rr), abs(ls - rs)))
    return diameter


def hex_neighbors(cell: Cell) -> Tuple[Cell, ...]:
    return tuple(add_cell(cell, direction) for direction in HEX_DIRECTIONS)


def a2_convex_hull_cells(cells: Iterable[Cell]) -> Set[Cell]:
    cell_set = set(cells)
    if not cell_set:
        return set()
    coords = [a2_coordinates(cell) for cell in cell_set]
    q_min, q_max = min(c[0] for c in coords), max(c[0] for c in coords)
    r_min, r_max = min(c[1] for c in coords), max(c[1] for c in coords)
    s_min, s_max = min(c[2] for c in coords), max(c[2] for c in coords)
    hull: Set[Cell] = set()
    for q in range(q_min, q_max + 1):
        for r in range(r_min, r_max + 1):
            s = -q - r
            if s_min <= s <= s_max:
                hull.add((q, r))
    return hull


def a2_convex_deficit(cells: Iterable[Cell]) -> int:
    cell_set = set(cells)
    return len(a2_convex_hull_cells(cell_set) - cell_set)


def a2_dimension(cells: Iterable[Cell]) -> int:
    cell_set = set(cells)
    if len(cell_set) <= 1:
        return 0 if cell_set else -1
    coords = [a2_coordinates(cell) for cell in cell_set]
    for axis in range(3):
        if len({coord[axis] for coord in coords}) == 1:
            return 1
    return 2


def hex_components(cells: Iterable[Cell]) -> List[Set[Cell]]:
    unseen = set(cells)
    components: List[Set[Cell]] = []
    while unseen:
        start = unseen.pop()
        component = {start}
        stack = [start]
        while stack:
            cell = stack.pop()
            for neighbor in hex_neighbors(cell):
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        components.append(component)
    return components


def boundary_edge_count(cells: Iterable[Cell]) -> int:
    cell_set = set(cells)
    if not cell_set:
        return 0
    adjacencies = 0
    for cell in cell_set:
        for direction in HEX_DIRECTIONS:
            neighbor = add_cell(cell, direction)
            if neighbor in cell_set and cell < neighbor:
                adjacencies += 1
    return 6 * len(cell_set) - 2 * adjacencies


def boundary_slope_partition(cells: Iterable[Cell]) -> Tuple[int, ...]:
    cell_set = set(cells)
    counts = [0 for _ in HEX_DIRECTIONS]
    for cell in cell_set:
        for i, direction in enumerate(HEX_DIRECTIONS):
            if add_cell(cell, direction) not in cell_set:
                counts[i] += 1
    return tuple(sorted(counts, reverse=True))


def axis_line_arrangement_signature(cells: Iterable[Cell]) -> Tuple[Tuple[int, ...], ...]:
    cell_set = set(cells)
    if not cell_set:
        return tuple()
    axis_profiles = []
    for axis in range(3):
        counts = Counter(a2_coordinates(cell)[axis] for cell in cell_set)
        axis_profiles.append(tuple(sorted(counts.values(), reverse=True)))
    return tuple(sorted(axis_profiles, reverse=True))


def _bounding_rectangle(cells: Set[Cell], pad: int = 1) -> Set[Cell]:
    q_values = [q for q, _ in cells]
    r_values = [r for _, r in cells]
    q_min, q_max = min(q_values) - pad, max(q_values) + pad
    r_min, r_max = min(r_values) - pad, max(r_values) + pad
    return {(q, r) for q in range(q_min, q_max + 1) for r in range(r_min, r_max + 1)}


def hex_holes(cells: Iterable[Cell]) -> int:
    cell_set = set(cells)
    if not cell_set:
        return 0
    universe = _bounding_rectangle(cell_set, pad=1)
    complement = universe - cell_set
    q_values = [q for q, _ in universe]
    r_values = [r for _, r in universe]
    q_min, q_max = min(q_values), max(q_values)
    r_min, r_max = min(r_values), max(r_values)
    holes = 0
    unseen = set(complement)
    while unseen:
        start = unseen.pop()
        component = {start}
        touches_boundary = start[0] in (q_min, q_max) or start[1] in (r_min, r_max)
        stack = [start]
        while stack:
            cell = stack.pop()
            for neighbor in hex_neighbors(cell):
                if neighbor not in unseen:
                    continue
                unseen.remove(neighbor)
                component.add(neighbor)
                if neighbor[0] in (q_min, q_max) or neighbor[1] in (r_min, r_max):
                    touches_boundary = True
                stack.append(neighbor)
        if not touches_boundary:
            holes += 1
    return holes


def manifold_label(components: int, holes: int, dimension: int) -> str:
    if dimension < 0:
        return "empty"
    if components > 1:
        return "disconnected"
    if holes == 1:
        return "annulus"
    if holes > 1:
        return "punctured"
    if dimension == 0:
        return "point"
    if dimension == 1:
        return "geodesic"
    return "disk"


def hex_patch_topology(cells: Iterable[Cell]) -> Dict[str, object]:
    cell_set = set(cells)
    components = len(hex_components(cell_set))
    holes = hex_holes(cell_set)
    dimension = a2_dimension(cell_set)
    return {
        "hex_components": components,
        "hex_holes": holes,
        "hex_euler_characteristic": components - holes,
        "boundary_edge_count": boundary_edge_count(cell_set),
        "boundary_slope_partition": str(boundary_slope_partition(cell_set)),
        "manifold_label": manifold_label(components, holes, dimension),
    }


def embedding_manifold_features(row: Dict[str, str]) -> Dict[str, object]:
    cells = set(all_template_cells(row))
    hull = a2_convex_hull_cells(cells)
    topology = hex_patch_topology(cells)
    axis_signature = axis_line_arrangement_signature(cells)
    boundary_signature = boundary_slope_partition(cells)
    support_signature = a2_support_signature(row)
    features: Dict[str, object] = {
        "embedding_cell_count": len(cells),
        "a2_dimension": a2_dimension(cells),
        "a2_convex_area": len(hull),
        "a2_convex_deficit": len(hull - cells),
        "a2_support_signature": support_signature,
        "a2_coxeter_diameter": a2_coxeter_diameter(row),
        "axis_line_arrangement": str(axis_signature),
        "boundary_slope_partition": str(boundary_signature),
    }
    features.update(topology)
    features["conway_embedding_signature"] = repr(
        (
            features["a2_dimension"],
            features["hex_euler_characteristic"],
            features["hex_holes"],
            features["a2_convex_deficit"],
            support_signature,
            boundary_signature,
            axis_signature,
        )
    )
    return features


def transform_role_cells(cells: Iterable[RoleCell], rot: int, reflect: bool, delta: Cell) -> Tuple[RoleCell, ...]:
    out = []
    for role, q, r in cells:
        tq, tr = add_cell(transform_cell((q, r), rot=rot, reflect=reflect), delta)
        out.append((role, tq, tr))
    return tuple(sorted(out))


def transform_edges(edges: Iterable[Edge], rot: int, reflect: bool, delta: Cell) -> Tuple[Edge, ...]:
    out = []
    for edge in edges:
        out.append(tuple(sorted(add_cell(transform_cell(cell, rot=rot, reflect=reflect), delta) for cell in edge)))
    return tuple(sorted(out))


def contains_colored_subtemplate(container: Dict[str, str], atom: Dict[str, str]) -> bool:
    container_cells = set(row_colored_cells(container))
    container_edges = set(parse_edges(container.get("obligation_edges", "")))
    atom_cells = row_colored_cells(atom)
    atom_edges = parse_edges(atom.get("obligation_edges", ""))
    if not atom_cells and not atom_edges:
        return False
    if not atom_cells:
        return set(atom_edges).issubset(container_edges)

    container_by_role: Dict[str, List[Cell]] = defaultdict(list)
    for role, q, r in container_cells:
        container_by_role[role].append((q, r))

    anchor_role, anchor_q, anchor_r = atom_cells[0]
    atom_anchor = (anchor_q, anchor_r)
    for reflect in (False, True):
        for rot in range(6):
            transformed_anchor = transform_cell(atom_anchor, rot=rot, reflect=reflect)
            for container_anchor in container_by_role.get(anchor_role, []):
                delta = sub_cell(container_anchor, transformed_anchor)
                moved_cells = set(transform_role_cells(atom_cells, rot=rot, reflect=reflect, delta=delta))
                if not moved_cells.issubset(container_cells):
                    continue
                moved_edges = set(transform_edges(atom_edges, rot=rot, reflect=reflect, delta=delta))
                if moved_edges.issubset(container_edges):
                    return True
    return False


def select_atomic_representatives(
    rows: Sequence[Dict[str, str]],
    max_edges: int = 5,
    min_frequency: int = 2,
) -> List[Dict[str, str]]:
    candidates = [
        row
        for row in rows
        if as_int(row, "num_obligations") <= max_edges and as_int(row, "frequency") >= min_frequency
    ]
    candidates.sort(
        key=lambda row: (
            as_int(row, "num_obligations"),
            as_int(row, "num_obligation_vertices"),
            -as_int(row, "frequency"),
            row.get("canonical_signature", ""),
        )
    )
    return candidates


def atomic_containment_rows(rows: Sequence[Dict[str, str]], atoms: Sequence[Dict[str, str]]) -> List[Dict]:
    out: List[Dict] = []
    for row in rows:
        contained = []
        for atom in atoms:
            if atom.get("canonical_signature") == row.get("canonical_signature"):
                continue
            if contains_colored_subtemplate(row, atom):
                contained.append(atom.get("template_id", ""))
        out.append(
            {
                "template_id": row.get("template_id", ""),
                "canonical_signature": row.get("canonical_signature", ""),
                "kind": row.get("kind", ""),
                "family": row.get("family", ""),
                "tau": as_int(row, "tau"),
                "pressure": as_int(row, "pressure"),
                "num_obligations": as_int(row, "num_obligations"),
                "contained_atom_count": len(contained),
                "contained_atoms": json.dumps(contained, separators=(",", ":")),
            }
        )
    return out


def select_abstract_atomic_representatives(
    rows: Sequence[Dict[str, str]],
    max_edges: int = 5,
    min_frequency: int = 2,
    max_atoms: int = 32,
) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        if as_int(row, "num_obligations") <= max_edges:
            signature = row.get("abstract_incidence_signature", "")
            if signature:
                grouped[signature].append(row)

    atoms: List[Dict[str, str]] = []
    for signature, group in grouped.items():
        abstract_frequency = sum(as_int(row, "frequency", 1) for row in group)
        if abstract_frequency < min_frequency:
            continue
        representative = min(
            group,
            key=lambda row: (
                as_int(row, "num_obligations"),
                as_int(row, "num_obligation_vertices"),
                as_int(row, "num_attacker_stones"),
                as_int(row, "num_defender_stones"),
                row.get("canonical_signature", ""),
            ),
        )
        atom = dict(representative)
        atom["abstract_signature_frequency"] = abstract_frequency
        atom["abstract_signature_representatives"] = len(group)
        atoms.append(atom)

    atoms.sort(
        key=lambda row: (
            as_int(row, "num_obligations"),
            as_int(row, "num_obligation_vertices"),
            -as_int(row, "abstract_signature_frequency"),
            row.get("abstract_incidence_signature", ""),
        )
    )
    return atoms[:max_atoms]


def subtemplate_poset_edges(
    rows: Sequence[Dict[str, str]],
    atoms: Sequence[Dict[str, str]],
    mode: str = "minor",
) -> List[Dict[str, str]]:
    relation = "abstract_incidence_minor" if mode == "minor" else "abstract_incidence_subgraph"
    edges: List[Dict[str, str]] = []
    for row in rows:
        for atom in atoms:
            atom_id = atom.get("template_id", "")
            row_id = row.get("template_id", "")
            if atom_id == row_id:
                continue
            atom_size = (
                as_int(atom, "num_obligations"),
                as_int(atom, "num_obligation_vertices"),
            )
            row_size = (
                as_int(row, "num_obligations"),
                as_int(row, "num_obligation_vertices"),
            )
            if atom_size >= row_size:
                continue
            if contains_abstract_incidence_minor(row, atom, mode=mode):
                edges.append(
                    {
                        "atom_template_id": atom_id,
                        "container_template_id": row_id,
                        "relation": relation,
                    }
                )
    return edges


def abstract_containment_rows(
    rows: Sequence[Dict[str, str]],
    atoms: Sequence[Dict[str, str]],
    poset_edges: Sequence[Dict[str, str]],
) -> List[Dict]:
    by_container: Dict[str, List[str]] = defaultdict(list)
    for edge in poset_edges:
        by_container[edge["container_template_id"]].append(edge["atom_template_id"])

    atom_ids = {atom.get("template_id", "") for atom in atoms}
    out: List[Dict] = []
    for row in rows:
        template_id = row.get("template_id", "")
        contained = sorted(by_container.get(template_id, []))
        out.append(
            {
                "template_id": template_id,
                "canonical_signature": row.get("canonical_signature", ""),
                "abstract_incidence_signature": row.get("abstract_incidence_signature", ""),
                "kind": row.get("kind", ""),
                "family": row.get("family", ""),
                "tau": as_int(row, "tau"),
                "pressure": as_int(row, "pressure"),
                "num_obligations": as_int(row, "num_obligations"),
                "is_abstract_atom": int(template_id in atom_ids),
                "contained_abstract_atom_count": len(contained),
                "contained_abstract_atoms": json.dumps(contained, separators=(",", ":")),
            }
        )
    return out


def d6_orbit_quotient_rows(rows: Sequence[Dict[str, str]]) -> List[Dict]:
    grouped: Dict[Tuple[str, str, str, int], Dict] = {}
    for row in rows:
        orbit = d6_orbit_features(row)
        key = (
            row.get("family", "") or "unknown",
            row.get("pair_shape", "") or row.get("pair_shape_D6", ""),
            a2_support_signature(row),
            int(orbit["d6_stabilizer_order"]),
        )
        if key not in grouped:
            grouped[key] = {
                "family": key[0],
                "pair_shape": key[1],
                "a2_support_signature": key[2],
                "d6_stabilizer_order": key[3],
                "templates": 0,
                "events": 0,
                "mean_d6_orbit_size": 0.0,
                "burnside_fixed_mass": 0.0,
            }
        bucket = grouped[key]
        bucket["templates"] += 1
        bucket["events"] += as_int(row, "frequency", 1)
        bucket["mean_d6_orbit_size"] += float(orbit["d6_orbit_size"])
        bucket["burnside_fixed_mass"] += float(orbit["burnside_fixed_fraction"])

    out = []
    for bucket in grouped.values():
        if bucket["templates"]:
            bucket["mean_d6_orbit_size"] = round(bucket["mean_d6_orbit_size"] / bucket["templates"], 6)
            bucket["burnside_fixed_mass"] = round(bucket["burnside_fixed_mass"], 6)
        out.append(bucket)
    out.sort(key=lambda row: (row["events"], row["templates"]), reverse=True)
    return out


def embedding_layer_summary_rows(rows: Sequence[Dict[str, str]]) -> List[Dict]:
    grouped: Dict[str, Dict] = {}
    for row in rows:
        signature = row.get("conway_embedding_signature", "")
        if signature not in grouped:
            grouped[signature] = {
                "conway_embedding_signature": signature,
                "templates": 0,
                "events": 0,
                "families": Counter(),
                "manifold_labels": Counter(),
                "mean_convex_deficit": 0.0,
                "mean_boundary_edges": 0.0,
                "mean_a2_diameter": 0.0,
            }
        bucket = grouped[signature]
        bucket["templates"] += 1
        bucket["events"] += as_int(row, "frequency", 1)
        bucket["families"][row.get("family", "unknown") or "unknown"] += 1
        bucket["manifold_labels"][row.get("manifold_label", "unknown") or "unknown"] += 1
        bucket["mean_convex_deficit"] += as_int(row, "a2_convex_deficit")
        bucket["mean_boundary_edges"] += as_int(row, "boundary_edge_count")
        bucket["mean_a2_diameter"] += as_int(row, "a2_coxeter_diameter")

    out = []
    for bucket in grouped.values():
        templates = bucket["templates"]
        row = dict(bucket)
        row["families"] = json.dumps(dict(sorted(bucket["families"].items())), separators=(",", ":"))
        row["manifold_labels"] = json.dumps(dict(sorted(bucket["manifold_labels"].items())), separators=(",", ":"))
        row["mean_convex_deficit"] = round(bucket["mean_convex_deficit"] / templates, 6)
        row["mean_boundary_edges"] = round(bucket["mean_boundary_edges"] / templates, 6)
        row["mean_a2_diameter"] = round(bucket["mean_a2_diameter"] / templates, 6)
        out.append(row)
    out.sort(key=lambda row: (row["events"], row["templates"]), reverse=True)
    return out


def cumulative_unique_counts(signatures: Sequence[str]) -> List[int]:
    seen = set()
    out: List[int] = []
    for signature in signatures:
        if signature:
            seen.add(signature)
        out.append(len(seen))
    return out


def source_span(source_counts: Dict[str, int]) -> int:
    return sum(1 for value in source_counts.values() if value > 0)


def source_entropy(source_counts: Dict[str, int]) -> float:
    total = sum(source_counts.values())
    if total <= 0:
        return 0.0
    probs = [value / total for value in source_counts.values() if value > 0]
    entropy = -sum(p * math.log(p) for p in probs)
    return entropy / math.log(len(probs)) if len(probs) > 1 else 0.0


def generality_index(source_counts: Dict[str, int]) -> float:
    """Frequency-weighted cross-source recurrence score."""
    total = sum(source_counts.values())
    if total <= 0:
        return 0.0
    span = source_span(source_counts)
    return math.log1p(total) * (1.0 + source_entropy(source_counts)) * math.sqrt(span)


def channel_label(row: Dict[str, str]) -> str:
    counts = parse_json_dict(row.get("source_counts", ""))
    frequency = as_int(row, "frequency")
    tau = as_int(row, "tau")
    kind = row.get("kind", "")
    span = source_span(counts)
    if kind == "exact" and (frequency >= 2 or span >= 2):
        return "signal"
    if span >= 2 and frequency >= 3:
        return "signal"
    if kind == "proto" and tau >= 6 and frequency <= 1 and span <= 1:
        return "reservoir"
    if frequency <= 1 and span <= 1:
        return "source-local"
    return "candidate-signal"


def integer_fingerprint(row: Dict[str, str]) -> Tuple[int, int, int, int, int, int, int, int]:
    hist = parse_json_dict(row.get("edge_size_histogram", ""))
    return (
        as_int(row, "tau"),
        as_int(row, "pressure"),
        as_int(row, "num_obligations"),
        as_int(row, "num_obligation_vertices"),
        as_int(row, "singleton_count"),
        as_int(row, "pair_edge_count"),
        int(hist.get("3", 0)),
        as_int(row, "automorphism_group_size"),
    )


def compression_summary(minimal_rows: Sequence[Dict[str, str]]) -> Dict:
    signatures = [row.get("canonical_signature", "") for row in minimal_rows]
    unique_curve = cumulative_unique_counts(signatures)
    raw = len(signatures)
    unique = unique_curve[-1] if unique_curve else 0
    return {
        "raw_events": raw,
        "canonical_templates": unique,
        "compression_ratio": raw / unique if unique else 0.0,
        "unique_curve": unique_curve,
    }


def family_source_matrix(canonical_rows: Sequence[Dict[str, str]]) -> Tuple[List[str], List[str], List[List[int]]]:
    families = sorted({row.get("family", "unknown") or "unknown" for row in canonical_rows})
    source_names = sorted(
        {
            source
            for row in canonical_rows
            for source in parse_json_dict(row.get("source_counts", "")).keys()
        }
    )
    matrix = [[0 for _ in source_names] for _ in families]
    family_index = {family: i for i, family in enumerate(families)}
    source_index = {source: i for i, source in enumerate(source_names)}
    for row in canonical_rows:
        family = row.get("family", "unknown") or "unknown"
        for source, count in parse_json_dict(row.get("source_counts", "")).items():
            matrix[family_index[family]][source_index[source]] += count
    return families, source_names, matrix


def enriched_template_rows(canonical_rows: Sequence[Dict[str, str]]) -> List[Dict]:
    out: List[Dict] = []
    for row in canonical_rows:
        counts = parse_json_dict(row.get("source_counts", ""))
        abstract_signature, abstract_exact = abstract_incidence_signature(row)
        orbit = d6_orbit_features(row)
        colors, edges = abstract_hypergraph(row)
        enriched = dict(row)
        enriched["source_span"] = source_span(counts)
        enriched["source_entropy"] = round(source_entropy(counts), 6)
        enriched["generality_index"] = round(generality_index(counts), 6)
        enriched["channel_label"] = channel_label(row)
        enriched["integer_fingerprint"] = str(integer_fingerprint(row))
        enriched["abstract_incidence_signature"] = abstract_signature
        enriched["abstract_signature_exact"] = int(abstract_exact)
        enriched["incidence_cell_count"] = len(colors)
        enriched["incidence_edge_count"] = len(edges)
        enriched["cell_color_histogram"] = json.dumps(dict(sorted(Counter(colors).items())), separators=(",", ":"))
        enriched.update(orbit)
        enriched.update(embedding_manifold_features(row))
        out.append(enriched)
    out.sort(
        key=lambda r: (
            float(r["generality_index"]),
            as_int(r, "frequency"),
            as_int(r, "tau"),
        ),
        reverse=True,
    )
    return out


def candidate_tau_rows(candidate_rows: Sequence[Dict[str, str]]) -> List[Dict]:
    out: List[Dict] = []
    for row in candidate_rows:
        obligations = as_int(row, "num_obligations")
        tau = as_int(row, "tau_exact")
        naive_pressure = max(0, obligations - 2)
        exact_pressure = as_int(row, "pressure_exact")
        out.append(
            {
                "num_obligations": obligations,
                "tau": tau,
                "naive_pressure": naive_pressure,
                "exact_pressure": exact_pressure,
                "overcount": naive_pressure - exact_pressure,
                "terminal": as_int(row, "terminal"),
            }
        )
    return out


def shape_counts(rows: Sequence[Dict[str, str]]) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        shape = row.get("pair_shape", "") or row.get("pair_shape_D6", "")
        if shape:
            counts[shape] += as_int(row, "frequency", 1)
    return counts


def sequence_table(enriched_rows: Sequence[Dict]) -> Dict:
    tau_sequence = [as_int(row, "tau") for row in enriched_rows[:48]]
    obligation_sequence = [as_int(row, "num_obligations") for row in enriched_rows[:48]]
    vertex_sequence = [as_int(row, "num_obligation_vertices") for row in enriched_rows[:48]]
    automorphism_sequence = [as_int(row, "automorphism_group_size") for row in enriched_rows[:48]]
    fingerprints = [row["integer_fingerprint"] for row in enriched_rows[:48]]
    return {
        "tau_by_generality_rank": tau_sequence,
        "obligations_by_generality_rank": obligation_sequence,
        "vertices_by_generality_rank": vertex_sequence,
        "automorphisms_by_generality_rank": automorphism_sequence,
        "fingerprints_by_generality_rank": fingerprints,
    }


def apply_nature_style() -> None:
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams["font.size"] = 7.5
    plt.rcParams["axes.spines.right"] = False
    plt.rcParams["axes.spines.top"] = False
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["legend.frameon"] = False


def add_panel_label(ax, label: str) -> None:
    ax.text(
        -0.08,
        1.04,
        label,
        transform=ax.transAxes,
        fontsize=9,
        fontweight="bold",
        ha="left",
        va="bottom",
        color=PALETTE["neutral_black"],
    )


def make_atlas_figure(
    candidate_rows: Sequence[Dict[str, str]],
    minimal_rows: Sequence[Dict[str, str]],
    canonical_rows: Sequence[Dict[str, str]],
    enriched_rows: Sequence[Dict],
    containment_rows: Sequence[Dict],
    out_prefix: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    apply_nature_style()
    fig = plt.figure(figsize=(7.25, 8.4), constrained_layout=False)
    grid = fig.add_gridspec(4, 2, height_ratios=[1.05, 1.0, 1.05, 0.95], hspace=0.54, wspace=0.34)

    tau_rows = candidate_tau_rows(candidate_rows)
    ax = fig.add_subplot(grid[0, 0])
    if tau_rows:
        xs = [r["num_obligations"] for r in tau_rows]
        ys = [r["tau"] for r in tau_rows]
        colors = [r["overcount"] for r in tau_rows]
        ax.scatter(xs, ys, c=colors, s=10, alpha=0.55, cmap="coolwarm", linewidth=0)
    ax.plot([0, max([r["num_obligations"] for r in tau_rows] + [3])], [0, max([r["num_obligations"] for r in tau_rows] + [3])], color=PALETTE["neutral_light"], lw=0.8, ls="--")
    ax.set_xlabel("urgent obligations")
    ax.set_ylabel("exact tau")
    ax.set_title("Threat count is not pressure")
    add_panel_label(ax, "a")

    ax = fig.add_subplot(grid[0, 1])
    comp = compression_summary(minimal_rows)
    if comp["unique_curve"]:
        raw_x = list(range(1, len(comp["unique_curve"]) + 1))
        ax.plot(raw_x, raw_x, color=PALETTE["neutral_light"], lw=1.0, ls="--", label="raw")
        ax.plot(raw_x, comp["unique_curve"], color=PALETTE["blue_main"], lw=1.8, label="D6 primitives")
    ax.set_xlabel("positive events")
    ax.set_ylabel("unique templates")
    ax.set_title("D6 compression curve")
    ax.legend(loc="upper left", fontsize=6)
    add_panel_label(ax, "b")

    ax = fig.add_subplot(grid[1, 0])
    freqs = [as_int(row, "frequency") for row in canonical_rows]
    freqs = sorted([f for f in freqs if f > 0], reverse=True)
    if freqs:
        ax.plot(range(1, len(freqs) + 1), freqs, marker="o", ms=2.5, lw=1.1, color=PALETTE["teal"])
        ax.set_yscale("log")
    ax.set_xlabel("template rank")
    ax.set_ylabel("frequency")
    ax.set_title("Primitive rank-frequency")
    add_panel_label(ax, "c")

    ax = fig.add_subplot(grid[1, 1])
    families, sources, matrix = family_source_matrix(canonical_rows)
    if matrix and sources:
        arr = np.array(matrix, dtype=float)
        order = np.argsort(arr.sum(axis=1))[::-1][:8]
        arr = arr[order]
        labels = [families[i] for i in order]
        im = ax.imshow(arr, aspect="auto", cmap="Blues")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels)
        ax.set_xticks(range(len(sources)))
        ax.set_xticklabels(sources, rotation=35, ha="right")
        fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="events")
    ax.set_title("Source recurrence by family")
    add_panel_label(ax, "d")

    ax = fig.add_subplot(grid[2, 0])
    channels = Counter(row["channel_label"] for row in enriched_rows)
    labels = list(channels.keys())
    if labels:
        values = [channels[label] for label in labels]
        colors = [
            PALETTE["blue_main"] if label == "signal" else PALETTE["red_strong"] if label == "reservoir" else PALETTE["neutral_mid"]
            for label in labels
        ]
        ax.bar(range(len(labels)), values, color=colors, edgecolor="black", linewidth=0.5)
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("templates")
    ax.set_title("Signal-channel split")
    add_panel_label(ax, "e")

    ax = fig.add_subplot(grid[2, 1])
    if enriched_rows:
        x = [as_int(row, "frequency") for row in enriched_rows]
        y = [as_float(row, "generality_index") for row in enriched_rows]
        size = [12 + 8 * as_int(row, "tau") for row in enriched_rows]
        color = [as_int(row, "source_span") for row in enriched_rows]
        ax.scatter(x, y, s=size, c=color, cmap="viridis", alpha=0.72, edgecolor="white", linewidth=0.3)
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xlabel("frequency")
    ax.set_ylabel("generality index")
    ax.set_title("Template generality landscape")
    add_panel_label(ax, "f")

    ax = fig.add_subplot(grid[3, 0])
    if containment_rows:
        contain_counts = Counter(
            int(row.get("contained_abstract_atom_count", row.get("contained_atom_count", 0)))
            for row in containment_rows
        )
        xs = sorted(contain_counts)
        ax.bar(xs, [contain_counts[x] for x in xs], color=PALETTE["violet"], edgecolor="black", linewidth=0.4)
    ax.set_xlabel("contained atoms")
    ax.set_ylabel("templates")
    ax.set_title("Abstract minor recursion")
    add_panel_label(ax, "g")

    ax = fig.add_subplot(grid[3, 1])
    if containment_rows:
        by_family: Dict[str, List[int]] = defaultdict(list)
        for row in containment_rows:
            by_family[row.get("family", "unknown")].append(
                int(row.get("contained_abstract_atom_count", row.get("contained_atom_count", 0)))
            )
        items = sorted(by_family.items(), key=lambda kv: sum(kv[1]), reverse=True)[:8]
        labels = [family for family, _ in items]
        means = [float(np.mean(values)) for _, values in items]
        ax.bar(range(len(items)), means, color=PALETTE["gold"], edgecolor="black", linewidth=0.4)
        ax.set_xticks(range(len(items)))
        ax.set_xticklabels(labels, rotation=25, ha="right")
    ax.set_ylabel("mean atoms/template")
    ax.set_title("Atomic load by family")
    add_panel_label(ax, "h")

    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{out_prefix}.svg", bbox_inches="tight")
    fig.savefig(f"{out_prefix}.pdf", bbox_inches="tight")
    fig.savefig(f"{out_prefix}.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_conjecture_report(
    run_path: Path,
    out_path: Path,
    summary: Dict,
    enriched_rows: Sequence[Dict],
    containment_rows: Sequence[Dict],
    comp: Dict,
    sequences: Dict,
) -> None:
    top = enriched_rows[:10]
    channel_counts = Counter(row["channel_label"] for row in enriched_rows)
    fingerprint_count = len({row["integer_fingerprint"] for row in enriched_rows})
    abstract_count = len({row.get("abstract_incidence_signature", "") for row in enriched_rows if row.get("abstract_incidence_signature")})
    embedding_count = len({row.get("conway_embedding_signature", "") for row in enriched_rows if row.get("conway_embedding_signature")})
    family_count = len({row.get("family", "") for row in enriched_rows})
    exact_signal = sum(1 for row in enriched_rows if row["channel_label"] == "signal" and row.get("kind") == "exact")
    proto_reservoir = sum(1 for row in enriched_rows if row["channel_label"] == "reservoir" and row.get("kind") == "proto")
    recursive_templates = sum(
        1
        for row in containment_rows
        if int(row.get("contained_abstract_atom_count", row.get("contained_atom_count", 0))) > 0
    )
    recursive_rate = recursive_templates / len(containment_rows) if containment_rows else 0.0
    stabilizers = Counter(as_int(row, "d6_stabilizer_order", 1) for row in enriched_rows)
    manifold_counts = Counter(row.get("manifold_label", "unknown") for row in enriched_rows)
    exact_abstract = sum(1 for row in enriched_rows if as_int(row, "abstract_signature_exact", 0))
    text = f"""# Primitive Template Atlas Notes

Run analysed: `{run_path}`

## Headline Measurements

- Raw positive events: {comp['raw_events']}
- Canonical templates: {comp['canonical_templates']}
- Compression ratio: {comp['compression_ratio']:.3f}
- Fingerprint compression: {len(enriched_rows)} templates -> {fingerprint_count} integer fingerprints
- Abstract incidence compression: {len(enriched_rows)} templates -> {abstract_count} colored hypergraph signatures
- Conway embedding compression: {len(enriched_rows)} templates -> {embedding_count} spatial signatures
- Family compression: {len(enriched_rows)} templates -> {family_count} motif families
- Channel labels: {dict(channel_counts)}
- Exact signal templates: {exact_signal}
- Proto reservoir templates: {proto_reservoir}
- Templates containing abstract minor atoms: {recursive_templates}/{len(containment_rows)} ({recursive_rate:.1%})
- Abstract signatures exact/fallback: {exact_abstract}/{len(enriched_rows)} exact
- D6 stabilizer orders: {dict(stabilizers)}
- Embedding manifold labels: {dict(manifold_counts)}

## Working Conjectures

1. **Template signal-channel conjecture.** Cross-source exact primitives are the tactical signal channel. They are small, recurrent, and visible to deeper search.
2. **Proto-reservoir conjecture.** Large high-tau proto templates that occur once are analogous to reservoir modes: locally high-energy but not yet demonstrably general.
3. **Rail-to-bridge spectral cascade.** Rail-like proto pressure is an early mode; bridge and kink motifs are later transfer modes that convert pressure into terminal obligations.
4. **Conway molecule conjecture.** Primitive templates behave like tactical molecules: most mined positions decompose into a small periodic table of rail, bridge, fork, and kink atoms.
5. **Sloane fingerprint conjecture.** The sequence `(tau, pressure, edges, vertices, singletons, pairs, triples, automorphisms)` is a compact integer fingerprint for template families.
6. **Two-level atlas conjecture.** Coordinate-level primitive templates may remain abundant, while fingerprint-level and family-level motifs form the finite tactical alphabet.
7. **Atomic containment conjecture.** If a large fraction of one-off templates contains a recurring abstract incidence minor, the apparent template explosion is recursive composition rather than genuinely new tactics.
8. **A2 support conjecture.** The natural symmetry object is the affine A2/Coxeter support of the hex lattice, with D6 orbit-stabilizer data as the finite point-group quotient.
9. **Embedding-layer conjecture.** Most coordinate novelty lives in the embedding of a smaller obligation core into an A2 patch; convex deficit and boundary words measure the embedding complexity.

## Top General Templates

| rank | template | channel | kind | tau | freq | span | family | fingerprint |
|---:|---|---|---|---:|---:|---:|---|---|
"""
    for i, row in enumerate(top, start=1):
        text += (
            f"| {i} | {row.get('template_id','')} | {row['channel_label']} | {row.get('kind','')} | "
            f"{row.get('tau','')} | {row.get('frequency','')} | {row['source_span']} | "
            f"{row.get('family','')} | `{row['integer_fingerprint']}` |\n"
        )
    text += f"""
## Sloane-Style Integer Sequences

```json
{json.dumps(sequences, indent=2)}
```

## Interpretation

The present evidence should be read as an atlas probe, not a final claim. Strong publication evidence requires the compression curve to bend toward a plateau and for the high-generality templates to recur across independent generators. The useful failure mode is clear: if canonical counts grow linearly with raw events, the finite-basis conjecture is false at that radius or the minimiser is too weak.

## Source Summary

```json
{json.dumps(summary, indent=2)}
```
"""
    out_path.write_text(text, encoding="utf-8")


def run_atlas(args: argparse.Namespace) -> Dict:
    run_path = Path(args.run)
    out = Path(args.out) if args.out else run_path / "atlas"
    out.mkdir(parents=True, exist_ok=True)
    data = run_path / "data"

    candidate_rows = read_csv(data / "candidate_moves.csv")
    minimal_rows = read_csv(data / "minimal_templates.csv")
    canonical_rows = read_csv(data / "canonical_templates.csv")
    if not canonical_rows:
        canonical_rows = read_csv(data / "primitive_templates.csv")
    if not minimal_rows and canonical_rows:
        minimal_rows = canonical_rows

    enriched = enriched_template_rows(canonical_rows)
    atoms = select_atomic_representatives(
        enriched,
        max_edges=args.max_atom_edges,
        min_frequency=args.min_atom_frequency,
    )
    containment = atomic_containment_rows(enriched, atoms)
    abstract_atoms = select_abstract_atomic_representatives(
        enriched,
        max_edges=args.max_atom_edges,
        min_frequency=args.min_atom_frequency,
        max_atoms=args.max_abstract_atoms,
    )
    poset = subtemplate_poset_edges(enriched, abstract_atoms, mode=args.abstract_containment_mode)
    abstract_containment = abstract_containment_rows(enriched, abstract_atoms, poset)
    d6_quotients = d6_orbit_quotient_rows(enriched)
    embedding_summary = embedding_layer_summary_rows(enriched)
    comp = compression_summary(minimal_rows)
    sequences = sequence_table(enriched)
    fingerprint_count = len({row["integer_fingerprint"] for row in enriched})
    abstract_signature_count = len(
        {row.get("abstract_incidence_signature", "") for row in enriched if row.get("abstract_incidence_signature")}
    )
    family_count = len({row.get("family", "") for row in enriched})

    enriched_fields = list(enriched[0].keys()) if enriched else [
        "template_id",
        "channel_label",
        "generality_index",
    ]
    write_csv(out / "template_signal_reservoir.csv", enriched, enriched_fields)
    write_csv(
        out / "atomic_representatives.csv",
        atoms,
        list(atoms[0].keys()) if atoms else ["template_id", "canonical_signature"],
    )
    write_csv(
        out / "atomic_containment.csv",
        containment,
        [
            "template_id",
            "canonical_signature",
            "kind",
            "family",
            "tau",
            "pressure",
            "num_obligations",
            "contained_atom_count",
            "contained_atoms",
        ],
    )
    write_csv(
        out / "abstract_atomic_representatives.csv",
        abstract_atoms,
        list(abstract_atoms[0].keys()) if abstract_atoms else ["template_id", "abstract_incidence_signature"],
    )
    write_csv(
        out / "abstract_containment.csv",
        abstract_containment,
        [
            "template_id",
            "canonical_signature",
            "abstract_incidence_signature",
            "kind",
            "family",
            "tau",
            "pressure",
            "num_obligations",
            "is_abstract_atom",
            "contained_abstract_atom_count",
            "contained_abstract_atoms",
        ],
    )
    write_csv(
        out / "subtemplate_poset.csv",
        poset,
        ["atom_template_id", "container_template_id", "relation"],
    )
    write_csv(
        out / "d6_orbit_quotients.csv",
        d6_quotients,
        [
            "family",
            "pair_shape",
            "a2_support_signature",
            "d6_stabilizer_order",
            "templates",
            "events",
            "mean_d6_orbit_size",
            "burnside_fixed_mass",
        ],
    )
    write_csv(
        out / "embedding_layer_summary.csv",
        embedding_summary,
        [
            "conway_embedding_signature",
            "templates",
            "events",
            "families",
            "manifold_labels",
            "mean_convex_deficit",
            "mean_boundary_edges",
            "mean_a2_diameter",
        ],
    )

    families, sources, matrix = family_source_matrix(canonical_rows)
    matrix_rows = []
    for family, values in zip(families, matrix):
        row = {"family": family}
        for source, value in zip(sources, values):
            row[source] = value
        matrix_rows.append(row)
    write_csv(out / "family_source_matrix.csv", matrix_rows, ["family"] + sources)

    shape_counter = shape_counts(canonical_rows)
    shape_rows = [
        {"rank": i, "pair_shape": shape, "frequency": count}
        for i, (shape, count) in enumerate(shape_counter.most_common(), start=1)
    ]
    write_csv(out / "pair_shape_spectrum.csv", shape_rows, ["rank", "pair_shape", "frequency"])

    summary = {
        "run": str(run_path),
        "candidate_rows": len(candidate_rows),
        "minimal_rows": len(minimal_rows),
        "canonical_rows": len(canonical_rows),
        "compression": {k: v for k, v in comp.items() if k != "unique_curve"},
        "fingerprint_count": fingerprint_count,
        "fingerprint_compression_ratio": len(enriched) / fingerprint_count if fingerprint_count else 0.0,
        "abstract_incidence_signature_count": abstract_signature_count,
        "abstract_incidence_compression_ratio": (
            len(enriched) / abstract_signature_count if abstract_signature_count else 0.0
        ),
        "family_count": family_count,
        "family_compression_ratio": len(enriched) / family_count if family_count else 0.0,
        "channel_counts": dict(Counter(row["channel_label"] for row in enriched)),
        "atomic_representatives": len(atoms),
        "templates_containing_atom": sum(1 for row in containment if int(row["contained_atom_count"]) > 0),
        "templates_containing_atom_rate": (
            sum(1 for row in containment if int(row["contained_atom_count"]) > 0) / len(containment)
            if containment
            else 0.0
        ),
        "abstract_atomic_representatives": len(abstract_atoms),
        "subtemplate_poset_edges": len(poset),
        "templates_containing_abstract_atom": sum(
            1 for row in abstract_containment if int(row["contained_abstract_atom_count"]) > 0
        ),
        "templates_containing_abstract_atom_rate": (
            sum(1 for row in abstract_containment if int(row["contained_abstract_atom_count"]) > 0)
            / len(abstract_containment)
            if abstract_containment
            else 0.0
        ),
        "d6_stabilizer_histogram": dict(Counter(str(as_int(row, "d6_stabilizer_order", 1)) for row in enriched)),
        "d6_mean_orbit_size": (
            sum(float(row["d6_orbit_size"]) for row in enriched) / len(enriched)
            if enriched
            else 0.0
        ),
        "burnside_fixed_fraction_sum": sum(float(row["burnside_fixed_fraction"]) for row in enriched),
        "a2_support_count": len({row.get("a2_support_signature", "") for row in enriched}),
        "conway_embedding_signature_count": len(
            {row.get("conway_embedding_signature", "") for row in enriched if row.get("conway_embedding_signature")}
        ),
        "embedding_layer_compression_ratio": (
            len(enriched)
            / len({row.get("conway_embedding_signature", "") for row in enriched if row.get("conway_embedding_signature")})
            if enriched
            else 0.0
        ),
        "manifold_label_counts": dict(Counter(row.get("manifold_label", "unknown") for row in enriched)),
        "annular_templates": sum(1 for row in enriched if row.get("manifold_label") == "annulus"),
        "mean_a2_convex_deficit": (
            sum(as_int(row, "a2_convex_deficit") for row in enriched) / len(enriched)
            if enriched
            else 0.0
        ),
        "top_generality": [
            {
                "template_id": row.get("template_id"),
                "kind": row.get("kind"),
                "tau": as_int(row, "tau"),
                "frequency": as_int(row, "frequency"),
                "source_span": row["source_span"],
                "generality_index": row["generality_index"],
                "family": row.get("family"),
                "channel_label": row["channel_label"],
                "fingerprint": row["integer_fingerprint"],
                "abstract_incidence_signature": row.get("abstract_incidence_signature"),
                "a2_support_signature": row.get("a2_support_signature"),
            }
            for row in enriched[:12]
        ],
        "sloane_sequences": sequences,
    }
    (out / "atlas_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    make_atlas_figure(
        candidate_rows,
        minimal_rows,
        canonical_rows,
        enriched,
        abstract_containment,
        out / "primitive_template_atlas",
    )
    make_conjecture_report(run_path, out / "conjectures.md", summary, enriched, abstract_containment, comp, sequences)
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Path to a template miner run directory")
    parser.add_argument("--out", default="", help="Output folder; defaults to RUN/atlas")
    parser.add_argument("--max-atom-edges", type=int, default=5)
    parser.add_argument("--min-atom-frequency", type=int, default=2)
    parser.add_argument("--max-abstract-atoms", type=int, default=32)
    parser.add_argument(
        "--abstract-containment-mode",
        choices=("minor", "exact"),
        default="minor",
        help="Use exact abstract subhypergraph containment or incidence-minor containment",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    summary = run_atlas(args)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
