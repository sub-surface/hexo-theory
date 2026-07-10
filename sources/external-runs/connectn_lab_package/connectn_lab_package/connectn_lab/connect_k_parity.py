from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from statistics import mean

from .hypergraph import Edge, exact_hitting_number
from .lattices import Cell, a2_hex
from .opening_optimality import canonical_white_openings
from .progressions import cells_in_ball
from .strategy_optimization import _urgent_obligation_details


@dataclass(frozen=True)
class ObligationStats:
    k: int
    radius: int
    obligations: int
    tau: int
    support_size: int


@dataclass(frozen=True)
class WhiteOpeningStats:
    k: int
    radius: int
    openings: int
    urgent_openings: int
    forcing_openings: int
    mean_tau: float
    max_tau: int
    mean_obligations: float
    max_obligations: int


@dataclass(frozen=True)
class BlackReplyEnvelope:
    k: int
    radius: int
    openings: int
    black_immediate_wins: int
    no_safe_reply_openings: int
    safe_replies_with_tau_gt2: int
    mean_black_tau_after_safe_reply: float
    max_black_tau_after_safe_reply: int
    mean_black_obligations_after_safe_reply: float
    max_black_obligations_after_safe_reply: int


@dataclass(frozen=True)
class ConnectKParityRow:
    k: int
    radius: int
    prime: bool
    parity: str
    tempo_owner: str
    seed_obligations: int
    seed_tau: int
    white_openings: int
    white_urgent_openings: int
    white_forcing_openings: int
    white_mean_tau: float
    white_max_tau: int
    black_immediate_wins: int
    black_no_safe_reply_openings: int
    black_reply_tau_gt2_openings: int
    black_reply_mean_tau: float
    black_reply_max_tau: int


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n == 2:
        return True
    if n % 2 == 0:
        return False
    divisor = 3
    while divisor * divisor <= n:
        if n % divisor == 0:
            return False
        divisor += 2
    return True


def first_threat_tempo_owner(k: int, move_budget: int = 2) -> str:
    if k <= move_budget:
        return "degenerate"
    urgent_layer = k - move_budget
    return "black" if urgent_layer % 2 == 1 else "white"


