"""Show why pair reduction is not enough: zones must preserve tau > p."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab import a2_hex
from connectn_lab.progressions import cells_in_ball
from connectn_lab.relevance import zone_report


double_rail = (
    frozenset({(-2, 0), (-1, 0)}),
    frozenset({(-2, 1), (-1, 1)}),
    frozenset({(-1, 0), (4, 0)}),
    frozenset({(-1, 1), (4, 1)}),
    frozenset({(4, 0), (5, 0)}),
    frozenset({(4, 1), (5, 1)}),
)

if __name__ == "__main__":
    lattice = a2_hex()
    universe = cells_in_ball(lattice, radius=6)

    combo_like = {c for e in double_rail for c in e}
    bad_zone = {(-2, 0), (-1, 0)}

    for name, zone in [("combo_like", combo_like), ("bad_zone", bad_zone)]:
        report = zone_report(double_rail, zone=zone, p=2, universe=universe)
        print("\n" + name)
        print("-" * len(name))
        print(report)
        if report.missed_atom_name:
            print("missed atom:", report.missed_atom_name)
            for i, e in enumerate(report.missed_atom_edges, 1):
                print(f"M{i}:", sorted(e))
