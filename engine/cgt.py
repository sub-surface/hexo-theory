"""
Combinatorial-game-theory probes for HexGo positions.

This module treats the live-line hypergraph as a Hackenbush-like local game:
live 6-windows are branches, empty cells are possible cuts/extensions, and
near-complete lines are hot. The numbers here are not exact Conway values.
They are empirical observables for testing whether HexGo's tactical regions
decompose into mostly independent hot components.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import math

from engine import AXES, WIN_LENGTH, HexGame

Cell = tuple[int, int]
WIN_TEMPERATURE = 1024.0
BLOCK_TEMPERATURE = 900.0


@dataclass(frozen=True)
class LiveLineRecord:
    """A live 6-window: empty, or occupied by exactly one player."""

    cells: tuple[Cell, ...]
    axis: int
    owner: int
    stones: int
    empties: tuple[Cell, ...]


@dataclass(frozen=True)
class ComponentSummary:
    """A hot connected component in the live-line incidence graph."""

    cells: tuple[Cell, ...]
    line_count: int
    max_temperature: float
    total_temperature: float


def _line_cells(q: int, r: int, dq: int, dr: int) -> tuple[Cell, ...]:
    return tuple((q + i * dq, r + i * dr) for i in range(WIN_LENGTH))


def live_line_records(game: HexGame) -> list[LiveLineRecord]:
    """Return every non-blocked 6-window that touches an occupied cell."""
    records: list[LiveLineRecord] = []
    seen: set[tuple[int, int, int]] = set()
    for sq, sr in game.board:
        for axis, (dq, dr) in enumerate(AXES):
            for offset in range(WIN_LENGTH):
                oq, or_ = sq - offset * dq, sr - offset * dr
                key = (axis, oq, or_)
                if key in seen:
                    continue
                seen.add(key)
                cells = _line_cells(oq, or_, dq, dr)
                players = {game.board[c] for c in cells if c in game.board}
                if len(players) > 1:
                    continue
                owner = next(iter(players), 0)
                empties = tuple(c for c in cells if c not in game.board)
                records.append(
                    LiveLineRecord(
                        cells=cells,
                        axis=axis,
                        owner=owner,
                        stones=WIN_LENGTH - len(empties),
                        empties=empties,
                    )
                )
    return records


def _pressure(stones: int) -> float:
    """Monotone line pressure; exact scale is empirical, not canonical CGT."""
    if stones <= 0:
        return 0.0
    return float((2 ** stones) - 1)


def cell_temperature(
    records: list[LiveLineRecord],
    cell: Cell,
    player: int,
) -> float:
    """
    Approximate local temperature of placing `player` at `cell`.

    Own near-wins are hottest, opponent near-wins are nearly as hot because
    they must be cut, and lower-order lines use a pressure swing.
    """
    opponent = 3 - player
    temp = 0.0
    for rec in records:
        if cell not in rec.empties:
            continue
        if rec.owner == player:
            if rec.stones >= WIN_LENGTH - 1:
                temp += WIN_TEMPERATURE
            else:
                temp += _pressure(rec.stones + 1) - _pressure(rec.stones)
        elif rec.owner == opponent:
            if rec.stones >= WIN_LENGTH - 1:
                temp += BLOCK_TEMPERATURE
            else:
                temp += 0.75 * _pressure(rec.stones)
        else:
            temp += _pressure(1)
    return temp


def temperature_map(
    game: HexGame,
    player: int | None = None,
    cells: set[Cell] | None = None,
) -> dict[Cell, float]:
    """Return approximate CGT temperature for candidate empty cells."""
    player = game.current_player if player is None else player
    records = live_line_records(game)
    if cells is None:
        cells = {c for rec in records for c in rec.empties}
        if not cells and not game.board:
            cells = {(0, 0)}
    return {c: cell_temperature(records, c, player) for c in cells if c not in game.board}


def component_summaries(
    game: HexGame,
    player: int | None = None,
    min_temperature: float = 8.0,
) -> list[ComponentSummary]:
    """
    Connected hot regions in the live-line incidence graph.

    Line nodes connect through all cells in their 6-window, including occupied
    stones, so two endpoints of the same almost-complete chain land in the
    same component even when no single window contains both endpoint cells.
    """
    player = game.current_player if player is None else player
    records = live_line_records(game)
    temps = temperature_map(game, player)
    hot = {c for c, t in temps.items() if t >= min_temperature}
    if not hot:
        return []

    graph: dict[tuple[str, object], set[tuple[str, object]]] = defaultdict(set)
    for idx, rec in enumerate(records):
        if not any(c in hot for c in rec.empties):
            continue
        line_node = ("line", idx)
        for c in rec.cells:
            cell_node = ("cell", c)
            graph[line_node].add(cell_node)
            graph[cell_node].add(line_node)

    out: list[ComponentSummary] = []
    seen: set[tuple[str, object]] = set()
    for c in sorted(hot):
        start = ("cell", c)
        if start in seen:
            continue
        queue = deque([start])
        seen.add(start)
        comp_nodes: set[tuple[str, object]] = set()
        while queue:
            node = queue.popleft()
            comp_nodes.add(node)
            for nxt in graph.get(node, set()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)

        comp_hot = sorted(
            node[1] for node in comp_nodes
            if node[0] == "cell" and node[1] in hot
        )
        comp_lines = sum(1 for node in comp_nodes if node[0] == "line")
        total = sum(temps[c] for c in comp_hot)
        out.append(
            ComponentSummary(
                cells=tuple(comp_hot),
                line_count=comp_lines,
                max_temperature=max((temps[c] for c in comp_hot), default=0.0),
                total_temperature=total,
            )
        )

    out.sort(key=lambda comp: (comp.max_temperature, comp.total_temperature), reverse=True)
    return out


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return float("nan")
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0.0 or vy <= 0.0:
        return float("nan")
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(vx * vy)


def position_summary(game: HexGame, player: int | None = None) -> dict[str, float | int]:
    """Aggregate CGT observables for one position."""
    from engine.analysis import potential_map

    player = game.current_player if player is None else player
    temps = temperature_map(game, player)
    comps = component_summaries(game, player)
    pot = potential_map(game)
    shared = sorted(set(temps) & set(pot))
    corr = _pearson(
        [math.log1p(pot[c]) for c in shared],
        [math.log1p(temps[c]) for c in shared],
    )
    total_temp = sum(temps.values())
    comp_total = sum(c.total_temperature for c in comps)
    top_comp = comps[0].total_temperature if comps else 0.0
    if comp_total > 0.0:
        shares = [c.total_temperature / comp_total for c in comps if c.total_temperature > 0.0]
        entropy = -sum(p * math.log(p) for p in shares)
    else:
        entropy = 0.0
    return {
        "candidate_count": len(temps),
        "component_count": len(comps),
        "top_temperature": max(temps.values(), default=0.0),
        "mean_temperature": total_temp / max(1, len(temps)),
        "total_temperature": total_temp,
        "top_component_share": top_comp / comp_total if comp_total > 0.0 else 0.0,
        "thermal_entropy": entropy,
        "potential_temperature_corr": corr,
    }


def move_rank_percentile(temps: dict[Cell, float], move: Cell) -> float:
    """Percentile rank of `move` temperature, where 1.0 means hottest."""
    if move not in temps or not temps:
        return 0.0
    score = temps[move]
    return sum(1 for v in temps.values() if v <= score) / len(temps)
