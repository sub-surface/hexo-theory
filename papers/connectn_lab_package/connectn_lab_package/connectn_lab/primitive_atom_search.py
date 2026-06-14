from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, permutations, product
from typing import Iterable, Mapping

from .atoms import canonical_atom_key
from .hypergraph import (
    Edge,
    connected_components,
    display_tau,
    exact_hitting_number,
    fingerprint,
    fractional_hitting_number,
    normalise_edges,
    support,
    tau_exceeds,
)
from .lattices import Cell, LatticeSpec
from .progressions import all_progressions


@dataclass(frozen=True)
class DeficitCandidate:
    """One possible urgent obligation from a concrete winning progression."""

    edge: Edge
    line: tuple[Cell, ...]
    black: frozenset[Cell]


@dataclass(frozen=True)
class PrimitiveAtomRecord:
    lattice: str
    k: int
    p: int
    radius: int
    obligations: int
    support_size: int
    tau: str
    tau_star: float | None
    integrality_gap: float | None
    fingerprint: tuple
    spectral_features: Mapping[str, float | int | None]
    abstract_key: tuple
    geometric_key: tuple
    edges: tuple[tuple[Cell, ...], ...]
    witness_lines: tuple[tuple[Cell, ...], ...]


def obligation_deficit_candidates(
    lattice: LatticeSpec,
    k: int,
    p: int,
    radius: int,
    edge_sizes: Iterable[int] | None = None,
) -> tuple[DeficitCandidate, ...]:
    """Generate all missing-cell obligations supported by k-progressions.

    A candidate represents one live line where Black occupies every cell except
    the obligation edge.  Families of candidates still need a consistency check:
    no obligation-empty cell may also be required black by another line.
    """
    sizes = tuple(edge_sizes) if edge_sizes is not None else tuple(range(1, p + 1))
    seen: set[tuple[tuple[Cell, ...], tuple[Cell, ...]]] = set()
    out: list[DeficitCandidate] = []
    for line in all_progressions(lattice, k=k, radius=radius, keep_inside=True):
        line_key = tuple(sorted(line))
        line_set = frozenset(line)
        for size in sizes:
            if size <= 0 or size > min(p, k):
                continue
            for missing in combinations(line_key, size):
                edge = frozenset(missing)
                key = (tuple(sorted(edge)), line_key)
                if key in seen:
                    continue
                seen.add(key)
                out.append(DeficitCandidate(edge=edge, line=line_key, black=frozenset(line_set - edge)))
    return tuple(sorted(out, key=lambda c: (tuple(sorted(c.edge)), c.line)))


def is_consistent_deficit_family(candidates: Iterable[DeficitCandidate]) -> bool:
    empty: set[Cell] = set()
    required_black: set[Cell] = set()
    for candidate in candidates:
        if candidate.edge & required_black:
            return False
        if candidate.black & empty:
            return False
        empty.update(candidate.edge)
        required_black.update(candidate.black)
    return True


def is_edge_primitive(edges: Iterable[Iterable[Cell]], p: int) -> bool:
    """Return True when every edge is necessary for the tau > p witness."""
    es = normalise_edges(edges)
    if not tau_exceeds(es, p):
        return False
    for i in range(len(es)):
        if tau_exceeds(es[:i] + es[i + 1 :], p):
            return False
    return True


def abstract_hypergraph_key(edges: Iterable[Iterable[Cell]]) -> tuple:
    """Canonical hypergraph key independent of board coordinates.

    This is an exact canonical labelling for small supports.  For larger supports
    it restricts permutations to equal-degree vertex classes, which keeps the
    experiment usable while preserving the main atom comparisons.
    """
    es = normalise_edges(edges)
    cells = sorted(support(es))
    if not cells:
        return tuple()

    degree = {cell: 0 for cell in cells}
    for edge in es:
        for cell in edge:
            degree[cell] += 1

    if len(cells) <= 8:
        orders = permutations(cells)
    else:
        grouped: dict[int, list[Cell]] = {}
        for cell in cells:
            grouped.setdefault(degree[cell], []).append(cell)
        groups = [sorted(grouped[d]) for d in sorted(grouped, reverse=True)]
        orders = (tuple(cell for group in parts for cell in group) for parts in product(*(permutations(g) for g in groups)))

    best: tuple | None = None
    for order in orders:
        mapping = {cell: i for i, cell in enumerate(order)}
        encoded = tuple(sorted(tuple(sorted(mapping[cell] for cell in edge)) for edge in es))
        if best is None or encoded < best:
            best = encoded
    return best if best is not None else tuple()


