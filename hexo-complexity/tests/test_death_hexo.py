from __future__ import annotations

from itertools import product

from death_hexo import (
    AXES,
    DeathHexGame,
    add,
    annihilation_bomb_position,
    execute_null_cycle,
    has_win,
    make_null_cycle_position,
    resolve_deaths,
    stable_board,
    transform_board,
    vulnerable_stones,
)
from experiments.run_death_hexo import solve_finite_line


def test_enemy_bracket_kills_central_stone() -> None:
    board = {(-1, 0): 1, (0, 0): 2, (1, 0): 1}
    assert vulnerable_stones(board) == {(0, 0)}
    assert resolve_deaths(board) == (((0, 0), 2),)
    assert board == {(-1, 0): 1, (1, 0): 1}


def test_friendly_bracket_does_not_kill() -> None:
    board = {(-1, 0): 1, (0, 0): 1, (1, 0): 1}
    assert vulnerable_stones(board) == set()
    assert resolve_deaths(board) == ()


def test_mutual_deaths_are_simultaneous() -> None:
    board = {(0, 0): 1, (1, 0): 2, (2, 0): 1, (3, 0): 2}
    assert vulnerable_stones(board) == {(1, 0), (2, 0)}
    resolve_deaths(board)
    assert board == {(0, 0): 1, (3, 0): 2}


def test_death_operator_is_idempotent_on_all_short_lines() -> None:
    for length in range(1, 8):
        for word in product((0, 1, 2), repeat=length):
            board = {(i, 0): owner for i, owner in enumerate(word) if owner}
            resolve_deaths(board)
            once = dict(board)
            assert resolve_deaths(board) == ()
            assert board == once


def test_opening_and_two_placement_turn_survive_suicide() -> None:
    game = DeathHexGame()
    assert game.make(0, 0) is not None
    assert game.current_player == 2
    assert game.opening_done

    game.board.update({(9, 0): 1, (11, 0): 1})
    first = game.make(10, 0)
    assert first is not None and first.placed_stone_died
    assert game.current_player == 2
    assert game.placements_in_turn == 1
    second = game.make(10, 0)
    assert second is not None and second.placed_stone_died
    assert game.current_player == 1
    assert game.placements_in_turn == 0


def test_white_can_invert_the_opening_in_one_turn() -> None:
    game = DeathHexGame()
    game.make(0, 0)
    game.make(-1, 0)
    event = game.make(1, 0)
    assert event is not None and event.captured == ((0, 0),)
    assert game.board == {(-1, 0): 2, (1, 0): 2}
    assert game.current_player == 1


def test_win_is_checked_after_death() -> None:
    game = DeathHexGame(opening_done=True, current_player=1)
    for q in range(5):
        game.board[(q, 0)] = 1
    game.board[(5, -1)] = 2
    game.board[(5, 1)] = 2
    event = game.make(5, 0)
    assert event is not None and event.placed_stone_died
    assert game.winner is None
    assert not has_win(game.board, 1)


def test_seven_stone_annihilation_bomb_is_legal_and_sharp() -> None:
    game, centre = annihilation_bomb_position()
    event = game.make(*centre)
    assert event is not None
    assert len(event.captured) == 6
    assert event.placed_stone_died
    assert len(event.deaths) == 7
    assert len(game.board) == 6
    assert stable_board(game.board)


def test_explicit_four_ply_null_cycle() -> None:
    before, after = execute_null_cycle(make_null_cycle_position())
    assert before == after


def test_death_rule_is_d6_equivariant() -> None:
    board = {
        (0, 0): 2,
        (-1, 0): 1,
        (1, 0): 1,
        (0, 1): 2,
        (1, -1): 1,
    }
    original_deaths = vulnerable_stones(board)
    for index in range(12):
        transformed = transform_board(board, index)
        expected = {next(iter(transform_board({cell: 1}, index))) for cell in original_deaths}
        assert vulnerable_stones(transformed) == expected


def test_each_axis_can_trigger_death() -> None:
    for axis in AXES:
        board = {add((0, 0), axis, -1): 1, (0, 0): 2, add((0, 0), axis): 1}
        assert vulnerable_stones(board) == {(0, 0)}


def test_exact_toy_exposes_second_player_win() -> None:
    ordinary = solve_finite_line(length=5, connect=3, death_rule=False)
    death = solve_finite_line(length=5, connect=3, death_rule=True)
    assert ordinary["root_outcome"] == "draw"
    assert death["root_outcome"] == "white"
    assert death["principal_variation"][-1]["terminal"] == 2
