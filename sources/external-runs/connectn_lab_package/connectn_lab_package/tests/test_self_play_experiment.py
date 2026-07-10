import json

from examples.self_play_experiment import run


def test_self_play_experiment_writes_viewer_loadable_corpus(tmp_path):
    out_dir = tmp_path / "self_play"

    run(
        out_dir=out_dir,
        radius=3,
        radius_to=3,
        turns=1,
        candidate_limit=5,
        opening_limit=1,
        black_strategies=("debt_builder",),
        white_strategies=("min_tau",),
    )

    corpus = json.loads((out_dir / "self_play_games.json").read_text(encoding="utf-8"))

    assert corpus["games"]
    assert corpus["games"][0]["moves"][0]["stones"] == [[0, 0]]
    assert (out_dir / "self_play_games.csv").exists()
    assert (out_dir / "strategy_matrix.csv").exists()
    assert (out_dir / "network_size_estimates.csv").exists()
    assert (out_dir / "README.md").exists()
