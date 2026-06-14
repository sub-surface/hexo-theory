from engine import HexGame
from engine.analysis import threat_cells
from engine.isomorphisms import (
    canonical_board_key,
    cube_coords,
    d6_transforms,
    live_line_incidence,
    transform_board,
)


def _manual_game(stones: dict[tuple[int, int], int], current_player: int = 1) -> HexGame:
    game = HexGame()
    game.board = dict(stones)
    game.move_history = list(stones)
    game.player_history = list(stones.values())
    game.current_player = current_player
    game.placements_in_turn = 0
    game.winner = None
    game.candidates = set()
    for q, r in game.board:
        for dq, dr in ((1, 0), (0, 1), (1, -1), (-1, 0), (0, -1), (-1, 1)):
            candidate = (q + dq, r + dr)
            if candidate not in game.board:
                game.candidates.add(candidate)
    return game


def test_cube_coordinates_sum_to_zero():
    assert cube_coords((3, -5)) == (3, -5, 2)
    assert sum(cube_coords((3, -5))) == 0


def test_d6_transforms_have_twelve_symmetries_off_axis():
    assert len(set(d6_transforms((2, 1)))) == 12


def test_canonical_board_key_identifies_rotated_copy():
    board = {(0, 0): 1, (1, 0): 1, (2, -1): 2}
    transformed = transform_board(board, transform_index=3)
    assert canonical_board_key(board) == canonical_board_key(transformed)


def test_live_line_incidence_exposes_threat_cell():
    game = _manual_game({(q, 0): 1 for q in range(5)})
    inc = live_line_incidence(game)
    assert (5, 0) in inc.empty_to_lines
    assert (5, 0) in threat_cells(game, player=1)
