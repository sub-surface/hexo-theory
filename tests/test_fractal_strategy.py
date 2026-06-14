from engine import WIN_LENGTH
from engine.fractal_strategy import (
    generate_strategy_fractal,
    verify_fractal_wins,
    winning_lines_for_board,
)


def test_base_fractal_contains_verified_length_six_wins():
    fractal = generate_strategy_fractal(depth=0)

    assert fractal.depth == 0
    assert len(fractal.motifs) == 3
    assert all(len(motif.cells) == WIN_LENGTH for motif in fractal.motifs)
    assert verify_fractal_wins(fractal)


def test_deeper_fractal_grows_by_six_eisenstein_branches():
    fractal = generate_strategy_fractal(depth=2, inflation=5)
    levels = [motif.level for motif in fractal.motifs]

    assert levels.count(0) == 3
    assert levels.count(1) == 18
    assert levels.count(2) == 108
    assert len(fractal.shell_counts) == 3
    assert verify_fractal_wins(fractal)


def test_winning_line_detector_matches_generated_motifs():
    fractal = generate_strategy_fractal(depth=1)

    lines = winning_lines_for_board(fractal.board, player=1)
    motif_lines = {motif.cells for motif in fractal.motifs}

    assert motif_lines <= set(lines)
