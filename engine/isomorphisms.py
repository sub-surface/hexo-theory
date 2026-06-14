"""Exact combinatorial quotients for HeXO positions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from engine import AXES, WIN_LENGTH, HexGame

Cell = tuple[int, int]
Board = Mapping[Cell, int]


@dataclass(frozen=True)
class IncidenceGraph:
    """Bipartite live-line graph between 6-windows and empty cells."""

    lines: tuple[tuple[Cell, ...], ...]
    empty_to_lines: dict[Cell, tuple[int, ...]]
    line_to_empty: tuple[tuple[Cell, ...], ...]


def cube_coords(cell: Cell) -> tuple[int, int, int]:
    """Return A2 cube coordinates for axial `(q, r)`."""
    q, r = cell
    return (q, r, -q - r)


def _from_cube(x: int, y: int, z: int) -> Cell:
    if x + y + z != 0:
        raise ValueError("A2 cube coordinates must sum to zero")
    return (x, y)


def _cube_transforms(x: int, y: int, z: int) -> tuple[tuple[int, int, int], ...]:
    return (
        (x, y, z),
        (-z, -x, -y),
        (y, z, x),
        (-x, -y, -z),
        (z, x, y),
        (-y, -z, -x),
        (y, x, z),
        (-z, -y, -x),
        (x, z, y),
        (-y, -x, -z),
        (z, y, x),
        (-x, -z, -y),
    )


def d6_transforms(cell: Cell) -> tuple[Cell, ...]:
    """Return the 12 D6 images of a cell around the origin."""
    return tuple(_from_cube(*coords) for coords in _cube_transforms(*cube_coords(cell)))


def transform_cell(cell: Cell, transform_index: int) -> Cell:
    """Apply one D6 transform by index in the stable `d6_transforms` order."""
    if not 0 <= transform_index < 12:
        raise ValueError("transform_index must be in [0, 11]")
    return d6_transforms(cell)[transform_index]


def transform_board(board: Board, transform_index: int) -> dict[Cell, int]:
    """Apply one D6 transform to every stone in a board mapping."""
    return {
        transform_cell(cell, transform_index): player
        for cell, player in board.items()
    }


def canonical_board_key(board: Board) -> tuple[tuple[int, int, int], ...]:
    """Return a translation-normalized D6-canonical key for a finite board."""
    if not board:
        return ()
    keys: list[tuple[tuple[int, int, int], ...]] = []
    for idx in range(12):
        transformed = transform_board(board, idx)
        min_q = min(q for q, _ in transformed)
        min_r = min(r for _, r in transformed)
        normalized = tuple(
            sorted((q - min_q, r - min_r, player) for (q, r), player in transformed.items())
        )
        keys.append(normalized)
    return min(keys)


def _line_cells(start: Cell, axis: Cell) -> tuple[Cell, ...]:
    q, r = start
    dq, dr = axis
    return tuple((q + i * dq, r + i * dr) for i in range(WIN_LENGTH))


def live_line_incidence(game: HexGame) -> IncidenceGraph:
    """
    Return the exact live-line incidence graph touching the current board.

    A line is live when it contains stones from at most one player. Empty lines
    that touch no occupied cell are intentionally omitted on the infinite board.
    """
    seen: set[tuple[int, int, int]] = set()
    lines: list[tuple[Cell, ...]] = []
    line_to_empty: list[tuple[Cell, ...]] = []
    empty_to_lines_tmp: dict[Cell, list[int]] = {}

    for sq, sr in game.board:
        for axis_idx, axis in enumerate(AXES):
            dq, dr = axis
            for offset in range(WIN_LENGTH):
                start = (sq - offset * dq, sr - offset * dr)
                key = (axis_idx, start[0], start[1])
                if key in seen:
                    continue
                seen.add(key)
                cells = _line_cells(start, axis)
                players = {game.board[c] for c in cells if c in game.board}
                if len(players) > 1:
                    continue
                empties = tuple(c for c in cells if c not in game.board)
                line_idx = len(lines)
                lines.append(cells)
                line_to_empty.append(empties)
                for cell in empties:
                    empty_to_lines_tmp.setdefault(cell, []).append(line_idx)

    empty_to_lines = {
        cell: tuple(line_indices)
        for cell, line_indices in empty_to_lines_tmp.items()
    }
    return IncidenceGraph(tuple(lines), empty_to_lines, tuple(line_to_empty))
