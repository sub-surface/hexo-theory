"""Lightweight geometry and repair probes for Death HeXO.

This experiment asks whether the death rule admits an exact aperiodic safe
geometry, then separates passive erasure repair from adversarial self-repair.
It replays already-recorded games for the empirical diagnostics and GIFs, so
the default run adds very little compute or heat.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
import math
from pathlib import Path
import random
import time
from typing import Iterable, Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from death_hexo import (
    AXES,
    DeathEvent,
    DeathHexGame,
    add,
    has_win,
    hex_distance,
    iter_cells_in_radius,
    resolve_deaths,
    stable_board,
    transform_cell,
)

RESULT_PATH = ROOT / "evidence" / "results" / "aperiodic_repair.json"
FIGURE_PATH = ROOT / "evidence" / "figures" / "fig_aperiodic_repair.png"
CAPTURE_GIF = ROOT / "evidence" / "figures" / "gif_death_hexo_capture_loop.gif"
GROWTH_GIF = ROOT / "evidence" / "figures" / "gif_death_hexo_aperiodic_growth.gif"
BASE_RESULT = ROOT / "evidence" / "results" / "death_hexo.json"

# The three directional increments are alpha, beta, and alpha-beta.
# All lie strictly between 1/5 and 1/2 in modulus.
ALPHA = math.sqrt(2.0) / 3.0
BETA = math.sqrt(3.0) / 8.0
PHASE = 1.0 / 7.0


def height_owner(cell: tuple[int, int], phase: float = PHASE) -> int:
    """Two-color irrational-height coding on the Eisenstein lattice."""
    q, r = cell
    return 1 + (math.floor(ALPHA * q + BETA * r + phase) & 1)


def height_patch(radius: int, phase: float = PHASE) -> dict[tuple[int, int], int]:
    return {cell: height_owner(cell, phase) for cell in iter_cells_in_radius(radius)}


def directional_steps() -> dict[str, float]:
    return {"q": ALPHA, "r": BETA, "q-r diagonal": ALPHA - BETA}


def factor_complexity(step: float, max_length: int, samples: int = 20_000) -> list[int]:
    word = tuple((math.floor(PHASE + i * step) & 1) for i in range(samples))
    return [len({word[i : i + n] for i in range(samples - n + 1)}) for n in range(1, max_length + 1)]


def finite_period_search(radius: int, max_shift: int) -> list[list[int]]:
    """Return shifts that imitate a period throughout a large finite window."""
    cells = tuple(iter_cells_in_radius(radius))
    candidates = []
    for dq in range(-max_shift, max_shift + 1):
        for dr in range(-max_shift, max_shift + 1):
            if (dq, dr) == (0, 0):
                continue
            if all(height_owner(cell) == height_owner(add(cell, (dq, dr))) for cell in cells):
                candidates.append([dq, dr])
    return candidates


def approximate_periods(max_shift: int, limit: int = 12) -> list[dict]:
    """Rank lattice translations by phase drift modulo the color period two."""
    rows = []
    for dq in range(-max_shift, max_shift + 1):
        for dr in range(-max_shift, max_shift + 1):
            if (dq, dr) == (0, 0):
                continue
            phase_shift = ALPHA * dq + BETA * dr
            nearest_even = 2 * round(phase_shift / 2)
            residual = abs(phase_shift - nearest_even)
            rows.append(
                {
                    "shift": [dq, dr],
                    "hex_distance": hex_distance((dq, dr)),
                    "phase_shift": phase_shift,
                    "nearest_even_integer": nearest_even,
                    "residual": residual,
                    "predicted_mismatch_density": residual,
                }
            )
    rows.sort(key=lambda row: (row["residual"], row["hex_distance"], row["shift"]))
    unique_up_to_sign = []
    seen = set()
    for row in rows:
        dq, dr = row["shift"]
        canonical = min((dq, dr), (-dq, -dr))
        if canonical in seen:
            continue
        seen.add(canonical)
        unique_up_to_sign.append(row)
        if len(unique_up_to_sign) == limit:
            break
    return unique_up_to_sign


def erasure_repair_audit(
    radius: int,
    deletion_sizes: Iterable[int],
    trials: int,
    seed: int,
) -> list[dict]:
    """Delete target stones, then restore them in random order."""
    target = height_patch(radius)
    cells = tuple(target)
    rng = random.Random(seed)
    rows = []
    for requested in deletion_sizes:
        size = min(requested, len(cells))
        failures = 0
        death_events = 0
        win_events = 0
        for _ in range(trials):
            deleted = rng.sample(cells, size)
            board = {cell: owner for cell, owner in target.items() if cell not in deleted}
            rng.shuffle(deleted)
            for cell in deleted:
                board[cell] = target[cell]
                death_events += len(resolve_deaths(board))
                win_events += int(has_win(board, 1) or has_win(board, 2))
            failures += int(board != target)
        rows.append(
            {
                "deleted": size,
                "trials": trials,
                "failed_repairs": failures,
                "deaths_during_repair": death_events,
                "wins_during_repair": win_events,
            }
        )
    return rows


def hostile_invasion_spectrum() -> dict:
    """Classify every radius-2 phase context after flipping the centre color."""
    context_domain = tuple(iter_cells_in_radius(2))
    audit_domain = tuple(iter_cells_in_radius(4))
    boundaries = []
    for q, r in context_domain:
        height = ALPHA * q + BETA * r
        boundaries.extend(((-height) % 2.0, (1.0 - height) % 2.0))
    boundaries.sort()
    if len(boundaries) != 38 or len(set(boundaries)) != 38:
        raise AssertionError("irrational-height phase boundaries unexpectedly collided")

    classes: Counter[tuple[bool, int, int | None]] = Counter()
    measures: Counter[tuple[bool, int, int | None]] = Counter()
    rejected_measure = 0.0
    repaired_measure = 0.0
    surviving_invasions_frozen = True
    rejected_invasions_repair = True

    for index, lower in enumerate(boundaries):
        upper = boundaries[(index + 1) % len(boundaries)]
        if index == len(boundaries) - 1:
            upper += 2.0
        phase = ((lower + upper) / 2.0) % 2.0
        measure = (upper - lower) / 2.0
        target = {cell: height_owner(cell, phase) for cell in audit_domain}
        board = dict(target)
        board[(0, 0)] = 3 - board[(0, 0)]
        deaths = resolve_deaths(board)
        invader_died = (0, 0) not in board
        collateral = sum(cell != (0, 0) for cell, _ in deaths)
        missing = [cell for cell in target if cell not in board]
        for cell in missing:
            board[cell] = target[cell]
            resolve_deaths(board)
        repaired = board == target
        repair_actions = len(missing) if repaired else None
        key = (invader_died, collateral, repair_actions)
        classes[key] += 1
        measures[key] += measure
        rejected_measure += measure * invader_died
        repaired_measure += measure * repaired
        rejected_invasions_repair &= (not invader_died) or repaired
        surviving_invasions_frozen &= invader_died or not repaired

    rows = []
    for key in sorted(classes, key=lambda value: (not value[0], value[1], value[2] or 99)):
        invader_died, collateral, repair_actions = key
        rows.append(
            {
                "invader_died": invader_died,
                "collateral_target_deaths": collateral,
                "target_color_repair_actions": repair_actions,
                "phase_contexts": classes[key],
                "phase_measure": measures[key],
            }
        )
    expected_rejection = 1.0 - 2.0 * min(abs(step) for step in directional_steps().values())
    return {
        "phase_contexts": len(boundaries),
        "classes": rows,
        "invader_rejection_measure": rejected_measure,
        "closed_form_rejection_measure": "1 - 2 beta = 1 - sqrt(3)/4",
        "closed_form_rejection_value": expected_rejection,
        "repairable_measure": repaired_measure,
        "all_rejected_invasions_target_repairable": rejected_invasions_repair,
        "all_surviving_invasions_frozen_under_target_only_refill": surviving_invasions_frozen,
    }


@dataclass
class ReplayFrame:
    board_before: dict[tuple[int, int], int]
    board_after: dict[tuple[int, int], int]
    event: DeathEvent | None
    state_key: tuple


def replay_moves(record: Mapping) -> list[ReplayFrame]:
    game = DeathHexGame(
        death_rule=bool(record["death_rule"]),
        death_timing=str(record["death_timing"]),
    )
    frames = [ReplayFrame({}, {}, None, game.state_key())]
    for q, r in record["moves"]:
        before = dict(game.board)
        event = game.make(q, r)
        if event is None:
            raise AssertionError(f"record contains illegal replay move {(q, r)}")
        frames.append(ReplayFrame(before, dict(game.board), event, game.state_key()))
    expected = sorted(tuple(cell) for cell in record["board"])
    actual = sorted((q, r, owner) for (q, r), owner in game.board.items())
    if actual != expected or (game.winner or 0) != record["winner"]:
        raise AssertionError("replay diverged from the stored game")
    return frames


def canonical_patch(
    board: Mapping[tuple[int, int], int],
    centre: tuple[int, int],
    radius: int = 2,
) -> tuple[int, ...]:
    domain = tuple(iter_cells_in_radius(radius))
    candidates = []
    for transform_index in range(12):
        transformed = sorted(
            (
                transform_cell(relative, transform_index),
                board.get(add(centre, relative), 0),
            )
            for relative in domain
        )
        values = tuple(value for _, value in transformed)
        swapped = tuple(3 - value if value else 0 for value in values)
        candidates.extend((values, swapped))
    return min(candidates)


def replay_diagnostics(records: Iterable[Mapping], local_horizon: int = 12) -> dict:
    death_records = [
        record
        for record in records
        if record["variant"] == "death" and record["death_timing"] == "placement"
    ]
    motif_counts: Counter[tuple[int, ...]] = Counter()
    death_tokens = 0
    death_events = 0
    repaired = 0
    converted = 0
    unresolved = 0
    reoccupation_lags: list[int] = []
    local_returns = 0
    local_return_lags: list[int] = []
    immediate_geometry_returns = 0
    suicide_retries = 0

    for record in death_records:
        frames = replay_moves(record)
        for index, frame in enumerate(frames[1:], start=1):
            event = frame.event
            assert event is not None
            motif_counts[canonical_patch(frame.board_after, event.cell)] += 1
            if (
                index + 1 < len(frames)
                and event.placed_stone_died
                and frames[index + 1].event is not None
                and frames[index + 1].event.cell == event.cell
                and frames[index + 1].event.player == event.player
            ):
                suicide_retries += 1

            if not event.deaths:
                continue
            death_events += 1
            before_key = canonical_patch(frame.board_before, event.cell)
            returned = False
            for future_index in range(index, min(len(frames), index + local_horizon + 1)):
                future_key = canonical_patch(frames[future_index].board_after, event.cell)
                if future_key == before_key:
                    lag = future_index - index
                    local_returns += 1
                    local_return_lags.append(lag)
                    immediate_geometry_returns += int(lag == 0)
                    returned = True
                    break
            _ = returned

            for dead_cell, dead_owner in event.deaths:
                death_tokens += 1
                outcome = None
                for future_index in range(index + 1, len(frames)):
                    future_owner = frames[future_index].board_after.get(dead_cell)
                    if future_owner is not None:
                        outcome = future_owner
                        reoccupation_lags.append(future_index - index)
                        break
                if outcome == dead_owner:
                    repaired += 1
                elif outcome == 3 - dead_owner:
                    converted += 1
                else:
                    unresolved += 1

    observations = sum(motif_counts.values())
    return {
        "games": len(death_records),
        "placements": observations,
        "radius_2_motifs": len(motif_counts),
        "motif_reuse_fraction": 1.0 - len(motif_counts) / max(1, observations),
        "most_common_motif_multiplicities": [count for _, count in motif_counts.most_common(12)],
        "death_tokens": death_tokens,
        "death_events": death_events,
        "same_owner_repaired": repaired,
        "opponent_converted": converted,
        "never_reoccupied": unresolved,
        "same_owner_repair_fraction": repaired / max(1, death_tokens),
        "conversion_fraction": converted / max(1, death_tokens),
        "median_reoccupation_lag": float(np.median(reoccupation_lags)) if reoccupation_lags else None,
        "death_events_with_symmetry_normalized_local_return_within_horizon": local_returns,
        "symmetry_normalized_local_return_fraction": local_returns / max(1, death_events),
        "immediate_symmetry_normalized_geometry_returns": immediate_geometry_returns,
        "median_symmetry_normalized_local_return_lag": float(np.median(local_return_lags)) if local_return_lags else None,
        "local_horizon": local_horizon,
        "same_turn_suicide_retries": suicide_retries,
    }


def best_sanctuary_fit(
    board: Mapping[tuple[int, int], int],
    phase_bins: int = 128,
) -> float:
    """Best color agreement over D6 orientation, phase, and global color swap."""
    if not board:
        return 0.0
    cells = tuple(board)
    owners = np.array([board[cell] for cell in cells])
    phases = np.arange(phase_bins, dtype=float) * (2.0 / phase_bins)
    best = 0.0
    for transform_index in range(12):
        transformed = (transform_cell(cell, transform_index) for cell in cells)
        heights = np.array([ALPHA * q + BETA * r for q, r in transformed])
        predictions = 1 + (np.floor(heights[:, None] + phases[None, :]).astype(np.int64) & 1)
        agreement = np.mean(predictions == owners[:, None], axis=0)
        best = max(best, float(np.maximum(agreement, 1.0 - agreement).max()))
    return best


def sanctuary_fit_audit(
    records: Iterable[Mapping],
    permutations: int,
    seed: int,
) -> list[dict]:
    """Compare final-board sanctuary fit with color-shuffled coordinate nulls."""
    rng = random.Random(seed)
    rows = []
    for record in records:
        if record["variant"] != "death" or record["death_timing"] != "placement":
            continue
        board = replay_moves(record)[-1].board_after
        cells = tuple(board)
        owners = list(board.values())
        actual = best_sanctuary_fit(board)
        null = []
        for _ in range(permutations):
            shuffled = list(owners)
            rng.shuffle(shuffled)
            null.append(best_sanctuary_fit(dict(zip(cells, shuffled))))
        null_mean = float(np.mean(null))
        null_sd = float(np.std(null))
        rows.append(
            {
                "black_agent": record["black_agent"],
                "white_agent": record["white_agent"],
                "live_stones": len(board),
                "actual_fit": actual,
                "shuffle_mean": null_mean,
                "shuffle_sd": null_sd,
                "excess_fit": actual - null_mean,
                "z_score": (actual - null_mean) / null_sd if null_sd else None,
            }
        )
    return rows


def grow_aperiodic_game(placements: int, search_radius: int = 40) -> list[ReplayFrame]:
    """Produce a legal cooperative 1-2-2 play inside the safe height field."""
    cells = sorted(
        iter_cells_in_radius(search_radius),
        key=lambda cell: (
            hex_distance(cell),
            math.atan2(math.sqrt(3.0) * 0.5 * cell[1], cell[0] + 0.5 * cell[1]),
            cell,
        ),
    )
    game = DeathHexGame()
    frames = [ReplayFrame({}, {}, None, game.state_key())]
    for _ in range(placements):
        player = game.current_player
        cell = next(cell for cell in cells if cell not in game.board and height_owner(cell) == player)
        before = dict(game.board)
        event = game.make(*cell)
        if event is None or event.deaths or game.winner is not None:
            raise AssertionError("safe aperiodic growth construction failed")
        frames.append(ReplayFrame(before, dict(game.board), event, game.state_key()))
    return frames


def _hex_xy(cell: tuple[int, int]) -> tuple[float, float]:
    q, r = cell
    return q + 0.5 * r, math.sqrt(3.0) * 0.5 * r


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def render_game_gif(
    frames: list[ReplayFrame],
    path: Path,
    title: str,
    max_frames: int,
    duration_ms: int,
) -> dict:
    indices = sorted(set(np.linspace(0, len(frames) - 1, min(max_frames, len(frames)), dtype=int)))
    all_cells = {
        cell
        for frame in frames
        for cell in (
            set(frame.board_after)
            | ({frame.event.cell} if frame.event else set())
            | ({cell for cell, _ in frame.event.deaths} if frame.event else set())
        )
    }
    xs, ys = zip(*(_hex_xy(cell) for cell in all_cells))
    width, height = 720, 520
    header, margin = 72, 24
    scale = min(
        (width - 2 * margin) / max(1.0, max(xs) - min(xs) + 1.0),
        (height - header - 2 * margin) / max(1.0, max(ys) - min(ys) + 1.0),
    )
    scale = min(scale, 43.0)
    centre_x = (min(xs) + max(xs)) / 2.0
    centre_y = (min(ys) + max(ys)) / 2.0
    font = _font(18)
    small = _font(14)
    rendered: list[Image.Image] = []
    cumulative_deaths = 0
    cumulative_at_index = []
    for frame in frames:
        if frame.event:
            cumulative_deaths += len(frame.event.deaths)
        cumulative_at_index.append(cumulative_deaths)

    for index in indices:
        frame = frames[index]
        image = Image.new("RGB", (width, height), (247, 245, 239))
        draw = ImageDraw.Draw(image)
        draw.text((margin, 15), title, fill=(27, 29, 32), font=font)
        event = frame.event
        status = f"placement {index}/{len(frames) - 1}   live {len(frame.board_after)}   deaths {cumulative_at_index[index]}"
        if event:
            status += f"   mover {'Black' if event.player == 1 else 'White'}"
        draw.text((margin, 43), status, fill=(75, 78, 82), font=small)

        def pixel(cell: tuple[int, int]) -> tuple[float, float]:
            x, y = _hex_xy(cell)
            return (
                width / 2.0 + (x - centre_x) * scale,
                header + (height - header) / 2.0 - (y - centre_y) * scale,
            )

        radius = max(3.0, 0.43 * scale)
        for cell, owner in frame.board_after.items():
            cx, cy = pixel(cell)
            points = [
                (
                    cx + radius * math.cos(math.pi / 6.0 + k * math.pi / 3.0),
                    cy + radius * math.sin(math.pi / 6.0 + k * math.pi / 3.0),
                )
                for k in range(6)
            ]
            fill = (31, 33, 38) if owner == 1 else (242, 237, 222)
            draw.polygon(points, fill=fill, outline=(110, 110, 110), width=1)
        if event:
            cx, cy = pixel(event.cell)
            draw.ellipse(
                (cx - radius * 0.72, cy - radius * 0.72, cx + radius * 0.72, cy + radius * 0.72),
                outline=(231, 155, 35),
                width=3,
            )
            for dead_cell, _ in event.deaths:
                dx, dy = pixel(dead_cell)
                arm = max(4.0, radius * 0.65)
                draw.line((dx - arm, dy - arm, dx + arm, dy + arm), fill=(196, 48, 43), width=3)
                draw.line((dx - arm, dy + arm, dx + arm, dy - arm), fill=(196, 48, 43), width=3)
        rendered.append(image.convert("P", palette=Image.Palette.ADAPTIVE, colors=96))

    durations = [duration_ms] * len(rendered)
    durations[-1] = 1200
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered[0].save(
        path,
        save_all=True,
        append_images=rendered[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return {"path": str(path.relative_to(ROOT)), "frames": len(rendered), "bytes": path.stat().st_size}


def diffraction(size: int) -> tuple[np.ndarray, list[dict]]:
    values = np.array(
        [[1.0 if height_owner((q, r)) == 1 else -1.0 for r in range(size)] for q in range(size)]
    )
    power = np.abs(np.fft.fftshift(np.fft.fft2(values))) ** 2 / values.size**2
    centre = size // 2
    power[centre, centre] = 0.0
    flat_indices = np.argpartition(power.ravel(), -16)[-16:]
    peaks = []
    for flat in flat_indices[np.argsort(power.ravel()[flat_indices])[::-1]]:
        q_index, r_index = np.unravel_index(flat, power.shape)
        peaks.append(
            {
                "frequency_q": (q_index - centre) / size,
                "frequency_r": (r_index - centre) / size,
                "intensity": float(power[q_index, r_index]),
            }
        )
    return power, peaks


def plot_geometry(path: Path, size: int, complexity: Mapping[str, list[int]]) -> list[dict]:
    patch = height_patch(12)
    power, peaks = diffraction(size)
    fig, axes = plt.subplots(2, 2, figsize=(11, 9), constrained_layout=True)

    for cell, owner in patch.items():
        x, y = _hex_xy(cell)
        axes[0, 0].scatter(
            x,
            y,
            s=19,
            c="#202124" if owner == 1 else "#e8dfc8",
            edgecolors="#777777",
            linewidths=0.25,
        )
    axes[0, 0].set_aspect("equal")
    axes[0, 0].axis("off")
    axes[0, 0].set_title("Exact aperiodic stable coloring")

    grid = np.linspace(-0.55, 0.55, 450)
    aa, bb = np.meshgrid(grid, grid)
    magnitudes = np.stack((np.abs(aa), np.abs(bb), np.abs(aa - bb)))
    stable = np.max(magnitudes, axis=0) < 0.5
    draw_safe = stable & (np.min(magnitudes, axis=0) > 0.2)
    chamber = stable.astype(float) + draw_safe.astype(float)
    axes[0, 1].contourf(aa, bb, chamber, levels=[-0.5, 0.5, 1.5, 2.5], colors=["#eeeeee", "#a9d5c1", "#2c8c6b"])
    axes[0, 1].plot(ALPHA, BETA, marker="*", markersize=14, color="#d1495b", label="chosen irrational slope")
    axes[0, 1].set_xlabel("alpha")
    axes[0, 1].set_ylabel("beta")
    axes[0, 1].set_aspect("equal")
    axes[0, 1].set_title("Open stable chamber; dark region also avoids six-runs")
    axes[0, 1].legend(fontsize=8)

    extent = (-0.5, 0.5, -0.5, 0.5)
    axes[1, 0].imshow(np.log10(power.T + 1e-8), origin="lower", extent=extent, cmap="magma", aspect="equal")
    axes[1, 0].set_xlabel("q reciprocal frequency")
    axes[1, 0].set_ylabel("r reciprocal frequency")
    axes[1, 0].set_title(f"Finite {size}x{size} diffraction: Bragg hierarchy")

    lengths = np.arange(1, len(next(iter(complexity.values()))) + 1)
    for label, counts in complexity.items():
        axes[1, 1].plot(lengths, counts, marker="o", markersize=3, label=label)
    axes[1, 1].plot(lengths, 2 * lengths, "--", color="#777777", label="2n")
    axes[1, 1].set_xlabel("factor length n")
    axes[1, 1].set_ylabel("distinct factors p(n)")
    axes[1, 1].set_title("Linear symbolic complexity on every lattice axis")
    axes[1, 1].legend(fontsize=8)

    fig.suptitle("A quasiperiodic sanctuary inside Death HeXO", fontsize=15)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=170)
    plt.close(fig)
    return peaks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="smaller FFT and shorter growth GIF")
    args = parser.parse_args()
    started = time.perf_counter()
    base = json.loads(BASE_RESULT.read_text(encoding="utf-8"))
    sample_records = base["sample_games"]
    steps = directional_steps()
    max_factor = 16 if args.quick else 32
    complexity = {
        label: factor_complexity(step, max_factor, samples=6_000 if args.quick else 20_000)
        for label, step in steps.items()
    }
    target = height_patch(12)
    repair = erasure_repair_audit(
        radius=8 if args.quick else 12,
        deletion_sizes=(1, 2, 4, 8, 16, 32) if args.quick else (1, 2, 4, 8, 16, 32, 64, 128),
        trials=8 if args.quick else 24,
        seed=271828,
    )
    invasion = hostile_invasion_spectrum()
    diagnostics = replay_diagnostics(sample_records)
    fit_audit = sanctuary_fit_audit(
        sample_records,
        permutations=12 if args.quick else 32,
        seed=161803,
    )
    capture_record = next(
        record
        for record in sample_records
        if record["variant"] == "death"
        and record["black_agent"] == "hybrid"
        and record["white_agent"] == "hybrid"
    )
    capture_frames = replay_moves(capture_record)
    growth_frames = grow_aperiodic_game(60 if args.quick else 120)
    capture_gif = render_game_gif(
        capture_frames,
        CAPTURE_GIF,
        "Death HeXO: capture-driven recurrent play",
        max_frames=36 if args.quick else 52,
        duration_ms=170,
    )
    growth_gif = render_game_gif(
        growth_frames,
        GROWTH_GIF,
        "Death HeXO: legal growth of an aperiodic sanctuary",
        max_frames=36 if args.quick else 52,
        duration_ms=170,
    )
    peaks = plot_geometry(FIGURE_PATH, 64 if args.quick else 128, complexity)

    payload = {
        "experiment": "aperiodic_repair",
        "parameters": {
            "alpha": ALPHA,
            "beta": BETA,
            "phase": PHASE,
            "directional_steps": steps,
            "quick": args.quick,
        },
        "analytic_claims": {
            "stable_chamber": "max(|alpha|, |beta|, |alpha-beta|) < 1/2",
            "six_run_free_chamber": "min(|alpha|, |beta|, |alpha-beta|) > 1/5",
            "aperiodicity_condition": "1, alpha, beta rationally independent",
            "pure_point_frequencies": "odd m multiples of (alpha/2, beta/2) modulo Z^2",
            "directional_factor_complexity_bound": "p(n) <= 2n from the 2n phase-partition boundaries",
            "almost_periods": "translations are ranked by |alpha*dq + beta*dr - 2k|; this is also their mismatch density",
            "erasure_repair": "every deleted subset can be restored in arbitrary order without death or a six-run",
            "strategic_status": "exact geometry and cooperative repair witness; not an adversarial winning strategy",
        },
        "finite_checks": {
            "radius_12_cells": len(target),
            "radius_12_stable": stable_board(target),
            "radius_12_black_win": has_win(target, 1),
            "radius_12_white_win": has_win(target, 2),
            "period_candidates_radius_24_shifts_10": finite_period_search(24, 10),
            "best_approximate_periods_shifts_40": approximate_periods(40),
            "factor_complexity": complexity,
            "factor_complexity_equals_2n": all(
                counts == [2 * n for n in range(1, max_factor + 1)] for counts in complexity.values()
            ),
        },
        "erasure_repair_audit": repair,
        "hostile_single_site_invasion": invasion,
        "sample_replay_diagnostics": diagnostics,
        "sanctuary_fit_against_color_shuffle": {
            "method": "best of 12 D6 orientations, 128 phases, and global color swap on final live stones",
            "status": "exploratory stored-game check, not an optimal-play sample",
            "rows": fit_audit,
        },
        "aperiodic_growth_game": {
            "placements": len(growth_frames) - 1,
            "final_stones": len(growth_frames[-1].board_after),
            "deaths": sum(len(frame.event.deaths) for frame in growth_frames[1:] if frame.event),
            "winner": growth_frames[-1].event.winner if growth_frames[-1].event else None,
        },
        "diffraction_peaks": peaks,
        "artifacts": {
            "figure": str(FIGURE_PATH.relative_to(ROOT)),
            "capture_gif": capture_gif,
            "aperiodic_growth_gif": growth_gif,
        },
        "wall_seconds": time.perf_counter() - started,
    }
    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"result": str(RESULT_PATH), "wall_seconds": payload["wall_seconds"]}, indent=2))


if __name__ == "__main__":
    main()
