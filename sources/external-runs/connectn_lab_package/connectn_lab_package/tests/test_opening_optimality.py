from connectn_lab.opening_optimality import (
    BLACK_OPENING_STRATEGIES,
    WHITE_SCREENING_STRATEGIES,
    analyse_opening,
    canonical_white_openings,
    torch_static_opening_features,
)


def test_canonical_white_openings_quotient_by_d6():
    openings = canonical_white_openings(radius=2)

    assert len(openings) == 19
    assert all((0, 0) not in opening.pair for opening in openings)
    assert all(opening.orbit_size <= 12 for opening in openings)


def test_opening_strategy_sets_are_asymmetric():
    assert "debt_builder" in BLACK_OPENING_STRATEGIES
    assert "screen_counter" in WHITE_SCREENING_STRATEGIES
    assert BLACK_OPENING_STRATEGIES != WHITE_SCREENING_STRATEGIES


def test_torch_static_opening_features_returns_one_row_per_opening():
    openings = canonical_white_openings(radius=2)

    features = torch_static_opening_features(openings, eval_radius=4, k=6, prefer_cuda=False)

    assert features["rows"] == len(openings)
    assert "device" in features
    assert len(features["black_bulk_pressure"]) == len(openings)
    assert max(features["white_bulk_pressure"]) > 0


def test_analyse_opening_returns_black_reply_and_rollout_metrics():
    opening = canonical_white_openings(radius=2)[0]

    record = analyse_opening(
        opening=opening,
        black_strategy="debt_builder",
        white_strategy="screen_counter",
        eval_radius=5,
        rollout_turns=3,
        candidate_limit=8,
    )

    assert record.white_pair == opening.pair
    assert len(record.black_reply) == 2
    assert record.completed_turns >= 1
    assert record.final_black_tau >= 0
