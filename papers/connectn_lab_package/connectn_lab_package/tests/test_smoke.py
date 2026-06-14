from connectn_lab import a2_hex, z2_diag
from connectn_lab.hypergraph import exact_hitting_number, tau_exceeds, fingerprint
from connectn_lab.atoms import shrink_to_atom, name_motif, canonical_atom_key
from connectn_lab.relevance import zone_report
from connectn_lab.progressions import cells_in_ball, all_progressions
from connectn_lab.obligations import urgent_obligations


def test_tau_threshold():
    edges = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(0, 1), (1, 1)}),
        frozenset({(0, 2), (1, 2)}),
    )
    assert exact_hitting_number(edges) == 3
    assert tau_exceeds(edges, 2)
    assert name_motif(edges, p=2) == "Independent Pair Triad"


def test_double_rail_zone_failure():
    edges = (
        frozenset({(-2, 0), (-1, 0)}),
        frozenset({(-2, 1), (-1, 1)}),
        frozenset({(-1, 0), (4, 0)}),
        frozenset({(-1, 1), (4, 1)}),
        frozenset({(4, 0), (5, 0)}),
        frozenset({(4, 1), (5, 1)}),
    )
    assert name_motif(edges, p=2) == "Double Rail"
    bad_zone = {(-2, 0), (-1, 0)}
    report = zone_report(edges, bad_zone, p=2, universe=cells_in_ball(a2_hex(), 6))
    assert report.threshold_preserved is False
    assert report.missed_atom_name is not None


def test_progressions_and_obligations():
    lattice = z2_diag()
    progs = all_progressions(lattice, k=4, radius=2)
    assert progs
    black = {(0, 0), (1, 0), (2, 0), (3, 0)}
    white = {(0, 1)}
    obs = urgent_obligations(black, white, lattice=lattice, k=5, p=1, radius=5, min_attacker_count=4)
    assert any((4, 0) in e for e in obs)


def run_all():
    test_tau_threshold()
    test_double_rail_zone_failure()
    test_progressions_and_obligations()
    print("all connectn_lab smoke tests passed")


if __name__ == "__main__":
    run_all()
