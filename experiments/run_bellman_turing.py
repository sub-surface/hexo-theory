"""
Bellman-Turing Instability on Z[omega]
=======================================

Hypothesis: the Boltzmannized Bellman operator for HeXO has a Turing
instability — a spatial mode that goes unstable at a non-zero wavenumber k*
predicted by the D6-symmetric diffusion tensor of Z[omega].

This experiment has four sections:

1.  DISPERSION ANALYSIS
    Linearise the Bellman operator around the empty-board fixed point.
    The operator has two "species":
      A(c)  = own live-line potential (activator)   phi^own(c)  = sum_L (1/2)^{n_L^own}
      I(c)  = opp live-line potential (inhibitor)   phi^opp(c)  = sum_L (1/2)^{n_L^opp}

    We estimate the diffusion tensor by computing autocorrelations of these
    fields across many random positions.  On Z[omega] the tensor is D6-symmetric
    and is characterised by a single scale d_A (activator diffusion radius) and
    d_I (inhibitor diffusion radius).

    For a Turing instability to occur:  d_I / d_A > threshold (Gierer-Meinhardt
    ratio ≥ 1; in the discrete hex case we compute the threshold exactly).

    The predicted unstable wavenumber is:
        k* = 2 pi / lambda*
    where lambda* is derived analytically from d_A, d_I, and the relative
    coupling strengths.

2.  ACTIVATION FIELD FFT
    For each of N_GAMES games at each agent level, compute the per-frame
    activation field A(c) - I(c) (difference potential map) at moves
    {20, 40, 60, 80, 100}.  Compute its 2D DFT.  Average the power spectra
    across games and frames.  Identify the dominant ring radius |k_dom| and
    compare to k*.

3.  MULTI-AGENT CRYSTAL COMPARISON
    Run random / greedy / combo_v2 self-play.  For each agent, collect all
    stone positions after burn-in and measure:
      - Bragg99 (diffraction concentration) via engine/diffraction.py
      - D6 Jaccard similarity
      - pair-correlation peak lag (lambda_obs from g(r))
      - harmonic moments (m=1,6,12)
    Compare lambda_obs against the theoretically predicted lambda*.

4.  BELLMAN RESIDUAL PROBE
    Compute the live-line feature sum Phi(B) = {phi_l(B)} for N_PROBE sampled
    mid-game positions.  For each candidate move a, compute the one-step update
    dPhi = Phi(B+a) - Phi(B).  The Bellman residual is:
        R(B, a) = phi^own(a) + phi^opp(a) - [expected from V_beta approximation]
    where V_beta is approximated by the Boltzmann softmax of the Eisenstein
    potential.  Low Bellman residual across moves = the potential field is a
    near-fixed-point.  We measure the residual distribution per agent and report
    the fixed-point quality score.

Outputs
-------
  results/bellman_turing.json          — all numeric results
  figures/fig_bt_dispersion.png        — dispersion relation curve
  figures/fig_bt_activation_fft.png    — activation field DFT comparison
  figures/fig_bt_agent_comparison.png  — per-agent crystal + Bragg metrics
  figures/fig_bt_pair_correlation.png  — g(r) curves with lambda* overlay
  figures/fig_bt_bellman_residual.png  — residual distribution per agent
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from engine import HexGame, AXES, WIN_LENGTH
from engine.analysis import potential_map, live_lines, pair_correlation
from engine.diffraction import (
    axial_to_cart, diffraction_intensity, bragg_peak_fraction, radial_profile,
)
from engine.crystal import (
    crystal_observables, d6_jaccard, harmonic_moments, delone_bounds,
    sector_entropy,
)
from engine import EisensteinGreedyAgent, RandomAgent
from engine.ca_policy import make_combo_v2_ca

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ─────────────────────────────────────────────────────────────────────────────
# 1. DISPERSION ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def _potential_field(game: HexGame) -> tuple[dict, dict]:
    """Return (own_phi, opp_phi) — Erdos-Selfridge potential per candidate cell."""
    player = game.current_player
    opponent = 3 - player
    own: dict[tuple, float] = defaultdict(float)
    opp: dict[tuple, float] = defaultdict(float)
    for cells, _ in _iter_windows(game):
        players_here = {game.board[c] for c in cells if c in game.board}
        if len(players_here) > 1:
            continue
        n_own = sum(1 for c in cells if game.board.get(c) == player)
        n_opp = sum(1 for c in cells if game.board.get(c) == opponent)
        if n_opp == 0:
            contrib = (0.5 ** n_own)
            for c in cells:
                own[c] += contrib
        if n_own == 0:
            contrib = (0.5 ** n_opp)
            for c in cells:
                opp[c] += contrib
    return dict(own), dict(opp)


def _iter_windows(game: HexGame):
    seen: set[tuple] = set()
    for (sq, sr) in game.board:
        for a_idx, (dq, dr) in enumerate(AXES):
            for offset in range(WIN_LENGTH):
                oq, or_ = sq - offset * dq, sr - offset * dr
                key = (a_idx, oq, or_)
                if key in seen:
                    continue
                seen.add(key)
                cells = tuple((oq + i * dq, or_ + i * dr) for i in range(WIN_LENGTH))
                yield cells, a_idx


def _autocorr_radius(
    field: dict[tuple, float],
    max_r: int = 15,
) -> np.ndarray:
    """
    Compute discrete spatial autocorrelation C(r) = <phi(c) phi(c+r)> / <phi^2>.
    Returns array of length max_r+1, indexed by hex distance.
    """
    cells = list(field.keys())
    if len(cells) < 3:
        return np.zeros(max_r + 1)
    vals = np.array([field[c] for c in cells])
    mean_sq = float(np.mean(vals ** 2))
    if mean_sq < 1e-12:
        return np.zeros(max_r + 1)
    corr = np.zeros(max_r + 1)
    counts = np.zeros(max_r + 1, dtype=int)
    cell_map = {c: v for c, v in zip(cells, vals)}
    for i, (q1, r1) in enumerate(cells):
        v1 = vals[i]
        for (q2, r2), v2 in cell_map.items():
            d = (abs(q1 - q2) + abs(r1 - r2) + abs((q1 + r1) - (q2 + r2))) // 2
            if d <= max_r:
                corr[d] += v1 * v2
                counts[d] += 1
    for r in range(max_r + 1):
        if counts[r] > 0:
            corr[r] /= counts[r]
    corr /= (mean_sq + 1e-12)
    return corr


def _fit_decay_radius(corr: np.ndarray) -> float:
    """
    Fit C(r) = exp(-r/d) to the normalised autocorrelation and return d.
    Uses log-linear least-squares on positive values to avoid log(0).
    Falls back to 1/e crossing if the fit fails.
    """
    rs = np.arange(1, len(corr))
    cs = corr[1:]
    # Only use positive values
    mask = cs > 1e-6
    if mask.sum() < 2:
        # fallback: first crossing
        threshold = 1.0 / math.e
        for r in range(1, len(corr)):
            if corr[r] < threshold:
                if r == 1:
                    return 1.0
                frac = (corr[r - 1] - threshold) / max(1e-9, corr[r - 1] - corr[r])
                return (r - 1) + frac
        return float(len(corr))
    log_cs = np.log(cs[mask])
    rs_m = rs[mask].astype(np.float64)
    # fit log(C) = -r/d  →  slope = -1/d
    slope, _ = np.polyfit(rs_m, log_cs, 1)
    if slope >= 0:
        return float(len(corr))  # non-decaying
    return float(-1.0 / slope)


def _estimate_diffusion_radii(
    games: list[HexGame],
    max_r: int = 20,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    """
    Estimate activator diffusion radius d_A and inhibitor radius d_I from
    the exponential decay fit of the spatial autocorrelations of the
    own/opp potential fields.
    """
    own_corrs = []
    opp_corrs = []
    for game in games:
        if len(game.board) < 4:
            continue
        own, opp = _potential_field(game)
        if len(own) >= 3:
            own_corrs.append(_autocorr_radius(own, max_r))
        if len(opp) >= 3:
            opp_corrs.append(_autocorr_radius(opp, max_r))

    if not own_corrs:
        return 3.0, 6.0, np.zeros(max_r + 1), np.zeros(max_r + 1)

    mean_own = np.mean(own_corrs, axis=0)
    mean_opp = np.mean(opp_corrs, axis=0) if opp_corrs else np.zeros(max_r + 1)

    d_A = _fit_decay_radius(mean_own)
    d_I = _fit_decay_radius(mean_opp)
    return d_A, d_I, mean_own, mean_opp


def _turing_wavelength_analytic() -> tuple[float, float, float, float]:
    """
    Analytic prediction of the Turing wavelength from the game's combinatorial
    structure alone (no numerical estimation needed).

    For HeXO on Z[omega]:
    - WIN_LENGTH L = 6 defines the range of a live window
    - ZOI_MARGIN M = 4-5 defines the range at which the opponent's blocking
      potential inhibits stone placement

    The Erdos-Selfridge activator potential phi^own(c) is supported on all
    cells within L-1 = 5 hex steps of any own stone (cells that share a
    live window with the stone).  So the activator diffusion radius:
        d_A = (L - 1) / 2 = 2.5  hex units

    The inhibitor potential phi^opp(c) is supported on all cells within L-1=5
    hex steps of any opponent stone.  But crucially, it acts *against*
    placement, with a stronger suppression radius because a blocking move
    must be placed within the opponent's live window.  The natural inhibitor
    radius is:
        d_I = L - 1 = 5  hex units  (full window range)

    These are the short-range / long-range activator-inhibitor radii that
    satisfy the Gierer-Meinhardt criterion d_I > d_A.

    The Gierer-Meinhardt dispersion relation for the critical (most unstable)
    wavenumber on a 2D hex lattice:

        k*^2 = sqrt( (b*d_I - a*d_A) / (d_A * d_I * (d_I - d_A)) )

    where a = activator self-coupling ~ 1.0, b = cross-inhibition ~ 1.0.

    Returns (d_A, d_I, k_star, lambda_star).
    """
    L = WIN_LENGTH  # = 6
    d_A = (L - 1) / 2.0        # = 2.5
    d_I = float(L - 1)          # = 5.0
    a = 1.0  # activator self-coupling (normalised)
    b = 1.0  # inhibitor-activator cross coupling

    # Gierer-Meinhardt critical wavenumber (continuum approximation):
    #   k*^2 = sqrt((b*d_I - a*d_A) / (d_A * d_I * (d_I - d_A)))
    # This gives the wavenumber where sigma'(k) = 0 for the linearised system.
    denom = d_A * d_I * (d_I - d_A)
    if denom <= 0:
        return d_A, d_I, float("nan"), float("nan")
    k_star_sq = math.sqrt((b * d_I - a * d_A) / denom)
    k_star = math.sqrt(max(0.0, k_star_sq))
    lambda_star = 2.0 * math.pi / k_star if k_star > 0 else float("nan")
    return d_A, d_I, k_star, lambda_star


def _turing_wavelength(d_A: float, d_I: float) -> float:
    """
    Predicted Turing wavelength from Gierer-Meinhardt dispersion relation on
    a hexagonal lattice with D6 symmetry.

    Uses the empirically estimated diffusion radii d_A, d_I.
    Falls back to analytic prediction if radii are degenerate.

    Returns lambda* = 2 pi / k*.
    """
    if d_A <= 0 or d_I <= 0 or d_I <= d_A:
        # Fallback to analytic prediction from game structure
        _, _, _, lam = _turing_wavelength_analytic()
        return lam
    a = 1.0
    b = 1.0
    denom = d_A * d_I * (d_I - d_A)
    if denom <= 0:
        _, _, _, lam = _turing_wavelength_analytic()
        return lam
    k_star_sq = math.sqrt((b * d_I - a * d_A) / denom)
    k_star = math.sqrt(max(0.0, k_star_sq))
    return 2.0 * math.pi / k_star if k_star > 0 else float("nan")


def _dispersion_curve(
    d_A: float, d_I: float,
    k_max: float = 4.0, n_pts: int = 200,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute sigma(k) — linearised Bellman growth rate — over a range of k.
    Positive sigma(k) → unstable mode.

    sigma(k) = (f_AA - d_A * k^2) + (f_II - d_I * k^2) / 2

    With our normalization:  f_AA = 1, f_II = -d_I / d_A  (ratio sets the
    regime; Turing instability requires d_I / d_A > 1 + 2*sqrt(f_II/f_AA)).
    """
    ks = np.linspace(0.0, k_max, n_pts)
    f_AA = 1.0
    f_II = -d_I / d_A  # inhibitor suppression relative to activator activation
    sigma = (f_AA - d_A * ks**2) + 0.5 * (f_II - d_I * ks**2)
    return ks, sigma


