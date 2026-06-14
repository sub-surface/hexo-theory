"""Verified recursive strategy patterns on the HexGo lattice."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from engine import AXES, WIN_LENGTH

Cell = tuple[int, int]
Board = Mapping[Cell, int]
HEX_DIRECTIONS: tuple[Cell, ...] = (
    (1, 0),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (0, -1),
    (1, -1),
)


@dataclass(frozen=True)
class StrategyMotif:
    """One verified length-6 line motif inside a recursive strategy pattern."""

    level: int
    center: Cell
    axis: int
    cells: tuple[Cell, ...]


@dataclass(frozen=True)
class StrategyFractal:
    """A recursively generated collection of HexGo-winning motifs."""

    depth: int
    inflation: int
    player: int
    board: dict[Cell, int]
    motifs: tuple[StrategyMotif, ...]
    centers_by_level: tuple[tuple[Cell, ...], ...]
    shell_counts: tuple[int, ...]

    @property
    def dimension_estimate(self) -> float:
        return math.log(len(HEX_DIRECTIONS)) / math.log(self.inflation)


def _add(cell: Cell, vector: Cell, scale: int = 1) -> Cell:
    return (cell[0] + vector[0] * scale, cell[1] + vector[1] * scale)


def _line_from(start: Cell, axis: Cell) -> tuple[Cell, ...]:
    return tuple(_add(start, axis, i) for i in range(WIN_LENGTH))


def _next_centers(centers: tuple[Cell, ...], step: int) -> tuple[Cell, ...]:
    out: set[Cell] = set()
    for center in centers:
        for direction in HEX_DIRECTIONS:
            out.add(_add(center, direction, step))
    return tuple(sorted(out))


def generate_strategy_fractal(
    depth: int = 3,
    inflation: int = 5,
    player: int = 1,
) -> StrategyFractal:
    """
    Generate a D6-symmetric recursive pattern made of verified winning motifs.

    The output is a strategy pattern, not a legal move transcript: all stones
    belong to one player so each local motif can be checked against the win rule.
    """
    if depth < 0:
        raise ValueError("depth must be non-negative")
    if inflation < 2:
        raise ValueError("inflation must be at least 2")
    if player not in (1, 2):
        raise ValueError("player must be 1 or 2")

    board: dict[Cell, int] = {}
    motifs: list[StrategyMotif] = []
    centers_by_level: list[tuple[Cell, ...]] = []
    centers: tuple[Cell, ...] = ((0, 0),)

    for level in range(depth + 1):
        centers_by_level.append(centers)
        for center in centers:
            for axis_idx, axis in enumerate(AXES):
                cells = _line_from(center, axis)
                motifs.append(StrategyMotif(level, center, axis_idx, cells))
                for cell in cells:
                    board[cell] = player
        if level < depth:
            centers = _next_centers(centers, inflation ** (level + 1))

    return StrategyFractal(
        depth=depth,
        inflation=inflation,
        player=player,
        board=board,
        motifs=tuple(motifs),
        centers_by_level=tuple(centers_by_level),
        shell_counts=tuple(len(level_centers) for level_centers in centers_by_level),
    )


def winning_lines_for_board(board: Board, player: int = 1) -> tuple[tuple[Cell, ...], ...]:
    """Enumerate all length-6 winning windows for `player` in a finite board."""
    seen: set[tuple[int, int, int]] = set()
    lines: list[tuple[Cell, ...]] = []
    for sq, sr in board:
        if board[(sq, sr)] != player:
            continue
        for axis_idx, axis in enumerate(AXES):
            dq, dr = axis
            for offset in range(WIN_LENGTH):
                start = (sq - offset * dq, sr - offset * dr)
                key = (axis_idx, start[0], start[1])
                if key in seen:
                    continue
                seen.add(key)
                cells = _line_from(start, axis)
                if all(board.get(cell) == player for cell in cells):
                    lines.append(cells)
    return tuple(sorted(lines))


def verify_fractal_wins(fractal: StrategyFractal) -> bool:
    """Return True when every generated motif is an actual HexGo win."""
    winning_lines = set(winning_lines_for_board(fractal.board, fractal.player))
    return all(
        len(motif.cells) == WIN_LENGTH
        and motif.cells in winning_lines
        and all(fractal.board.get(cell) == fractal.player for cell in motif.cells)
        for motif in fractal.motifs
    )