def analysis_radius(k: int, minimum: int = 3) -> int:
    return max(minimum, (k + 1) // 2)


def _obligation_edges(attacker: set[Cell], defender: set[Cell], radius: int, k: int) -> tuple[Edge, ...]:
    return tuple(edge for edge, _direction in _urgent_obligation_details(attacker, defender, radius=radius, k=k))


def _tau(edges: tuple[Edge, ...], cap: int = 3) -> int:
    return exact_hitting_number(edges, cap=cap) if edges else 0


def _support_size(edges: tuple[Edge, ...]) -> int:
    return len(set().union(*edges)) if edges else 0


def seed_obligation_stats(k: int, radius: int | None = None) -> ObligationStats:
    r = analysis_radius(k) if radius is None else radius
    edges = _obligation_edges({(0, 0)}, set(), radius=r, k=k)
    return ObligationStats(k=k, radius=r, obligations=len(edges), tau=_tau(edges, cap=8), support_size=_support_size(edges))


def white_opening_obligation_stats(k: int, radius: int | None = None, opening_limit: int | None = None) -> WhiteOpeningStats:
    r = analysis_radius(k) if radius is None else radius
    openings = canonical_white_openings(r)
    if opening_limit is not None:
        openings = openings[:opening_limit]
    taus: list[int] = []
    obligation_counts: list[int] = []
    for opening in openings:
        edges = _obligation_edges(set(opening.pair), {(0, 0)}, radius=r, k=k)
        taus.append(_tau(edges))
        obligation_counts.append(len(edges))
    if not taus:
        return WhiteOpeningStats(k, r, 0, 0, 0, 0.0, 0, 0.0, 0)
    return WhiteOpeningStats(
        k=k,
        radius=r,
        openings=len(openings),
        urgent_openings=sum(1 for count in obligation_counts if count > 0),
        forcing_openings=sum(1 for value in taus if value > 2),
        mean_tau=mean(taus),
        max_tau=max(taus),
        mean_obligations=mean(obligation_counts),
        max_obligations=max(obligation_counts),
    )


def _safe_black_reply_scores(k: int, radius: int, white_pair: tuple[Cell, Cell]) -> tuple[bool, bool, int, int]:
    black = {(0, 0)}
    white = set(white_pair)
    black_edges_before = _obligation_edges(black, white, radius=radius, k=k)
    if black_edges_before:
        return True, False, _tau(black_edges_before), len(black_edges_before)

    white_edges_before = _obligation_edges(white, black, radius=radius, k=k)
    empty = sorted(cells_in_ball(a2_hex(), radius) - black - white)
    best_tau = -1
    best_obligations = 0
    found_safe = False

    def blocks_all_white(move: tuple[Cell, Cell]) -> bool:
        if not white_edges_before:
            return True
        move_set = set(move)
        return all(edge & move_set for edge in white_edges_before)

    for move in combinations(empty, 2):
        if not blocks_all_white(move):
            continue
        found_safe = True
        new_black = black | set(move)
        black_edges = _obligation_edges(new_black, white, radius=radius, k=k)
        value = _tau(black_edges)
        if value > best_tau or (value == best_tau and len(black_edges) > best_obligations):
            best_tau = value
            best_obligations = len(black_edges)
    if not found_safe:
        return False, True, 0, 0
    return False, False, best_tau, best_obligations


def black_first_reply_envelope(k: int, radius: int | None = None, opening_limit: int | None = None) -> BlackReplyEnvelope:
    r = analysis_radius(k) if radius is None else radius
    openings = canonical_white_openings(r)
    if opening_limit is not None:
        openings = openings[:opening_limit]
    immediate = 0
    no_safe = 0
    best_taus: list[int] = []
    best_obligation_counts: list[int] = []
    for opening in openings:
        black_wins_now, white_forces, best_tau, best_obligations = _safe_black_reply_scores(k, r, opening.pair)
        if black_wins_now:
            immediate += 1
            best_taus.append(best_tau)
            best_obligation_counts.append(best_obligations)
        elif white_forces:
            no_safe += 1
        else:
            best_taus.append(best_tau)
            best_obligation_counts.append(best_obligations)
    return BlackReplyEnvelope(
        k=k,
        radius=r,
        openings=len(openings),
        black_immediate_wins=immediate,
        no_safe_reply_openings=no_safe,
        safe_replies_with_tau_gt2=sum(1 for value in best_taus if value > 2),
        mean_black_tau_after_safe_reply=mean(best_taus) if best_taus else 0.0,
        max_black_tau_after_safe_reply=max(best_taus) if best_taus else 0,
        mean_black_obligations_after_safe_reply=mean(best_obligation_counts) if best_obligation_counts else 0.0,
        max_black_obligations_after_safe_reply=max(best_obligation_counts) if best_obligation_counts else 0,
    )


def connect_k_row(k: int, opening_limit: int | None = None, radius: int | None = None) -> ConnectKParityRow:
    r = analysis_radius(k) if radius is None else radius
    seed = seed_obligation_stats(k, radius=r)
    white = white_opening_obligation_stats(k, radius=r, opening_limit=opening_limit)
    black = black_first_reply_envelope(k, radius=r, opening_limit=opening_limit)
    return ConnectKParityRow(
        k=k,
        radius=r,
        prime=is_prime(k),
        parity="even" if k % 2 == 0 else "odd",
        tempo_owner=first_threat_tempo_owner(k),
        seed_obligations=seed.obligations,
        seed_tau=seed.tau,
        white_openings=white.openings,
        white_urgent_openings=white.urgent_openings,
        white_forcing_openings=white.forcing_openings,
        white_mean_tau=white.mean_tau,
        white_max_tau=white.max_tau,
        black_immediate_wins=black.black_immediate_wins,
        black_no_safe_reply_openings=black.no_safe_reply_openings,
        black_reply_tau_gt2_openings=black.safe_replies_with_tau_gt2,
        black_reply_mean_tau=black.mean_black_tau_after_safe_reply,
        black_reply_max_tau=black.max_black_tau_after_safe_reply,
    )


def sweep_connect_k(k_min: int, k_max: int, opening_limit: int | None = None) -> tuple[ConnectKParityRow, ...]:
    return tuple(connect_k_row(k, opening_limit=opening_limit) for k in range(k_min, k_max + 1))
