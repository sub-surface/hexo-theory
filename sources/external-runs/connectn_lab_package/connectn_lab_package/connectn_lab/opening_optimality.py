from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .lattices import Cell, a2_hex
from .progressions import cells_in_ball
from .strategy_optimization import (
    choose_strategy_move,
    has_connect_win,
    position_metrics,
)


BLACK_OPENING_STRATEGIES: tuple[str, ...] = ("debt_builder", "attacker", "hybrid", "min_bulk", "min_atoms")
WHITE_SCREENING_STRATEGIES: tuple[str, ...] = ("screen_counter", "min_tau", "min_atoms", "min_bulk", "min_family", "hybrid")


@dataclass(frozen=True)
class CanonicalOpening:
    opening_id: str
    pair: tuple[Cell, Cell]
    canonical_key: tuple[Cell, Cell]
    orbit_size: int
    max_radius: int
    min_pair_distance: int


@dataclass(frozen=True)
class OpeningAnalysisRecord:
    opening_id: str
    white_pair: tuple[Cell, Cell]
    black_strategy: str
    white_strategy: str
    black_reply: tuple[Cell, ...]
    winner: str | None
    completed_turns: int
    final_black_tau: int
    final_white_tau: int
    final_black_obligations: int
    final_white_obligations: int
    final_black_pair_atoms: int
    final_white_pair_atoms: int
    final_black_bulk_pressure: float
    final_white_bulk_pressure: float
    final_black_family_max: int
    final_white_family_max: int
    first_black_tau_gt2: int | None
    first_white_tau_gt2: int | None
    max_black_tau: int
    max_white_tau: int
    max_black_obligations: int
    max_white_obligations: int
    black_stones: int
    white_stones: int


def _cell_distance(a: Cell, b: Cell) -> int:
    dq = b[0] - a[0]
    dr = b[1] - a[1]
    return max(abs(dq), abs(dr), abs(dq + dr))


def _pair_radius(pair: Iterable[Cell]) -> int:
    return max(_cell_distance((0, 0), cell) for cell in pair)


def _canonical_pair(pair: tuple[Cell, Cell]) -> tuple[Cell, Cell]:
    lattice = a2_hex()
    variants = [tuple(sorted(transform(cell) for cell in pair)) for transform in lattice.symmetries]
    return min(variants)


def canonical_white_openings(radius: int) -> tuple[CanonicalOpening, ...]:
    """Enumerate White first pairs modulo the D6 stabilizer of the Black seed."""
    cells = sorted(cells_in_ball(a2_hex(), radius) - {(0, 0)})
    grouped: dict[tuple[Cell, Cell], set[tuple[Cell, Cell]]] = {}
    for pair in combinations(cells, 2):
        key = _canonical_pair(pair)
        orbit = grouped.setdefault(key, set())
        for transform in a2_hex().symmetries:
            orbit.add(tuple(sorted(transform(cell) for cell in pair)))

    openings: list[CanonicalOpening] = []
    for i, (key, orbit) in enumerate(sorted(grouped.items(), key=lambda item: (_pair_radius(item[0]), item[0])), 1):
        openings.append(
            CanonicalOpening(
                opening_id=f"O{i:04d}",
                pair=key,
                canonical_key=key,
                orbit_size=len(orbit),
                max_radius=_pair_radius(key),
                min_pair_distance=_cell_distance(key[0], key[1]),
            )
        )
    return tuple(openings)


def torch_static_opening_features(
    openings: tuple[CanonicalOpening, ...],
    eval_radius: int,
    k: int = 6,
    prefer_cuda: bool = True,
) -> dict[str, object]:
    """Vectorized static opening features, using CUDA when available."""
    try:
        import torch
    except Exception:
        return _cpu_static_opening_features(openings, eval_radius=eval_radius, k=k, device="no_torch")

    device = "cuda" if prefer_cuda and torch.cuda.is_available() else "cpu"
    from .strategy_optimization import _all_lines  # local experimental cache

    cells = sorted(cells_in_ball(a2_hex(), eval_radius))
    cell_index = {cell: i for i, cell in enumerate(cells)}
    lines = _all_lines(eval_radius, k)
    line_mask = torch.zeros((len(lines), len(cells)), device=device)
    for line_i, line in enumerate(lines):
        for cell in line:
            line_mask[line_i, cell_index[cell]] = 1.0

    black = torch.zeros((len(cells),), device=device)
    black[cell_index[(0, 0)]] = 1.0
    white = torch.zeros((len(openings), len(cells)), device=device)
    for row, opening in enumerate(openings):
        for cell in opening.pair:
            if cell in cell_index:
                white[row, cell_index[cell]] = 1.0

    black_counts = line_mask @ black
    white_counts = white @ line_mask.T
    empty_counts = k - black_counts.unsqueeze(0) - white_counts
    black_live = (white_counts == 0) & (black_counts.unsqueeze(0) > 0)
    white_live = (black_counts.unsqueeze(0) == 0) & (white_counts > 0)
    black_bulk = torch.where(black_live, (black_counts.unsqueeze(0) ** 2) / torch.clamp(empty_counts, min=1), torch.zeros_like(empty_counts)).sum(dim=1)
    white_bulk = torch.where(white_live, (white_counts**2) / torch.clamp(empty_counts, min=1), torch.zeros_like(empty_counts)).sum(dim=1)
    root_lines_blocked = ((black_counts.unsqueeze(0) > 0) & (white_counts > 0)).sum(dim=1)
    white_two_lines = ((white_counts >= 2) & (black_counts.unsqueeze(0) == 0)).sum(dim=1)

    return {
        "rows": len(openings),
        "device": device,
        "black_bulk_pressure": [float(v) for v in black_bulk.detach().cpu().tolist()],
        "white_bulk_pressure": [float(v) for v in white_bulk.detach().cpu().tolist()],
        "root_lines_blocked": [int(v) for v in root_lines_blocked.detach().cpu().tolist()],
        "white_two_lines": [int(v) for v in white_two_lines.detach().cpu().tolist()],
    }


