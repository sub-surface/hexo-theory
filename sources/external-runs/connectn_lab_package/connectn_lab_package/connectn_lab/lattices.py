from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Sequence, Tuple

Cell = Tuple[int, int]
Transform = Callable[[Cell], Cell]


def _translate_to_origin(cells: Iterable[Cell]) -> tuple[Cell, ...]:
    cells = list(cells)
    if not cells:
        return tuple()
    min_x = min(x for x, _ in cells)
    min_y = min(y for _, y in cells)
    return tuple(sorted((x - min_x, y - min_y) for x, y in cells))


@dataclass(frozen=True)
class LatticeSpec:
    """A small lattice model for connect-n progression games.

    Coordinates are integer pairs.  For A2, these are axial hex coordinates.
    The `directions` field should contain one representative for each unoriented
    progression foliation; the code also searches the negative direction when
    needed through start positions.
    """

    name: str
    directions: tuple[Cell, ...]
    symmetries: tuple[Transform, ...]
    ball_metric: str = "chebyshev"

    def canonical_cells(self, cells: Iterable[Cell]) -> tuple[Cell, ...]:
        """Canonicalise a set of cells up to lattice symmetries and translation."""
        variants = []
        base = list(cells)
        for transform in self.symmetries:
            variants.append(_translate_to_origin(transform(c) for c in base))
        return min(variants) if variants else tuple()


# D4 actions on Z^2.
def _z2_symmetries() -> tuple[Transform, ...]:
    return (
        lambda c: ( c[0],  c[1]),
        lambda c: ( c[0], -c[1]),
        lambda c: (-c[0],  c[1]),
        lambda c: (-c[0], -c[1]),
        lambda c: ( c[1],  c[0]),
        lambda c: ( c[1], -c[0]),
        lambda c: (-c[1],  c[0]),
        lambda c: (-c[1], -c[0]),
    )


# D6 actions on A2 axial coordinates.  Axial (q, r) is cube (q, -q-r, r).
def _a2_rotate60(c: Cell) -> Cell:
    q, r = c
    return (-r, q + r)


def _a2_reflect(c: Cell) -> Cell:
    q, r = c
    return (r, q)


def _compose(f: Transform, g: Transform) -> Transform:
    return lambda c: f(g(c))


def _a2_symmetries() -> tuple[Transform, ...]:
    rotations: list[Transform] = []

    def rot_n(n: int) -> Transform:
        def f(c: Cell) -> Cell:
            out = c
            for _ in range(n % 6):
                out = _a2_rotate60(out)
            return out
        return f

    rotations = [rot_n(n) for n in range(6)]
    reflections = [_compose(rot, _a2_reflect) for rot in rotations]
    return tuple(rotations + reflections)


def z2_rook() -> LatticeSpec:
    """Square grid with horizontal/vertical winning lines only."""
    return LatticeSpec(
        name="Z2_rook",
        directions=((1, 0), (0, 1)),
        symmetries=_z2_symmetries(),
        ball_metric="chebyshev",
    )


def z2_diag() -> LatticeSpec:
    """Square grid with horizontal, vertical, and two diagonal foliations."""
    return LatticeSpec(
        name="Z2_diag",
        directions=((1, 0), (0, 1), (1, 1), (1, -1)),
        symmetries=_z2_symmetries(),
        ball_metric="chebyshev",
    )


def a2_hex() -> LatticeSpec:
    """A2 axial hex lattice with three axial line foliations."""
    return LatticeSpec(
        name="A2_hex",
        directions=((1, 0), (0, 1), (1, -1)),
        symmetries=_a2_symmetries(),
        ball_metric="hex",
    )
