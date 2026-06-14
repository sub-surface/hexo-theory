from engine.two_move_sum import Component, best_one_move_sum, best_two_move_sum


def test_two_lukewarm_components_can_beat_one_hot_component():
    hot = (Component("hot", moves=(10.0,)),)
    warm_pair = (
        Component("warm_a", moves=(6.0,)),
        Component("warm_b", moves=(6.0,)),
    )

    assert best_one_move_sum(hot).score == 10.0
    best = best_two_move_sum(warm_pair)

    assert best.score == 12.0
    assert best.components == ("warm_a", "warm_b")


def test_two_move_sum_allows_spending_both_moves_in_one_component():
    components = (
        Component("ladder", moves=(7.0, 6.5)),
        Component("single", moves=(5.0,)),
    )

    best = best_two_move_sum(components)

    assert best.score == 13.5
    assert best.components == ("ladder", "ladder")
