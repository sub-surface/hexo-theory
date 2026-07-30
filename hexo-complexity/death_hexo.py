"""Reference engine and analysis primitives for Death HeXO.

Death HeXO keeps HeXO's infinite A2 lattice, 1-2-2 placement rhythm, and
length-6 axial win condition.  After a placement, every stone bracketed by
enemy stones on an opposite neighbour pair is removed simultaneously.

The implementation is deliberately self-contained.  It does not modify the
capture-free sibling engine and is small enough for exhaustive toy solvers to
audit directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
from typing import Iterable, Mapping, Protocol

Cell = tuple[int, int]
Board = dict[Cell, int]

AXES: tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))
DIRS: tuple[Cell, ...] = AXES + tuple((-q, -r) for q, r in AXES)


def add(a: Cell, b: Cell, scale: int = 1) -> Cell:
    return (a[0] + scale * b[0], a[1] + scale * b[1])


def hex_distance(a: Cell, b: Cell = (0, 0)) -> int:
    dq = a[0] - b[0]
    dr = a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def vulnerable_stones(board: Mapping[Cell, int]) -> frozenset[Cell]:
    """Return stones in an enemy x-o-x pattern along at least one axis."""
    marked: set[Cell] = set()
    for cell, player in board.items():
        enemy = 3 - player
        for axis in AXES:
            if board.get(add(cell, axis)) == enemy and board.get(add(cell, axis, -1)) == enemy:
                marked.add(cell)
                break
    return frozenset(marked)


def resolve_deaths(board: Board) -> tuple[tuple[Cell, int], ...]:
    """Remove one simultaneous death wave and return the removed stones."""
    deaths = tuple(sorted((cell, board[cell]) for cell in vulnerable_stones(board)))
    for cell, _ in deaths:
        del board[cell]
    return deaths


def line_cells(start: Cell, axis: Cell, length: int) -> tuple[Cell, ...]:
    return tuple(add(start, axis, i) for i in range(length))


def winning_lines(board: Mapping[Cell, int], player: int, connect: int = 6) -> tuple[tuple[Cell, ...], ...]:
    """Return canonical consecutive winning segments occupied by ``player``."""
    wins: set[tuple[Cell, ...]] = set()
    for cell, owner in board.items():
        if owner != player:
            continue
        for axis in AXES:
            previous = add(cell, axis, -1)
            if board.get(previous) == player:
                continue
            run: list[Cell] = []
            cursor = cell
            while board.get(cursor) == player:
                run.append(cursor)
                cursor = add(cursor, axis)
            for offset in range(max(0, len(run) - connect + 1)):
                wins.add(tuple(run[offset : offset + connect]))
    return tuple(sorted(wins))


def has_win(board: Mapping[Cell, int], player: int, connect: int = 6) -> bool:
    return bool(winning_lines(board, player, connect))


def max_run(board: Mapping[Cell, int], player: int) -> int:
    """Longest consecutive axial run for ``player``."""
    best = 0
    for cell, owner in board.items():
        if owner != player:
            continue
        for axis in AXES:
            if board.get(add(cell, axis, -1)) == player:
                continue
            length = 0
            cursor = cell
            while board.get(cursor) == player:
                length += 1
                cursor = add(cursor, axis)
            best = max(best, length)
    return best


def live_windows(board: Mapping[Cell, int], connect: int = 6) -> tuple[tuple[Cell, ...], ...]:
    """Enumerate length-``connect`` windows touching the finite board."""
    windows: set[tuple[Cell, ...]] = set()
    for cell in board:
        for axis in AXES:
            for offset in range(connect):
                start = add(cell, axis, -offset)
                windows.add(line_cells(start, axis, connect))
    return tuple(sorted(windows))


def line_potential(board: Mapping[Cell, int], player: int, connect: int = 6, base: float = 3.0) -> float:
    """Erdos-Selfridge-style live-window potential for one player."""
    enemy = 3 - player
    total = 0.0
    for window in live_windows(board, connect):
        if any(board.get(cell) == enemy for cell in window):
            continue
        count = sum(board.get(cell) == player for cell in window)
        if count:
            total += base**count - 1.0
    return total


def frontier_cells(board: Mapping[Cell, int]) -> tuple[Cell, ...]:
    """Finite local-policy candidate set; the mathematical board stays infinite."""
    if not board:
        return ((0, 0),)
    cells = {
        add(stone, direction)
        for stone in board
        for direction in DIRS
        if add(stone, direction) not in board
    }
    return tuple(sorted(cells))


def cube_coords(cell: Cell) -> tuple[int, int, int]:
    q, r = cell
    return (q, r, -q - r)


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


def transform_cell(cell: Cell, transform_index: int) -> Cell:
    if not 0 <= transform_index < 12:
        raise ValueError("transform_index must lie in [0, 11]")
    x, y, z = _cube_transforms(*cube_coords(cell))[transform_index]
    return (x, y)


def transform_board(board: Mapping[Cell, int], transform_index: int) -> Board:
    return {transform_cell(cell, transform_index): player for cell, player in board.items()}


@dataclass(frozen=True)
class DeathEvent:
    cell: Cell
    player: int
    deaths: tuple[tuple[Cell, int], ...]
    captured: tuple[Cell, ...]
    own_deaths: tuple[Cell, ...]
    placed_stone_died: bool
    board_size_before: int
    board_size_after: int
    turn_ended: bool
    winner: int | None


@dataclass
class DeathHexGame:
    """Auditable Death HeXO state machine.

    ``death_timing='placement'`` is canonical.  ``'turn'`` is retained only
    for the semantic-sensitivity experiment: cleanup and win detection occur
    after the complete one- or two-placement turn.
    """

    connect: int = 6
    death_rule: bool = True
    death_timing: str = "placement"
    board: Board = field(default_factory=dict)
    current_player: int = 1
    placements_in_turn: int = 0
    opening_done: bool = False
    winner: int | None = None
    move_history: list[Cell] = field(default_factory=list)
    player_history: list[int] = field(default_factory=list)
    death_history: list[DeathEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.connect < 2:
            raise ValueError("connect must be at least 2")
        if self.death_timing not in {"placement", "turn"}:
            raise ValueError("death_timing must be 'placement' or 'turn'")

    def clone(self) -> "DeathHexGame":
        return DeathHexGame(
            connect=self.connect,
            death_rule=self.death_rule,
            death_timing=self.death_timing,
            board=dict(self.board),
            current_player=self.current_player,
            placements_in_turn=self.placements_in_turn,
            opening_done=self.opening_done,
            winner=self.winner,
            move_history=list(self.move_history),
            player_history=list(self.player_history),
            death_history=list(self.death_history),
        )

    def state_key(self) -> tuple:
        return (
            tuple(sorted((q, r, player) for (q, r), player in self.board.items())),
            self.current_player,
            self.placements_in_turn,
            self.opening_done,
            self.winner,
        )

    def legal_moves(self) -> tuple[Cell, ...]:
        return frontier_cells(self.board)

    def make(self, q: int, r: int) -> DeathEvent | None:
        """Place one stone, resolve the configured death wave, and advance phase."""
        cell = (q, r)
        if self.winner is not None or cell in self.board:
            return None

        player = self.current_player
        before = len(self.board)
        self.board[cell] = player
        self.move_history.append(cell)
        self.player_history.append(player)
        self.placements_in_turn += 1

        limit = 2 if self.opening_done else 1
        turn_ended = self.placements_in_turn >= limit
        deaths: tuple[tuple[Cell, int], ...] = ()
        should_resolve = self.death_rule and (
            self.death_timing == "placement" or turn_ended
        )
        if should_resolve:
            deaths = resolve_deaths(self.board)

        should_check_win = self.death_timing == "placement" or turn_ended
        if should_check_win and has_win(self.board, player, self.connect):
            self.winner = player

        if turn_ended and self.winner is None:
            self.opening_done = True
            self.current_player = 3 - player
            self.placements_in_turn = 0

        own_deaths = tuple(c for c, owner in deaths if owner == player)
        captured = tuple(c for c, owner in deaths if owner == 3 - player)
        event = DeathEvent(
            cell=cell,
            player=player,
            deaths=deaths,
            captured=captured,
            own_deaths=own_deaths,
            placed_stone_died=cell in own_deaths,
            board_size_before=before,
            board_size_after=len(self.board),
            turn_ended=turn_ended,
            winner=self.winner,
        )
        self.death_history.append(event)
        return event


class Agent(Protocol):
    name: str

    def choose_move(self, game: DeathHexGame) -> Cell: ...


@dataclass
class RandomAgent:
    name: str = "random"
    seed: int = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose_move(self, game: DeathHexGame) -> Cell:
        return self._rng.choice(game.legal_moves())


@dataclass
class HeuristicAgent:
    """Local one-ply policy spanning line-building, defense, and capture."""

    name: str
    seed: int = 0
    attack_weight: float = 1.0
    defence_weight: float = 1.1
    capture_weight: float = 8.0
    material_weight: float = 0.25
    run_weight: float = 20.0
    suicide_penalty: float = 12.0
    max_candidates: int = 96

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def choose_move(self, game: DeathHexGame) -> Cell:
        me = game.current_player
        opp = 3 - me
        candidates = list(game.legal_moves())
        if len(candidates) > self.max_candidates:
            candidates.sort(
                key=lambda c: min(hex_distance(c, stone) for stone in game.board)
            )
            cutoff = candidates[: self.max_candidates]
            self._rng.shuffle(cutoff)
            candidates = cutoff

        scored: list[tuple[float, Cell]] = []
        for cell in candidates:
            trial = game.clone()
            event = trial.make(*cell)
            if event is None:
                continue
            if trial.winner == me:
                return cell

            own_potential = line_potential(trial.board, me, trial.connect)
            opp_potential = line_potential(trial.board, opp, trial.connect)
            material = sum(owner == me for owner in trial.board.values()) - sum(
                owner == opp for owner in trial.board.values()
            )
            run_balance = max_run(trial.board, me) - self.defence_weight * max_run(
                trial.board, opp
            )
            score = (
                self.attack_weight * own_potential
                - self.defence_weight * opp_potential
                + self.capture_weight * len(event.captured)
                + self.material_weight * material
                + self.run_weight * run_balance
                - self.suicide_penalty * int(event.placed_stone_died)
            )
            scored.append((score, cell))

        if not scored:
            raise RuntimeError("no legal local candidate")
        best = max(score for score, _ in scored)
        tied = [cell for score, cell in scored if math.isclose(score, best, rel_tol=1e-12, abs_tol=1e-12)]
        return self._rng.choice(tied)


def make_agent(name: str, seed: int) -> Agent:
    if name == "random":
        return RandomAgent(seed=seed)
    if name == "line":
        return HeuristicAgent(
            name="line",
            seed=seed,
            capture_weight=0.5,
            material_weight=0.1,
            suicide_penalty=18.0,
        )
    if name == "hunter":
        return HeuristicAgent(
            name="hunter",
            seed=seed,
            attack_weight=0.65,
            defence_weight=0.85,
            capture_weight=28.0,
            material_weight=1.0,
            run_weight=8.0,
            suicide_penalty=8.0,
        )
    if name == "hybrid":
        return HeuristicAgent(
            name="hybrid",
            seed=seed,
            attack_weight=1.0,
            defence_weight=1.15,
            capture_weight=9.0,
            material_weight=0.4,
            run_weight=18.0,
            suicide_penalty=16.0,
        )
    raise KeyError(f"unknown agent: {name}")


def play_game(
    black: Agent,
    white: Agent,
    *,
    connect: int = 6,
    death_rule: bool = True,
    death_timing: str = "placement",
    max_placements: int = 160,
    random_opening_placements: int = 0,
    opening_seed: int = 0,
) -> dict:
    game = DeathHexGame(
        connect=connect,
        death_rule=death_rule,
        death_timing=death_timing,
    )
    seen = {game.state_key(): 1}
    repeat_visits = 0
    max_repeat = 1
    board_sizes: list[int] = []
    captures = {1: 0, 2: 0}
    suicides = {1: 0, 2: 0}
    max_deaths = 0

    def observe(event: DeathEvent) -> None:
        nonlocal repeat_visits, max_repeat, max_deaths
        captures[event.player] += len(event.captured)
        suicides[event.player] += int(event.placed_stone_died)
        max_deaths = max(max_deaths, len(event.deaths))
        board_sizes.append(len(game.board))
        key = game.state_key()
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            repeat_visits += 1
            max_repeat = max(max_repeat, seen[key])

    opening_rng = random.Random(opening_seed)
    while (
        game.winner is None
        and len(game.move_history) < min(random_opening_placements, max_placements)
    ):
        event = game.make(*opening_rng.choice(game.legal_moves()))
        if event is None:
            raise RuntimeError("random opening generated an illegal move")
        observe(event)

    while game.winner is None and len(game.move_history) < max_placements:
        mover = black if game.current_player == 1 else white
        event = game.make(*mover.choose_move(game))
        if event is None:
            raise RuntimeError(f"{mover.name} returned an illegal move")
        observe(event)

    return {
        "winner": game.winner or 0,
        "placements": len(game.move_history),
        "final_stones": len(game.board),
        "total_deaths": sum(len(event.deaths) for event in game.death_history),
        "captures_black": captures[1],
        "captures_white": captures[2],
        "suicides_black": suicides[1],
        "suicides_white": suicides[2],
        "max_deaths_single_placement": max_deaths,
        "repeat_visits": repeat_visits,
        "max_state_multiplicity": max_repeat,
        "max_run_black": max_run(game.board, 1),
        "max_run_white": max_run(game.board, 2),
        "mean_live_stones": sum(board_sizes) / max(1, len(board_sizes)),
        "random_opening_placements": min(random_opening_placements, len(game.move_history)),
        "board": [[q, r, owner] for (q, r), owner in sorted(game.board.items())],
        "moves": [[q, r] for q, r in game.move_history],
    }


def make_null_cycle_position() -> DeathHexGame:
    """Return a stable position with one suicide-pass hole for each player."""
    game = DeathHexGame(opening_done=True, current_player=1)
    game.board = {
        (-1, 0): 2,
        (1, 0): 2,
        (9, 0): 1,
        (11, 0): 1,
    }
    return game


def execute_null_cycle(game: DeathHexGame | None = None) -> tuple[tuple, tuple]:
    """Execute P1 at (0,0) twice and P2 at (10,0) twice."""
    game = make_null_cycle_position() if game is None else game
    before = game.state_key()
    for cell in ((0, 0), (0, 0), (10, 0), (10, 0)):
        event = game.make(*cell)
        if event is None or not event.placed_stone_died:
            raise AssertionError("null-cycle construction failed")
    return before, game.state_key()


def annihilation_bomb_position() -> tuple[DeathHexGame, Cell]:
    """Six enemy neighbours and six friendly radial supports around an empty centre."""
    game = DeathHexGame(opening_done=True, current_player=1)
    for direction in DIRS:
        game.board[add((0, 0), direction)] = 2
        game.board[add((0, 0), direction, 2)] = 1
    return game, (0, 0)


def stable_board(board: Mapping[Cell, int]) -> bool:
    return not vulnerable_stones(board)


def iter_cells_in_radius(radius: int) -> Iterable[Cell]:
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            yield (q, r)
