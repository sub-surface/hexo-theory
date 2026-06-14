from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations, permutations
from math import log2
from typing import Iterable

from .d6_seeded_hypergraph import hex_spiral
from .hypergraph import Edge, connected_components, exact_hitting_number, normalise_edges, support
from .lattices import Cell, a2_hex
from .progressions import all_progressions, cells_in_ball


A2_DIRECTIONS: tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))
STRATEGIES: tuple[str, ...] = (
    "earliest",
    "min_tau",
    "min_atoms",
    "min_bulk",
    "min_family",
    "hybrid",
    "attacker",
    "debt_builder",
    "screen_counter",
)


@lru_cache(maxsize=None)
def _all_lines(radius: int, k: int) -> tuple[tuple[Cell, ...], ...]:
    return tuple(all_progressions(a2_hex(), k=k, radius=radius, keep_inside=True))


@lru_cache(maxsize=None)
def _ball(radius: int) -> frozenset[Cell]:
    return frozenset(cells_in_ball(a2_hex(), radius))


@lru_cache(maxsize=None)
def _spiral_index(radius: int) -> dict[Cell, int]:
    return {cell: index for cell, index in hex_spiral(radius)}


@dataclass(frozen=True)
class SideMetrics:
    obligations: int
    tau: int
    support_size: int
    components: int
    pair_k4_atoms: int
    pair_c5_atoms: int
    bulk_pressure: float
    family_max: int
    family_entropy: float
    line_win: bool

    @property
    def pair_atoms(self) -> int:
        return self.pair_k4_atoms + self.pair_c5_atoms


@dataclass(frozen=True)
class PositionMetrics:
    black: SideMetrics
    white: SideMetrics

    @property
    def black_tau(self) -> int:
        return self.black.tau

    @property
    def white_tau(self) -> int:
        return self.white.tau

    @property
    def black_obligations(self) -> int:
        return self.black.obligations

    @property
    def white_obligations(self) -> int:
        return self.white.obligations

    @property
    def black_bulk_pressure(self) -> float:
        return self.black.bulk_pressure

    @property
    def white_bulk_pressure(self) -> float:
        return self.white.bulk_pressure

    @property
    def black_family_max(self) -> int:
        return self.black.family_max

    @property
    def white_family_max(self) -> int:
        return self.white.family_max


@dataclass(frozen=True)
class StrategyTurnRecord:
    turn: int
    white_strategy: str
    black_strategy: str
    white_move: tuple[Cell, ...]
    black_move: tuple[Cell, ...]
    winner: str | None
    black_stones: int
    white_stones: int
    black_tau: int
    white_tau: int
    black_obligations: int
    white_obligations: int
    black_pair_atoms: int
    white_pair_atoms: int
    black_bulk_pressure: float
    white_bulk_pressure: float
    black_family_max: int
    white_family_max: int
    value_after_white: float
    value_after_black: float | None


@dataclass(frozen=True)
class StrategyGameResult:
    black_strategy: str
    white_strategy: str
    radius: int
    turns: int
    k: int
    candidate_limit: int
    black: frozenset[Cell]
    white: frozenset[Cell]
    winner: str | None
    terminal_turn: int | None
    turn_records: tuple[StrategyTurnRecord, ...]


def _normalise_direction(delta: Cell) -> Cell:
    dx, dy = delta
    for ux, uy in A2_DIRECTIONS:
        if (dx, dy) == (ux, uy) or (dx, dy) == (-ux, -uy):
            return (ux, uy)
    raise ValueError(f"not an A2 unit direction: {delta}")


def has_connect_win(stones: set[Cell] | frozenset[Cell], k: int = 6, radius: int = 6) -> bool:
    stone_set = set(stones)
    for line in _all_lines(radius, k):
        if set(line).issubset(stone_set):
            return True
    return False


def _urgent_obligation_details(
    attacker: set[Cell],
    defender: set[Cell],
    radius: int,
    k: int,
    p: int = 2,
) -> tuple[tuple[Edge, Cell], ...]:
    out: list[tuple[Edge, Cell]] = []
    seen: set[Edge] = set()
    for line in _all_lines(radius, k):
        line_set = set(line)
        if line_set & defender:
            continue
        attacker_count = len(line_set & attacker)
        empty = frozenset(line_set - attacker - defender)
        if attacker_count >= k - p and 0 < len(empty) <= p:
            direction = _normalise_direction((line[1][0] - line[0][0], line[1][1] - line[0][1]))
            if empty not in seen:
                seen.add(empty)
                out.append((empty, direction))
    return tuple(out)


