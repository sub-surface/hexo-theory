"""A tiny family sweep for seeded biased Connect-n hypergraph games.

This is not a full solver.  It demonstrates the data columns a larger sweep
should produce: lattice, k, p, q, motif, tau, tau*, support size, fingerprint.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dataclasses import asdict

from connectn_lab.experiments import GameSpec, stats_for_edges
from connectn_lab.lattices import a2_hex, z2_diag, z2_rook


# A generic p=2 forcing family: three independent two-cell obligations.
p2_atom = (
    frozenset({(0, 0), (1, 0)}),
    frozenset({(0, 1), (1, 1)}),
    frozenset({(0, 2), (1, 2)}),
)

# A generic p=1 forcing family: two independent singleton obligations.
p1_atom = (
    frozenset({(0, 0)}),
    frozenset({(1, 0)}),
)


def print_row(d):
    print(f"{d['game']} | {d['motif']} | obligations={d['obligations']} | support={d['support_size']} | tau={d['tau']} | tau*={d['tau_star']} | gap={d['integrality_gap']}")


if __name__ == "__main__":
    for lattice in (z2_rook(), z2_diag(), a2_hex()):
        for p, edges in [(1, p1_atom), (2, p2_atom)]:
            spec = GameSpec(lattice=lattice, k=6, p=p, q=1)
            print_row(asdict(stats_for_edges(spec, edges)))
