"""connectn_lab: small tools for seeded biased Connect-n progression-hypergraph experiments."""

from .lattices import LatticeSpec, z2_rook, z2_diag, a2_hex
from .progressions import progression, cells_in_ball, all_progressions
from .hypergraph import (
    support,
    exact_hitting_number,
    display_tau,
    tau_exceeds,
    restrict_edges_to_zone,
    fingerprint,
    connected_components,
)
from .obligations import live_progressions, urgent_obligations
from .atoms import Atom, shrink_to_atom, canonical_atom_key, name_motif

__all__ = [
    "LatticeSpec", "z2_rook", "z2_diag", "a2_hex",
    "progression", "cells_in_ball", "all_progressions",
    "support", "exact_hitting_number", "display_tau", "tau_exceeds",
    "restrict_edges_to_zone", "fingerprint", "connected_components",
    "live_progressions", "urgent_obligations",
    "Atom", "shrink_to_atom", "canonical_atom_key", "name_motif",
]
