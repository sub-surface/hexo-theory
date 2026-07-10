from connectn_lab.opening_optimality import canonical_white_openings
from connectn_lab.opening_tablebase import (
    SearchConfig,
    canonical_state_key,
    build_opening_corpus,
    estimate_tree_size,
    search_position,
    torch_rank_openings_for_solve,
)


def test_canonical_state_key_uses_d6_symmetry():
    black = frozenset({(0, 0), (1, 0)})
    white = frozenset({(0, 1)})
    rotated_black = frozenset({(0, 0), (0, 1)})
    rotated_white = frozenset({(-1, 1)})

    assert canonical_state_key(black, white, "black") == canonical_state_key(rotated_black, rotated_white, "black")


def test_search_position_returns_principal_variation_and_table_stats():
    opening = canonical_white_openings(radius=3)[0]
    config = SearchConfig(radius=3, depth=1, candidate_cells=8, k=6)

    result = search_position(
        black=frozenset({(0, 0)}),
        white=frozenset(opening.pair),
        player="black",
        config=config,
    )

    assert result.nodes > 0
    assert result.best_move is not None
    assert len(result.best_move) == 2
    assert result.principal_variation


def test_build_opening_corpus_covers_radius3_openings():
    config = SearchConfig(radius=3, depth=1, candidate_cells=7, k=6, max_tree_nodes=10_000)

    rows = build_opening_corpus(radius=3, config=config, limit=5)

    assert len(rows) == 5
    assert all(row.radius == 3 for row in rows)
    assert all(row.best_black_reply for row in rows)
    assert all(row.estimated_tree_nodes > 0 for row in rows)
    assert all(row.pruning_mode in {"none", "beam", "alpha_beta"} for row in rows)


def test_tree_estimate_and_torch_ranking_are_available():
    config = SearchConfig(radius=3, depth=3, candidate_cells=10, k=6)
    openings = canonical_white_openings(radius=3)[:6]

    estimate = estimate_tree_size(config)
    ranking = torch_rank_openings_for_solve(openings, eval_radius=3, k=6, prefer_cuda=False)

    assert estimate["naive_leaf_nodes"] > estimate["candidate_pair_branching"]
    assert ranking["rows"] == len(openings)
    assert len(ranking["solve_priority"]) == len(openings)
