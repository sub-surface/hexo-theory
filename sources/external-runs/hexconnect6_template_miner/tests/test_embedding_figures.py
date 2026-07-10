import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hexconnect6_embedding_figures.py"
spec = importlib.util.spec_from_file_location("hexconnect6_embedding_figures", MODULE_PATH)
figs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(figs)


def test_quotient_ladder_rows_orders_from_raw_to_family():
    summary = {
        "canonical_rows": 296,
        "conway_embedding_signature_count": 206,
        "abstract_incidence_signature_count": 73,
        "fingerprint_count": 35,
        "family_count": 5,
    }

    rows = figs.quotient_ladder_rows(summary)

    assert [row["name"] for row in rows] == [
        "D6 templates",
        "embedding signatures",
        "incidence signatures",
        "integer fingerprints",
        "motif families",
    ]
    assert [row["count"] for row in rows] == [296, 206, 73, 35, 5]
    assert rows[-1]["compression_from_previous"] == 7.0


def test_manifold_distribution_counts_rows():
    rows = [
        {"manifold_label": "disk"},
        {"manifold_label": "disk"},
        {"manifold_label": "annulus"},
        {"manifold_label": ""},
    ]

    assert figs.manifold_distribution(rows) == {"disk": 2, "annulus": 1, "unknown": 1}


def test_family_atom_load_matrix_is_dense_and_sorted():
    rows = [
        {"family": "rail", "contained_abstract_atom_count": "2"},
        {"family": "rail", "contained_abstract_atom_count": "0"},
        {"family": "bridge", "contained_abstract_atom_count": "1"},
    ]

    families, loads, matrix = figs.family_atom_load_matrix(rows)

    assert families == ["rail", "bridge"]
    assert loads == [0, 1, 2]
    assert matrix == [[1, 0, 1], [0, 1, 0]]


def test_find_annular_templates_uses_manifold_label():
    rows = [
        {"template_id": "a", "manifold_label": "disk"},
        {"template_id": "b", "manifold_label": "annulus"},
    ]

    assert [row["template_id"] for row in figs.find_annular_templates(rows)] == ["b"]
