from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Iterable

from .hypergraph import exact_hitting_number, support
from .lattices import Cell, a2_hex
from .opening_optimality import CanonicalOpening, canonical_white_openings
from .strategy_optimization import (
    _ball,
    _cell_pressure,
    _spiral_index,
    _urgent_obligation_details,
    has_connect_win,
    position_metrics,
)


@dataclass(frozen=True)
class SearchConfig:
    radius: int = 3
    depth: int = 2
    candidate_cells: int = 10
    k: int = 6
    win_value: float = 1_000_000.0
    max_tree_nodes: int = 250_000


@dataclass(frozen=True)
class SearchResult:
    score: float
    best_move: tuple[Cell, ...] | None
    principal_variation: tuple[dict, ...]
    nodes: int
    cache_hits: int


@dataclass(frozen=True)
class OpeningCorpusRow:
    opening_id: str
    radius: int
    effective_depth: int
    effective_candidate_cells: int
    white_pair: tuple[Cell, Cell]
    best_black_reply: tuple[Cell, ...]
    score: float
    nodes: int
    cache_hits: int
    estimated_tree_nodes: int
    naive_leaf_nodes: int
    pruning_mode: str
    final_class: str
    black_tau: int
    white_tau: int
    black_obligations: int
    white_obligations: int
    black_bulk_pressure: float
    white_bulk_pressure: float
    principal_variation: tuple[dict, ...]


def estimate_tree_size(config: SearchConfig) -> dict[str, int]:
    board_cells = len(_ball(config.radius))
    opening_empty = max(0, board_cells - 3)
    naive_pair_branching = opening_empty * max(0, opening_empty - 1) // 2
    candidate_pair_branching = config.candidate_cells * max(0, config.candidate_cells - 1) // 2
    naive_leaf_nodes = naive_pair_branching ** config.depth
    candidate_leaf_nodes = candidate_pair_branching ** config.depth
    estimated_tree_nodes = sum(candidate_pair_branching ** d for d in range(config.depth + 1))
    return {
        "board_cells": board_cells,
        "opening_empty_cells": opening_empty,
        "naive_pair_branching": naive_pair_branching,
        "candidate_pair_branching": candidate_pair_branching,
        "naive_leaf_nodes": naive_leaf_nodes,
        "candidate_leaf_nodes": candidate_leaf_nodes,
        "estimated_tree_nodes": estimated_tree_nodes,
    }


def _pruned_config(config: SearchConfig) -> tuple[SearchConfig, str]:
    estimate = estimate_tree_size(config)
    if estimate["estimated_tree_nodes"] <= config.max_tree_nodes:
        return config, "alpha_beta"
    candidate_cells = config.candidate_cells
    while candidate_cells > 4:
        trial = SearchConfig(
            radius=config.radius,
            depth=config.depth,
            candidate_cells=candidate_cells - 1,
            k=config.k,
            win_value=config.win_value,
            max_tree_nodes=config.max_tree_nodes,
        )
        if estimate_tree_size(trial)["estimated_tree_nodes"] <= config.max_tree_nodes:
            return trial, "beam"
        candidate_cells -= 1
    return SearchConfig(
        radius=config.radius,
        depth=max(1, config.depth - 1),
        candidate_cells=candidate_cells,
        k=config.k,
        win_value=config.win_value,
        max_tree_nodes=config.max_tree_nodes,
    ), "beam"


def torch_rank_openings_for_solve(
    openings: tuple[CanonicalOpening, ...],
    eval_radius: int,
    k: int = 6,
    prefer_cuda: bool = True,
) -> dict[str, object]:
    from .opening_optimality import torch_static_opening_features

    features = torch_static_opening_features(openings, eval_radius=eval_radius, k=k, prefer_cuda=prefer_cuda)
    priorities = []
    for i, opening in enumerate(openings):
        black_bulk = float(features["black_bulk_pressure"][i])
        white_bulk = float(features["white_bulk_pressure"][i])
        blocked = int(features["root_lines_blocked"][i])
        priority = black_bulk - 0.55 * white_bulk - 0.25 * blocked
        priorities.append((opening.opening_id, priority))
    priorities.sort(key=lambda item: item[1], reverse=True)
    return {
        "rows": len(openings),
        "device": features["device"],
        "solve_priority": priorities,
    }


