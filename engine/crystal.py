"""Large-scale crystal and symmetry observables for HexGo point sets."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

from engine.diffraction import axial_to_cart, bragg_peak_fraction, diffraction_intensity
from engine.isomorphisms import d6_transforms

Cell = tuple[int, int]


def axial_to_xy_cell(cell: Cell) -> tuple[float, float]:
    """Convert one axial cell to Cartesian coordinates in the hex basis."""
    q, r = cell
    return (q + 0.5 * r, (math.sqrt(3.0) / 2.0) * r)


def hex_distance(cell: Cell, origin: Cell = (0, 0)) -> int:
    """Hex-grid distance between two axial coordinates."""
    q, r = cell
    oq, or_ = origin
    return (
        abs(q - oq)
        + abs(r - or_)
        + abs((q + r) - (oq + or_))
    ) // 2


def _as_cells(cells: Iterable[Cell]) -> list[Cell]:
    return list(dict.fromkeys(cells))


def sector_counts(cells: Iterable[Cell], n_sectors: int = 6) -> tuple[int, ...]:
    """Angular sector counts around the origin."""
    counts = [0] * n_sectors
    for cell in _as_cells(cells):
        x, y = axial_to_xy_cell(cell)
        if x == 0.0 and y == 0.0:
            continue
        angle = math.atan2(y, x)
        if angle < 0:
            angle += 2.0 * math.pi
        idx = min(n_sectors - 1, int(n_sectors * angle / (2.0 * math.pi)))
        counts[idx] += 1
    return tuple(counts)


def sector_entropy(cells: Iterable[Cell], n_sectors: int = 6) -> float:
    """Normalized entropy of angular sector occupancy."""
    counts = np.array(sector_counts(cells, n_sectors), dtype=np.float64)
    total = counts.sum()
    if total <= 0:
        return 0.0
    probs = counts[counts > 0] / total
    return float(-(probs * np.log(probs)).sum() / math.log(n_sectors))


def harmonic_moments(
    cells: Iterable[Cell],
    orders: Iterable[int] = range(1, 13),
) -> dict[int, float]:
    """
    Rotational harmonic magnitudes.

    Large order-6 or order-12 moments indicate hex/D6 angular organization.
    Lower-order moments expose symmetry breaking.
    """
    pts = [
        axial_to_xy_cell(cell)
        for cell in _as_cells(cells)
        if cell != (0, 0)
    ]
    orders = list(orders)
    if not pts:
        return {order: 0.0 for order in orders}
    angles = np.array([math.atan2(y, x) for x, y in pts], dtype=np.float64)
    out: dict[int, float] = {}
    for order in orders:
        moment = np.exp(1j * order * angles).mean()
        out[int(order)] = float(abs(moment))
    return out


def d6_jaccard(cells: Iterable[Cell]) -> float:
    """Average Jaccard similarity between a point set and its D6 images."""
    base = set(_as_cells(cells))
    if not base:
        return 1.0
    scores = []
    for transform_idx in range(12):
        transformed = {d6_transforms(cell)[transform_idx] for cell in base}
        union = base | transformed
        scores.append(len(base & transformed) / len(union))
    return float(sum(scores) / len(scores))


def box_count_dimension(
    cells: Iterable[Cell],
    scales: Sequence[int] = (1, 2, 4, 8),
) -> float:
    """Estimate a box-counting dimension from axial square bins."""
    pts = _as_cells(cells)
    if len(pts) < 2:
        return 0.0
    xs = np.array([q for q, _ in pts], dtype=np.int64)
    ys = np.array([r for _, r in pts], dtype=np.int64)
    counts = []
    inv_scales = []
    for scale in scales:
        if scale <= 0:
            continue
        boxes = set(zip(np.floor_divide(xs, scale), np.floor_divide(ys, scale)))
        if len(boxes) > 1:
            counts.append(math.log(len(boxes)))
            inv_scales.append(math.log(1.0 / scale))
    if len(counts) < 2:
        return 0.0
    slope, _ = np.polyfit(np.array(inv_scales), np.array(counts), deg=1)
    return float(max(0.0, slope))


def delone_bounds(cells: Iterable[Cell]) -> tuple[float, float]:
    """Return nearest-neighbor lower and upper bounds for a finite point set."""
    pts = axial_to_cart(_as_cells(cells))
    n_points = pts.shape[0]
    if n_points < 2:
        return (float("nan"), float("nan"))
    diff = pts[:, None, :] - pts[None, :, :]
    dist = np.sqrt((diff * diff).sum(axis=2))
    mask = ~np.eye(n_points, dtype=bool)
    d_min = float(dist[mask].min())
    nearest = np.where(mask, dist, np.inf).min(axis=1)
    return (d_min, float(nearest.max()))


def bragg99_for_cells(
    cells: Iterable[Cell],
    grid: int = 64,
    k_extent: float = 2.0 * math.pi,
    device: str | None = "cpu",
) -> float:
    """Compute Bragg99 diffraction concentration for a finite point set."""
    pts = axial_to_cart(_as_cells(cells))
    if pts.shape[0] < 2:
        return 0.0
    _, _, intensity = diffraction_intensity(
        pts,
        k_extent=k_extent,
        grid=grid,
        device=device,
        normalise=True,
    )
    return float(bragg_peak_fraction(intensity, threshold_q=0.99))


def crystal_observables(
    cells: Iterable[Cell],
    diffraction_grid: int = 64,
    compute_diffraction: bool = True,
) -> dict[str, float | int | dict[int, float] | tuple[int, ...]]:
    """Collect real-space, angular, Delone, and reciprocal-space observables."""
    pts = _as_cells(cells)
    moments = harmonic_moments(pts)
    d_min, d_max = delone_bounds(pts)
    out: dict[str, float | int | dict[int, float] | tuple[int, ...]] = {
        "stone_count": len(pts),
        "radius_max": max((hex_distance(cell) for cell in pts), default=0),
        "d6_jaccard": d6_jaccard(pts),
        "symmetry_break": 1.0 - d6_jaccard(pts),
        "sector_entropy": sector_entropy(pts),
        "box_dimension": box_count_dimension(pts),
        "d_min": d_min,
        "d_max": d_max,
        "harmonics": moments,
        "moment_1": moments.get(1, 0.0),
        "moment_2": moments.get(2, 0.0),
        "moment_3": moments.get(3, 0.0),
        "moment_6": moments.get(6, 0.0),
        "moment_12": moments.get(12, 0.0),
        "sector_counts": sector_counts(pts),
    }
    out["bragg99"] = (
        bragg99_for_cells(pts, grid=diffraction_grid)
        if compute_diffraction else 0.0
    )
    return out
