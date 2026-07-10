import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hexconnect6_template_atlas.py"
spec = importlib.util.spec_from_file_location("hexconnect6_template_atlas", MODULE_PATH)
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)


def test_cumulative_unique_counts_tracks_d6_compression():
    signatures = ["a", "b", "a", "c", "b"]

    assert atlas.cumulative_unique_counts(signatures) == [1, 2, 2, 3, 3]


def test_generality_index_rewards_cross_source_recurrence():
    one_source = {"random": 5}
    three_sources = {"random": 2, "rail": 2, "selfplay": 1}

    assert atlas.source_span(three_sources) == 3
    assert atlas.generality_index(three_sources) > atlas.generality_index(one_source)


def test_channel_label_separates_signal_from_reservoir():
    signal = {
        "kind": "exact",
        "tau": "3",
        "frequency": "5",
        "source_counts": '{"random":2,"rail":1,"selfplay":2}',
    }
    reservoir = {
        "kind": "proto",
        "tau": "8",
        "frequency": "1",
        "source_counts": '{"adversarial":1}',
    }

    assert atlas.channel_label(signal) == "signal"
    assert atlas.channel_label(reservoir) == "reservoir"


def test_integer_fingerprint_is_stable_and_structural():
    row = {
        "tau": "4",
        "pressure": "2",
        "num_obligations": "7",
        "num_obligation_vertices": "11",
        "singleton_count": "1",
        "pair_edge_count": "2",
        "edge_size_histogram": '{"1":1,"2":2,"3":4}',
        "automorphism_group_size": "2",
    }

    assert atlas.integer_fingerprint(row) == (4, 2, 7, 11, 1, 2, 4, 2)


def test_colored_template_containment_discounts_translation_and_rotation():
    atom = {
        "attacker_stones": "[[0,0]]",
        "defender_stones": "[]",
        "move_stones": "[[1,0],[0,1]]",
        "obligation_edges": "[[[2,0]]]",
    }
    container = {
        "attacker_stones": "[[5,-2],[6,-2]]",
        "defender_stones": "[]",
        "move_stones": "[[5,-1],[4,-1],[3,0]]",
        "obligation_edges": "[[[5,0]],[[8,-2]]]",
    }

    assert atlas.contains_colored_subtemplate(container, atom)


def test_select_atomic_representatives_uses_frequency_and_size():
    rows = [
        {"template_id": "large", "frequency": "5", "num_obligations": "8", "canonical_signature": "l"},
        {"template_id": "atom", "frequency": "2", "num_obligations": "3", "canonical_signature": "a"},
        {"template_id": "rare", "frequency": "1", "num_obligations": "2", "canonical_signature": "r"},
    ]

    atoms = atlas.select_atomic_representatives(rows, max_edges=4, min_frequency=2)

    assert [row["template_id"] for row in atoms] == ["atom"]


def test_abstract_colored_hypergraph_signature_ignores_coordinates():
    first = {
        "attacker_stones": "[[0,0]]",
        "defender_stones": "[]",
        "move_stones": "[[1,0],[0,1]]",
        "obligation_edges": "[[[2,0],[2,1]],[[2,0],[3,0]]]",
    }
    second = {
        "attacker_stones": "[[10,7]]",
        "defender_stones": "[]",
        "move_stones": "[[-4,8],[9,-2]]",
        "obligation_edges": "[[[5,5],[6,5]],[[6,5],[7,9]]]",
    }
    different = {
        "attacker_stones": "[[10,7]]",
        "defender_stones": "[[0,0]]",
        "move_stones": "[[-4,8],[9,-2]]",
        "obligation_edges": "[[[5,5],[6,5]],[[6,5],[7,9]]]",
    }

    sig_first, exact_first = atlas.abstract_incidence_signature(first)
    sig_second, exact_second = atlas.abstract_incidence_signature(second)
    sig_different, _ = atlas.abstract_incidence_signature(different)

    assert exact_first
    assert exact_second
    assert sig_first == sig_second
    assert sig_first != sig_different


