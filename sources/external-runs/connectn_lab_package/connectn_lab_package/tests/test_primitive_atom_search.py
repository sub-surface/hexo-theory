from connectn_lab.lattices import z2_diag
from connectn_lab.primitive_atom_search import (
    DeficitCandidate,
    abstract_hypergraph_key,
    atom_spectral_features,
    is_edge_primitive,
    mine_pair_graph_critical_atoms_from_candidates,
    mine_primitive_atoms_from_candidates,
    overlap_summary,
)


def _candidate(edge, i):
    edge = frozenset(edge)
    black = frozenset({(100 + i, 0), (100 + i, 1)})
    return DeficitCandidate(edge=edge, line=tuple(sorted(edge | black)), black=black)


def test_edge_primitive_detects_connected_five_cycle_for_p2():
    edges = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(1, 0), (2, 0)}),
        frozenset({(2, 0), (3, 0)}),
        frozenset({(3, 0), (4, 0)}),
        frozenset({(4, 0), (0, 0)}),
    )

    assert is_edge_primitive(edges, p=2)


def test_abstract_key_ignores_coordinate_names():
    left = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(1, 0), (2, 0)}),
        frozenset({(2, 0), (0, 0)}),
    )
    right = (
        frozenset({(9, 9), (8, 9)}),
        frozenset({(8, 9), (7, 9)}),
        frozenset({(7, 9), (9, 9)}),
    )

    assert abstract_hypergraph_key(left) == abstract_hypergraph_key(right)


def test_candidate_mining_keeps_connected_atoms_and_excludes_disconnected_sums():
    five_cycle = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(1, 0), (2, 0)}),
        frozenset({(2, 0), (3, 0)}),
        frozenset({(3, 0), (4, 0)}),
        frozenset({(4, 0), (0, 0)}),
    )
    disconnected_triad = (
        frozenset({(10, 0), (11, 0)}),
        frozenset({(12, 0), (13, 0)}),
        frozenset({(14, 0), (15, 0)}),
    )
    candidates = [_candidate(edge, i) for i, edge in enumerate(five_cycle + disconnected_triad)]

    records = mine_primitive_atoms_from_candidates(
        candidates,
        lattice=z2_diag(),
        k=6,
        p=2,
        radius=4,
        max_edges=5,
        max_support=5,
        require_connected=True,
    )

    keys = {record.abstract_key for record in records}
    assert abstract_hypergraph_key(five_cycle) in keys
    assert abstract_hypergraph_key(disconnected_triad) not in keys


def test_overlap_summary_counts_shared_abstract_atoms():
    records = mine_primitive_atoms_from_candidates(
        [_candidate(edge, i) for i, edge in enumerate((
            frozenset({(0, 0), (1, 0)}),
            frozenset({(1, 0), (2, 0)}),
            frozenset({(2, 0), (3, 0)}),
            frozenset({(3, 0), (4, 0)}),
            frozenset({(4, 0), (0, 0)}),
        ))],
        lattice=z2_diag(),
        k=6,
        p=2,
        radius=4,
        max_edges=5,
        max_support=5,
    )

    summary = overlap_summary({"left": records, "right": records})

    assert summary[("left", "right")]["shared_abstract_atoms"] == 1


def test_spectral_features_capture_cycle_degeneracy():
    edges = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(1, 0), (2, 0)}),
        frozenset({(2, 0), (3, 0)}),
        frozenset({(3, 0), (4, 0)}),
        frozenset({(4, 0), (0, 0)}),
    )

    features = atom_spectral_features(edges)

    assert features["laplacian_zero_modes"] == 1
    assert features["low_mode_degeneracy"] == 2
    assert features["spectral_gap"] > 0


def test_fast_pair_graph_miner_finds_k4_and_c5_atoms():
    k4 = (
        frozenset({(0, 0), (1, 0)}),
        frozenset({(0, 0), (2, 0)}),
        frozenset({(0, 0), (3, 0)}),
        frozenset({(1, 0), (2, 0)}),
        frozenset({(1, 0), (3, 0)}),
        frozenset({(2, 0), (3, 0)}),
    )
    c5 = (
        frozenset({(10, 0), (11, 0)}),
        frozenset({(11, 0), (12, 0)}),
        frozenset({(12, 0), (13, 0)}),
        frozenset({(13, 0), (14, 0)}),
        frozenset({(14, 0), (10, 0)}),
    )
    candidates = [_candidate(edge, i) for i, edge in enumerate(k4 + c5)]

    records = mine_pair_graph_critical_atoms_from_candidates(
        candidates,
        lattice=z2_diag(),
        k=6,
        radius=4,
        max_support=5,
    )

    keys = {record.abstract_key for record in records}
    assert abstract_hypergraph_key(k4) in keys
    assert abstract_hypergraph_key(c5) in keys