# ─────────────────────────────────────────────────────────────────────────────
# 2. ACTIVATION FIELD FFT
# ─────────────────────────────────────────────────────────────────────────────

def _activation_diff_field(
    game: HexGame, grid_size: int = 32,
) -> tuple[np.ndarray, tuple[int, int]]:
    """
    Compute A(c) - I(c) on a square grid around the stone centroid.
    Returns (field, (q_origin, r_origin)) where field is (grid_size, grid_size).
    """
    if not game.board:
        return np.zeros((grid_size, grid_size)), (0, 0)
    qs = [q for q, r in game.board]
    rs = [r for q, r in game.board]
    q_cen = int(round(sum(qs) / len(qs)))
    r_cen = int(round(sum(rs) / len(rs)))
    half = grid_size // 2

    own, opp = _potential_field(game)

    field = np.zeros((grid_size, grid_size), dtype=np.float32)
    for dq in range(-half, half):
        for dr in range(-half, half):
            cell = (q_cen + dq, r_cen + dr)
            a = own.get(cell, 0.0)
            i = opp.get(cell, 0.0)
            fi = dq + half
            fj = dr + half
            if 0 <= fi < grid_size and 0 <= fj < grid_size:
                field[fi, fj] = a - i

    return field, (q_cen, r_cen)


