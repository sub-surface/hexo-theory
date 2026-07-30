"""Reproducible empirical sweep for Death HeXO.

The experiment combines four scales:

1. exhaustive local rewrite audits;
2. exact finite 1-D reachability games with draws and cycles;
3. transfer-matrix counts for stable fully occupied A2 rhombi;
4. matched Monte Carlo games with and without the death rule.

Run ``python experiments/run_death_hexo.py --quick`` for a development pass.
The full sweep is the default.
"""
from __future__ import annotations

import argparse
from collections import defaultdict, deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from itertools import product
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import RegularPolygon
import numpy as np

from death_hexo import (
    AXES,
    DIRS,
    DeathHexGame,
    add,
    annihilation_bomb_position,
    execute_null_cycle,
    make_agent,
    make_null_cycle_position,
    play_game,
    resolve_deaths,
    vulnerable_stones,
)

RESULT_DIR = ROOT / "evidence" / "results"
FIGURE_DIR = ROOT / "evidence" / "figures"
RESULT_PATH = RESULT_DIR / "death_hexo.json"


def _line_board(word: tuple[int, ...]) -> dict[tuple[int, int], int]:
    return {(i, 0): owner for i, owner in enumerate(word) if owner}


def _simultaneous_word(word: tuple[int, ...]) -> tuple[int, ...]:
    board = _line_board(word)
    resolve_deaths(board)
    return tuple(board.get((i, 0), 0) for i in range(len(word)))


def _sequential_word(word: tuple[int, ...], reverse: bool = False) -> tuple[int, ...]:
    cells = list(word)
    while True:
        vulnerable = [
            i
            for i in range(1, len(cells) - 1)
            if cells[i] and cells[i - 1] == cells[i + 1] == 3 - cells[i]
        ]
        if not vulnerable:
            return tuple(cells)
        cells[max(vulnerable) if reverse else min(vulnerable)] = 0


def rule_audit(max_length: int) -> dict:
    rows = []
    idempotence_violations = 0
    for length in range(1, max_length + 1):
        stable_binary = 0
        stable_ternary = 0
        order_sensitive = 0
        simultaneous_multi_death = 0
        for word in product((0, 1, 2), repeat=length):
            simultaneous = _simultaneous_word(word)
            if _simultaneous_word(simultaneous) != simultaneous:
                idempotence_violations += 1
            if simultaneous == word:
                stable_ternary += 1
            left = _sequential_word(word)
            right = _sequential_word(word, reverse=True)
            if simultaneous != left or simultaneous != right or left != right:
                order_sensitive += 1
            removed = sum(a != 0 and b == 0 for a, b in zip(word, simultaneous))
            if removed >= 2:
                simultaneous_multi_death += 1
        for word in product((1, 2), repeat=length):
            if _simultaneous_word(word) == word:
                stable_binary += 1
        rows.append(
            {
                "length": length,
                "stable_fully_occupied": stable_binary,
                "stable_with_empties": stable_ternary,
                "order_sensitive_positions": order_sensitive,
                "multi_stone_simultaneous_deaths": simultaneous_multi_death,
            }
        )

    recurrence_holds = all(
        rows[i]["stable_fully_occupied"]
        == rows[i - 1]["stable_fully_occupied"] + rows[i - 2]["stable_fully_occupied"]
        for i in range(2, len(rows))
    )
    ternary_recurrence_holds = all(
        rows[i]["stable_with_empties"]
        == 2 * rows[i - 1]["stable_with_empties"]
        + 2 * rows[i - 2]["stable_with_empties"]
        + rows[i - 3]["stable_with_empties"]
        for i in range(3, len(rows))
    )
    ternary_roots = np.roots([1.0, -2.0, -2.0, -1.0])
    ternary_real_root = float(max(root.real for root in ternary_roots))
    conjugate_moduli = sorted(
        float(abs(root)) for root in ternary_roots if not math.isclose(root.real, ternary_real_root)
    )
    game, centre = annihilation_bomb_position()
    bomb = game.make(*centre)
    before, after = execute_null_cycle(make_null_cycle_position())
    opening = DeathHexGame()
    opening.make(0, 0)
    opening.make(-1, 0)
    opening_event = opening.make(1, 0)
    return {
        "semantics": "simultaneous deletion after each atomic placement",
        "rows": rows,
        "idempotence_violations": idempotence_violations,
        "fibonacci_recurrence_holds": recurrence_holds,
        "asymptotic_growth_target": (1.0 + math.sqrt(5.0)) / 2.0,
        "stable_with_empties_algebra": {
            "recurrence": "b_n = 2 b_(n-1) + 2 b_(n-2) + b_(n-3)",
            "recurrence_holds": ternary_recurrence_holds,
            "minimal_polynomial": "x^3 - 2 x^2 - 2 x - 1",
            "growth_root": ternary_real_root,
            "conjugate_moduli": conjugate_moduli,
            "is_pisot": all(modulus < 1.0 for modulus in conjugate_moduli),
        },
        "annihilation_bomb": {
            "total_deaths": len(bomb.deaths) if bomb else None,
            "enemy_captures": len(bomb.captured) if bomb else None,
            "placed_stone_died": bomb.placed_stone_died if bomb else None,
            "net_board_change": (bomb.board_size_after - bomb.board_size_before) if bomb else None,
        },
        "null_cycle": {
            "placements": 4,
            "state_repeats_exactly": before == after,
        },
        "opening_inversion": {
            "black_opening_removed": (0, 0) not in opening.board,
            "white_survivors": sum(owner == 2 for owner in opening.board.values()),
            "black_survivors": sum(owner == 1 for owner in opening.board.values()),
            "black_to_move": opening.current_player == 1,
            "deaths_on_second_white_placement": len(opening_event.deaths) if opening_event else None,
        },
    }