def _bulk_pressure(attacker: set[Cell], defender: set[Cell], radius: int, k: int) -> float:
    pressure = 0.0
    for line in _all_lines(radius, k):
        line_set = set(line)
        if line_set & defender:
            continue
        attacker_count = len(line_set & attacker)
        if attacker_count == 0:
            continue
        empty_count = len(line_set - attacker - defender)
        if empty_count == 0:
            pressure += 1000.0
        else:
            pressure += (attacker_count * attacker_count) / empty_count
    return pressure


def _family_stats(details: Iterable[tuple[Edge, Cell]]) -> tuple[int, float]:
    counts = {direction: 0 for direction in A2_DIRECTIONS}
    total = 0
    for _, direction in details:
        counts[direction] += 1
        total += 1
    if total == 0:
        return 0, 0.0
    entropy = 0.0
    for count in counts.values():
        if count:
            p = count / total
            entropy -= p * log2(p)
    return max(counts.values()), entropy


def count_pair_atom_witnesses(edges: Iterable[Iterable[Cell]]) -> dict[str, int]:
    pair_edges = {frozenset(edge) for edge in normalise_edges(edges) if len(edge) == 2}
    cells = sorted(support(pair_edges))
    k4 = 0
    c5_seen: set[tuple[tuple[Cell, ...], ...]] = set()
    for quad in combinations(cells, 4):
        if all(frozenset((a, b)) in pair_edges for a, b in combinations(quad, 2)):
            k4 += 1

    for quint in combinations(cells, 5):
        root = quint[0]
        for rest in permutations(quint[1:]):
            cycle = (root,) + rest
            if cycle[1] > cycle[-1]:
                continue
            cycle_edges = []
            ok = True
            for i in range(5):
                edge = frozenset((cycle[i], cycle[(i + 1) % 5]))
                if edge not in pair_edges:
                    ok = False
                    break
                cycle_edges.append(tuple(sorted(edge)))
            if ok:
                c5_seen.add(tuple(sorted(cycle_edges)))
    return {"k4": k4, "c5": len(c5_seen)}


def _side_metrics(attacker: set[Cell], defender: set[Cell], radius: int, k: int) -> SideMetrics:
    details = _urgent_obligation_details(attacker, defender, radius=radius, k=k)
    obligations = tuple(edge for edge, _ in details)
    atom_counts = count_pair_atom_witnesses(obligations)
    family_max, family_entropy = _family_stats(details)
    return SideMetrics(
        obligations=len(obligations),
        tau=exact_hitting_number(obligations, cap=2),
        support_size=len(support(obligations)),
        components=len(connected_components(obligations)),
        pair_k4_atoms=atom_counts["k4"],
        pair_c5_atoms=atom_counts["c5"],
        bulk_pressure=_bulk_pressure(attacker, defender, radius=radius, k=k),
        family_max=family_max,
        family_entropy=family_entropy,
        line_win=has_connect_win(attacker, k=k, radius=radius),
    )


def position_metrics(black: set[Cell], white: set[Cell], radius: int, k: int = 6) -> PositionMetrics:
    return PositionMetrics(
        black=_side_metrics(set(black), set(white), radius=radius, k=k),
        white=_side_metrics(set(white), set(black), radius=radius, k=k),
    )


