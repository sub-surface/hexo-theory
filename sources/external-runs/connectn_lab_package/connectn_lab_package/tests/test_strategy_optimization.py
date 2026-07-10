from connectn_lab.strategy_optimization import (
    count_pair_atom_witnesses,
    choose_strategy_move,
    has_connect_win,
    position_metrics,
    run_strategy_game,
)


def test_has_connect_win_on_a2_line():
    black = {(i, 0) for i in range(6)}

    assert has_connect_win(black, k=6, radius=6)


def test_count_pair_atom_witnesses_separates_k4_and_c5():
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

    counts = count_pair_atom_witnesses(k4 + c5)

    assert counts["k4"] == 1
    assert counts["c5"] == 1


def test_min_tau_strategy_blocks_two_cell_connect6_obligation():
    black = {(0, 0), (1, 0), (2, 0), (3, 0)}
    white = set()

    move = choose_strategy_move(
        strategy="min_tau",
        player="white",
        black=black,
        white=white,
        radius=6,
        k=6,
        move_size=2,
        candidate_limit=12,
    )

    assert set(move) == {(-1, 0), (4, 0)}


def test_position_metrics_include_tau_atom_and_bulk_fields():
    black = {(0, 0), (1, 0), (2, 0), (3, 0)}
    white = set()

    metrics = position_metrics(black=black, white=white, radius=6, k=6)

    assert metrics.black_tau == 2
    assert metrics.black_obligations >= 1
    assert metrics.black_bulk_pressure > 0
    assert metrics.black_family_max >= 1


def test_strategy_game_uses_seeded_one_two_two_schedule():
    result = run_strategy_game(
        black_strategy="min_bulk",
        white_strategy="min_tau",
        radius=5,
        turns=4,
        k=6,
        candidate_limit=10,
    )

    assert (0, 0) in result.black
    assert len(result.turn_records[0].white_move) == 2
    assert len(result.turn_records[0].black_move) == 2
