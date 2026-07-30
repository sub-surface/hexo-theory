from __future__ import annotations

import random

from death_hexo import has_win, resolve_deaths, stable_board
from experiments.run_aperiodic_repair import (
    best_sanctuary_fit,
    directional_steps,
    grow_aperiodic_game,
    height_patch,
    hostile_invasion_spectrum,
)


def test_irrational_height_patch_is_stable_and_six_free() -> None:
    patch = height_patch(12)
    assert stable_board(patch)
    assert not has_win(patch, 1)
    assert not has_win(patch, 2)


def test_height_slope_lies_in_the_safe_draw_chamber() -> None:
    magnitudes = [abs(step) for step in directional_steps().values()]
    assert min(magnitudes) > 1 / 5
    assert max(magnitudes) < 1 / 2


def test_arbitrary_erasure_order_repairs_without_death_or_win() -> None:
    target = height_patch(6)
    rng = random.Random(314159)
    deleted = rng.sample(tuple(target), 40)
    board = {cell: owner for cell, owner in target.items() if cell not in deleted}
    rng.shuffle(deleted)
    for cell in deleted:
        board[cell] = target[cell]
        assert resolve_deaths(board) == ()
        assert not has_win(board, 1)
        assert not has_win(board, 2)
    assert board == target


def test_cooperative_aperiodic_growth_is_a_legal_draw_prefix() -> None:
    frames = grow_aperiodic_game(80, search_radius=20)
    assert len(frames[-1].board_after) == 80
    assert all(frame.event is None or not frame.event.deaths for frame in frames)
    assert frames[-1].event is not None and frames[-1].event.winner is None


def test_sanctuary_fit_recovers_the_constructed_phase_family() -> None:
    assert best_sanctuary_fit(height_patch(8)) == 1.0


def test_hostile_invasion_has_an_exact_repairability_threshold() -> None:
    spectrum = hostile_invasion_spectrum()
    assert spectrum["phase_contexts"] == 38
    assert abs(
        spectrum["invader_rejection_measure"]
        - spectrum["closed_form_rejection_value"]
    ) < 1e-12
    assert abs(spectrum["repairable_measure"] - spectrum["invader_rejection_measure"]) < 1e-12
    assert spectrum["all_rejected_invasions_target_repairable"]
    assert spectrum["all_surviving_invasions_frozen_under_target_only_refill"]
