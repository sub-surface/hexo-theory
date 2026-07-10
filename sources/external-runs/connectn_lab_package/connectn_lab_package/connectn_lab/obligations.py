from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .lattices import Cell, LatticeSpec
from .progressions import all_progressions
from .hypergraph import Edge, normalise_edges


@dataclass(frozen=True)
class LineRecord:
    cells: tuple[Cell, ...]
    attacker_count: int
    defender_count: int
    empty: frozenset[Cell]


def live_progressions(
    attacker: set[Cell],
    defender: set[Cell],
    lattice: LatticeSpec,
    k: int,
    radius: int,
) -> list[LineRecord]:
    """Extract live k-progressions with no defender stones in the line."""
    records: list[LineRecord] = []
    for line in all_progressions(lattice, k=k, radius=radius, keep_inside=True):
        s = set(line)
        d_count = len(s & defender)
        if d_count:
            continue
        a_count = len(s & attacker)
        empty = frozenset(s - attacker - defender)
        if a_count > 0:
            records.append(LineRecord(line, a_count, d_count, empty))
    return records


def urgent_obligations(
    attacker: set[Cell],
    defender: set[Cell],
    lattice: LatticeSpec,
    k: int,
    p: int,
    radius: int,
    min_attacker_count: int | None = None,
) -> tuple[Edge, ...]:
    """Build a defender obligation family from urgent live progressions.

    A line becomes an obligation when the attacker could complete it on their next
    normal turn, i.e. the number of empty cells is <= p.  The defender must hit at
    least one empty cell in each such line.
    """
    if min_attacker_count is None:
        min_attacker_count = max(1, k - p)
    out = []
    for rec in live_progressions(attacker, defender, lattice, k=k, radius=radius):
        if rec.attacker_count >= min_attacker_count and 0 < len(rec.empty) <= p:
            out.append(rec.empty)
    # Remove duplicates while preserving deterministic order.
    seen = set()
    uniq = []
    for e in normalise_edges(out):
        if e not in seen:
            seen.add(e)
            uniq.append(e)
    return tuple(uniq)