def canonical_state_key(black: frozenset[Cell], white: frozenset[Cell], player: str) -> tuple:
    variants = []
    for transform in a2_hex().symmetries:
        tb = tuple(sorted(transform(cell) for cell in black))
        tw = tuple(sorted(transform(cell) for cell in white))
        variants.append((tb, tw, player))
    return min(variants)


def _move_key(move: Iterable[Cell]) -> tuple[Cell, ...]:
    index = _spiral_index(16)
    return tuple(sorted(move, key=lambda cell: index.get(cell, 10_000)))


def _candidate_cells(player: str, black: frozenset[Cell], white: frozenset[Cell], config: SearchConfig) -> tuple[Cell, ...]:
    own = set(black if player == "black" else white)
    opponent = set(white if player == "black" else black)
    empty = set(_ball(config.radius)) - set(black) - set(white)
    forced: set[Cell] = set()
    for edge, _ in _urgent_obligation_details(opponent, own, radius=config.radius, k=config.k):
        forced.update(edge)
    for edge, _ in _urgent_obligation_details(own, opponent, radius=config.radius, k=config.k):
        forced.update(edge)
    index = _spiral_index(config.radius)

    def score(cell: Cell) -> tuple[float, int]:
        block = _cell_pressure(cell, opponent, own, radius=config.radius, k=config.k)
        build = _cell_pressure(cell, own, opponent, radius=config.radius, k=config.k)
        urgent = 10000.0 if cell in forced else 0.0
        asym = 1.35 if player == "black" else 1.85
        return (-(urgent + asym * block + build), index[cell])

    ranked = sorted(empty, key=score)
    merged = list(dict.fromkeys([cell for cell in ranked if cell in forced] + ranked))
    return tuple(merged[: max(config.candidate_cells, min(len(merged), config.candidate_cells + len(forced)))])


def candidate_moves(player: str, black: frozenset[Cell], white: frozenset[Cell], config: SearchConfig) -> tuple[tuple[Cell, ...], ...]:
    cells = _candidate_cells(player, black, white, config)
    moves = tuple(_move_key(pair) for pair in combinations(cells, 2))
    return tuple(sorted(set(moves), key=lambda move: tuple(_spiral_index(config.radius)[cell] for cell in move)))


def _evaluate(black: frozenset[Cell], white: frozenset[Cell], config: SearchConfig) -> float:
    if has_connect_win(black, k=config.k, radius=config.radius):
        return config.win_value
    if has_connect_win(white, k=config.k, radius=config.radius):
        return -config.win_value
    metrics = position_metrics(set(black), set(white), radius=config.radius, k=config.k)
    black_obs = tuple(edge for edge, _ in _urgent_obligation_details(set(black), set(white), radius=config.radius, k=config.k))
    white_obs = tuple(edge for edge, _ in _urgent_obligation_details(set(white), set(black), radius=config.radius, k=config.k))
    black_support = len(support(black_obs))
    white_support = len(support(white_obs))
    return (
        6500 * (metrics.black.tau - metrics.white.tau)
        + 85 * (metrics.black.obligations - metrics.white.obligations)
        + 18 * (metrics.black.family_max - metrics.white.family_max)
        + 0.35 * (metrics.black.bulk_pressure - metrics.white.bulk_pressure)
        + 8 * (black_support - white_support)
    )


