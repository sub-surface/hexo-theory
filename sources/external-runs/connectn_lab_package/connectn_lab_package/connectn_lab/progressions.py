from __future__ import annotations

from typing import Iterable, Iterator, Sequence, Tuple

from .lattices import Cell, LatticeSpec


def progression(start: Cell, direction: Cell, k: int) -> tuple[Cell, ...]:
    sx, sy = start
    dx, dy = direction
    return tuple((sx + i * dx, sy + i * dy) for i in range(k))


def cell_radius(cell: Cell, lattice: LatticeSpec) -> int:
    x, y = cell
    if lattice.ball_metric == "hex":
        # axial hex radius = max(|q|, |r|, |q+r|)
        return max(abs(x), abs(y), abs(x + y))
    if lattice.ball_metric == "manhattan":
        return abs(x) + abs(y)
    return max(abs(x), abs(y))


def cells_in_ball(lattice: LatticeSpec, radius: int) -> set[Cell]:
    out: set[Cell] = set()
    for x in range(-radius, radius + 1):
        for y in range(-radius, radius + 1):
            c = (x, y)
            if cell_radius(c, lattice) <= radius:
                out.add(c)
    return out


def all_progressions(lattice: LatticeSpec, k: int, radius: int, keep_inside: bool = True) -> list[tuple[Cell, ...]]:
    """Enumerate k-term progressions whose cells lie in a radius ball.

    This intentionally over-generates starts and canonicalises by sorted cell set
    to avoid duplicates from opposite orientations.  It is for experiments, not
    high-performance engines.
    """
    ball = cells_in_ball(lattice, radius)
    starts = cells_in_ball(lattice, radius + k)
    seen: set[tuple[Cell, ...]] = set()
    out: list[tuple[Cell, ...]] = []
    for s in starts:
        for d in lattice.directions:
            for sign in (1, -1):
                dd = (sign * d[0], sign * d[1])
                line = progression(s, dd, k)
                if keep_inside and not set(line).issubset(ball):
                    continue
                key = tuple(sorted(line))
                if key not in seen:
                    seen.add(key)
                    out.append(line)
    return out
