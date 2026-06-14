"""
Tests for engine/cgt.py threat-Hackenbush approximations.

Run: python -m pytest tests/test_cgt.py -v
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import HexGame
from engine.cgt import (
    component_summaries,
    move_rank_percentile,
    position_summary,
    temperature_map,
)


def _manual_game(stones: dict[tuple[int, int], int], current_player: int = 1) -> HexGame:
    g = HexGame()
    g.board = dict(stones)
    g.move_history = list(stones)
    g.player_history = list(stones.values())
    g.current_player = current_player
    g.placements_in_turn = 0
    g.winner = None
    g.candidates = set()
    for q, r in g.board:
        for dq, dr in ((1, 0), (0, 1), (1, -1), (-1, 0), (0, -1), (-1, 1)):
            c = (q + dq, r + dr)
            if c not in g.board:
                g.candidates.add(c)
    return g


def test_immediate_win_cell_is_hottest_for_current_player():
    stones = {(i, 0): 1 for i in range(5)}
    stones.update({(10, i): 2 for i in range(4)})
    g = _manual_game(stones, current_player=1)

    temps = temperature_map(g, player=1)

    assert (5, 0) in temps
    assert temps[(5, 0)] == max(temps.values())
    assert temps[(5, 0)] > 100.0


def test_two_far_threats_decompose_into_two_hot_components():
    stones = {(i, 0): 1 for i in range(5)}
    stones.update({(100 + i, 0): 1 for i in range(5)})
    stones.update({(50, i): 2 for i in range(3)})
    g = _manual_game(stones, current_player=1)

    comps = component_summaries(g, player=1, min_temperature=100.0)

    assert len(comps) >= 2
    assert all(c.max_temperature > 100.0 for c in comps[:2])


def test_position_summary_reports_temperature_potential_correlation():
    stones = {(0, 0): 1, (1, 0): 1, (0, 1): 2, (0, 2): 2}
    g = _manual_game(stones, current_player=1)

    summary = position_summary(g, player=1)

    assert summary["candidate_count"] > 0
    assert "potential_temperature_corr" in summary
    assert "component_count" in summary
    assert summary["top_temperature"] >= 0.0


def test_move_rank_percentile_is_one_for_unique_hottest_move():
    temps = {(0, 0): 1.0, (1, 0): 10.0, (2, 0): 3.0}

    assert move_rank_percentile(temps, (1, 0)) == 1.0
    assert move_rank_percentile(temps, (0, 0)) < move_rank_percentile(temps, (2, 0))
    assert move_rank_percentile(temps, (99, 99)) == 0.0
