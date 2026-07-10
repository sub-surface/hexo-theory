import csv

from examples.connect_k_parity_experiment import run


def test_connect_k_parity_experiment_writes_artifacts(tmp_path):
    out_dir = tmp_path / "k_parity"

    run(out_dir=out_dir, k_min=3, k_max=5, opening_limit=4)

    rows = list(csv.DictReader((out_dir / "connect_k_parity.csv").open(encoding="utf-8")))

    assert [row["k"] for row in rows] == ["3", "4", "5"]
    assert (out_dir / "figures" / "tempo_and_reply_tau.png").exists()
    assert (out_dir / "figures" / "prime_composite_reply_tau.png").exists()
    assert (out_dir / "README.md").exists()