def radial_capture_spectrum() -> dict:
    """Exhaust all stable radius-2 radial contexts for a Black centre move."""
    centre = (0, 0)
    ring = tuple(add(centre, direction) for direction in DIRS)
    supports = tuple(add(centre, direction, 2) for direction in DIRS)
    cells = ring + supports
    total_contexts = 0
    stable_contexts = 0
    capture_histogram: dict[int, int] = defaultdict(int)
    death_histogram: dict[int, int] = defaultdict(int)
    self_death_contexts = 0
    capture_contexts = 0

    for assignment in product((0, 1, 2), repeat=len(cells)):
        total_contexts += 1
        board = {cell: owner for cell, owner in zip(cells, assignment) if owner}
        if vulnerable_stones(board):
            continue
        stable_contexts += 1
        board[centre] = 1
        deaths = resolve_deaths(board)
        captured = sum(owner == 2 for _, owner in deaths)
        self_died = any(cell == centre for cell, _ in deaths)
        capture_histogram[captured] += 1
        death_histogram[len(deaths)] += 1
        self_death_contexts += int(self_died)
        capture_contexts += int(captured > 0)

    return {
        "scope": "uniform enumeration of 12 radial cells; pre-position required stable",
        "total_contexts": total_contexts,
        "stable_contexts": stable_contexts,
        "capture_histogram": {str(k): v for k, v in sorted(capture_histogram.items())},
        "total_death_histogram": {str(k): v for k, v in sorted(death_histogram.items())},
        "capture_context_fraction": capture_contexts / stable_contexts,
        "self_death_context_fraction": self_death_contexts / stable_contexts,
        "mean_enemy_captures": sum(k * v for k, v in capture_histogram.items()) / stable_contexts,
        "mean_total_deaths": sum(k * v for k, v in death_histogram.items()) / stable_contexts,
        "maximum_enemy_captures": max(capture_histogram),
        "maximum_total_deaths": max(death_histogram),
    }


def _stable_binary_rows(width: int) -> tuple[int, ...]:
    rows = []
    for bits in range(1 << width):
        seq = tuple((bits >> q) & 1 for q in range(width))
        if all(not (seq[q] == seq[q + 2] != seq[q + 1]) for q in range(width - 2)):
            rows.append(bits)
    return tuple(rows)


def _bit(row: int, q: int) -> int:
    return (row >> q) & 1


def _compatible_triple(older: int, previous: int, new: int, width: int) -> bool:
    for q in range(width):
        if _bit(older, q) == _bit(new, q) != _bit(previous, q):
            return False
    for q in range(width - 2):
        if _bit(new, q) == _bit(older, q + 2) != _bit(previous, q + 1):
            return False
    return True


def count_stable_rhombus(size: int) -> int:
    """Count full binary A2 colorings of an n x n axial rhombus without x-o-x."""
    rows = _stable_binary_rows(size)
    if size == 1:
        return len(rows)
    states = {(first, second): 1 for first in rows for second in rows}
    if size == 2:
        return sum(states.values())
    compatibility = {
        (older, previous): tuple(
            new for new in rows if _compatible_triple(older, previous, new, size)
        )
        for older in rows
        for previous in rows
    }
    for _ in range(2, size):
        nxt: dict[tuple[int, int], int] = defaultdict(int)
        for (older, previous), count in states.items():
            for new in compatibility[(older, previous)]:
                nxt[(previous, new)] += count
        states = nxt
    return sum(states.values())