def search_position(
    black: frozenset[Cell],
    white: frozenset[Cell],
    player: str,
    config: SearchConfig,
) -> SearchResult:
    table: dict[tuple, tuple[float, tuple[Cell, ...] | None, tuple[dict, ...]]] = {}
    stats = {"nodes": 0, "cache_hits": 0}

    def rec(b: frozenset[Cell], w: frozenset[Cell], side: str, depth: int, alpha: float, beta: float) -> tuple[float, tuple[Cell, ...] | None, tuple[dict, ...]]:
        stats["nodes"] += 1
        key = (canonical_state_key(b, w, side), depth)
        if key in table:
            stats["cache_hits"] += 1
            return table[key]
        if depth == 0 or has_connect_win(b, k=config.k, radius=config.radius) or has_connect_win(w, k=config.k, radius=config.radius):
            value = _evaluate(b, w, config)
            out = (value, None, tuple())
            table[key] = out
            return out
        moves = candidate_moves(side, b, w, config)
        if not moves:
            out = (_evaluate(b, w, config), None, tuple())
            table[key] = out
            return out

        if side == "black":
            best = -float("inf")
            best_move = None
            best_pv: tuple[dict, ...] = tuple()
            for move in moves:
                nb = frozenset(set(b) | set(move))
                value, _, pv = rec(nb, w, "white", depth - 1, alpha, beta)
                if value > best:
                    best = value
                    best_move = move
                    best_pv = ({"player": "black", "move": tuple(move), "score": value},) + pv
                alpha = max(alpha, best)
                if beta <= alpha:
                    break
        else:
            best = float("inf")
            best_move = None
            best_pv = tuple()
            for move in moves:
                nw = frozenset(set(w) | set(move))
                value, _, pv = rec(b, nw, "black", depth - 1, alpha, beta)
                if value < best:
                    best = value
                    best_move = move
                    best_pv = ({"player": "white", "move": tuple(move), "score": value},) + pv
                beta = min(beta, best)
                if beta <= alpha:
                    break
        out = (best, best_move, best_pv)
        table[key] = out
        return out

    score, move, pv = rec(black, white, player, config.depth, -float("inf"), float("inf"))
    return SearchResult(score=score, best_move=move, principal_variation=pv, nodes=stats["nodes"], cache_hits=stats["cache_hits"])


def _classify(score: float, metrics) -> str:
    if score > 100_000:
        return "black_forced_line"
    if score < -100_000:
        return "white_counter_line"
    if metrics.black.tau > 2:
        return "black_tau_gt2"
    if metrics.white.tau > 2:
        return "white_tau_gt2"
    if metrics.black.tau == 2 and metrics.black.obligations:
        return "black_tau2_debt"
    if metrics.black.bulk_pressure > metrics.white.bulk_pressure + 5:
        return "black_bulk_edge"
    return "screened_or_balanced"


def _row_for_opening(opening: CanonicalOpening, config: SearchConfig, pruning_mode: str) -> OpeningCorpusRow:
    black = frozenset({(0, 0)})
    white = frozenset(opening.pair)
    result = search_position(black, white, "black", config)
    reply = result.best_move or tuple()
    after_black = frozenset(set(black) | set(reply))
    metrics = position_metrics(set(after_black), set(white), radius=config.radius, k=config.k)
    return OpeningCorpusRow(
        opening_id=opening.opening_id,
        radius=config.radius,
        effective_depth=config.depth,
        effective_candidate_cells=config.candidate_cells,
        white_pair=opening.pair,
        best_black_reply=reply,
        score=result.score,
        nodes=result.nodes,
        cache_hits=result.cache_hits,
        estimated_tree_nodes=estimate_tree_size(config)["estimated_tree_nodes"],
        naive_leaf_nodes=estimate_tree_size(config)["naive_leaf_nodes"],
        pruning_mode=pruning_mode,
        final_class=_classify(result.score, metrics),
        black_tau=metrics.black.tau,
        white_tau=metrics.white.tau,
        black_obligations=metrics.black.obligations,
        white_obligations=metrics.white.obligations,
        black_bulk_pressure=metrics.black.bulk_pressure,
        white_bulk_pressure=metrics.white.bulk_pressure,
        principal_variation=result.principal_variation,
    )


def build_opening_corpus(radius: int, config: SearchConfig | None = None, limit: int | None = None) -> tuple[OpeningCorpusRow, ...]:
    cfg, pruning_mode = _pruned_config(config or SearchConfig(radius=radius))
    openings = canonical_white_openings(radius)
    if limit is not None:
        openings = openings[:limit]
    ranking = torch_rank_openings_for_solve(openings, eval_radius=cfg.radius, k=cfg.k, prefer_cuda=True)
    opening_by_id = {opening.opening_id: opening for opening in openings}
    ordered_ids = [opening_id for opening_id, _ in ranking["solve_priority"]]
    ordered = [opening_by_id[opening_id] for opening_id in ordered_ids if opening_id in opening_by_id]
    return tuple(_row_for_opening(opening, cfg, pruning_mode) for opening in ordered)