def atom_spectral_features(edges: Iterable[Iterable[Cell]]) -> dict[str, float | int | None]:
    """Incidence-support Laplacian features for a primitive atom.

    The quantization-paper analogy used by the corpus experiment is deliberately
    modest: a self-adjoint finite graph operator produces discrete modes; local
    symmetry shows up as degeneracy; a quadratic dispersion can be tested later
    by mapping spatial eigenvalues to squared frequencies.
    """
    es = normalise_edges(edges)
    cells = sorted(support(es))
    if not cells:
        return {
            "laplacian_zero_modes": 0,
            "spectral_gap": None,
            "low_mode_degeneracy": 0,
            "spectral_radius": None,
            "quadratic_dispersion_gap": None,
        }
    try:
        import numpy as np  # type: ignore
    except Exception:
        return {
            "laplacian_zero_modes": None,
            "spectral_gap": None,
            "low_mode_degeneracy": None,
            "spectral_radius": None,
            "quadratic_dispersion_gap": None,
        }

    idx = {cell: i for i, cell in enumerate(cells)}
    adjacency = np.zeros((len(cells), len(cells)), dtype=float)
    for edge in es:
        ordered = sorted(edge)
        if len(ordered) == 1:
            continue
        for a, b in combinations(ordered, 2):
            i = idx[a]
            j = idx[b]
            adjacency[i, j] += 1.0
            adjacency[j, i] += 1.0
    degree = np.diag(adjacency.sum(axis=1))
    laplacian = degree - adjacency
    eigenvalues = np.linalg.eigvalsh(laplacian)
    eigenvalues = np.array([0.0 if abs(v) < 1e-9 else float(v) for v in eigenvalues])
    positives = [float(v) for v in eigenvalues if v > 1e-9]
    zero_modes = int(len(eigenvalues) - len(positives))
    gap = positives[0] if positives else None
    low_degeneracy = 0
    if positives:
        low_degeneracy = sum(1 for v in positives if abs(v - positives[0]) < 1e-7)
    spectral_radius = float(eigenvalues[-1]) if len(eigenvalues) else None
    quadratic_gap = (gap * gap) if gap is not None else None
    return {
        "laplacian_zero_modes": zero_modes,
        "spectral_gap": gap,
        "low_mode_degeneracy": low_degeneracy,
        "spectral_radius": spectral_radius,
        "quadratic_dispersion_gap": quadratic_gap,
    }


def _record_from_candidates(
    selected: tuple[DeficitCandidate, ...],
    lattice: LatticeSpec,
    k: int,
    p: int,
    radius: int,
) -> PrimitiveAtomRecord:
    edges = tuple(candidate.edge for candidate in selected)
    tau_cap = p + 1
    tau_value = exact_hitting_number(edges, cap=tau_cap)
    tau_star = fractional_hitting_number(edges)
    tau_exact = exact_hitting_number(edges)
    gap = tau_exact - tau_star if tau_star is not None else None
    return PrimitiveAtomRecord(
        lattice=lattice.name,
        k=k,
        p=p,
        radius=radius,
        obligations=len(edges),
        support_size=len(support(edges)),
        tau=display_tau(tau_value, cap=tau_cap),
        tau_star=tau_star,
        integrality_gap=gap,
        fingerprint=fingerprint(edges, cap=tau_cap),
        spectral_features=atom_spectral_features(edges),
        abstract_key=abstract_hypergraph_key(edges),
        geometric_key=canonical_atom_key(edges, lattice),
        edges=tuple(tuple(sorted(edge)) for edge in edges),
        witness_lines=tuple(candidate.line for candidate in selected),
    )