def stable_rhombus_sweep(max_size: int) -> list[dict]:
    out = []
    for size in range(1, max_size + 1):
        count = count_stable_rhombus(size)
        out.append(
            {
                "size": size,
                "sites": size * size,
                "count": count,
                "bits_per_site": math.log2(count) / (size * size),
                "row_alphabet_size": len(_stable_binary_rows(size)),
            }
        )
    return out


def fit_stable_entropy(rows: list[dict], min_size: int = 4) -> dict:
    """Finite-size fit h(n)=h_inf+a/n+b/n^2; exploratory, not a proof."""
    selected = [row for row in rows if row["size"] >= min_size]
    design = np.array(
        [[1.0, 1.0 / row["size"], 1.0 / (row["size"] ** 2)] for row in selected]
    )
    target = np.array([row["bits_per_site"] for row in selected])
    coefficients = np.linalg.lstsq(design, target, rcond=None)[0]
    residual = design @ coefficients - target
    entropy = float(coefficients[0])
    return {
        "model": "h(n) = h_inf + a/n + b/n^2",
        "min_size": min_size,
        "max_size": max(row["size"] for row in selected),
        "h_inf_bits_per_site": entropy,
        "growth_base_per_site": 2.0**entropy,
        "a": float(coefficients[1]),
        "b": float(coefficients[2]),
        "rmse": float(math.sqrt(float(np.mean(residual**2)))),
        "status": "small-strip extrapolation",
    }


LineState = tuple[tuple[int, ...], int, int, bool]
Terminal = tuple[str, int]


def _line_has_win(word: tuple[int, ...], player: int, connect: int) -> bool:
    run = 0
    for owner in word:
        run = run + 1 if owner == player else 0
        if run >= connect:
            return True
    return False


def _line_move(
    state: LineState,
    index: int,
    connect: int,
    death_rule: bool,
) -> Terminal | LineState:
    word, player, placed, opening_done = state
    cells = list(word)
    if cells[index] != 0:
        raise ValueError("occupied line cell")
    cells[index] = player
    if death_rule:
        cells = list(_simultaneous_word(tuple(cells)))
    new_word = tuple(cells)
    if _line_has_win(new_word, player, connect):
        return ("terminal", player)

    limit = 2 if opening_done else 1
    placed += 1
    if placed >= limit:
        player = 3 - player
        placed = 0
        opening_done = True
    if not any(owner == 0 for owner in new_word):
        return ("terminal", 0)
    return (new_word, player, placed, opening_done)


def _line_move_details(
    state: LineState,
    index: int,
    connect: int,
    death_rule: bool,
) -> tuple[Terminal | LineState, tuple[int, ...], tuple[int, ...]]:
    placed_word = list(state[0])
    placed_word[index] = state[1]
    child = _line_move(state, index, connect, death_rule)
    if death_rule:
        resolved = _simultaneous_word(tuple(placed_word))
    else:
        resolved = tuple(placed_word)
    deaths = tuple(i for i, (before, after) in enumerate(zip(placed_word, resolved)) if before and not after)
    return child, resolved, deaths


