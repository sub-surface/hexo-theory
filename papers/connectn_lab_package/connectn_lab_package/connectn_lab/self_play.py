from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .lattices import Cell
from .opening_optimality import BLACK_OPENING_STRATEGIES, WHITE_SCREENING_STRATEGIES, canonical_white_openings
from .strategy_optimization import (
    choose_strategy_move,
    has_connect_win,
    position_metrics,
)


@dataclass(frozen=True)
class SelfPlayConfig:
    radius: int = 3
    turns: int = 4
    k: int = 6
    candidate_limit: int = 8
    opening_limit: int = 8
    black_strategies: tuple[str, ...] = BLACK_OPENING_STRATEGIES
    white_strategies: tuple[str, ...] = WHITE_SCREENING_STRATEGIES


@dataclass(frozen=True)
class SelfPlayRecord:
    game_id: str
    black_strategy: str
    white_strategy: str
    radius: int
    turns: int
    k: int
    candidate_limit: int
    opening_id: str | None
    opening_pair: tuple[Cell, ...]
    moves: tuple[dict[str, object], ...]
    winner: str | None
    wlu: str
    terminal_ply: int | None
    black_stones: int
    white_stones: int
    final_class: str
    final_black_tau: int
    final_white_tau: int
    final_black_obligations: int
    final_white_obligations: int
    final_black_pair_atoms: int
    final_white_pair_atoms: int
    final_black_bulk_pressure: float
    final_white_bulk_pressure: float
    first_black_tau_gt2: int | None
    first_white_tau_gt2: int | None
    max_black_tau: int
    max_white_tau: int
    tactical_score: float


@dataclass(frozen=True)
class StrategyMatchupSummary:
    black_strategy: str
    white_strategy: str
    games: int
    black_wins: int
    white_wins: int
    undecided: int
    black_win_rate: float
    white_win_rate: float
    mean_terminal_ply: float
    mean_final_black_tau: float
    mean_final_white_tau: float
    mean_black_bulk_pressure: float
    mean_white_bulk_pressure: float
    mean_tactical_score: float


@dataclass(frozen=True)
class NetworkSizeEstimate:
    radius: int
    board_cells: int
    full_pair_actions: int
    candidate_cells: int
    candidate_pair_actions: int
    feature_channels: int
    trunk_width: int
    blocks: int
    factorized_policy_params: int
    full_policy_params: int
    value_head_params: int
    total_factorized_params: int
    total_full_policy_params: int
    boundary_to_bulk_ratio: float
    generalization_index: float
    recommended_architecture: str
    generalization_regime: str


def _cell_list(cell: Cell) -> list[int]:
    return [int(cell[0]), int(cell[1])]


def _move(color: str, stones: Iterable[Cell]) -> dict[str, object]:
    return {"color": color, "stones": [_cell_list(cell) for cell in stones]}


def _wlu(winner: str | None) -> str:
    if winner == "black":
        return "B"
    if winner == "white":
        return "W"
    return "U"


def _final_class(winner: str | None, metrics) -> str:
    if winner == "black":
        return "black_forced_line"
    if winner == "white":
        return "white_counter_line"
    if metrics.black.tau > 2:
        return "black_tau_gt2"
    if metrics.white.tau > 2:
        return "white_tau_gt2"
    if metrics.black.tau == 2 and metrics.black.obligations:
        return "black_tau2_debt"
    if metrics.white.tau == 2 and metrics.white.obligations:
        return "white_tau2_screen"
    return "undecided_balanced"


def _tactical_score(metrics) -> float:
    return (
        6500 * (metrics.black.tau - metrics.white.tau)
        + 85 * (metrics.black.obligations - metrics.white.obligations)
        + 22 * (metrics.black.pair_atoms - metrics.white.pair_atoms)
        + 0.35 * (metrics.black.bulk_pressure - metrics.white.bulk_pressure)
        + 18 * (metrics.black.family_max - metrics.white.family_max)
    )


