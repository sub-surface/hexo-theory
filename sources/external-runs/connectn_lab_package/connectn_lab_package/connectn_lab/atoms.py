from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .lattices import Cell, LatticeSpec
from .hypergraph import (
    Edge,
    connected_components,
    exact_hitting_number,
    fingerprint,
    normalise_edges,
    support,
    tau_exceeds,
)


@dataclass(frozen=True)
class Atom:
    name: str
    edges: tuple[Edge, ...]
    p: int
    tau_display: str
    fingerprint: tuple
    support_size: int
    components: int
    canonical_key: tuple | None = None


def shrink_to_atom(edges: Iterable[Iterable[Cell]], p: int) -> tuple[Edge, ...]:
    """Greedily remove obligations while preserving tau > p.

    This returns a small witness, not a proof of global minor minimality under all
    edge orders.  Repeated randomised passes can be added for heavier searches.
    """
    current = list(normalise_edges(edges))
    changed = True
    while changed:
        changed = False
        for i in range(len(current)):
            trial = current[:i] + current[i + 1:]
            if tau_exceeds(trial, p):
                current = trial
                changed = True
                break
    return tuple(current)


def canonical_atom_key(edges: Iterable[Iterable[Cell]], lattice: LatticeSpec) -> tuple:
    """Canonicalise an obligation hypergraph up to lattice symmetries/translation.

    Each transformed edge set is translated to origin by global support minimum;
    edges are sorted by their cells.  This is enough for small experimental atlas
    keys.  Larger work may need graph-isomorphism canonical labelling.
    """
    es = normalise_edges(edges)
    variants = []
    for transform in lattice.symmetries:
        transformed_edges = [frozenset(transform(c) for c in e) for e in es]
        sup = support(transformed_edges)
        if not sup:
            variants.append(tuple())
            continue
        min_x = min(x for x, _ in sup)
        min_y = min(y for _, y in sup)
        norm_edges = []
        for e in transformed_edges:
            norm_edges.append(tuple(sorted((x - min_x, y - min_y) for x, y in e)))
        variants.append(tuple(sorted(norm_edges)))
    return min(variants)


def _all_disjoint(edges: tuple[Edge, ...]) -> bool:
    cells: set[Cell] = set()
    for e in edges:
        if cells & e:
            return False
        cells.update(e)
    return True


def name_motif(edges: Iterable[Iterable[Cell]], p: int = 2) -> str:
    es = normalise_edges(edges)
    sizes = sorted(len(e) for e in es)
    comps = connected_components(es)
    if len(es) == p + 1 and all(len(e) == 1 for e in es):
        return "Independent Singleton Triad" if p == 2 else f"Independent Singleton {p+1}-ad"
    if len(es) == p + 1 and len(set(sizes)) == 1 and _all_disjoint(es):
        return "Independent Pair Triad" if sizes[0] == 2 and p == 2 else f"Independent {sizes[0]}-Set {p+1}-ad"
    if (
        p == 2
        and len(es) == 6
        and all(len(e) == 2 for e in es)
        and len(comps) == 2
        and all(len(c) == 3 for c in comps)
        and all(exact_hitting_number(c) == 2 for c in comps)
    ):
        return "Double Rail"
    if exact_hitting_number(es, cap=p) > p:
        return "Unnamed Forcing Atom"
    return "Nonforcing Obligation Family"


def make_atom(edges: Iterable[Iterable[Cell]], p: int, lattice: LatticeSpec | None = None, cap: int | None = None) -> Atom:
    cap = p + 1 if cap is None else cap
    es = normalise_edges(edges)
    tau = exact_hitting_number(es, cap=cap)
    tau_disp = f">{cap}" if tau == cap + 1 else str(tau)
    return Atom(
        name=name_motif(es, p=p),
        edges=es,
        p=p,
        tau_display=tau_disp,
        fingerprint=fingerprint(es, cap=cap),
        support_size=len(support(es)),
        components=len(connected_components(es)),
        canonical_key=canonical_atom_key(es, lattice) if lattice is not None else None,
    )