def solve_finite_line(length: int, connect: int, death_rule: bool) -> dict:
    """Exact reachability-game solution; unresolved attractor complement is draw."""
    start: LineState = ((0,) * length, 1, 0, False)
    queue = deque([start])
    nodes = {start}
    successors: dict[LineState, tuple[Terminal | LineState, ...]] = {}
    successor_moves: dict[LineState, tuple[tuple[int, Terminal | LineState], ...]] = {}
    edge_count = 0

    while queue:
        state = queue.popleft()
        word = state[0]
        moves: list[Terminal | LineState] = []
        indexed_moves: list[tuple[int, Terminal | LineState]] = []
        for index, owner in enumerate(word):
            if owner:
                continue
            nxt = _line_move(state, index, connect, death_rule)
            moves.append(nxt)
            indexed_moves.append((index, nxt))
            if not (isinstance(nxt[0], str)) and nxt not in nodes:
                nodes.add(nxt)
                queue.append(nxt)
        if not moves:
            moves.append(("terminal", 0))
            indexed_moves.append((-1, ("terminal", 0)))
        successors[state] = tuple(moves)
        successor_moves[state] = tuple(indexed_moves)
        edge_count += len(moves)

    values: dict[LineState, int] = {}
    ranks: dict[LineState, int] = {}
    iterations = 0
    while True:
        iterations += 1
        changed = 0
        for state in nodes:
            if state in values:
                continue
            child_values: list[int | None] = []
            for child in successors[state]:
                if isinstance(child[0], str):
                    child_values.append(1 if child[1] == 1 else -1 if child[1] == 2 else 0)
                else:
                    child_values.append(values.get(child))
            controller = state[1]
            if controller == 1:
                if 1 in child_values:
                    values[state] = 1
                elif child_values and all(value == -1 for value in child_values):
                    values[state] = -1
            else:
                if -1 in child_values:
                    values[state] = -1
                elif child_values and all(value == 1 for value in child_values):
                    values[state] = 1
            if state in values:
                ranks[state] = iterations
                changed += 1
        if not changed:
            break

    root_value = values.get(start, 0)
    draw_states = len(nodes) - len(values)
    root_move_values = []
    for index, child in successor_moves[start]:
        if isinstance(child[0], str):
            child_value = 1 if child[1] == 1 else -1 if child[1] == 2 else 0
            child_rank = 0
        else:
            child_value = values.get(child, 0)
            child_rank = ranks.get(child)
        root_move_values.append(
            {
                "cell": index,
                "value": child_value,
                "outcome": "black" if child_value == 1 else "white" if child_value == -1 else "draw",
                "attractor_rank": child_rank,
            }
        )
    principal_variation = []
    if root_value:
        state = start
        for _ in range(4 * len(nodes) + 4):
            options = []
            for index, child in successor_moves[state]:
                if isinstance(child[0], str):
                    value = 1 if child[1] == 1 else -1 if child[1] == 2 else 0
                    rank = 0
                else:
                    value = values.get(child, 0)
                    rank = ranks.get(child, 10**9)
                if value == root_value:
                    options.append((rank, index, child))
            if not options:
                break
            if state[1] == (1 if root_value == 1 else 2):
                _, index, child = min(options)
            else:
                _, index, child = max(options)
            detailed_child, resolved, deaths = _line_move_details(state, index, connect, death_rule)
            if detailed_child != child:
                raise AssertionError("principal-variation transition mismatch")
            principal_variation.append(
                {
                    "player": state[1],
                    "cell": index,
                    "before": list(state[0]),
                    "after": list(resolved),
                    "deaths": list(deaths),
                    "terminal": child[1] if isinstance(child[0], str) else None,
                }
            )
            if isinstance(child[0], str):
                break
            state = child
    return {
        "length": length,
        "connect": connect,
        "death_rule": death_rule,
        "root_outcome": "black" if root_value == 1 else "white" if root_value == -1 else "draw",
        "root_value": root_value,
        "reachable_states": len(nodes),
        "edges": edge_count,
        "draw_states": draw_states,
        "draw_state_fraction": draw_states / len(nodes),
        "attractor_iterations": iterations,
        "root_move_values": root_move_values,
        "principal_variation": principal_variation,
    }


def exact_line_sweep(max_length: int) -> list[dict]:
    results = []
    for length in range(3, max_length + 1):
        for connect in range(3, min(6, length) + 1):
            for death_rule in (False, True):
                results.append(solve_finite_line(length, connect, death_rule))
    return results


def _simulation_job(spec: tuple) -> dict:
    (
        variant,
        death_rule,
        timing,
        black_name,
        white_name,
        seed,
        max_placements,
        opening_placements,
    ) = spec
    black = make_agent(black_name, seed * 2 + 1)
    white = make_agent(white_name, seed * 2 + 2)
    record = play_game(
        black,
        white,
        death_rule=death_rule,
        death_timing=timing,
        max_placements=max_placements,
        random_opening_placements=opening_placements,
        opening_seed=seed + 991,
    )
    record.update(
        {
            "variant": variant,
            "death_rule": death_rule,
            "death_timing": timing,
            "black_agent": black_name,
            "white_agent": white_name,
            "seed": seed,
        }
    )
    return record


