from connectn_lab.self_play import (
    SelfPlayConfig,
    estimate_network_size,
    game_to_viewer_record,
    network_size_sweep,
    play_self_play_game,
    run_self_play_corpus,
    summarise_matchups,
)


def test_network_size_estimates_scale_with_radius():
    small = estimate_network_size(radius=3, candidate_limit=6)
    large = estimate_network_size(radius=5, candidate_limit=6)

    assert small.board_cells == 37
    assert large.board_cells > small.board_cells
    assert large.full_pair_actions > small.full_pair_actions
    assert large.factorized_policy_params > small.factorized_policy_params
    assert large.boundary_to_bulk_ratio < small.boundary_to_bulk_ratio


def test_network_size_sweep_returns_radius_rows():
    rows = network_size_sweep(radius_min=3, radius_max=5, candidate_limit=6)

    assert [row.radius for row in rows] == [3, 4, 5]
    assert all(row.recommended_architecture for row in rows)


def test_play_self_play_game_records_opening_and_metrics():
    record = play_self_play_game(
        game_id="G0001",
        black_strategy="debt_builder",
        white_strategy="screen_counter",
        radius=3,
        turns=2,
        candidate_limit=5,
        opening_id="O-demo",
        opening_pair=((-1, 0), (-1, 1)),
    )

    assert record.game_id == "G0001"
    assert record.opening_id == "O-demo"
    assert record.moves[0]["color"] == "black"
    assert record.moves[1]["color"] == "white"
    assert record.wlu in {"B", "W", "U"}
    assert record.black_stones >= 3
    assert record.white_stones >= 2


def test_run_self_play_corpus_and_summaries_compare_strategy_pairs():
    config = SelfPlayConfig(
        radius=3,
        turns=1,
        candidate_limit=5,
        opening_limit=2,
        black_strategies=("debt_builder", "hybrid"),
        white_strategies=("screen_counter", "min_tau"),
    )

    records = run_self_play_corpus(config)
    summaries = summarise_matchups(records)

    assert len(records) == 8
    assert len(summaries) == 4
    assert all(summary.games == 2 for summary in summaries)
    assert sum(summary.black_wins + summary.white_wins + summary.undecided for summary in summaries) == len(records)


def test_game_to_viewer_record_is_loadable_shape():
    record = play_self_play_game(
        game_id="G0002",
        black_strategy="attacker",
        white_strategy="min_tau",
        radius=3,
        turns=1,
        candidate_limit=5,
    )

    game = game_to_viewer_record(record)

    assert game["game_id"] == "G0002"
    assert game["moves"][0]["stones"] == [[0, 0]]
    assert game["result"] in {"black", "white", "none"}
