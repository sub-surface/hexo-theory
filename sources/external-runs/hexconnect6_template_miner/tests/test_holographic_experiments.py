import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hexconnect6_holographic_experiments.py"
spec = importlib.util.spec_from_file_location("hexconnect6_holographic_experiments", MODULE_PATH)
holo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(holo)


def shifted_row(delta_q=0, delta_r=0):
    def shift(c):
        return [c[0] + delta_q, c[1] + delta_r]

    return {
        "template_id": "x",
        "attacker_stones": json.dumps([shift([0, 0]), shift([1, 0])]),
        "defender_stones": json.dumps([shift([0, 1])]),
        "move_stones": json.dumps([shift([2, 0]), shift([1, 1])]),
        "obligation_edges": json.dumps([[shift([3, 0]), shift([3, 1])], [shift([0, 2])]]),
    }


def test_noether_line_charge_signature_is_translation_invariant():
    assert holo.noether_line_charge_signature(shifted_row()) == holo.noether_line_charge_signature(
        shifted_row(11, -4)
    )


def test_boundary_flux_signature_is_d6_invariant():
    row = shifted_row()
    transformed = holo.transform_row_geometry(row, rot=2, reflect=True, delta=(7, -3))

    assert holo.boundary_flux_signature(row) == holo.boundary_flux_signature(transformed)


def test_holographic_signature_combines_line_and_boundary_data():
    row = shifted_row()
    signature = holo.holographic_boundary_signature(row)

    assert "line=" in signature
    assert "flux=" in signature
    assert "support=" in signature


def test_coarse_holographic_signature_is_translation_invariant_and_compresses_detail():
    row = shifted_row()
    same_boundary_type = shifted_row(20, 5)

    assert holo.coarse_holographic_signature(row) == holo.coarse_holographic_signature(same_boundary_type)
    assert len(holo.coarse_holographic_signature(row)) < len(holo.holographic_boundary_signature(row))


def test_signature_group_metrics_report_purity_and_compression():
    rows = [
        {"sig": "a", "tau": "3", "family": "rail"},
        {"sig": "a", "tau": "3", "family": "rail"},
        {"sig": "a", "tau": "4", "family": "rail"},
        {"sig": "b", "tau": "5", "family": "bridge"},
    ]

    metrics = holo.signature_group_metrics(rows, "sig", ["tau", "family"])

    assert metrics["groups"] == 2
    assert metrics["compression_ratio"] == 2.0
    assert metrics["tau_purity"] == 0.75
    assert metrics["family_purity"] == 1.0


def test_signature_prediction_metrics_use_group_majority():
    train_rows = [
        {"sig": "a", "tau": "3"},
        {"sig": "a", "tau": "3"},
        {"sig": "b", "tau": "4"},
    ]

    metrics = holo.signature_prediction_metrics(train_rows, "sig", "tau")

    assert metrics["accuracy"] == 0.666667
    assert metrics["covered_fraction"] == 0.666667