def play_self_play_game(
    game_id: str,
    black_strategy: str,
    white_strategy: str,
    radius: int,
    turns: int,
    candidate_limit: int,
    opening_id: str | None = None,
    opening_pair: tuple[Cell, ...] | None = None,
    k: int = 6,
) -> SelfPlayRecord:
    black: set[Cell] = {(0, 0)}
    white: set[Cell] = set()
    moves: list[dict[str, object]] = [_move("black", ((0, 0),))]
    metric_history = []
    winner: str | None = None
    terminal_ply: int | None = None
    ply = 0

    def snapshot() -> None:
        metric_history.append(position_metrics(black, white, radius=radius, k=k))

    def apply_player_move(player: str) -> bool:
        nonlocal winner, terminal_ply, ply
        move = choose_strategy_move(
            black_strategy if player == "black" else white_strategy,
            player,
            black=black,
            white=white,
            radius=radius,
            k=k,
            move_size=2,
            candidate_limit=candidate_limit,
        )
        if len(move) < 2:
            return False
        if player == "black":
            black.update(move)
            moves.append(_move("black", move))
            if has_connect_win(black, k=k, radius=radius):
                winner = "black"
        else:
            white.update(move)
            moves.append(_move("white", move))
            if has_connect_win(white, k=k, radius=radius):
                winner = "white"
        ply += 1
        snapshot()
        if winner is not None:
            terminal_ply = ply
        return True

    if opening_pair:
        white.update(opening_pair)
        moves.append(_move("white", opening_pair))
        ply += 1
        snapshot()
        if has_connect_win(white, k=k, radius=radius):
            winner = "white"
            terminal_ply = ply
    else:
        snapshot()

    for _turn in range(turns):
        if winner is not None:
            break
        if opening_pair:
            if not apply_player_move("black") or winner is not None:
                break
            if not apply_player_move("white"):
                break
        else:
            if not apply_player_move("white") or winner is not None:
                break
            if not apply_player_move("black"):
                break

    final_metrics = metric_history[-1] if metric_history else position_metrics(black, white, radius=radius, k=k)

    def first_gt2(side: str) -> int | None:
        for i, metrics in enumerate(metric_history):
            value = metrics.black.tau if side == "black" else metrics.white.tau
            if value > 2:
                return i
        return None

    return SelfPlayRecord(
        game_id=game_id,
        black_strategy=black_strategy,
        white_strategy=white_strategy,
        radius=radius,
        turns=turns,
        k=k,
        candidate_limit=candidate_limit,
        opening_id=opening_id,
        opening_pair=tuple(opening_pair or tuple()),
        moves=tuple(moves),
        winner=winner,
        wlu=_wlu(winner),
        terminal_ply=terminal_ply,
        black_stones=len(black),
        white_stones=len(white),
        final_class=_final_class(winner, final_metrics),
        final_black_tau=final_metrics.black.tau,
        final_white_tau=final_metrics.white.tau,
        final_black_obligations=final_metrics.black.obligations,
        final_white_obligations=final_metrics.white.obligations,
        final_black_pair_atoms=final_metrics.black.pair_atoms,
        final_white_pair_atoms=final_metrics.white.pair_atoms,
        final_black_bulk_pressure=final_metrics.black.bulk_pressure,
        final_white_bulk_pressure=final_metrics.white.bulk_pressure,
        first_black_tau_gt2=first_gt2("black"),
        first_white_tau_gt2=first_gt2("white"),
        max_black_tau=max(metrics.black.tau for metrics in metric_history),
        max_white_tau=max(metrics.white.tau for metrics in metric_history),
        tactical_score=_tactical_score(final_metrics),
    )


def run_self_play_corpus(config: SelfPlayConfig) -> tuple[SelfPlayRecord, ...]:
    openings = canonical_white_openings(config.radius)[: config.opening_limit] if config.opening_limit else tuple()
    opening_rows: tuple[tuple[str | None, tuple[Cell, ...] | None], ...]
    if openings:
        opening_rows = tuple((opening.opening_id, opening.pair) for opening in openings)
    else:
        opening_rows = ((None, None),)

    records: list[SelfPlayRecord] = []
    game_no = 1
    for black_strategy in config.black_strategies:
        for white_strategy in config.white_strategies:
            for opening_id, opening_pair in opening_rows:
                records.append(
                    play_self_play_game(
                        game_id=f"G{game_no:05d}",
                        black_strategy=black_strategy,
                        white_strategy=white_strategy,
                        radius=config.radius,
                        turns=config.turns,
                        candidate_limit=config.candidate_limit,
                        opening_id=opening_id,
                        opening_pair=opening_pair,
                        k=config.k,
                    )
                )
                game_no += 1
    return tuple(records)


