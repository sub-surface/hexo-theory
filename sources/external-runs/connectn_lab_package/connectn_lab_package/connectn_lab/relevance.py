from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .lattices import Cell
from .hypergraph import (
    Edge,
    exact_hitting_number,
    missed_edges,
    normalise_edges,
    restrict_edges_to_zone,
    support,
    tau_exceeds,
)
from .atoms import shrink_to_atom, name_motif


@dataclass(frozen=True)
class ZoneReport:
    tau_full: str
    tau_zone: str
    threshold_preserved: bool
    obligations_full: int
    obligations_zone: int
    obligations_missed: int
    support_full: int
    support_zone: int
    pair_reduction: float
    missed_atom_name: str | None
    missed_atom_edges: tuple[Edge, ...]


def pair_count(n: int) -> int:
    return n * (n - 1) // 2


def zone_report(edges: Iterable[Iterable[Cell]], zone: set[Cell], p: int, universe: set[Cell] | None = None, cap: int | None = None) -> ZoneReport:
    cap = p + 1 if cap is None else cap
    full = normalise_edges(edges)
    zoned = restrict_edges_to_zone(full, zone)
    full_tau = exact_hitting_number(full, cap=cap)
    zone_tau = exact_hitting_number(zoned, cap=cap)
    full_gt = full_tau > p
    zone_gt = zone_tau > p
    missed = missed_edges(full, zoned)
    missed_atom: tuple[Edge, ...] = tuple()
    missed_name: str | None = None
    if missed and tau_exceeds(missed, p):
        missed_atom = shrink_to_atom(missed, p=p)
        missed_name = name_motif(missed_atom, p=p)
    full_support = support(full)
    total_cells = len(universe) if universe is not None else len(full_support)
    denom = pair_count(total_cells) or 1
    zone_pairs = pair_count(len(zone))
    reduction = 1.0 - zone_pairs / denom
    return ZoneReport(
        tau_full=(f">{cap}" if full_tau == cap + 1 else str(full_tau)),
        tau_zone=(f">{cap}" if zone_tau == cap + 1 else str(zone_tau)),
        threshold_preserved=(full_gt == zone_gt),
        obligations_full=len(full),
        obligations_zone=len(zoned),
        obligations_missed=len(missed),
        support_full=len(full_support),
        support_zone=len(zone),
        pair_reduction=reduction,
        missed_atom_name=missed_name,
        missed_atom_edges=missed_atom,
    )