def _candidate_cells(
    player: str,
    black: set[Cell],
    white: set[Cell],
    radius: int,
    k: int,
    candidate_limit: int,
) -> tuple[Cell, ...]:
    occupied = black | white
    empty = set(_ball(radius)) - occupied
    own = black if player == "black" else white
    opponent = white if player == "black" else black
    forced: set[Cell] = set()
    for edge, _ in _urgent_obligation_details(opponent, own, radius=radius, k=k):
        forced.update(edge)
    for edge, _ in _urgent_obligation_details(own, opponent, radius=radius, k=k):
        forced.update(edge)

    index = _spiral_index(radius)

    def cell_score(cell: Cell) -> tuple[float, int]:
        defensive = _cell_pressure(cell, opponent, own, radius=radius, k=k)
        offensive = _cell_pressure(cell, own, opponent, radius=radius, k=k)
        urgency = 10000.0 if cell in forced else 0.0
        return (-(urgency + 1.75 * defensive + offensive), index[cell])

    ranked = sorted(empty, key=cell_score)
    selected = list(dict.fromkeys([cell for cell in ranked if cell in forced] + ranked[:candidate_limit]))
    return tuple(selected[: max(candidate_limit, min(len(selected), candidate_limit + len(forced)))])


def _cell_pressure(cell: Cell, attacker: set[Cell], defender: set[Cell], radius: int, k: int) -> float:
    pressure = 0.0
    if cell in attacker or cell in defender:
        return pressure
    for line in _all_lines(radius, k):
        if cell not in line:
            continue
        line_set = set(line)
        if line_set & defender:
            continue
        attacker_count = len(line_set & attacker)
        if attacker_count:
            empty_count = len(line_set - attacker - defender)
            pressure += (attacker_count * attacker_count) / max(1, empty_count)
    return pressure


def _strategy_score(strategy: str, player: str, metrics: PositionMetrics) -> float:
    own = metrics.black if player == "black" else metrics.white
    opponent = metrics.white if player == "black" else metrics.black
    if opponent.line_win:
        return 1_000_000_000.0
    if own.line_win:
        return -1_000_000_000.0
    if strategy == "earliest":
        return 0.0
    if strategy == "min_tau":
        return 10_000 * opponent.tau + 80 * opponent.obligations + opponent.support_size - 400 * own.tau
    if strategy == "min_atoms":
        return 20_000 * opponent.pair_atoms + 5_000 * opponent.tau + 50 * opponent.obligations - 5_000 * own.pair_atoms
    if strategy == "min_bulk":
        return opponent.bulk_pressure + 20 * opponent.family_max + 500 * opponent.tau - 0.35 * own.bulk_pressure
    if strategy == "min_family":
        return 600 * opponent.tau + 120 * opponent.family_max - 30 * opponent.family_entropy + 15 * opponent.components
    if strategy == "hybrid":
        return (
            8_000 * opponent.tau
            + 6_000 * opponent.pair_atoms
            + 60 * opponent.obligations
            + 20 * opponent.family_max
            + 0.45 * opponent.bulk_pressure
            - 2_000 * own.tau
            - 2_000 * own.pair_atoms
            - 0.20 * own.bulk_pressure
        )
    if strategy == "attacker":
        return (
            1_500 * opponent.tau
            + 10 * opponent.obligations
            - 8_000 * own.tau
            - 5_000 * own.pair_atoms
            - 120 * own.obligations
            - 0.75 * own.bulk_pressure
        )
    if strategy == "debt_builder":
        return (
            5_500 * opponent.tau
            + 80 * opponent.obligations
            + 0.65 * opponent.bulk_pressure
            - 9_000 * own.tau
            - 160 * own.obligations
            - 90 * own.family_max
            - 0.85 * own.bulk_pressure
        )
    if strategy == "screen_counter":
        return (
            10_000 * opponent.tau
            + 120 * opponent.obligations
            + 70 * opponent.family_max
            + 0.80 * opponent.bulk_pressure
            - 1_200 * own.tau
            - 25 * own.obligations
            - 0.25 * own.bulk_pressure
        )
    raise ValueError(f"unknown strategy: {strategy}")