def _wilson(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total == 0:
        return (0.0, 1.0)
    p = successes / total
    denom = 1.0 + z * z / total
    centre = (p + z * z / (2.0 * total)) / denom
    half = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def aggregate_simulations(records: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for record in records:
        key = (record["variant"], record["black_agent"], record["white_agent"])
        groups[key].append(record)

    metrics = (
        "placements",
        "final_stones",
        "total_deaths",
        "captures_black",
        "captures_white",
        "suicides_black",
        "suicides_white",
        "max_deaths_single_placement",
        "repeat_visits",
        "max_state_multiplicity",
        "max_run_black",
        "max_run_white",
        "mean_live_stones",
    )
    out = []
    for (variant, black, white), games in sorted(groups.items()):
        black_wins = sum(game["winner"] == 1 for game in games)
        white_wins = sum(game["winner"] == 2 for game in games)
        decisive = black_wins + white_wins
        summary = {
            "variant": variant,
            "black_agent": black,
            "white_agent": white,
            "games": len(games),
            "black_wins": black_wins,
            "white_wins": white_wins,
            "draws_or_cutoffs": len(games) - decisive,
            "decisive_fraction": decisive / len(games),
            "black_share_decisive": black_wins / decisive if decisive else None,
            "black_share_wilson95": list(_wilson(black_wins, decisive)),
            "repeat_game_fraction": sum(game["repeat_visits"] > 0 for game in games) / len(games),
            "turnover": sum(game["total_deaths"] for game in games)
            / max(1, sum(game["placements"] for game in games)),
            "live_stone_yield": sum(game["final_stones"] for game in games)
            / max(1, sum(game["placements"] for game in games)),
        }
        for metric in metrics:
            values = [float(game[metric]) for game in games]
            summary[f"mean_{metric}"] = statistics.fmean(values)
            summary[f"median_{metric}"] = statistics.median(values)
        out.append(summary)
    return out


def simulation_sweep(
    games_per_matchup: int,
    max_placements: int,
    workers: int,
    opening_placements: int,
) -> tuple[list[dict], list[dict]]:
    matchups = (
        ("random", "random"),
        ("line", "line"),
        ("hunter", "hunter"),
        ("hybrid", "hybrid"),
        ("hybrid", "line"),
        ("line", "hybrid"),
    )
    variants = (
        ("ordinary", False, "placement", matchups),
        ("death", True, "placement", matchups),
        ("death_turn_end", True, "turn", (("hybrid", "hybrid"),)),
    )
    specs = []
    for variant, death_rule, timing, variant_matchups in variants:
        for black, white in variant_matchups:
            for game_index in range(games_per_matchup):
                seed = 1729 + game_index + 1000 * len(specs)
                specs.append(
                    (
                        variant,
                        death_rule,
                        timing,
                        black,
                        white,
                        seed,
                        max_placements,
                        opening_placements,
                    )
                )

    if workers == 1:
        records = [_simulation_job(spec) for spec in specs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            records = list(pool.map(_simulation_job, specs, chunksize=1))
    return aggregate_simulations(records), records


def _hex_xy(cell: tuple[int, int]) -> tuple[float, float]:
    q, r = cell
    return (q + 0.5 * r, math.sqrt(3.0) * 0.5 * r)


def _draw_board(ax, board: Iterable[tuple[int, int, int]], title: str) -> None:
    board = list(board)
    if not board:
        ax.set_title(title)
        ax.axis("off")
        return
    for q, r, owner in board:
        x, y = _hex_xy((q, r))
        patch = RegularPolygon(
            (x, y),
            numVertices=6,
            radius=0.48,
            orientation=math.pi / 6,
            facecolor="#191919" if owner == 1 else "#f4f0e8",
            edgecolor="#6e6e6e",
            linewidth=0.8,
        )
        ax.add_patch(patch)
    xs, ys = zip(*(_hex_xy((q, r)) for q, r, _ in board))
    ax.set_xlim(min(xs) - 1.0, max(xs) + 1.0)
    ax.set_ylim(min(ys) - 1.0, max(ys) + 1.0)
    ax.set_aspect("equal")
    ax.set_title(title)
    ax.axis("off")


def plot_mechanics(path: Path) -> None:
    game, centre = annihilation_bomb_position()
    pre = dict(game.board)
    pre[centre] = 1
    doomed = vulnerable_stones(pre)
    event = game.make(*centre)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), constrained_layout=True)
    _draw_board(axes[0], [(q, r, p) for (q, r), p in pre.items()], "Post-placement: 7 stones marked")
    for cell in doomed:
        x, y = _hex_xy(cell)
        axes[0].plot(x, y, "x", color="#d62728", markersize=15, markeredgewidth=2.4)
    _draw_board(
        axes[1],
        [(q, r, p) for (q, r), p in game.board.items()],
        f"After simultaneous cleanup: net {event.board_size_after - event.board_size_before:+d}",
    )
    fig.suptitle("Death HeXO annihilation bomb (black plays the centre)", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_stable_entropy(rule: dict, rhombi: list[dict], path: Path) -> None:
    lengths = np.array([row["length"] for row in rule["rows"]])
    binary_counts = np.array(
        [row["stable_fully_occupied"] for row in rule["rows"]], dtype=float
    )
    ternary_counts = np.array(
        [row["stable_with_empties"] for row in rule["rows"]], dtype=float
    )
    binary_ratios = binary_counts[1:] / binary_counts[:-1]
    ternary_ratios = ternary_counts[1:] / ternary_counts[:-1]
    phi = (1.0 + math.sqrt(5.0)) / 2.0
    lambda_death = rule["stable_with_empties_algebra"]["growth_root"]
    sizes = np.array([row["size"] for row in rhombi])
    entropy = np.array([row["bits_per_site"] for row in rhombi])

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.3), constrained_layout=True)
    axes[0].plot(lengths, binary_counts, "o-", color="#1f77b4", label="occupied: {B,W}")
    axes[0].plot(lengths, ternary_counts, "s-", color="#ff7f0e", label="with empty: {0,B,W}")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("line length n")
    axes[0].set_ylabel("count")
    axes[0].set_title("1-D stable-word counts")
    axes[0].legend(fontsize=8)

    axes[1].plot(lengths[1:], binary_ratios, "o-", color="#1f77b4", label="occupied ratio")
    axes[1].plot(lengths[1:], ternary_ratios, "s-", color="#ff7f0e", label="vacancy ratio")
    axes[1].axhline(phi, color="#1f77b4", alpha=0.5, linestyle="--", label="phi")
    axes[1].axhline(
        lambda_death,
        color="#ff7f0e",
        alpha=0.5,
        linestyle="--",
        label="lambda_D",
    )
    axes[1].set_xlabel("line length n")
    axes[1].set_ylabel("successive-count ratio")
    axes[1].set_title("Two exact Pisot entropy bases")
    axes[1].legend(fontsize=8)

    axes[2].plot(sizes, entropy, "o-", color="#2ca02c")
    axes[2].axhline(math.log2(phi), color="#7f7f7f", linestyle="--", label="1-D log2(phi)")
    axes[2].set_xlabel("n for n x n axial rhombus")
    axes[2].set_ylabel("log2(count) / n^2")
    axes[2].set_title("2-D stable-coloring entropy density")
    axes[2].legend(fontsize=8)
    fig.suptitle("The death rule selects a finite-type stable subshift", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_exact_phase(exact: list[dict], path: Path) -> None:
    lengths = sorted({row["length"] for row in exact})
    connects = sorted({row["connect"] for row in exact})
    matrices = {}
    for death_rule in (False, True):
        root = np.full((len(connects), len(lengths)), np.nan)
        draw = np.full_like(root, np.nan)
        for row in exact:
            if row["death_rule"] != death_rule:
                continue
            i = connects.index(row["connect"])
            j = lengths.index(row["length"])
            root[i, j] = row["root_value"]
            draw[i, j] = row["draw_state_fraction"]
        matrices[death_rule] = (root, draw)

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), constrained_layout=True)
    cmap = ListedColormap(["#d95f5f", "#d9d9d9", "#222222"])
    for ax, death_rule, title in zip(axes[:2], (False, True), ("ordinary", "death")):
        masked = np.ma.masked_invalid(matrices[death_rule][0])
        image = ax.imshow(masked, vmin=-1, vmax=1, cmap=cmap, origin="lower", aspect="auto")
        ax.set_title(f"Root outcome: {title}")
        ax.set_xticks(range(len(lengths)), lengths)
        ax.set_yticks(range(len(connects)), connects)
        ax.set_xlabel("finite line length")
        ax.set_ylabel("connect-k")
        for i in range(len(connects)):
            for j in range(len(lengths)):
                if not np.isnan(matrices[death_rule][0][i, j]):
                    label = {1: "B", 0: "D", -1: "W"}[int(matrices[death_rule][0][i, j])]
                    color = "white" if label in {"B", "W"} else "black"
                    ax.text(j, i, label, ha="center", va="center", color=color, fontsize=9)

    delta = matrices[True][1] - matrices[False][1]
    im = axes[2].imshow(np.ma.masked_invalid(delta), cmap="coolwarm", origin="lower", aspect="auto")
    axes[2].set_title("Change in draw-state fraction")
    axes[2].set_xticks(range(len(lengths)), lengths)
    axes[2].set_yticks(range(len(connects)), connects)
    axes[2].set_xlabel("finite line length")
    axes[2].set_ylabel("connect-k")
    fig.colorbar(im, ax=axes[2], shrink=0.85)
    fig.suptitle("Exact 1-D 1-2-2 reachability games (B=Black, W=White, D=draw)", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_empirical(summaries: list[dict], path: Path) -> None:
    rows = [row for row in summaries if row["variant"] in {"ordinary", "death"}]
    labels = [
        f"{row['black_agent']} v {row['white_agent']}"
        for row in rows
        if row["variant"] == "ordinary"
    ]
    metrics = (
        ("decisive_fraction", "decisive fraction"),
        ("turnover", "deaths / placement"),
        ("live_stone_yield", "final stones / placement"),
        ("repeat_game_fraction", "games revisiting a state"),
    )
    lookup = {(row["variant"], row["black_agent"], row["white_agent"]): row for row in rows}
    pairs = [tuple(label.split(" v ")) for label in labels]
    x = np.arange(len(labels))
    width = 0.38
    fig, axes = plt.subplots(2, 2, figsize=(13, 8), constrained_layout=True)
    for ax, (metric, title) in zip(axes.flat, metrics):
        ordinary = [lookup[("ordinary", a, b)][metric] for a, b in pairs]
        death = [lookup[("death", a, b)][metric] for a, b in pairs]
        ax.bar(x - width / 2, ordinary, width, label="ordinary", color="#9ecae1")
        ax.bar(x + width / 2, death, width, label="death", color="#fb6a4a")
        ax.set_title(title)
        ax.set_xticks(x, labels, rotation=25, ha="right", fontsize=8)
        ax.grid(axis="y", alpha=0.2)
    axes[0, 0].legend()
    fig.suptitle("Matched local-policy self-play: death rule versus ordinary HeXO", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_samples(records: list[dict], path: Path) -> None:
    selected = {}
    for record in records:
        key = (record["variant"], record["black_agent"], record["white_agent"])
        if key in {
            ("ordinary", "hybrid", "hybrid"),
            ("death", "hybrid", "hybrid"),
        } and key not in selected:
            selected[key] = record
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), constrained_layout=True)
    for ax, variant in zip(axes, ("ordinary", "death")):
        record = selected[(variant, "hybrid", "hybrid")]
        _draw_board(
            ax,
            record["board"],
            f"{variant}: {record['final_stones']} live / {record['placements']} placed\n"
            f"winner={record['winner']}, deaths={record['total_deaths']}",
        )
    fig.suptitle("Representative hybrid self-play endpoints", fontsize=14)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def _git_snapshot() -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip()
        )
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="small development sweep")
    parser.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 1))
    parser.add_argument(
        "--exact-extension",
        action="store_true",
        help="append the n=10/11 boundary audit to an existing full result",
    )
    parser.add_argument(
        "--local-extension",
        action="store_true",
        help="append the exact radius-2 capture spectrum to an existing result",
    )
    parser.add_argument(
        "--refresh-derived",
        action="store_true",
        help="refresh fast derived statistics in an existing result",
    )
    args = parser.parse_args()

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    if args.refresh_derived:
        if not RESULT_PATH.exists():
            raise FileNotFoundError("run the experiment before --refresh-derived")
        payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        payload["config"]["exact_boundary_cases"] = [[10, 5], [10, 6], [11, 6]]
        payload["rule_audit"] = rule_audit(payload["config"]["rule_audit_max_length"])
        payload["stable_rhombus_fit"] = fit_stable_entropy(payload["stable_rhombi"])
        ternary_roots = np.roots([1.0, -2.0, -2.0, -1.0])
        ternary_real_root = float(max(root.real for root in ternary_roots))
        conjugate_moduli = sorted(
            float(abs(root))
            for root in ternary_roots
            if not math.isclose(root.real, ternary_real_root)
        )
        ternary_rows = payload["rule_audit"]["rows"]
        payload["rule_audit"]["stable_with_empties_algebra"] = {
            "recurrence": "b_n = 2 b_(n-1) + 2 b_(n-2) + b_(n-3)",
            "recurrence_holds": all(
                ternary_rows[i]["stable_with_empties"]
                == 2 * ternary_rows[i - 1]["stable_with_empties"]
                + 2 * ternary_rows[i - 2]["stable_with_empties"]
                + ternary_rows[i - 3]["stable_with_empties"]
                for i in range(3, len(ternary_rows))
            ),
            "minimal_polynomial": "x^3 - 2 x^2 - 2 x - 1",
            "growth_root": ternary_real_root,
            "conjugate_moduli": conjugate_moduli,
            "is_pisot": all(modulus < 1.0 for modulus in conjugate_moduli),
        }
        opening = DeathHexGame()
        opening.make(0, 0)
        opening.make(-1, 0)
        opening_event = opening.make(1, 0)
        payload["rule_audit"]["opening_inversion"] = {
            "black_opening_removed": (0, 0) not in opening.board,
            "white_survivors": sum(owner == 2 for owner in opening.board.values()),
            "black_survivors": sum(owner == 1 for owner in opening.board.values()),
            "black_to_move": opening.current_player == 1,
            "deaths_on_second_white_placement": len(opening_event.deaths) if opening_event else None,
        }
        for summary in payload["simulations"]:
            decisive = summary["black_wins"] + summary["white_wins"]
            summary["decisive_fraction_wilson95"] = list(
                _wilson(decisive, summary["games"])
            )
        RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        plot_stable_entropy(
            payload["rule_audit"],
            payload["stable_rhombi"],
            FIGURE_DIR / "fig_death_hexo_stable_entropy.png",
        )
        plot_exact_phase(
            payload["exact_finite_lines"],
            FIGURE_DIR / "fig_death_hexo_exact_phase.png",
        )
        print(json.dumps({
            "result": str(RESULT_PATH),
            "stable_rhombus_fit": payload["stable_rhombus_fit"],
        }, indent=2))
        return

    if args.local_extension:
        if not RESULT_PATH.exists():
            raise FileNotFoundError("run the experiment before --local-extension")
        payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        payload["radial_capture_spectrum"] = radial_capture_spectrum()
        RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({
            "result": str(RESULT_PATH),
            "radial_capture_spectrum": payload["radial_capture_spectrum"],
        }, indent=2))
        return

    if args.exact_extension:
        if not RESULT_PATH.exists():
            raise FileNotFoundError("run the full experiment before --exact-extension")
        payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
        extension = [
            solve_finite_line(10, 5, True),
            solve_finite_line(10, 6, True),
            solve_finite_line(11, 6, True),
        ]
        keys = {(row["length"], row["connect"], row["death_rule"]) for row in extension}
        retained = [
            row
            for row in payload["exact_finite_lines"]
            if (row["length"], row["connect"], row["death_rule"]) not in keys
        ]
        payload["exact_finite_lines"] = retained + extension
        payload["exact_boundary_audit"] = {
            "cases": [[10, 5], [10, 6], [11, 6]],
            "purpose": "test and falsify the provisional n=2k-1 White-win threshold",
        }
        RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        plot_exact_phase(payload["exact_finite_lines"], FIGURE_DIR / "fig_death_hexo_exact_phase.png")
        print(json.dumps({"result": str(RESULT_PATH), "extension": extension}, indent=2))
        return

    started = time.perf_counter()
    config = {
        "quick": args.quick,
        "seed_base": 1729,
        "rule_audit_max_length": 7 if args.quick else 10,
        "rhombus_max_size": 5 if args.quick else 8,
        "exact_line_max_length": 7 if args.quick else 9,
        "exact_boundary_cases": [] if args.quick else [[10, 5], [10, 6], [11, 6]],
        "games_per_matchup": 4 if args.quick else 24,
        "max_placements": 70 if args.quick else 140,
        "random_opening_placements": 4 if args.quick else 8,
        "workers": max(1, args.workers),
    }

    rule = rule_audit(config["rule_audit_max_length"])
    rhombi = stable_rhombus_sweep(config["rhombus_max_size"])
    exact = exact_line_sweep(config["exact_line_max_length"])
    if not args.quick:
        exact.extend(
            (
                solve_finite_line(10, 5, True),
                solve_finite_line(10, 6, True),
                solve_finite_line(11, 6, True),
            )
        )
    simulations, records = simulation_sweep(
        config["games_per_matchup"],
        config["max_placements"],
        config["workers"],
        config["random_opening_placements"],
    )

    plot_mechanics(FIGURE_DIR / "fig_death_hexo_mechanics.png")
    plot_stable_entropy(rule, rhombi, FIGURE_DIR / "fig_death_hexo_stable_entropy.png")
    plot_exact_phase(exact, FIGURE_DIR / "fig_death_hexo_exact_phase.png")
    plot_empirical(simulations, FIGURE_DIR / "fig_death_hexo_empirical.png")
    plot_samples(records, FIGURE_DIR / "fig_death_hexo_samples.png")

    sample_games = []
    seen_samples = set()
    for record in records:
        key = (record["variant"], record["black_agent"], record["white_agent"])
        if key in seen_samples:
            continue
        seen_samples.add(key)
        sample_games.append(record)

    payload = {
        "experiment": "death_hexo",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "git": _git_snapshot(),
        "rule_audit": rule,
        "radial_capture_spectrum": radial_capture_spectrum(),
        "stable_rhombi": rhombi,
        "stable_rhombus_fit": fit_stable_entropy(rhombi),
        "exact_finite_lines": exact,
        "simulations": simulations,
        "sample_games": sample_games,
        "wall_seconds": time.perf_counter() - started,
        "figures": [
            "evidence/figures/fig_death_hexo_mechanics.png",
            "evidence/figures/fig_death_hexo_stable_entropy.png",
            "evidence/figures/fig_death_hexo_exact_phase.png",
            "evidence/figures/fig_death_hexo_empirical.png",
            "evidence/figures/fig_death_hexo_samples.png",
        ],
    }
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "result": str(RESULT_PATH),
        "wall_seconds": payload["wall_seconds"],
        "idempotence_violations": rule["idempotence_violations"],
        "annihilation_bomb": rule["annihilation_bomb"],
        "null_cycle": rule["null_cycle"],
        "largest_rhombus": rhombi[-1],
        "simulation_groups": len(simulations),
    }, indent=2))


if __name__ == "__main__":
    main()