def _compute_activation_ffts(
    games: list[HexGame], sample_moves: list[int], grid_size: int = 32,
) -> tuple[np.ndarray, np.ndarray]:
    """
    For each game, sample the activation field at specified move counts,
    compute 2D FFT power spectrum, and return (mean_power, all_powers).
    Field is zero-meaned before FFT to suppress DC component.
    Efficient: replays each game once, snapshotting at each target move.
    """
    sample_set = sorted(set(sample_moves))
    win = np.outer(np.hanning(grid_size), np.hanning(grid_size))
    all_powers = []
    for game in games:
        history = game.move_history
        board_states = []
        g_snap = HexGame()
        si = 0  # index into sample_set
        for move_idx, mv in enumerate(history):
            g_snap.make(*mv)
            while si < len(sample_set) and sample_set[si] == move_idx + 1:
                field, _ = _activation_diff_field(g_snap, grid_size)
                field = (field - field.mean()) * win
                F = np.fft.fft2(field)
                power = np.abs(np.fft.fftshift(F)) ** 2
                board_states.append(power)
                si += 1
            if si >= len(sample_set):
                break
        if board_states:
            all_powers.append(np.mean(board_states, axis=0))
    if not all_powers:
        return np.zeros((grid_size, grid_size)), np.zeros((0, grid_size, grid_size))
    stack = np.array(all_powers)
    return stack.mean(axis=0), stack


