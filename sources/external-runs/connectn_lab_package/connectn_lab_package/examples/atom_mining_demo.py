"""Mine and compare small forcing atoms across A2 and Cartesian grids."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab import a2_hex, z2_diag
from connectn_lab.atoms import make_atom, shrink_to_atom, name_motif
from connectn_lab.hypergraph import exact_hitting_number, display_tau, fingerprint, fractional_hitting_number, tau_exceeds


def show(title, lattice, edges, p=2):
    print("\n" + title)
    print("-" * len(title))
    atom = make_atom(edges, p=p, lattice=lattice)
    tau = exact_hitting_number(edges, cap=p + 1)
    tau_star = fractional_hitting_number(edges)
    print("lattice:", lattice.name)
    print("full motif:", atom.name)
    print("tau exact/capped:", display_tau(tau, cap=p + 1))
    print("tau > p:", tau > p)
    print("tau*:", None if tau_star is None else round(tau_star, 4))
    print("support size:", atom.support_size)
    print("fingerprint:", fingerprint(edges, cap=p + 1))
    print("canonical key:", atom.canonical_key)
    for i, e in enumerate(atom.edges, 1):
        print(f"E{i}:", sorted(e))

    if tau_exceeds(edges, p):
        witness = shrink_to_atom(edges, p=p)
        if len(witness) != len(atom.edges):
            print("minimal witness extracted:", name_motif(witness, p=p))
            for i, e in enumerate(witness, 1):
                print(f"W{i}:", sorted(e))


# Three disjoint pair obligations: the cleanest non-coverable p=2 witness.
independent_pair_triad = (
    frozenset({(0, 0), (1, 0)}),
    frozenset({(0, 1), (1, 1)}),
    frozenset({(0, 2), (1, 2)}),
)

# The Double Rail found in the HexConnect6 demo: two components, each tau=2.
double_rail = (
    frozenset({(-2, 0), (-1, 0)}),
    frozenset({(-2, 1), (-1, 1)}),
    frozenset({(-1, 0), (4, 0)}),
    frozenset({(-1, 1), (4, 1)}),
    frozenset({(4, 0), (5, 0)}),
    frozenset({(4, 1), (5, 1)}),
)

# A square-grid version of Double Rail with the same abstract incidence pattern.
square_double_rail = double_rail

if __name__ == "__main__":
    show("A2 Independent Pair Triad", a2_hex(), independent_pair_triad)
    show("A2 Double Rail", a2_hex(), double_rail)
    show("Z2-diagonal Double Rail embedding", z2_diag(), square_double_rail)
