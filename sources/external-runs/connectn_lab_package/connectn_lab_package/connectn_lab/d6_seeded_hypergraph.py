from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .hypergraph import connected_components, exact_hitting_number, support
from .lattices import Cell, a2_hex
from .obligations import urgent_obligations
from .progressions import cell_radius


_A2_LINE_DIRECTIONS: tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))
_A2_RING_DIRECTIONS: tuple[Cell, ...] = ((0, -1), (-1, 0), (-1, 1), (0, 1), (1, 0), (1, -1))


@dataclass(frozen=True)
class D6TurnRecord:
    turn: int
    white_added: tuple[Cell, ...]
    black_added: tuple[Cell, ...]
    black_stones: int
    white_stones: int
    black_obligations: int
    white_obligations: int
    black_tau: int
    white_tau: int
    black_components: int
    white_components: int
    black_support: int
    white_support: int
    black_sector_counts: tuple[int, ...]
    white_sector_counts: tuple[int, ...]


@dataclass(frozen=True)
class D6SeededProcessResult:
    radius: int
    turns: int
    k: int
    attack_min_weight: int
    order: tuple[Cell, ...]
    black: frozenset[Cell]
    white: frozenset[Cell]
    black_sequence_indices: tuple[int, ...]
    white_sequence_indices: tuple[int, ...]
    turn_records: tuple[D6TurnRecord, ...]


def hex_spiral(radius: int) -> tuple[tuple[Cell, int], ...]:
    """Return A2 cells in a deterministic D6 shell spiral order."""
    out: list[tuple[Cell, int]] = [((0, 0), 0)]
    index = 1
    for r in range(1, radius + 1):
        q, s = r, 0
        for dq, ds in _A2_RING_DIRECTIONS:
            for _ in range(r):
                out.append(((q, s), index))
                index += 1
                q += dq
                s += ds
    return tuple(out)


def d6_cooccurrence_weight(a: Cell, b: Cell, k: int = 6) -> int:
    """Number of k-progressions in one foliation that can contain both cells.

    This is the weighted 2-section of the A2 Connect-k winning-set hypergraph.
    Non-collinear cells have weight 0. Collinear cells at axial distance d < k
    share exactly k-d length-k progressions along that foliation.
    """
    if a == b:
        return k
    dq = b[0] - a[0]
    dr = b[1] - a[1]
    for ux, uy in _A2_LINE_DIRECTIONS:
        if ux == 0:
            if dq != 0:
                continue
            distance = abs(dr)
        elif uy == 0:
            if dr != 0:
                continue
            distance = abs(dq)
        else:
            if dq + dr != 0:
                continue
            distance = abs(dq)
        if 0 < distance < k:
            return k - distance
    return 0


def d6_sector(cell: Cell) -> int:
    """Coarse D6 angular sector for shell-level asymmetry summaries."""
    q, r = cell
    if q >= 0 and r >= 0:
        return 0
    if q < 0 <= q + r:
        return 1
    if r > 0 and q + r < 0:
        return 2
    if q <= 0 and r <= 0:
        return 3
    if q > 0 >= q + r:
        return 4
    return 5


def _is_attacked_by(cell: Cell, opponent: Iterable[Cell], k: int, attack_min_weight: int) -> bool:
    return any(d6_cooccurrence_weight(cell, stone, k=k) >= attack_min_weight for stone in opponent)


def _choose_next(
    count: int,
    order: tuple[Cell, ...],
    own: set[Cell],
    opponent: set[Cell],
    k: int,
    attack_min_weight: int,
) -> tuple[Cell, ...]:
    added: list[Cell] = []
    occupied = own | opponent
    for cell in order:
        if len(added) == count:
            break
        if cell in occupied:
            continue
        if _is_attacked_by(cell, opponent, k=k, attack_min_weight=attack_min_weight):
            continue
        added.append(cell)
        occupied.add(cell)
        own.add(cell)
    return tuple(added)


def _sector_counts(stones: Iterable[Cell]) -> tuple[int, ...]:
    counts = [0] * 6
    for cell in stones:
        if cell == (0, 0):
            continue
        counts[d6_sector(cell)] += 1
    return tuple(counts)


def _record(
    turn: int,
    white_added: tuple[Cell, ...],
    black_added: tuple[Cell, ...],
    black: set[Cell],
    white: set[Cell],
    k: int,
    radius: int,
) -> D6TurnRecord:
    lattice = a2_hex()
    black_obligations = urgent_obligations(black, white, lattice=lattice, k=k, p=2, radius=radius)
    white_obligations = urgent_obligations(white, black, lattice=lattice, k=k, p=2, radius=radius)
    return D6TurnRecord(
        turn=turn,
        white_added=white_added,
        black_added=black_added,
        black_stones=len(black),
        white_stones=len(white),
        black_obligations=len(black_obligations),
        white_obligations=len(white_obligations),
        black_tau=exact_hitting_number(black_obligations, cap=2),
        white_tau=exact_hitting_number(white_obligations, cap=2),
        black_components=len(connected_components(black_obligations)),
        white_components=len(connected_components(white_obligations)),
        black_support=len(support(black_obligations)),
        white_support=len(support(white_obligations)),
        black_sector_counts=_sector_counts(black),
        white_sector_counts=_sector_counts(white),
    )


def run_d6_seeded_process(
    radius: int,
    turns: int,
    k: int = 6,
    attack_min_weight: int = 1,
) -> D6SeededProcessResult:
    """Run the OEIS-inspired 1-2-2 D6 Connect6 hypergraph filling process."""
    spiral = hex_spiral(radius)
    order = tuple(cell for cell, _ in spiral)
    order_index = {cell: index for cell, index in spiral}
    black: set[Cell] = {(0, 0)}
    white: set[Cell] = set()
    records: list[D6TurnRecord] = []

    for turn in range(turns):
        white_added = _choose_next(2, order, white, black, k=k, attack_min_weight=attack_min_weight)
        black_added = tuple()
        if turn > 0:
            black_added = _choose_next(2, order, black, white, k=k, attack_min_weight=attack_min_weight)
        records.append(
            _record(
                turn=turn,
                white_added=white_added,
                black_added=black_added,
                black=black,
                white=white,
                k=k,
                radius=radius,
            )
        )
        if len(white_added) < 2 or (turn > 0 and len(black_added) < 2):
            break

    black_indices = tuple(sorted(order_index[cell] for cell in black))
    white_indices = tuple(sorted(order_index[cell] for cell in white))
    return D6SeededProcessResult(
        radius=radius,
        turns=turns,
        k=k,
        attack_min_weight=attack_min_weight,
        order=order,
        black=frozenset(black),
        white=frozenset(white),
        black_sequence_indices=black_indices,
        white_sequence_indices=white_indices,
        turn_records=tuple(records),
    )


def shell_color_counts(result: D6SeededProcessResult) -> dict[int, tuple[int, int]]:
    lattice = a2_hex()
    shells = {}
    for cell in result.black | result.white:
        shell = cell_radius(cell, lattice)
        black_count, white_count = shells.get(shell, (0, 0))
        if cell in result.black:
            black_count += 1
        else:
            white_count += 1
        shells[shell] = (black_count, white_count)
    return dict(sorted(shells.items()))