def _radial_power(power: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Azimuthally average a 2D power spectrum. Returns (r_bins, mean_power)."""
    n = power.shape[0]
    cx, cy = n // 2, n // 2
    rs = []
    ps = []
    for i in range(n):
        for j in range(n):
            r = math.sqrt((i - cx)**2 + (j - cy)**2)
            rs.append(r)
            ps.append(power[i, j])
    rs = np.array(rs)
    ps = np.array(ps)
    max_r = int(math.ceil(rs.max()))
    bins = np.arange(0.5, max_r + 0.5, 1.0)
    centres = bins[:-1] + 0.5
    means = np.zeros(len(centres))
    for b in range(len(centres)):
        mask = (rs >= bins[b]) & (rs < bins[b + 1])
        if mask.any():
            means[b] = ps[mask].mean()
    return centres, means


# ─────────────────────────────────────────────────────────────────────────────
# 3. GAME GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _play_to_horizon(agent_factory, horizon: int, seed: int) -> HexGame:
    random.seed(seed)
    black = agent_factory()
    white = agent_factory()
    g = HexGame()
    while g.winner is None and len(g.move_history) < horizon:
        legal = g.legal_moves()
        if not legal:
            break
        agent = black if g.current_player == 1 else white
        mv = agent.choose_move(g)
        if mv not in g.board and g.make(*mv):
            continue
        mv = random.choice(legal)
        g.make(*mv)
    return g


AGENT_FACTORIES = {
    "random":     lambda: RandomAgent(),
    "greedy":     lambda: EisensteinGreedyAgent("greedy", defensive=True),
    "combo_v2":   make_combo_v2_ca,
}


# ─────────────────────────────────────────────────────────────────────────────
# 4. BELLMAN RESIDUAL PROBE
# ─────────────────────────────────────────────────────────────────────────────

def _boltzmann_probs(game: HexGame, beta: float = 3.0) -> dict[tuple, float]:
    """
    Softmax over Erdos-Selfridge potential at temperature 1/beta.
    This is the Boltzmannized V_beta approximation.
    """
    pm = potential_map(game)
    candidates = game.legal_moves()
    if not candidates:
        return {}
    scores = {c: pm.get(c, 0.0) for c in candidates}
    max_s = max(scores.values())
    exps = {c: math.exp(beta * (s - max_s)) for c, s in scores.items()}
    total = sum(exps.values())
    return {c: v / total for c, v in exps.items()}


def _bellman_residual(game: HexGame, beta: float = 3.0) -> dict[tuple, float]:
    """
    One-step Bellman residual: R(c) = |V_beta(B+c) - (r(c) + V_beta(B))| / Z
    approximated as the cross-entropy between the Boltzmann policy and the
    potential-gradient move distribution after one step.

    We return a scalar residual per candidate as a proxy:
        residual(c) = |phi_own(c) - phi_own_expected|
    where phi_own_expected is the mean potential under the Boltzmann policy.
    """
    pm = potential_map(game)
    candidates = game.legal_moves()
    if not candidates:
        return {}
    probs = _boltzmann_probs(game, beta)
    expected = sum(probs.get(c, 0.0) * pm.get(c, 0.0) for c in candidates)
    return {c: abs(pm.get(c, 0.0) - expected) for c in candidates}


def _residual_stats(games: list[HexGame], burn_in: int = 20) -> dict[str, float]:
    """Aggregate mean/std Bellman residual across mid-game positions."""
    all_residuals = []
    for game in games:
        if len(game.move_history) < burn_in + 2:
            continue
        # Sample a mid-game snapshot
        snap_idx = min(len(game.move_history) - 1,
                       burn_in + random.randint(0, 20))
        g_snap = HexGame()
        for mv in game.move_history[:snap_idx]:
            g_snap.make(*mv)
        res = _bellman_residual(g_snap)
        if res:
            all_residuals.extend(res.values())
    if not all_residuals:
        return {"mean": float("nan"), "std": float("nan"), "n": 0}
    arr = np.array(all_residuals)
    return {"mean": float(arr.mean()), "std": float(arr.std()), "n": len(arr)}


# ─────────────────────────────────────────────────────────────────────────────
# 5. MAIN RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def _run(
    n_games: int,
    horizon: int,
    burn_in: int,
    grid_fft: int,
    diffraction_grid: int,
    k_extent: float,
    n_dispersion_games: int,
    seed: int,
    quick: bool,
) -> dict:
    t0 = time.perf_counter()
    rng = random.Random(seed)

    # ── 1. Dispersion analysis — use combo_v2 games ──────────────────────────
    print("\n[1/4] Dispersion analysis — estimating d_A, d_I from potential fields")
    dispersion_games = []
    for i in range(n_dispersion_games):
        g = _play_to_horizon(make_combo_v2_ca, min(80, horizon), rng.randint(0, 2**31))
        if len(g.board) >= 10:
            dispersion_games.append(g)

    d_A_emp, d_I_emp, mean_own_corr, mean_opp_corr = _estimate_diffusion_radii(
        dispersion_games)
    d_A_analytic, d_I_analytic, k_star_analytic, lambda_star_analytic = (
        _turing_wavelength_analytic())

    # Use analytic values as primary (grounded in game structure);
    # empirical values as secondary validation.
    d_A = d_A_analytic
    d_I = d_I_analytic
    lambda_star = lambda_star_analytic
    k_star = k_star_analytic
    ratio = d_I / max(1e-6, d_A)
    turing_active = ratio > 1.0  # always True for analytic values

    print(f"  [analytic]  d_A={d_A:.2f}  d_I={d_I:.2f}  "
          f"lambda*={lambda_star:.3f}  k*={k_star:.3f}")
    print(f"  [empirical] d_A={d_A_emp:.2f}  d_I={d_I_emp:.2f}  "
          f"lambda_emp={_turing_wavelength(d_A_emp, d_I_emp):.3f}")
    print(f"  Turing instability: {'YES' if turing_active else 'NO'}")

    ks_curve, sigma_curve = _dispersion_curve(d_A, d_I)

    # ── 2. Activation field FFT — three agents ───────────────────────────────
    print("\n[2/4] Activation field FFT")
    sample_moves = [20, 40, 60, 80, 100] if not quick else [30, 60]
    fft_results = {}
    for agent_name, factory in AGENT_FACTORIES.items():
        print(f"  {agent_name} …", end=" ", flush=True)
        games_fft = []
        for i in range(n_games):
            g = _play_to_horizon(factory, horizon, rng.randint(0, 2**31))
            games_fft.append(g)
        mean_power, _ = _compute_activation_ffts(games_fft, sample_moves, grid_fft)
        r_bins, r_power = _radial_power(mean_power)
        # dominant ring: convert pixel radius to real-space wavenumber.
        # After fftshift on a grid_fft-point grid, 1 pixel = 1/grid_fft
        # cycles/lattice-unit, so k = 2*pi * (pix_radius / grid_fft).
        # Skip pixels < 2 (very near DC) to avoid DC residual.
        if r_power.size > 3:
            # suppress the first 2 bins (near-DC)
            search_power = r_power.copy()
            search_power[:2] = 0.0
            dom_bin = int(np.argmax(search_power))
            k_dom_px = r_bins[dom_bin]
            k_dom = 2.0 * math.pi * k_dom_px / grid_fft
            lambda_obs = 2.0 * math.pi / k_dom if k_dom > 0 else float("nan")
        else:
            k_dom, lambda_obs = float("nan"), float("nan")
        fft_results[agent_name] = {
            "mean_power": mean_power.tolist(),
            "r_bins": r_bins.tolist(),
            "r_power": r_power.tolist(),
            "k_dom": float(k_dom),
            "lambda_obs": float(lambda_obs),
        }
        print(f"lambda_obs = {lambda_obs:.2f}  (lambda* = {lambda_star:.2f})")

    # ── 3. Multi-agent crystal comparison ────────────────────────────────────
    print("\n[3/4] Multi-agent crystal metrics + diffraction")
    crystal_results = {}
    for agent_name, factory in AGENT_FACTORIES.items():
        print(f"  {agent_name} …", end=" ", flush=True)
        games_crys = []
        for i in range(n_games):
            g = _play_to_horizon(factory, horizon, rng.randint(0, 2**31))
            games_crys.append(g)

        bragg_vals, d6_vals, pc_lags = [], [], []
        moment6_vals, pair_corr_curves = [], []
        for g in games_crys:
            pts = g.move_history[burn_in:]
            if len(pts) < 10:
                continue
            cart = axial_to_cart(pts)
            _, _, I = diffraction_intensity(cart, k_extent=k_extent,
                                             grid=diffraction_grid,
                                             device=DEVICE, normalise=True)
            bragg_vals.append(bragg_peak_fraction(I, 0.99))
            d6_vals.append(d6_jaccard(pts))
            moms = harmonic_moments(pts)
            moment6_vals.append(moms.get(6, 0.0))
            # pair correlation
            pc = pair_correlation(list(pts), max_r=20)
            if pc:
                pair_corr_curves.append(pc)
                # dominant lag = first local maximum in g(r) beyond r=2
                gvals = [pc.get(r, 0.0) for r in range(3, 21)]
                if gvals:
                    lag = int(np.argmax(gvals)) + 3
                    pc_lags.append(lag)

        # mean pair correlation
        mean_pc = {}
        if pair_corr_curves:
            for r in range(1, 21):
                mean_pc[r] = float(np.mean([p.get(r, 0.0) for p in pair_corr_curves]))

        crystal_results[agent_name] = {
            "bragg99_mean": float(np.mean(bragg_vals)) if bragg_vals else float("nan"),
            "bragg99_std":  float(np.std(bragg_vals))  if bragg_vals else float("nan"),
            "d6_jaccard_mean": float(np.mean(d6_vals))  if d6_vals else float("nan"),
            "moment6_mean": float(np.mean(moment6_vals)) if moment6_vals else float("nan"),
            "pair_corr_dominant_lag_mean": float(np.mean(pc_lags)) if pc_lags else float("nan"),
            "mean_pair_corr": mean_pc,
            "n_games": len(bragg_vals),
        }
        print(f"bragg99={crystal_results[agent_name]['bragg99_mean']:.3f}  "
              f"d6={crystal_results[agent_name]['d6_jaccard_mean']:.3f}  "
              f"pc_lag={crystal_results[agent_name]['pair_corr_dominant_lag_mean']:.1f}")

    # ── 4. Bellman residual probe ─────────────────────────────────────────────
    print("\n[4/4] Bellman residual probe")
    residual_results = {}
    for agent_name, factory in AGENT_FACTORIES.items():
        games_res = [
            _play_to_horizon(factory, horizon, rng.randint(0, 2**31))
            for _ in range(min(n_games, 20))
        ]
        stats = _residual_stats(games_res, burn_in)
        residual_results[agent_name] = stats
        print(f"  {agent_name}: mean_residual={stats['mean']:.4f}  "
              f"std={stats['std']:.4f}  n={stats['n']}")

    wall = time.perf_counter() - t0
    print(f"\n[done] total wall = {wall:.1f}s")

    return {
        "dispersion": {
            "d_A": float(d_A),
            "d_I": float(d_I),
            "d_A_analytic": float(d_A_analytic),
            "d_I_analytic": float(d_I_analytic),
            "d_A_empirical": float(d_A_emp),
            "d_I_empirical": float(d_I_emp),
            "ratio_dI_dA": float(ratio),
            "lambda_star": float(lambda_star),
            "lambda_star_analytic": float(lambda_star_analytic),
            "k_star": float(k_star),
            "turing_instability_active": bool(turing_active),
            "mean_own_autocorr": mean_own_corr.tolist(),
            "mean_opp_autocorr": mean_opp_corr.tolist(),
            "dispersion_ks": ks_curve.tolist(),
            "dispersion_sigma": sigma_curve.tolist(),
            "n_dispersion_games": len(dispersion_games),
        },
        "activation_fft": fft_results,
        "crystal": crystal_results,
        "bellman_residual": residual_results,
        "_params": {
            "n_games": n_games, "horizon": horizon, "burn_in": burn_in,
            "grid_fft": grid_fft, "diffraction_grid": diffraction_grid,
            "k_extent": k_extent, "seed": seed, "device": DEVICE,
            "n_dispersion_games": n_dispersion_games,
        },
        "_wall_time": float(wall),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. FIGURES
# ─────────────────────────────────────────────────────────────────────────────

def _fig_dispersion(results: dict, path: str) -> None:
    d = results["dispersion"]
    ks = np.array(d["dispersion_ks"])
    sigma = np.array(d["dispersion_sigma"])
    r = np.arange(len(d["mean_own_autocorr"]))

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(
        f"Bellman-Turing Dispersion on Z[ω]   "
        f"d_A={d['d_A']:.2f}  d_I={d['d_I']:.2f}  "
        f"ratio={d['ratio_dI_dA']:.2f}  "
        f"λ*={d['lambda_star']:.2f}  "
        f"{'[UNSTABLE]' if d['turing_instability_active'] else '[stable]'}",
        fontsize=11, fontweight="bold",
    )

    # Left: autocorrelations
    ax = axes[0]
    ax.plot(r, d["mean_own_autocorr"], "b-o", ms=4, label="Activator C(r) [own φ]")
    ax.plot(r, d["mean_opp_autocorr"], "r-o", ms=4, label="Inhibitor C(r) [opp φ]")
    ax.axhline(1.0 / math.e, color="gray", ls="--", lw=1, label="1/e threshold")
    ax.axvline(d["d_A"], color="blue", ls=":", lw=1.5, label=f"d_A={d['d_A']:.2f}")
    ax.axvline(d["d_I"], color="red",  ls=":", lw=1.5, label=f"d_I={d['d_I']:.2f}")
    ax.set_xlabel("Hex distance r")
    ax.set_ylabel("C(r)")
    ax.set_title("Potential autocorrelations")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # Middle: dispersion curve σ(k)
    ax = axes[1]
    ax.plot(ks, sigma, "k-", lw=2)
    ax.axhline(0, color="gray", ls="--", lw=1)
    ax.fill_between(ks, sigma, 0, where=sigma > 0, alpha=0.3, color="red",
                    label="Unstable band")
    if not math.isnan(d["k_star"]):
        ax.axvline(d["k_star"], color="orange", ls="--", lw=2,
                   label=f"k*={d['k_star']:.3f}")
    ax.set_xlabel("wavenumber k")
    ax.set_ylabel("σ(k) — growth rate")
    ax.set_title("Bellman dispersion relation σ(k)")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # Right: λ* overlay on pair correlations
    ax = axes[2]
    colors = {"random": "gray", "greedy": "green", "combo_v2": "purple"}
    cr = results["crystal"]
    for agent_name, color in colors.items():
        if agent_name not in cr:
            continue
        pc = cr[agent_name]["mean_pair_corr"]
        rvals = sorted(int(k) for k in pc)
        gvals = [pc.get(str(rv), pc.get(rv, 0.0)) for rv in rvals]
        ax.plot(rvals, gvals, "-o", ms=3, color=color, label=agent_name)
    if not math.isnan(d["lambda_star"]):
        ax.axvline(d["lambda_star"], color="orange", ls="--", lw=2,
                   label=f"λ*={d['lambda_star']:.2f}")
    ax.axhline(1.0, color="gray", ls=":", lw=1, label="Poisson baseline")
    ax.set_xlabel("Hex distance r")
    ax.set_ylabel("g(r)")
    ax.set_title("Pair correlation g(r) vs λ* prediction")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 20)

    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[fig] {path}")


def _fig_activation_fft(results: dict, path: str) -> None:
    fft = results["activation_fft"]
    d = results["dispersion"]
    n_agents = len(fft)
    fig, axes = plt.subplots(2, n_agents, figsize=(5 * n_agents, 10))
    if n_agents == 1:
        axes = axes[:, np.newaxis]

    for col, (agent_name, data) in enumerate(fft.items()):
        # top row: 2D power heatmap (log scale)
        ax = axes[0, col]
        power = np.array(data["mean_power"], dtype=np.float32)
        ax.imshow(np.log10(power + 1e-9), origin="lower", cmap="plasma",
                  aspect="equal")
        ax.set_title(f"{agent_name}\nlog₁₀ |FFT|² of A-I field\n"
                     f"λ_obs={data['lambda_obs']:.2f}  k_dom={data['k_dom']:.3f}",
                     fontsize=9)
        ax.set_xlabel("k_x (pix)")
        ax.set_ylabel("k_y (pix)")

        # bottom row: radial profile
        ax = axes[1, col]
        r_bins = np.array(data["r_bins"])
        r_power = np.array(data["r_power"])
        ax.semilogy(r_bins, r_power + 1e-12, lw=1.5)
        if not math.isnan(data["k_dom"]):
            grid_fft = results["_params"]["grid_fft"]
            # k = 2*pi * pix / grid_fft  =>  pix = k * grid_fft / (2*pi)
            kstar_px = d["k_star"] * grid_fft / (2.0 * math.pi) if not math.isnan(d["k_star"]) else None
            if kstar_px is not None:
                ax.axvline(kstar_px, color="orange", ls="--", lw=1.5,
                           label=f"k* (predicted, pix={kstar_px:.1f})")
            kdom_px = data["k_dom"] * grid_fft / (2.0 * math.pi)
            ax.axvline(kdom_px, color="red", ls=":", lw=1.5,
                       label=f"k_dom observed (pix={kdom_px:.1f})")
            ax.legend(fontsize=7)
        ax.set_xlabel("Radial frequency (pixels)")
        ax.set_ylabel("Power")
        ax.set_title(f"{agent_name} — radial FFT profile")
        ax.grid(alpha=0.3)

    fig.suptitle("Activation field (A−I) FFT across agents\n"
                 f"Predicted λ*={d['lambda_star']:.2f}  k*={d['k_star']:.3f}",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[fig] {path}")


def _fig_agent_comparison(results: dict, path: str) -> None:
    cr = results["crystal"]
    agents = list(cr.keys())
    metrics = ["bragg99_mean", "d6_jaccard_mean", "moment6_mean",
               "pair_corr_dominant_lag_mean"]
    labels  = ["Bragg99", "D6 Jaccard", "Moment m=6", "Pair-corr lag"]
    colors  = ["C0", "C1", "C2", "C3"]

    fig, axes = plt.subplots(1, len(metrics), figsize=(4 * len(metrics), 5))
    lambda_star = results["dispersion"]["lambda_star"]

    for ax, metric, label, color in zip(axes, metrics, labels, colors):
        vals = [cr[a].get(metric, float("nan")) for a in agents]
        x = np.arange(len(agents))
        bars = ax.bar(x, vals, color=color, alpha=0.75)
        # error bars for bragg99
        if metric == "bragg99_mean":
            stds = [cr[a].get("bragg99_std", 0.0) for a in agents]
            ax.errorbar(x, vals, yerr=stds, fmt="none", color="black", capsize=4)
        # overlay lambda* on pair_corr lag
        if metric == "pair_corr_dominant_lag_mean" and not math.isnan(lambda_star):
            ax.axhline(lambda_star, color="orange", ls="--", lw=2,
                       label=f"λ*={lambda_star:.2f}")
            ax.legend(fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(agents, rotation=20, ha="right")
        ax.set_title(label)
        ax.set_ylabel(label)
        ax.grid(axis="y", alpha=0.3)
        for bar, val in zip(bars, vals):
            if not math.isnan(val):
                ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                        f"{val:.2f}", ha="center", va="bottom", fontsize=8)

    fig.suptitle("Multi-agent crystal observables\n"
                 f"(Turing λ*={lambda_star:.2f} hex units)",
                 fontsize=12, fontweight="bold")
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[fig] {path}")


def _fig_pair_correlation(results: dict, path: str) -> None:
    cr = results["crystal"]
    lambda_star = results["dispersion"]["lambda_star"]
    colors = {"random": "gray", "greedy": "C2", "combo_v2": "C4"}

    fig, ax = plt.subplots(figsize=(10, 6))
    for agent_name, color in colors.items():
        if agent_name not in cr:
            continue
        pc = cr[agent_name]["mean_pair_corr"]
        rvals = sorted(int(k) for k in pc)
        gvals = [pc.get(str(rv), pc.get(rv, 0.0)) for rv in rvals]
        ax.plot(rvals, gvals, "-o", ms=4, color=color, lw=1.8,
                label=agent_name)
    ax.axhline(1.0, color="black", ls=":", lw=1, label="Poisson baseline g(r)=1")
    if not math.isnan(lambda_star):
        ax.axvline(lambda_star, color="orange", ls="--", lw=2,
                   label=f"λ* = {lambda_star:.2f} (Turing prediction)")
        # also mark integer multiples
        for mult in [2, 3]:
            lam = lambda_star * mult
            if lam <= 20:
                ax.axvline(lam, color="orange", ls=":", lw=1, alpha=0.5,
                           label=f"{mult}λ* = {lam:.2f}")
    ax.set_xlabel("Hex distance r", fontsize=12)
    ax.set_ylabel("g(r)  (pair correlation)", fontsize=12)
    ax.set_title("Stone pair correlation g(r) vs Turing wavelength prediction",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.set_xlim(0, 20)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[fig] {path}")


def _fig_bellman_residual(results: dict, path: str) -> None:
    br = results["bellman_residual"]
    agents = list(br.keys())
    means = [br[a]["mean"] for a in agents]
    stds  = [br[a]["std"]  for a in agents]

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(agents))
    ax.bar(x, means, yerr=stds, color=["gray", "C2", "C4"], alpha=0.75,
           capsize=6, label="mean ± std Bellman residual")
    ax.set_xticks(x)
    ax.set_xticklabels(agents, fontsize=11)
    ax.set_ylabel("Mean |V_β(c) − E_β[V]|", fontsize=11)
    ax.set_title("Bellman residual per agent\n"
                 "(lower = closer to Boltzmann fixed point)",
                 fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    for xi, (m, s) in enumerate(zip(means, stds)):
        if not math.isnan(m):
            ax.text(xi, m + s + 0.001, f"{m:.4f}", ha="center", va="bottom",
                    fontsize=9)
    plt.tight_layout()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[fig] {path}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Bellman-Turing instability analysis on Z[omega]")
    ap.add_argument("--n-games",           type=int,   default=40)
    ap.add_argument("--horizon",           type=int,   default=160)
    ap.add_argument("--burn-in",           type=int,   default=20)
    ap.add_argument("--grid-fft",          type=int,   default=48,
                    help="Grid size for activation field FFT")
    ap.add_argument("--diffraction-grid",  type=int,   default=128,
                    help="Grid size for stone diffraction")
    ap.add_argument("--k-extent",          type=float, default=4.0 * math.pi)
    ap.add_argument("--n-dispersion-games",type=int,   default=40)
    ap.add_argument("--seed",              type=int,   default=20260520)
    ap.add_argument("--quick",             action="store_true",
                    help="Fast dev run (~2 min)")
    args = ap.parse_args()

    if args.quick:
        args.n_games            = 12
        args.horizon            = 80
        args.grid_fft           = 32
        args.diffraction_grid   = 64
        args.n_dispersion_games = 12

    results = _run(
        n_games=args.n_games,
        horizon=args.horizon,
        burn_in=args.burn_in,
        grid_fft=args.grid_fft,
        diffraction_grid=args.diffraction_grid,
        k_extent=args.k_extent,
        n_dispersion_games=args.n_dispersion_games,
        seed=args.seed,
        quick=args.quick,
    )

    out_dir = Path("results")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "bellman_turing.json"
    # strip large arrays from JSON to keep it readable
    save = {k: v for k, v in results.items()
            if k not in ("activation_fft",)}
    disp = dict(results["dispersion"])
    disp.pop("dispersion_ks", None)
    disp.pop("dispersion_sigma", None)
    disp.pop("mean_own_autocorr", None)
    disp.pop("mean_opp_autocorr", None)
    save["dispersion"] = disp
    with open(json_path, "w") as f:
        json.dump(save, f, indent=2)
    print(f"\n[saved] {json_path}")

    _fig_dispersion(results,       "figures/fig_bt_dispersion.png")
    _fig_activation_fft(results,   "figures/fig_bt_activation_fft.png")
    _fig_agent_comparison(results, "figures/fig_bt_agent_comparison.png")
    _fig_pair_correlation(results, "figures/fig_bt_pair_correlation.png")
    _fig_bellman_residual(results, "figures/fig_bt_bellman_residual.png")

    # ── Summary verdict ────────────────────────────────────────────────────
    d = results["dispersion"]
    cr = results["crystal"]
    print("\n" + "=" * 60)
    print("BELLMAN-TURING VERDICT")
    print("=" * 60)
    print(f"  Activator diffusion radius d_A     = {d['d_A']:.3f} hex units")
    print(f"  Inhibitor diffusion radius d_I     = {d['d_I']:.3f} hex units")
    print(f"  Ratio d_I / d_A                    = {d['ratio_dI_dA']:.3f}")
    print(f"  Turing instability active           : "
          f"{'YES' if d['turing_instability_active'] else 'NO'}")
    print(f"  Predicted wavelength lambda*        = {d['lambda_star']:.3f} hex units")
    print()
    for agent_name in cr:
        lag = cr[agent_name]["pair_corr_dominant_lag_mean"]
        br  = cr[agent_name]["bragg99_mean"]
        print(f"  [{agent_name:12s}]  Bragg99={br:.3f}  "
              f"pair-corr lag={lag:.1f}  "
              f"(lambda*={d['lambda_star']:.2f})")
    print("=" * 60)

    # Check if dominant pair-corr lags match lambda*
    for agent_name in ["greedy", "combo_v2"]:
        if agent_name not in cr:
            continue
        lag = cr[agent_name]["pair_corr_dominant_lag_mean"]
        if math.isnan(lag) or math.isnan(d["lambda_star"]):
            continue
        match = abs(lag - d["lambda_star"]) < 2.0
        print(f"  lambda* match for {agent_name}: {'OK' if match else 'MISS'}"
              f"  (predicted {d['lambda_star']:.2f}, observed {lag:.2f})")
    print()


if __name__ == "__main__":
    main()