def choose_strategy_move(
    strategy: str,
    player: str,
    black: set[Cell],
    white: set[Cell],
    radius: int,
    k: int = 6,
    move_size: int = 2,
    candidate_limit: int = 14,
) -> tuple[Cell, ...]:
    if strategy not in STRATEGIES:
        raise ValueError(f"unknown strategy: {strategy}")
    candidates = _candidate_cells(player, set(black), set(white), radius=radius, k=k, candidate_limit=candidate_limit)
    index = _spiral_index(radius)
    if len(candidates) <= move_size:
        return tuple(candidates)

    best_move: tuple[Cell, ...] | None = None
    best_key: tuple[float, tuple[int, ...]] | None = None
    for move in combinations(candidates, move_size):
        new_black = set(black)
        new_white = set(white)
        if player == "black":
            new_black.update(move)
        else:
            new_white.update(move)
        score = _strategy_score(strategy, player, position_metrics(new_black, new_white, radius=radius, k=k))
        tie = tuple(sorted(index[cell] for cell in move))
        key = (score, tie)
        if best_key is None or key < best_key:
            best_key = key
            best_move = tuple(sorted(move, key=lambda cell: index[cell]))
    return best_move if best_move is not None else tuple()


def _record(
    turn: int,
    white_strategy: str,
    black_strategy: str,
    white_move: tuple[Cell, ...],
    black_move: tuple[Cell, ...],
    winner: str | None,
    black: set[Cell],
    white: set[Cell],
    radius: int,
    k: int,
    value_after_white: float,
    value_after_black: float | None,
) -> StrategyTurnRecord:
    metrics = position_metrics(black, white, radius=radius, k=k)
    return StrategyTurnRecord(
        turn=turn,
        white_strategy=white_strategy,
        black_strategy=black_strategy,
        white_move=white_move,
        black_move=black_move,
        winner=winner,
        black_stones=len(black),
        white_stones=len(white),
        black_tau=metrics.black.tau,
        white_tau=metrics.white.tau,
        black_obligations=metrics.black.obligations,
        white_obligations=metrics.white.obligations,
        black_pair_atoms=metrics.black.pair_atoms,
        white_pair_atoms=metrics.white.pair_atoms,
        black_bulk_pressure=metrics.black.bulk_pressure,
        white_bulk_pressure=metrics.white.bulk_pressure,
        black_family_max=metrics.black.family_max,
        white_family_max=metrics.white.family_max,
        value_after_white=value_after_white,
        value_after_black=value_after_black,
    )


def run_strategy_game(
    black_strategy: str,
    white_strategy: str,
    radius: int,
    turns: int,
    k: int = 6,
    candidate_limit: int = 14,
) -> StrategyGameResult:
    black: set[Cell] = {(0, 0)}
    white: set[Cell] = set()
    records: list[StrategyTurnRecord] = []
    winner: str | None = None
    terminal_turn: int | None = None

    for turn in range(turns):
        white_move = choose_strategy_move(
            white_strategy,
            "white",
            black=black,
            white=white,
            radius=radius,
            k=k,
            move_size=2,
            candidate_limit=candidate_limit,
        )
        white.update(white_move)
        after_white_metrics = position_metrics(black, white, radius=radius, k=k)
        value_after_white = _strategy_score(white_strategy, "white", after_white_metrics)
        black_move: tuple[Cell, ...] = tuple()
        value_after_black: float | None = None
        if has_connect_win(white, k=k, radius=radius):
            winner = "white"
            terminal_turn = turn
        else:
            black_move = choose_strategy_move(
                black_strategy,
                "black",
                black=black,
                white=white,
                radius=radius,
                k=k,
                move_size=2,
                candidate_limit=candidate_limit,
            )
            black.update(black_move)
            after_black_metrics = position_metrics(black, white, radius=radius, k=k)
            value_after_black = _strategy_score(black_strategy, "black", after_black_metrics)
            if has_connect_win(black, k=k, radius=radius):
                winner = "black"
                terminal_turn = turn
        records.append(
            _record(
                turn=turn,
                white_strategy=white_strategy,
                black_strategy=black_strategy,
                white_move=white_move,
                black_move=black_move,
                winner=winner,
                black=black,
                white=white,
                radius=radius,
                k=k,
                value_after_white=value_after_white,
                value_after_black=value_after_black,
            )
        )
        if winner is not None or len(white_move) < 2 or len(black_move) < 2:
            break

    return StrategyGameResult(
        black_strategy=black_strategy,
        white_strategy=white_strategy,
        radius=radius,
        turns=turns,
        k=k,
        candidate_limit=candidate_limit,
        black=frozenset(black),
        white=frozenset(white),
        winner=winner,
        terminal_turn=terminal_turn,
        turn_records=tuple(records),
    )