def summarise_matchups(records: Iterable[SelfPlayRecord]) -> tuple[StrategyMatchupSummary, ...]:
    groups: dict[tuple[str, str], list[SelfPlayRecord]] = {}
    for record in records:
        groups.setdefault((record.black_strategy, record.white_strategy), []).append(record)

    summaries = []
    for (black_strategy, white_strategy), group in sorted(groups.items()):
        games = len(group)
        black_wins = sum(1 for record in group if record.winner == "black")
        white_wins = sum(1 for record in group if record.winner == "white")
        undecided = games - black_wins - white_wins
        terminal_values = [record.terminal_ply if record.terminal_ply is not None else record.turns * 2 for record in group]
        summaries.append(
            StrategyMatchupSummary(
                black_strategy=black_strategy,
                white_strategy=white_strategy,
                games=games,
                black_wins=black_wins,
                white_wins=white_wins,
                undecided=undecided,
                black_win_rate=black_wins / games,
                white_win_rate=white_wins / games,
                mean_terminal_ply=mean(terminal_values),
                mean_final_black_tau=mean(record.final_black_tau for record in group),
                mean_final_white_tau=mean(record.final_white_tau for record in group),
                mean_black_bulk_pressure=mean(record.final_black_bulk_pressure for record in group),
                mean_white_bulk_pressure=mean(record.final_white_bulk_pressure for record in group),
                mean_tactical_score=mean(record.tactical_score for record in group),
            )
        )
    return tuple(summaries)


def game_to_viewer_record(record: SelfPlayRecord) -> dict[str, object]:
    return {
        "game_id": record.game_id,
        "moves": list(record.moves),
        "result": record.winner or "none",
        "class": record.final_class,
        "black_strategy": record.black_strategy,
        "white_strategy": record.white_strategy,
        "opening_id": record.opening_id,
        "wlu": record.wlu,
        "tactical_score": record.tactical_score,
    }


def _architecture_for_radius(radius: int) -> tuple[str, str, int, int, int]:
    if radius <= 3:
        return "tiny_factorized_mlp", "memorisation_dominated", 12, 64, 2
    if radius <= 5:
        return "small_residual_hex_cnn", "opening_transfer", 14, 96, 3
    if radius <= 7:
        return "local_message_passing", "local_atom_generalisation", 16, 128, 4
    return "d6_equivariant_message_passing", "infinite_proxy", 18, 192, max(5, radius - 3)


def estimate_network_size(radius: int, candidate_limit: int | None = None) -> NetworkSizeEstimate:
    board_cells = 1 + 3 * radius * (radius + 1)
    full_pair_actions = board_cells * (board_cells - 1) // 2
    candidate_cells = candidate_limit if candidate_limit is not None else min(board_cells, max(6, 2 * radius + 4))
    candidate_pair_actions = candidate_cells * max(0, candidate_cells - 1) // 2
    architecture, regime, feature_channels, trunk_width, blocks = _architecture_for_radius(radius)

    trunk_params = feature_channels * trunk_width * 7 + blocks * 2 * trunk_width * trunk_width * 7
    factorized_policy_head = trunk_width * board_cells + trunk_width * trunk_width
    full_policy_head = trunk_width * full_pair_actions
    value_head_params = trunk_width * 128 + 129
    total_factorized = trunk_params + factorized_policy_head + value_head_params
    total_full = trunk_params + full_policy_head + value_head_params
    boundary_to_bulk = (6 * radius) / board_cells
    generalization_index = max(0.0, min(1.0, 1.0 - boundary_to_bulk))

    return NetworkSizeEstimate(
        radius=radius,
        board_cells=board_cells,
        full_pair_actions=full_pair_actions,
        candidate_cells=candidate_cells,
        candidate_pair_actions=candidate_pair_actions,
        feature_channels=feature_channels,
        trunk_width=trunk_width,
        blocks=blocks,
        factorized_policy_params=int(factorized_policy_head),
        full_policy_params=int(full_policy_head),
        value_head_params=int(value_head_params),
        total_factorized_params=int(total_factorized),
        total_full_policy_params=int(total_full),
        boundary_to_bulk_ratio=boundary_to_bulk,
        generalization_index=generalization_index,
        recommended_architecture=architecture,
        generalization_regime=regime,
    )


def network_size_sweep(radius_min: int, radius_max: int, candidate_limit: int | None = None) -> tuple[NetworkSizeEstimate, ...]:
    return tuple(estimate_network_size(radius, candidate_limit=candidate_limit) for radius in range(radius_min, radius_max + 1))