def _cpu_static_opening_features(openings: tuple[CanonicalOpening, ...], eval_radius: int, k: int, device: str) -> dict[str, object]:
    rows = []
    for opening in openings:
        metrics = position_metrics(black={(0, 0)}, white=set(opening.pair), radius=eval_radius, k=k)
        rows.append(metrics)
    return {
        "rows": len(openings),
        "device": device,
        "black_bulk_pressure": [row.black.bulk_pressure for row in rows],
        "white_bulk_pressure": [row.white.bulk_pressure for row in rows],
        "root_lines_blocked": [0 for _ in rows],
        "white_two_lines": [0 for _ in rows],
    }


def analyse_opening(
    opening: CanonicalOpening,
    black_strategy: str,
    white_strategy: str,
    eval_radius: int,
    rollout_turns: int,
    candidate_limit: int,
    k: int = 6,
) -> OpeningAnalysisRecord:
    black: set[Cell] = {(0, 0)}
    white: set[Cell] = set(opening.pair)
    black_reply = choose_strategy_move(
        black_strategy,
        "black",
        black=black,
        white=white,
        radius=eval_radius,
        k=k,
        move_size=2,
        candidate_limit=candidate_limit,
    )
    black.update(black_reply)

    winner: str | None = "black" if has_connect_win(black, k=k, radius=eval_radius) else None
    records = [position_metrics(black, white, radius=eval_radius, k=k)]
    completed_turns = 0
    if winner is None:
        for turn in range(rollout_turns):
            completed_turns = turn + 1
            white_move = choose_strategy_move(
                white_strategy,
                "white",
                black=black,
                white=white,
                radius=eval_radius,
                k=k,
                move_size=2,
                candidate_limit=candidate_limit,
            )
            white.update(white_move)
            records.append(position_metrics(black, white, radius=eval_radius, k=k))
            if has_connect_win(white, k=k, radius=eval_radius):
                winner = "white"
                break
            black_move = choose_strategy_move(
                black_strategy,
                "black",
                black=black,
                white=white,
                radius=eval_radius,
                k=k,
                move_size=2,
                candidate_limit=candidate_limit,
            )
            black.update(black_move)
            records.append(position_metrics(black, white, radius=eval_radius, k=k))
            if has_connect_win(black, k=k, radius=eval_radius):
                winner = "black"
                break

    final = records[-1]

    def first_gt2(side: str) -> int | None:
        for i, metrics in enumerate(records):
            tau = metrics.black.tau if side == "black" else metrics.white.tau
            if tau > 2:
                return i
        return None

    return OpeningAnalysisRecord(
        opening_id=opening.opening_id,
        white_pair=opening.pair,
        black_strategy=black_strategy,
        white_strategy=white_strategy,
        black_reply=tuple(black_reply),
        winner=winner,
        completed_turns=completed_turns,
        final_black_tau=final.black.tau,
        final_white_tau=final.white.tau,
        final_black_obligations=final.black.obligations,
        final_white_obligations=final.white.obligations,
        final_black_pair_atoms=final.black.pair_atoms,
        final_white_pair_atoms=final.white.pair_atoms,
        final_black_bulk_pressure=final.black.bulk_pressure,
        final_white_bulk_pressure=final.white.bulk_pressure,
        final_black_family_max=final.black.family_max,
        final_white_family_max=final.white.family_max,
        first_black_tau_gt2=first_gt2("black"),
        first_white_tau_gt2=first_gt2("white"),
        max_black_tau=max(metrics.black.tau for metrics in records),
        max_white_tau=max(metrics.white.tau for metrics in records),
        max_black_obligations=max(metrics.black.obligations for metrics in records),
        max_white_obligations=max(metrics.white.obligations for metrics in records),
        black_stones=len(black),
        white_stones=len(white),
    )