def mine_primitive_atoms_from_candidates(
    candidates: Iterable[DeficitCandidate],
    lattice: LatticeSpec,
    k: int,
    p: int,
    radius: int,
    max_edges: int = 6,
    max_support: int = 8,
    require_connected: bool = True,
) -> tuple[PrimitiveAtomRecord, ...]:
    """Search consistent line-deficit families for connected primitive atoms."""
    ordered = tuple(sorted(candidates, key=lambda c: (tuple(sorted(c.edge)), c.line)))
    by_geometric_key: dict[tuple, PrimitiveAtomRecord] = {}

    def dfs(
        start: int,
        selected: tuple[DeficitCandidate, ...],
        edges: tuple[Edge, ...],
        empty: frozenset[Cell],
        required_black: frozenset[Cell],
    ) -> None:
        if edges and tau_exceeds(edges, p):
            if (
                is_edge_primitive(edges, p)
                and (not require_connected or len(connected_components(edges)) == 1)
            ):
                record = _record_from_candidates(selected, lattice=lattice, k=k, p=p, radius=radius)
                by_geometric_key.setdefault(record.geometric_key, record)
            return

        if len(edges) >= max_edges:
            return

        used_edges = set(edges)
        for i in range(start, len(ordered)):
            candidate = ordered[i]
            if candidate.edge in used_edges:
                continue
            if require_connected and edges and not (candidate.edge & empty):
                continue
            new_empty = empty | candidate.edge
            if len(new_empty) > max_support:
                continue
            if candidate.edge & required_black:
                continue
            if candidate.black & empty:
                continue
            dfs(
                i + 1,
                selected + (candidate,),
                edges + (candidate.edge,),
                frozenset(new_empty),
                frozenset(required_black | candidate.black),
            )

    dfs(0, tuple(), tuple(), frozenset(), frozenset())
    return tuple(sorted(by_geometric_key.values(), key=lambda r: (r.support_size, r.obligations, r.geometric_key)))


def mine_primitive_atoms(
    lattice: LatticeSpec,
    k: int,
    p: int,
    radius: int,
    max_edges: int = 6,
    max_support: int = 8,
    require_connected: bool = True,
    edge_sizes: Iterable[int] | None = None,
) -> tuple[PrimitiveAtomRecord, ...]:
    candidates = obligation_deficit_candidates(lattice=lattice, k=k, p=p, radius=radius, edge_sizes=edge_sizes)
    return mine_primitive_atoms_from_candidates(
        candidates,
        lattice=lattice,
        k=k,
        p=p,
        radius=radius,
        max_edges=max_edges,
        max_support=max_support,
        require_connected=require_connected,
    )


def _first_consistent_witness(
    edge_family: tuple[Edge, ...],
    candidates_by_edge: Mapping[Edge, tuple[DeficitCandidate, ...]],
    max_alternatives_per_edge: int = 24,
) -> tuple[DeficitCandidate, ...] | None:
    choices = [candidates_by_edge.get(edge, tuple())[:max_alternatives_per_edge] for edge in edge_family]
    if any(not choice for choice in choices):
        return None

    def backtrack(
        index: int,
        selected: tuple[DeficitCandidate, ...],
        empty: frozenset[Cell],
        required_black: frozenset[Cell],
    ) -> tuple[DeficitCandidate, ...] | None:
        if index == len(choices):
            return selected
        for candidate in choices[index]:
            if candidate.edge & required_black:
                continue
            if candidate.black & empty:
                continue
            result = backtrack(
                index + 1,
                selected + (candidate,),
                frozenset(empty | candidate.edge),
                frozenset(required_black | candidate.black),
            )
            if result is not None:
                return result
        return None

    return backtrack(0, tuple(), frozenset(), frozenset())


def _edge_pair(a: Cell, b: Cell) -> Edge:
    return frozenset((a, b))


def _cycle_edge_family(cells: tuple[Cell, ...]) -> tuple[Edge, ...]:
    return tuple(sorted(
        (_edge_pair(cells[i], cells[(i + 1) % len(cells)]) for i in range(len(cells))),
        key=lambda e: sorted(e),
    ))