def test_abstract_signature_is_exact_componentwise_for_repeated_edges():
    row = {
        "attacker_stones": "[[100,100],[101,100]]",
        "defender_stones": "[]",
        "move_stones": "[[102,100],[103,100]]",
        "obligation_edges": (
            "[[[0,0],[1,0],[2,0]],"
            "[[10,0],[11,0],[12,0]],"
            "[[20,0],[21,0],[22,0]],"
            "[[30,0],[31,0],[32,0]],"
            "[[40,0],[41,0],[42,0]],"
            "[[50,0],[51,0],[52,0]]]"
        ),
    }

    _, exact = atlas.abstract_incidence_signature(row, exact_limit=10)

    assert exact


def test_abstract_incidence_minor_allows_larger_container_edges():
    atom = {
        "template_id": "atom",
        "attacker_stones": "[[0,0]]",
        "defender_stones": "[]",
        "move_stones": "[[1,0],[0,1]]",
        "obligation_edges": "[[[2,0],[2,1]]]",
    }
    container = {
        "template_id": "container",
        "attacker_stones": "[[7,7]]",
        "defender_stones": "[]",
        "move_stones": "[[3,4],[4,3]]",
        "obligation_edges": "[[[5,5],[6,5],[7,5]]]",
    }
    role_mismatch = {
        "template_id": "mismatch",
        "attacker_stones": "[]",
        "defender_stones": "[[7,7]]",
        "move_stones": "[[3,4],[4,3]]",
        "obligation_edges": "[[[5,5],[6,5],[7,5]]]",
    }

    assert atlas.contains_abstract_incidence_minor(container, atom, mode="minor")
    assert not atlas.contains_abstract_incidence_minor(container, atom, mode="exact")
    assert not atlas.contains_abstract_incidence_minor(role_mismatch, atom, mode="minor")


def test_subtemplate_poset_records_abstract_minor_edges():
    atom = {
        "template_id": "atom",
        "attacker_stones": "[[0,0]]",
        "defender_stones": "[]",
        "move_stones": "[[1,0],[0,1]]",
        "obligation_edges": "[[[2,0],[2,1]]]",
        "num_obligations": "1",
        "num_obligation_vertices": "2",
        "frequency": "2",
    }
    container = {
        "template_id": "container",
        "attacker_stones": "[[7,7]]",
        "defender_stones": "[]",
        "move_stones": "[[3,4],[4,3]]",
        "obligation_edges": "[[[5,5],[6,5],[7,5]]]",
        "num_obligations": "1",
        "num_obligation_vertices": "3",
        "frequency": "1",
    }

    edges = atlas.subtemplate_poset_edges([atom, container], [atom], mode="minor")

    assert edges == [
        {
            "atom_template_id": "atom",
            "container_template_id": "container",
            "relation": "abstract_incidence_minor",
        }
    ]


def test_d6_orbit_and_a2_coxeter_features_are_invariant():
    row = {
        "automorphism_group_size": "2",
        "attacker_stones": "[[0,0],[2,0]]",
        "defender_stones": "[]",
        "move_stones": "[[0,1],[1,0]]",
        "obligation_edges": "[[[2,1],[3,1]]]",
    }
    rotated = {
        "automorphism_group_size": "2",
        "attacker_stones": "[[0,0],[0,2]]",
        "defender_stones": "[]",
        "move_stones": "[[-1,1],[0,1]]",
        "obligation_edges": "[[[ -1,3],[ -1,4]]]",
    }

    orbit = atlas.d6_orbit_features(row)

    assert orbit["d6_stabilizer_order"] == 2
    assert orbit["d6_orbit_size"] == 6
    assert orbit["burnside_fixed_fraction"] == 1 / 6
    assert atlas.a2_support_signature(row) == atlas.a2_support_signature(rotated)
