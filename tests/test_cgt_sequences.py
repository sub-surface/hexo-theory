from engine import HexGame
from experiments.run_cgt_sequences import sequence_snapshot


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


def test_sequence_snapshot_reports_integer_invariants_and_hotness():
    game = _manual_game({(q, 0): 1 for q in range(5)})

    row = sequence_snapshot(game, agent_name="manual", game_idx=0, ply=5, player=1)

    assert row["agent"] == "manual"
    assert row["live_lines"] > 0
    assert row["hot_components"] >= 1
    assert row["max_temperature"] > 100.0
    assert row["max_temperature_ties"] >= 1
    assert row["candidate_orbit_count"] >= 1
