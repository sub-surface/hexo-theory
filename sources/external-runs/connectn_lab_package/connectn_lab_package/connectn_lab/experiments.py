from __future__ import annotations

from dataclasses import dataclass, asdict
from itertools import combinations
from typing import Iterable

from .lattices import LatticeSpec, Cell, a2_hex, z2_diag, z2_rook
from .hypergraph import exact_hitting_number, fractional_hitting_number, fingerprint, support, tau_exceeds
from .atoms import canonical_atom_key, make_atom, shrink_to_atom


@dataclass(frozen=True)
class GameSpec:
    lattice: LatticeSpec
    k: int
    p: int
    q: int
    seed: str = "central-root"

    @property
    def label(self) -> str:
        return f"Connect({self.lattice.name}, k={self.k}, p={self.p}, q={self.q}, seed={self.seed})"


@dataclass(frozen=True)
class AtomStats:
    game: str
    motif: str
    obligations: int
    support_size: int
    tau: str
    tau_star: float | None
    integrality_gap: float | None
    fingerprint: tuple


def stats_for_edges(spec: GameSpec, edges: Iterable[Iterable[Cell]]) -> AtomStats:
    atom_edges = shrink_to_atom(edges, p=spec.p) if tau_exceeds(edges, spec.p) else tuple(frozenset(e) for e in edges)
    atom = make_atom(atom_edges, p=spec.p, lattice=spec.lattice)
    tau_star = fractional_hitting_number(atom_edges)
    tau_num = exact_hitting_number(atom_edges) if len(support(atom_edges)) <= 12 else None
    gap = None
    if tau_star is not None and tau_num is not None:
        gap = tau_num - tau_star
    return AtomStats(
        game=spec.label,
        motif=atom.name,
        obligations=len(atom.edges),
        support_size=atom.support_size,
        tau=atom.tau_display,
        tau_star=tau_star,
        integrality_gap=gap,
        fingerprint=atom.fingerprint,
    )


def standard_specs(k_values=(5, 6), p_values=(1, 2), q_values=(1,)) -> list[GameSpec]:
    specs: list[GameSpec] = []
    for lattice in (z2_rook(), z2_diag(), a2_hex()):
        for k in k_values:
            for p in p_values:
                for q in q_values:
                    if q <= p:
                        specs.append(GameSpec(lattice=lattice, k=k, p=p, q=q))
    return specs
