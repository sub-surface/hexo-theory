"""
UDC positions over Z[omega]: testing Proposition P6.

Constructs planar point sets from the Eisenstein integers Z[omega] (the hex
lattice) using the CM class-field-tower machinery from the OpenAI unit-distance
disproof, and compares their crystal observables to random controls.

Algebraic setup
---------------
Z[omega], omega = e^{2pi i/3}, is the ring of integers of Q(omega).
For a rational prime q = 1 mod 3, there is a factorisation q = pi * pi_bar
in Z[omega] (Z[omega] is a PID, class number 1).

The UDC construction builds norm-one directions:
    u_S = (prod_{i in S} pi_i) / (prod_{i not in S} pi_bar_i) / eta
where eta is a normalising constant.  In complex absolute value |u_S| = 1.

We implement this by working over C directly:
- Pick t primes q_i = 1 mod 3, factorise each as q_i = pi_i * pi_bar_i.
- Form all 2^t complex numbers u_S = prod_{i in S} c(pi_i) * prod_{i not in S} c(pi_bar_i),
  where c(pi) is the complex embedding of pi.
- Normalise: v_S = u_S / |u_S|.  These are unit-modulus directions.
- The hex lattice point set: take the Z[omega] disc of radius R, then keep
  all pairs (x, y) such that (x - y) / |(x - y)| is in {v_S} and |(x-y)|
  is approximately a fixed scale s (one "unit distance" in the construction).

For comparing to HeXO we interpret the Z[omega] points directly as axial
hex coordinates (a, b) = (q, r).

Proposition P6 (to falsify or support)
---------------------------------------
UDC positions over Z[omega] have higher Bragg99 and moment_6 than
random disc controls of the same stone count.

Falsifiable predictions
-----------------------
P6a: mean Bragg99(udc_t*) > mean Bragg99(random_disc), for all t.
P6b: mean moment_6(udc_t*) > mean moment_6(random_disc).
P6c: Bragg99 is non-decreasing in t (more split primes -> more structure).
P6d: n grows with t (larger t -> more points at fixed R).

Output
------
results/udc_positions.json
figures/fig_udc_positions_bragg.png
figures/fig_udc_positions_gallery.png
figures/fig_udc_positions_harmonics.png
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from itertools import combinations
from pathlib import Path
from typing import NamedTuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine.crystal import (
    axial_to_xy_cell,
    bragg99_for_cells,
    crystal_observables,
    harmonic_moments,
)

JSON_PATH = Path("results/udc_positions.json")
FIG_BRAGG = Path("figures/fig_udc_positions_bragg.png")
FIG_GALLERY = Path("figures/fig_udc_positions_gallery.png")
FIG_HARMONICS = Path("figures/fig_udc_positions_harmonics.png")
FIG_GEOMETRY = Path("figures/fig_udc_positions_geometry.png")


# ---------------------------------------------------------------------------
# Eisenstein-integer arithmetic
# ---------------------------------------------------------------------------
# Z[omega], omega = (-1 + i*sqrt(3)) / 2
# Norm: N(a + b*omega) = a^2 - a*b + b^2
# Embedding: c(a + b*omega) = a + b*(-1/2 + i*sqrt(3)/2)

_SQRT3 = math.sqrt(3.0)


def _eisen_to_c(a: int, b: int) -> complex:
    return complex(a - b * 0.5, b * _SQRT3 * 0.5)


def _eisen_norm(a: int, b: int) -> int:
    return a * a - a * b + b * b


def _eisen_mul(a1: int, b1: int, a2: int, b2: int) -> tuple[int, int]:
    # omega^2 = -1 - omega
    return (a1 * a2 - b1 * b2, a1 * b2 + b1 * a2 - b1 * b2)


def _eisen_conj(a: int, b: int) -> tuple[int, int]:
    # conj(a + b*omega) = a + b*omega_bar = a + b*(-1 - omega) = (a-b) - b*omega
    return (a - b, -b)


class EisenPrime(NamedTuple):
    q: int
    pi_a: int
    pi_b: int
    pibar_a: int
    pibar_b: int


def _find_eisenstein_prime(q: int) -> EisenPrime:
    """Find pi in Z[omega] with N(pi) = q (for prime q = 1 mod 3)."""
    limit = int(math.isqrt(q)) + 2
    for a in range(-limit, limit + 1):
        for b in range(-limit, limit + 1):
            if _eisen_norm(a, b) == q and not (a == 0 and b == 0):
                ca, cb = _eisen_conj(a, b)
                # Ensure pi != pi_bar (i.e. not real) and take the canonical one
                if (ca, cb) != (a, b):
                    return EisenPrime(q, a, b, ca, cb)
    raise ValueError(f"No Eisenstein prime found for q={q}")


def _primes_1mod3(n: int) -> list[int]:
    out: list[int] = []
    c = 7
    while len(out) < n:
        if c % 3 == 1 and all(c % p != 0 for p in range(2, int(math.isqrt(c)) + 1)):
            out.append(c)
        c += 1
    return out


# ---------------------------------------------------------------------------
# Gaussian-integer arithmetic Z[i]  (the original Erdos / Sawin baseline)
# ---------------------------------------------------------------------------
# Z[i] = {a + b*i}; norm a^2 + b^2; primes split iff q = 1 mod 4.

def _gauss_to_c(a: int, b: int) -> complex:
    return complex(a, b)


def _gauss_norm(a: int, b: int) -> int:
    return a * a + b * b


def _gauss_mul(a1: int, b1: int, a2: int, b2: int) -> tuple[int, int]:
    return (a1 * a2 - b1 * b2, a1 * b2 + b1 * a2)


def _gauss_conj(a: int, b: int) -> tuple[int, int]:
    return (a, -b)


def _find_gaussian_prime(q: int) -> EisenPrime:
    """Find pi in Z[i] with N(pi) = q (for prime q = 1 mod 4)."""
    limit = int(math.isqrt(q)) + 2
    for a in range(0, limit + 1):
        for b in range(0, limit + 1):
            if _gauss_norm(a, b) == q and not (a == 0 and b == 0):
                ca, cb = _gauss_conj(a, b)
                if (ca, cb) != (a, b):
                    return EisenPrime(q, a, b, ca, cb)
    raise ValueError(f"No Gaussian prime found for q={q}")


def _primes_1mod4(n: int) -> list[int]:
    out: list[int] = []
    c = 5
    while len(out) < n:
        if c % 4 == 1 and all(c % p != 0 for p in range(2, int(math.isqrt(c)) + 1)):
            out.append(c)
        c += 1
    return out


def _primes_1mod12(n: int) -> list[int]:
    """Primes q = 1 mod 12 -- these split completely in Q(zeta_12) = Q(omega, i)."""
    out: list[int] = []
    c = 13
    while len(out) < n:
        if c % 12 == 1 and all(c % p != 0 for p in range(2, int(math.isqrt(c)) + 1)):
            out.append(c)
        c += 1
    return out


# ---------------------------------------------------------------------------
# Geometry abstraction
# ---------------------------------------------------------------------------
# Three candidate base lattices for the UDC construction.  See the geometry
# discussion in docs/theory/2026-05-22-udc-positions.md section "Geometry".
#
#   eisenstein  Z[omega]    A2 triangular lattice, D6 symmetry -> matches HeXO
#   gaussian    Z[i]        square lattice, D4 symmetry        -> Erdos baseline
#   z12         Z[omega] with q = 1 mod 12 split primes        -> CM field Q(zeta12)
#
# The genuine proof CM field is K = L(i), L = Q(sqrt 3), i.e. K = Q(zeta_12),
# degree 4.  Since Q(zeta_12) = Q(omega) . Q(i), a rational prime q splits
# completely in K iff q = 1 mod 12 (split in BOTH Q(omega) and Q(i)).  The
# norm-one elements of K restrict, under the omega-place, to norm-one
# elements of Z[omega] built from primes q = 1 mod 12.  So the "z12" geometry
# is the Eisenstein lattice with the stricter q = 1 mod 12 split rule -- the
# correct projection of the degree-4 CM construction onto the hex plane,
# without forcing a rank-4 ring through this 2-coordinate interface.

class Geometry(NamedTuple):
    name: str
    to_c: "callable"           # (a, b) -> complex   (lattice coords -> C)
    norm: "callable"           # (a, b) -> int
    mul: "callable"            # (a1,b1,a2,b2) -> (a,b)
    conj: "callable"           # (a,b) -> (a,b)
    find_prime: "callable"     # q -> EisenPrime
    primes: "callable"         # n -> list[int]  (the first n splitting primes)
    split_rule: str            # human-readable congruence condition


GEOMETRIES: dict[str, Geometry] = {
    "eisenstein": Geometry(
        name="eisenstein",
        to_c=_eisen_to_c, norm=_eisen_norm, mul=_eisen_mul, conj=_eisen_conj,
        find_prime=_find_eisenstein_prime, primes=_primes_1mod3,
        split_rule="q = 1 mod 3",
    ),
    "gaussian": Geometry(
        name="gaussian",
        to_c=_gauss_to_c, norm=_gauss_norm, mul=_gauss_mul, conj=_gauss_conj,
        find_prime=_find_gaussian_prime, primes=_primes_1mod4,
        split_rule="q = 1 mod 4",
    ),
    "z12": Geometry(
        name="z12",
        to_c=_eisen_to_c, norm=_eisen_norm, mul=_eisen_mul, conj=_eisen_conj,
        find_prime=_find_eisenstein_prime, primes=_primes_1mod12,
        split_rule="q = 1 mod 12  (splits in Q(zeta_12) = Q(omega,i))",
    ),
}


# ---------------------------------------------------------------------------
# UDC construction (geometry-parametrised)
# ---------------------------------------------------------------------------

def _udc_translations(geom: Geometry, eprimes: list[EisenPrime]) -> list[tuple[int, int]]:
    """
    The 2^t integer subset-product translations in the chosen lattice.

    For each subset S, the translation is the lattice element
        d_S = prod_{i in S} pi_i  *  prod_{i not in S} pi_bar_i
    All 2^t translations share the same complex modulus prod_i sqrt(q_i).
    Two lattice points x, y are a "unit pair" iff x - y is one of these.
    """
    translations: list[tuple[int, int]] = []
    for mask in range(1 << len(eprimes)):
        a, b = 1, 0
        for idx, ep in enumerate(eprimes):
            if mask >> idx & 1:
                a, b = geom.mul(a, b, ep.pi_a, ep.pi_b)
            else:
                a, b = geom.mul(a, b, ep.pibar_a, ep.pibar_b)
        translations.append((a, b))
    return list(dict.fromkeys(translations))


def _udc_point_set(
    geom: Geometry,
    eprimes: list[EisenPrime],
    window_radius: float,
    unit_scale: float,
) -> list[tuple[int, int]]:
    """
    Build a UDC-style point set in the given geometry.

    1. Enumerate lattice points in the disc of radius `window_radius`.
    2. Two points x, y are a "unit pair" iff x - y is a subset-product
       translation (all have complex modulus = unit_scale = prod sqrt(q_i)).
    3. Keep all points that participate in at least one unit pair.
    """
    R = int(math.ceil(window_radius)) + 1
    disc: list[tuple[int, int]] = []
    for a in range(-R, R + 1):
        for b in range(-R, R + 1):
            if abs(geom.to_c(a, b)) <= window_radius:
                disc.append((a, b))

    if len(disc) < 2:
        return []

    int_translations = _udc_translations(geom, eprimes)
    disc_set = set(disc)
    active: set[tuple[int, int]] = set()
    for (xa, xb) in disc:
        for (da, db) in int_translations:
            ya, yb = xa + da, xb + db
            if (ya, yb) in disc_set:
                active.add((xa, xb))
                active.add((ya, yb))
                break

    return sorted(active)


def _count_unit_pairs(
    cells: list[tuple[int, int]],
    int_translations: list[tuple[int, int]],
) -> int:
    cell_set = set(cells)
    count = 0
    for (xa, xb) in cells:
        for (da, db) in int_translations:
            if (xa + da, xb + db) in cell_set:
                count += 1
    return count // 2  # unordered pairs


# ---------------------------------------------------------------------------
# Control populations
# ---------------------------------------------------------------------------

def _random_disc_points(n: int, radius: int, rng: random.Random) -> list[tuple[int, int]]:
    pool = []
    for a in range(-radius - 1, radius + 2):
        for b in range(-radius - 1, radius + 2):
            if abs(_eisen_to_c(a, b)) <= radius:
                pool.append((a, b))
    k = min(n, len(pool))
    return rng.sample(pool, k)


def _hex_ball_points(radius: int) -> list[tuple[int, int]]:
    pts = []
    for q in range(-radius, radius + 1):
        for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
            pts.append((q, r))
    return pts


# ---------------------------------------------------------------------------
# Crystal observables (with OOM guard)
# ---------------------------------------------------------------------------
MAX_DELONE_POINTS = 1500


def _safe_crystal_obs(cells: list[tuple[int, int]], grid: int, rng: random.Random) -> dict:
    """Call crystal_observables, sub-sampling if too large for Delone O(n^2)."""
    if len(cells) > MAX_DELONE_POINTS:
        cells = rng.sample(cells, MAX_DELONE_POINTS)
    return crystal_observables(cells, diffraction_grid=grid)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _to_xy(cells: list[tuple[int, int]]) -> np.ndarray:
    return np.array([axial_to_xy_cell(c) for c in cells], dtype=np.float64)


# Stone-colour convention (HeXO): P1 = Black, P2 = White.
_BLACK = dict(facecolor="#111111", edgecolor="#111111")
_WHITE = dict(facecolor="#fafafa", edgecolor="#333333")


def _udc_owner(cell: tuple[int, int]) -> int:
    """
    Assign each UDC lattice point a HeXO player.

    The A2 lattice Z[omega] is tripartite under (a - b) mod 3, but for a
    two-player game we use the natural sublattice bipartition by parity of
    (a + b): adjacent points along any of the 3 win axes alternate parity,
    so this colours the unit-distance graph as a HeXO placement order
    (Black on even sites, White on odd) -- a pairing-strategy colouring.
    """
    a, b = cell
    return 1 if (a + b) % 2 == 0 else 2


def plot_gallery(records: list[dict], random_cells: list[tuple[int, int]], path: Path) -> None:
    panels = records + [{"label": "random_disc", "cells": random_cells, "bragg99": None}]
    cols = min(4, len(panels))
    rows = math.ceil(len(panels) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(4 * cols, 4 * rows), squeeze=False)
    for ax, p in zip(axes.ravel(), panels):
        cells = p["cells"]
        pts = _to_xy(cells)
        if len(pts):
            ax.set_facecolor("#d9d9d9")
            owners = np.array([_udc_owner(tuple(c)) for c in cells])
            for owner, style in ((1, _BLACK), (2, _WHITE)):
                mask = owners == owner
                if mask.any():
                    ax.scatter(pts[mask, 0], pts[mask, 1], s=14,
                               facecolor=style["facecolor"], edgecolor=style["edgecolor"],
                               linewidths=0.3, alpha=0.95)
        b = p.get("bragg99")
        b_str = f"{b:.3f}" if b is not None else "?"
        ax.set_title(f"{p['label']}\nN={len(cells)}  B99={b_str}", fontsize=8)
        ax.set_aspect("equal")
        ax.grid(alpha=0.2, linestyle=":")
    for ax in axes.ravel()[len(panels):]:
        ax.axis("off")
    fig.suptitle("UDC positions over Z[omega] vs random disc  (Black = P1, White = P2 sublattice)")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=160)
    plt.close(fig)


def plot_bragg(records: list[dict], random_b99: float, hex_b99: float, path: Path) -> None:
    labels = [r["label"] for r in records] + ["random_disc", "hex_ball"]
    vals = [r["bragg99"] for r in records] + [random_b99, hex_b99]
    colors = ["#4c78a8"] * len(records) + ["#e45756", "#72b7b2"]
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 1.1), 5))
    ax.bar(x, vals, color=colors)
    ax.axhline(random_b99, color="#e45756", linewidth=0.9, linestyle="--", alpha=0.7, label="random baseline")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_ylabel("Bragg99")
    ax.set_ylim(0, 1.05)
    ax.set_title("P6a: UDC Bragg99 vs baselines  (blue=UDC, red=random, teal=hex_ball)")
    ax.grid(axis="y", alpha=0.3, linestyle=":")
    ax.legend(fontsize=8)
    for xi, val in zip(x, vals):
        ax.text(xi, val + 0.01, f"{val:.3f}", ha="center", va="bottom", fontsize=8)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=160)
    plt.close(fig)


def plot_harmonics(records: list[dict], random_cells: list[tuple[int, int]], path: Path) -> None:
    orders = list(range(1, 13))
    fig, ax = plt.subplots(figsize=(10, 6))
    for rec in records:
        m = harmonic_moments(rec["cells"], orders)
        ax.plot(orders, [m.get(o, 0.0) for o in orders], marker="o", linewidth=1.2, label=rec["label"])
    rm = harmonic_moments(random_cells, orders)
    ax.plot(orders, [rm.get(o, 0.0) for o in orders],
            marker="s", color="#e45756", linestyle="--", linewidth=1.2, label="random_disc")
    ax.axvline(6, color="#222", linewidth=0.8, linestyle=":")
    ax.axvline(12, color="#222", linewidth=0.8, linestyle=":")
    ax.set_xlabel("harmonic order m")
    ax.set_ylabel("|mean exp(i m theta)|")
    ax.set_title("P6b: Angular harmonics -- D6 order-6 moment test")
    ax.set_xticks(orders)
    ax.grid(alpha=0.3, linestyle=":")
    ax.legend(fontsize=8, ncol=2)
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def _run_geometry(geom: Geometry, args: argparse.Namespace, rng: random.Random) -> list[dict]:
    """Build UDC records for one base geometry, one per t value."""
    max_t = max(args.t_values)
    all_q = geom.primes(max_t + 1)
    print(f"\n=== Geometry: {geom.name}  (split rule: {geom.split_rule}) ===")
    print(f"Split primes: {all_q[:max_t]}")
    eprimes_all: list[EisenPrime] = []
    for q in all_q[:max_t]:
        ep = geom.find_prime(q)
        eprimes_all.append(ep)
        print(f"  q={q}: pi=({ep.pi_a},{ep.pi_b}), N(pi)={geom.norm(ep.pi_a, ep.pi_b)}")

    records: list[dict] = []
    for t in args.t_values:
        eprimes = eprimes_all[:t]
        label = f"{geom.name}_t{t}"
        unit_scale = math.prod(ep.q for ep in eprimes) ** 0.5
        int_translations = _udc_translations(geom, eprimes)

        radii_to_try = sorted(set(
            [r for r in args.window_radii if r >= unit_scale * 0.9]
            + [unit_scale * m for m in [2, 3, 4]]
        ))
        best_cells: list[tuple[int, int]] = []
        for R in radii_to_try:
            cells = _udc_point_set(geom, eprimes, R, unit_scale)
            if len(cells) > len(best_cells):
                best_cells = cells
            if len(best_cells) >= args.target_n:
                break

        if not best_cells:
            print(f"  {label}: no active points, skipping")
            continue

        obs = _safe_crystal_obs(best_cells, args.diffraction_grid, rng)
        nu = _count_unit_pairs(best_cells, int_translations)
        record = {
            "label": label,
            "geometry": geom.name,
            "t": t,
            "split_primes": [ep.q for ep in eprimes],
            "unit_scale": unit_scale,
            "n_translations": len(int_translations),
            "n_stones": len(best_cells),
            "nu_unit_pairs": nu,
            "nu_per_n": nu / max(1, len(best_cells)),
            "bragg99": float(obs["bragg99"]),
            "moment_6": float(obs["moment_6"]),
            "moment_12": float(obs["moment_12"]),
            "d6_jaccard": float(obs["d6_jaccard"]),
            "sector_entropy": float(obs["sector_entropy"]),
            "box_dimension": float(obs["box_dimension"]),
            "cells": sorted(best_cells),
        }
        records.append(record)
        print(f"  {label}: n={len(best_cells)}, nu={nu}, nu/n={record['nu_per_n']:.3f}, "
              f"Bragg99={record['bragg99']:.4f}, moment_6={record['moment_6']:.4f}, "
              f"d6_jaccard={record['d6_jaccard']:.3f}")
    return records


def plot_geometry_comparison(all_records: list[dict], random_b99: float, path: Path) -> None:
    """Grouped Bragg99 / moment_6 / D6-Jaccard bars, faceted by geometry."""
    geoms = sorted({r["geometry"] for r in all_records})
    metrics = ["bragg99", "moment_6", "d6_jaccard"]
    geom_color = {"eisenstein": "#4c78a8", "gaussian": "#e45756", "z12": "#54a24b"}

    fig, axes = plt.subplots(1, len(metrics), figsize=(5 * len(metrics), 5), squeeze=False)
    for ax, metric in zip(axes.ravel(), metrics):
        for gi, g in enumerate(geoms):
            rows = sorted([r for r in all_records if r["geometry"] == g], key=lambda r: r["t"])
            ts = [r["t"] for r in rows]
            vals = [r[metric] for r in rows]
            ax.plot(ts, vals, marker="o", linewidth=1.6,
                    color=geom_color.get(g, None), label=g)
        if metric == "bragg99":
            ax.axhline(random_b99, color="#888", linestyle="--", linewidth=1.0,
                       label="random baseline")
        ax.set_xlabel("number of split primes t")
        ax.set_ylabel(metric)
        ax.set_title(metric)
        ax.grid(alpha=0.3, linestyle=":")
        ax.legend(fontsize=8)
    fig.suptitle("Lattice geometry comparison for the UDC construction\n"
                 "(eisenstein = A2/D6 = HeXO lattice; gaussian = Z[i]/D4 = Erdos baseline)")
    plt.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=160)
    plt.close(fig)


def run(args: argparse.Namespace) -> dict:
    rng = random.Random(args.seed)
    t0 = time.time()

    geometries = [GEOMETRIES[g] for g in args.geometries]
    all_records: list[dict] = []
    for geom in geometries:
        all_records.extend(_run_geometry(geom, args, rng))

    # Random + hex-ball baselines matching median UDC size
    median_n = int(np.median([r["n_stones"] for r in all_records])) if all_records else 100
    radius_for_n = int(math.ceil(math.sqrt(median_n / math.pi))) + 5
    random_cells = _random_disc_points(median_n, radius_for_n, rng)
    rng_obs = _safe_crystal_obs(random_cells, args.diffraction_grid, rng)
    random_b99 = float(rng_obs["bragg99"])
    print(f"\nRandom baseline (n={len(random_cells)}): Bragg99={random_b99:.4f}, "
          f"moment_6={rng_obs['moment_6']:.4f}")

    hex_cells = _hex_ball_points(int(math.ceil(math.sqrt(median_n / math.pi))) + 1)[:median_n]
    hex_obs = _safe_crystal_obs(hex_cells, args.diffraction_grid, rng)
    hex_b99 = float(hex_obs["bragg99"])
    print(f"Hex-ball baseline  (n={len(hex_cells)}): Bragg99={hex_b99:.4f}, "
          f"moment_6={hex_obs['moment_6']:.4f}")

    # P6 verdicts — computed on the primary (eisenstein) geometry
    primary = "eisenstein" if "eisenstein" in args.geometries else args.geometries[0]
    primary_records = sorted([r for r in all_records if r["geometry"] == primary],
                             key=lambda r: r["t"])
    p6a = [r["bragg99"] > random_b99 for r in primary_records]
    p6b = [r["moment_6"] > float(rng_obs["moment_6"]) for r in primary_records]
    b99s = [r["bragg99"] for r in primary_records]
    p6c = all(b99s[i] <= b99s[i + 1] for i in range(len(b99s) - 1)) if len(b99s) > 1 else None
    if len(primary_records) >= 2:
        ts = np.array([r["t"] for r in primary_records], dtype=float)
        ns = np.array([r["n_stones"] for r in primary_records], dtype=float)
        gamma_fit = float(np.polyfit(ts, np.log(np.maximum(ns, 1)), 1)[0])
    else:
        gamma_fit = None

    # Geometry verdict: which geometry has highest mean Bragg99 / D6-Jaccard?
    geom_means = {}
    for g in args.geometries:
        rows = [r for r in all_records if r["geometry"] == g]
        if rows:
            geom_means[g] = {
                "mean_bragg99": float(np.mean([r["bragg99"] for r in rows])),
                "mean_moment_6": float(np.mean([r["moment_6"] for r in rows])),
                "mean_d6_jaccard": float(np.mean([r["d6_jaccard"] for r in rows])),
            }

    print(f"\n--- P6 verdicts ({primary} geometry) ---")
    print(f"P6a Bragg99 > random: {p6a}")
    print(f"P6b moment_6 > random: {p6b}")
    print(f"P6c Bragg99 monotone in t: {p6c}")
    print(f"P6d gamma (log n ~ gamma*t): {gamma_fit}")
    print("\n--- Geometry comparison (mean over t) ---")
    for g, m in geom_means.items():
        print(f"  {g:12s}  Bragg99={m['mean_bragg99']:.3f}  "
              f"moment_6={m['mean_moment_6']:.3f}  d6_jaccard={m['mean_d6_jaccard']:.3f}")

    # Plots — gallery uses primary geometry records
    plot_gallery(primary_records, random_cells, FIG_GALLERY)
    plot_bragg(primary_records, random_b99, hex_b99, FIG_BRAGG)
    plot_harmonics(primary_records, random_cells, FIG_HARMONICS)
    if len(args.geometries) > 1:
        plot_geometry_comparison(all_records, random_b99, FIG_GEOMETRY)

    figures = [str(FIG_BRAGG), str(FIG_GALLERY), str(FIG_HARMONICS)]
    if len(args.geometries) > 1:
        figures.append(str(FIG_GEOMETRY))

    result = {
        "experiment": "udc_positions",
        "config": vars(args),
        "wall_time_sec": time.time() - t0,
        "udc_records": [{k: v for k, v in r.items() if k != "cells"} for r in all_records],
        "random_baseline": {
            "n_stones": len(random_cells),
            "bragg99": random_b99,
            "moment_6": float(rng_obs["moment_6"]),
        },
        "hex_ball_baseline": {
            "n_stones": len(hex_cells),
            "bragg99": hex_b99,
            "moment_6": float(hex_obs["moment_6"]),
        },
        "geometry_means": geom_means,
        "p6_verdicts": {
            "primary_geometry": primary,
            "p6a_bragg99_above_random": p6a,
            "p6b_moment6_above_random": p6b,
            "p6c_bragg99_monotone_in_t": p6c,
            "p6d_gamma_fit": gamma_fit,
        },
        "figures": figures,
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t-values", nargs="+", type=int, default=[1, 2, 3, 4, 5],
                        help="Number of split primes per UDC set")
    parser.add_argument("--window-radii", nargs="+", type=float, default=[5.0, 8.0, 12.0, 16.0, 20.0],
                        help="Disc window radii to try per t")
    parser.add_argument("--target-n", type=int, default=500,
                        help="Stop growing window once this many active points found")
    parser.add_argument("--diffraction-grid", type=int, default=72)
    parser.add_argument("--geometries", nargs="+", default=["eisenstein", "gaussian"],
                        choices=sorted(GEOMETRIES.keys()),
                        help="Base lattices to compare (eisenstein=A2/D6, gaussian=Z[i]/D4)")
    parser.add_argument("--seed", type=int, default=20260522)
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    if args.quick:
        args.t_values = [1, 2, 3]
        args.window_radii = [4.0, 6.0, 8.0, 10.0]
        args.target_n = 300
        args.diffraction_grid = 48

    result = run(args)

    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_clean(v) for v in obj]
        if isinstance(obj, float) and not math.isfinite(obj):
            return None
        if isinstance(obj, tuple):
            return list(obj)
        return obj

    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(_clean(result), indent=2), encoding="utf-8")
    print(f"\nwrote {JSON_PATH}")
    for fig in result["figures"]:
        print(f"wrote {fig}")
    print(f"wall_time_sec={result['wall_time_sec']:.1f}")


if __name__ == "__main__":
    main()