def mine_pair_graph_critical_atoms_from_candidates(
    candidates: Iterable[DeficitCandidate],
    lattice: LatticeSpec,
    k: int,
    radius: int,
    max_support: int = 5,
    max_alternatives_per_edge: int = 24,
) -> tuple[PrimitiveAtomRecord, ...]:
    """Fast p=2, pair-obligation miner for edge-critical graph atoms.

    For two-cell obligations and defender budget p=2, the first connected
    edge-critical tau>2 graph atoms are K4 and C5. This scanner looks for those
    abstract atoms in the concrete progression-deficit candidate graph, then
    validates that one line witness per edge can coexist in a legal local
    black/empty assignment.
    """
    candidates_by_edge: dict[Edge, list[DeficitCandidate]] = {}
    for candidate in candidates:
        if len(candidate.edge) != 2:
            continue
        candidates_by_edge.setdefault(candidate.edge, []).append(candidate)
    frozen_by_edge = {
        edge: tuple(sorted(edge_candidates, key=lambda c: c.line))
        for edge, edge_candidates in candidates_by_edge.items()
    }
    cells = sorted(support(frozen_by_edge))
    adjacency: dict[Cell, set[Cell]] = {cell: set() for cell in cells}
    for edge in frozen_by_edge:
        a, b = tuple(edge)
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    records: dict[tuple, PrimitiveAtomRecord] = {}
    seen_edge_families: set[tuple[tuple[Cell, ...], ...]] = set()

    def maybe_add(edge_family: tuple[Edge, ...]) -> None:
        family_key = tuple(sorted(tuple(sorted(edge)) for edge in edge_family))
        if family_key in seen_edge_families:
            return
        seen_edge_families.add(family_key)
        if len(support(edge_family)) > max_support:
            return
        if not is_edge_primitive(edge_family, p=2):
            return
        witness = _first_consistent_witness(
            edge_family,
            frozen_by_edge,
            max_alternatives_per_edge=max_alternatives_per_edge,
        )
        if witness is None:
            return
        record = _record_from_candidates(witness, lattice=lattice, k=k, p=2, radius=radius)
        records.setdefault(record.geometric_key, record)

    if max_support >= 4:
        for root in cells:
            later_neighbors = sorted(cell for cell in adjacency[root] if cell > root)
            for triple in combinations(later_neighbors, 3):
                if all(_edge_pair(a, b) in frozen_by_edge for a, b in combinations(triple, 2)):
                    maybe_add(tuple(_edge_pair(a, b) for a, b in combinations((root,) + triple, 2)))

    if max_support >= 5:
        for root in cells:
            for a in sorted(cell for cell in adjacency[root] if cell > root):
                for b in sorted(cell for cell in adjacency[a] if cell > root and cell != a and cell != root):
                    if b == a:
                        continue
                    for c in sorted(cell for cell in adjacency[b] if cell > root and cell not in {root, a, b}):
                        for d in sorted(cell for cell in adjacency[c] & adjacency[root] if cell > root and cell not in {a, b, c}):
                            cycle = (root, a, b, c, d)
                            if cycle[1] > cycle[-1]:
                                continue
                            maybe_add(_cycle_edge_family(cycle))

    return tuple(sorted(records.values(), key=lambda r: (r.support_size, r.obligations, r.geometric_key)))


def mine_pair_graph_critical_atoms(
    lattice: LatticeSpec,
    k: int,
    radius: int,
    max_support: int = 5,
    max_alternatives_per_edge: int = 24,
) -> tuple[PrimitiveAtomRecord, ...]:
    candidates = obligation_deficit_candidates(lattice=lattice, k=k, p=2, radius=radius, edge_sizes=(2,))
    return mine_pair_graph_critical_atoms_from_candidates(
        candidates,
        lattice=lattice,
        k=k,
        radius=radius,
        max_support=max_support,
        max_alternatives_per_edge=max_alternatives_per_edge,
    )


def overlap_summary(results: Mapping[str, Iterable[PrimitiveAtomRecord]]) -> dict[tuple[str, str], dict[str, float | int]]:
    key_sets = {name: {record.abstract_key for record in records} for name, records in results.items()}
    names = sorted(key_sets)
    out: dict[tuple[str, str], dict[str, float | int]] = {}
    for i, left in enumerate(names):
        for right in names[i:]:
            left_keys = key_sets[left]
            right_keys = key_sets[right]
            shared = left_keys & right_keys
            union = left_keys | right_keys
            out[(left, right)] = {
                "left_count": len(left_keys),
                "right_count": len(right_keys),
                "shared_abstract_atoms": len(shared),
                "jaccard": (len(shared) / len(union)) if union else 1.0,
            }
    return out
