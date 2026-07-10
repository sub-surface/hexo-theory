from __future__ import annotations

import argparse

from .lattices import a2_hex, z2_diag
from .atoms import make_atom
from .relevance import zone_report
from .progressions import cells_in_ball


def double_rail_edges():
    return (
        frozenset({(-2, 0), (-1, 0)}),
        frozenset({(-2, 1), (-1, 1)}),
        frozenset({(-1, 0), (4, 0)}),
        frozenset({(-1, 1), (4, 1)}),
        frozenset({(4, 0), (5, 0)}),
        frozenset({(4, 1), (5, 1)}),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Small demos for seeded Connect-n hypergraph experiments.")
    parser.add_argument("--demo", choices=["atom", "zone"], default="atom")
    args = parser.parse_args()
    lattice = a2_hex()
    edges = double_rail_edges()
    if args.demo == "atom":
        atom = make_atom(edges, p=2, lattice=lattice)
        print(atom)
    else:
        zone = {(-2, 0), (-1, 0), (-2, 1), (-1, 1)}
        universe = cells_in_ball(lattice, radius=6)
        print(zone_report(edges, zone=zone, p=2, universe=universe))


if __name__ == "__main__":
    main()
