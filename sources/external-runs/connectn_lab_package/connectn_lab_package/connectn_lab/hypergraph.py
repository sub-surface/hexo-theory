from __future__ import annotations

from itertools import combinations
from typing import Iterable, Sequence

from .lattices import Cell

Edge = frozenset[Cell]


def normalise_edges(edges: Iterable[Iterable[Cell]]) -> tuple[Edge, ...]:
    return tuple(frozenset(e) for e in edges if len(frozenset(e)) > 0)


def support(edges: Iterable[Iterable[Cell]]) -> set[Cell]:
    out: set[Cell] = set()
    for e in edges:
        out.update(e)
    return out


def exact_hitting_number(edges: Iterable[Iterable[Cell]], cap: int | None = None) -> int:
    """Exact transversal number by brute force.

    If `cap` is supplied and no hitting set of size <= cap exists, returns
    `cap + 1` as a sentinel meaning `> cap`.
    """
    es = normalise_edges(edges)
    if not es:
        return 0
    cells = sorted(support(es))
    max_r = len(cells) if cap is None else min(cap, len(cells))
    for r in range(max_r + 1):
        for combo in combinations(cells, r):
            hit = set(combo)
            if all(hit & e for e in es):
                return r
    if cap is not None:
        return cap + 1
    return len(cells) + 1


def tau_exceeds(edges: Iterable[Iterable[Cell]], threshold: int) -> bool:
    return exact_hitting_number(edges, cap=threshold) > threshold


def display_tau(value: int, cap: int | None = None) -> str:
    if cap is not None and value == cap + 1:
        return f">{cap}"
    return str(value)


def restrict_edges_to_zone(edges: Iterable[Iterable[Cell]], zone: set[Cell]) -> tuple[Edge, ...]:
    """Keep only obligations fully supported in `zone`.

    This models a relevance zone that deletes candidate support outside itself.
    """
    out = []
    for e in normalise_edges(edges):
        if set(e).issubset(zone):
            out.append(e)
    return tuple(out)


def missed_edges(full_edges: Iterable[Iterable[Cell]], zone_edges: Iterable[Iterable[Cell]]) -> tuple[Edge, ...]:
    z = set(normalise_edges(zone_edges))
    return tuple(e for e in normalise_edges(full_edges) if e not in z)


def connected_components(edges: Iterable[Iterable[Cell]]) -> list[tuple[Edge, ...]]:
    es = list(normalise_edges(edges))
    if not es:
        return []
    remaining = set(range(len(es)))
    comps: list[tuple[Edge, ...]] = []
    while remaining:
        root = remaining.pop()
        stack = [root]
        comp_idx = {root}
        comp_support = set(es[root])
        changed = True
        while stack:
            i = stack.pop()
            for j in list(remaining):
                if comp_support & es[j]:
                    remaining.remove(j)
                    stack.append(j)
                    comp_idx.add(j)
                    comp_support.update(es[j])
        comps.append(tuple(es[i] for i in sorted(comp_idx)))
    return comps


def edge_overlap_signature(edges: Iterable[Iterable[Cell]]) -> tuple[int, ...]:
    es = list(normalise_edges(edges))
    sig = []
    for i in range(len(es)):
        for j in range(i + 1, len(es)):
            sig.append(len(es[i] & es[j]))
    return tuple(sorted(sig))


def fingerprint(edges: Iterable[Iterable[Cell]], cap: int | None = 3) -> tuple:
    es = normalise_edges(edges)
    deg: dict[Cell, int] = {}
    for e in es:
        for c in e:
            deg[c] = deg.get(c, 0) + 1
    tau = exact_hitting_number(es, cap=cap)
    return (
        len(es),
        tuple(sorted(len(e) for e in es)),
        tuple(sorted(deg.values(), reverse=True)),
        edge_overlap_signature(es),
        display_tau(tau, cap),
    )


def fractional_hitting_number(edges: Iterable[Iterable[Cell]]) -> float | None:
    """Compute tau* using scipy if available; otherwise return None.

    This is deliberately optional so the package stays stdlib-only.  If scipy is
    installed, it solves min sum x_v subject to sum_{v in e} x_v >= 1, x_v >= 0.
    """
    es = normalise_edges(edges)
    cells = sorted(support(es))
    if not es:
        return 0.0
    try:
        from scipy.optimize import linprog  # type: ignore
    except Exception:
        return None
    idx = {c: i for i, c in enumerate(cells)}
    c = [1.0] * len(cells)
    A_ub = []
    b_ub = []
    for e in es:
        row = [0.0] * len(cells)
        for cell in e:
            row[idx[cell]] = -1.0
        A_ub.append(row)
        b_ub.append(-1.0)
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=[(0, None)] * len(cells), method="highs")
    if not res.success:
        return None
    return float(res.fun)
