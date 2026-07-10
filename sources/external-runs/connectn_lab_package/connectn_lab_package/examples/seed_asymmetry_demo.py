"""Demonstrate the conceptual difference between q=1 and q=2 seeds.

This is a representation demo rather than proof of advantage: it prints the
remaining symmetry stabiliser idea and extracts urgent obligations around a small
manually constructed position.
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab import a2_hex, z2_diag
from connectn_lab.seeds import named_seed
from connectn_lab.obligations import urgent_obligations
from connectn_lab.hypergraph import exact_hitting_number, display_tau, fingerprint


def show_seed(lattice, q):
    black = named_seed("central-root", q=q)
    # Add a small line scaffold so obligations exist for q=1/q=2 comparison.
    black |= {(2, 0), (3, 0)}
    white = {(0, 2), (2, -1)}
    obs = urgent_obligations(black, white, lattice=lattice, k=6, p=2, radius=5, min_attacker_count=3)
    tau = exact_hitting_number(obs, cap=3)
    print(f"\n{lattice.name}, q={q}")
    print("black seed/scaffold:", sorted(black))
    print("urgent obligations:", len(obs))
    print("tau capped at 3:", display_tau(tau, cap=3))
    print("fingerprint:", fingerprint(obs, cap=3))


if __name__ == "__main__":
    print("q=1 is a rooted singleton; q=2 changes material balance but still defines a local origin/scaffold.")
    for lattice in (a2_hex(), z2_diag()):
        show_seed(lattice, q=1)
        show_seed(lattice, q=2)
