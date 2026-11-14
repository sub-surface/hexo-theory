"""
Group theory of HeXO via the Eisenstein integers — a Conway-style investigation.

Two readings of "six in a straight line" are compared throughout:
  R3  (the rule)  six *adjacent* cells along one of the 3 unit axes 1, ω, ω²-ish
                  (axial (1,0), (0,1), (1,-1)), anywhere on the board.
  R6  (variant)   R3 plus the 3 "vertex" directions (1,1), (2,-1), (1,-2) = √-3·units:
                  geometrically straight but the cells only touch at corners.

Sections:
  rules       audit competition/arena.py check_win: translation invariance, R3 not R6.
  symmetry    p6m stabilisers of early positions (symmetry is spent by ply 3).
  rooks       toroidal hex rooks (R3) / hex queens (R6) on Z/n x Z/n.  A density-1/k
              periodic blocker exists iff these are solvable at n=k (Hall–Paige / Pólya).
  lattices    best sublattice blocker for every win length k (2 is inert in Z[ω]).
  blocking    exact MILP: least-density periodic hitting set of all 6-windows,
              over every period lattice of index <= N.
  tilings     pairing (1-1 alternation) and triple-tiling (1-2-2) draw certificates:
              smallest win length k for which a periodic one exists.
  ladder      rank over Z[ω]: A2 (rank 1, the board) -> E8 (rank 4, tetracode)
              -> ternary Golay (rank 12, Leech); and the 3B moonshine identity
              T_3B = 27 (θ_A2 / θ_{A2 + hole})^3 - 15 checked from lattice counts.

    python experiments/run_eisenstein_group_theory.py --quick
    python experiments/run_eisenstein_group_theory.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
import time
from collections import Counter
from math import gcd
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evidence" / "results"
FIGURES = ROOT / "evidence" / "figures"

AXIS3 = ((1, 0), (0, 1), (1, -1))
VERTEX3 = ((1, 1), (2, -1), (1, -2))
DIRS = {"R3": AXIS3, "R6": AXIS3 + VERTEX3}


# ─── p6m on axial coordinates ────────────────────────────────────────────────

def rot60(c):
    q, r = c
    return (-r, q + r)


def refl(c):
    q, r = c
    return (r, q)


def d6_elements():
    """The 12 linear maps of Z[ω] preserving the unit set, as functions on cells."""
    els = []
    for flip in (False, True):
        for k in range(6):
            def g(c, k=k, flip=flip):
                if flip:
                    c = refl(c)
                for _ in range(k):
                    c = rot60(c)
                return c
            els.append(g)
    return els


D6 = d6_elements()


def hex_disc(R):
    return [(q, r) for q in range(-R, R + 1) for r in range(-R, R + 1) if abs(q + r) <= R]


def stabiliser_order(black, white):
    """|Stab_{p6m}(position)|: g ∈ D6 with a translation t such that g(B)+t=B, g(W)+t=W."""
    B, W = frozenset(black), frozenset(white)
    ref = min(B)
    n = 0
    for g in D6:
        gB = [g(c) for c in B]
        m = min(gB)
        t = (ref[0] - m[0], ref[1] - m[1])
        if frozenset((c[0] + t[0], c[1] + t[1]) for c in gB) != B:
            continue
        if frozenset((g(c)[0] + t[0], g(c)[1] + t[1]) for c in W) == W:
            n += 1
    return n


def run_symmetry(quick):
    """Stabiliser-order distribution of positions after each ply, stones within radius R."""
    R = 3
    disc = hex_disc(R)
    out = {"radius": R}
    out["ply1"] = {"12": 1}
    rest = [c for c in disc if c != (0, 0)]
    ply2 = Counter(stabiliser_order([(0, 0)], w) for w in itertools.combinations(rest, 2))
    out["ply2"] = {str(k): v for k, v in sorted(ply2.items())}
    # ply 3 exhaustively in full mode; Monte Carlo in quick mode
    rng = random.Random(0)
    def sample(ply, n):
        cnt = Counter()
        for _ in range(n):
            nstones = 1 + 2 * (ply - 1)
            cells = rng.sample(disc, nstones)
            # stone 0 is Black's opener, then turns alternate W W, B B, ...
            black = [cells[0]] + [cells[i] for i in range(1, nstones) if ((i - 1) // 2) % 2 == 1]
            white = [cells[i] for i in range(1, nstones) if ((i - 1) // 2) % 2 == 0]
            cnt[stabiliser_order(black, white)] += 1
        return cnt
    if quick:
        p3 = sample(3, 20000)
    else:
        p3 = Counter()
        for w in itertools.combinations(rest, 2):
            others = [c for c in rest if c not in w]
            for b in itertools.combinations(others, 2):
                p3[stabiliser_order([(0, 0), *b], w)] += 1
    out["ply3"] = {str(k): v for k, v in sorted(p3.items())}
    for ply in (4, 5):
        out[f"ply{ply}"] = {str(k): v for k, v in sorted(sample(ply, 20000 if quick else 200000).items())}
    out["ply3_exhaustive"] = not quick
    return out


# ─── toroidal hex rooks / queens ─────────────────────────────────────────────

def torus_functionals(variant):
    """Linear functionals (a,b): line through (q,r) in direction d is {a q + b r = const}."""
    return [(-d[1], d[0]) for d in DIRS[variant]]


def count_torus_solutions(n, variant, limit=None):
    """Number of n-point sets on (Z/n)^2 meeting every line of every direction exactly once.
    Row r holds the point (σ(r), r); functionals other than r must be injective."""
    funcs = [f for f in torus_functionals(variant) if f != (0, 1)]  # rows are automatic
    used = [0] * len(funcs)
    count = 0
    first = None
    sol = [0] * n

    def rec(r):
        nonlocal count, first
        if limit is not None and count >= limit:
            return
        if r == n:
            count += 1
            if first is None:
                first = list(sol)
            return
        for q in range(n):
            bits = []
            ok = True
            for i, (a, b) in enumerate(funcs):
                v = (a * q + b * r) % n
                bit = 1 << v
                if used[i] & bit:
                    ok = False
                    break
                bits.append(bit)
            if not ok:
                continue
            for i, bit in enumerate(bits):
                used[i] |= bit
            sol[r] = q
            rec(r + 1)
            for i, bit in enumerate(bits):
                used[i] ^= bit
    rec(0)
    return count, first


def best_partial(n, variant):
    """Max number of lines-classes hit when forced to place n points with rows+columns exact:
    the 'near-miss' — how many distinct values the worst functional attains at best."""
    funcs = [f for f in torus_functionals(variant) if f not in ((0, 1), (-1, 0))]
    best, arg = -1, None
    for perm in itertools.permutations(range(n)):
        score = min(len({(a * perm[r] + b * r) % n for r in range(n)}) for a, b in funcs)
        if score > best:
            best, arg = score, perm
    return best, list(arg)


def run_rooks(quick):
    nmax = {"R3": 11 if quick else 13, "R6": 13 if quick else 17}
    out = {}
    for v in ("R3", "R6"):
        rows = []
        for n in range(1, nmax[v] + 1):
            t = time.time()
            c, first = count_torus_solutions(n, v)
            rows.append({"n": n, "solutions": c, "example": first, "sec": round(time.time() - t, 2)})
        out[v] = rows
    out["near_miss_n6_R3"] = best_partial(6, "R3")
    return out


# ─── sublattice blockers ─────────────────────────────────────────────────────

def lattice_blocker_indices(variant, nmax):
    """n such that some Λ with Z²/Λ ≅ Z/n has every direction a generator (e1→1, e2→b)."""
    ok = {}
    for n in range(1, nmax + 1):
        bs = [b for b in range(n) if all(gcd((d[0] + d[1] * b) % n, n) == 1 for d in DIRS[variant])]
        if bs:
            ok[n] = bs
    return ok


def run_lattices():
    out = {}
    for v in ("R3", "R6"):
        good = lattice_blocker_indices(v, 40)
        per_k = {}
        for k in range(2, 25):
            ns = [n for n in good if 1 < n <= k]
            per_k[k] = max(ns) if ns else None
        out[v] = {"good_indices": sorted(good), "best_index_for_k": per_k,
                  "example_b": {n: good[n][0] for n in good}}
    return out


# ─── exact periodic blocking via MILP ────────────────────────────────────────

def hnf_lattices(n):
    """All sublattices of Z² of index n, as Λ = <(a,0),(b,c)>, a·c = n, 0 <= b < a."""
    for a in range(1, n + 1):
        if n % a == 0:
            for b in range(a):
                yield (a, b, n // a)


def reducer(a, b, c):
    def red(x, y):
        k = y // c
        x -= k * b
        y -= k * c
        return (x % a) * c + y
    return red


def blocking_milp(args):
    """Least number of torus cells (mod Λ) hitting every k-window of every direction."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    (a, b, c), k, variant, tlim = args
    n = a * c
    red = reducer(a, b, c)
    rows = set()
    for x in range(a):
        for y in range(c):
            for d in DIRS[variant]:
                rows.add(frozenset(red(x + i * d[0], y + i * d[1]) for i in range(k)))
    A = np.zeros((len(rows), n))
    for i, w in enumerate(rows):
        A[i, list(w)] = 1
    res = milp(np.ones(n), constraints=LinearConstraint(A, 1, np.inf),
               integrality=np.ones(n), bounds=Bounds(0, 1),
               options={"time_limit": tlim})
    if res.x is None:
        return (a, b, c), None, None, False
    sel = [i for i in range(n) if res.x[i] > 0.5]
    return (a, b, c), len(sel), sel, res.status == 0


def run_blocking(quick, pool):
    out = {}
    for v in ("R3", "R6"):
        for k in (5, 6, 7):
            N = 60 if (k == 6 and not quick) else 30   # k = 5, 7 are sanity checks
            jobs = [(L, k, v, 20.0) for n in range(1, N + 1) for L in hnf_lattices(n)]
            best_by_index = {}
            best = (2.0, None)
            for L, m, sel, exact in pool.imap_unordered(blocking_milp, jobs, chunksize=4):
                n = L[0] * L[2]
                dens = m / n
                cur = best_by_index.get(n)
                if cur is None or dens < cur["density"]:
                    best_by_index[n] = {"density": dens, "count": m, "lattice": L,
                                        "cells": sel, "proved_optimal": exact}
                if dens < best[0] - 1e-12 or (abs(dens - best[0]) < 1e-12 and n < best[1]["index"]):
                    best = (dens, {"index": n, "lattice": L, "cells": sel, "count": m})
            out[f"{v}_k{k}"] = {"max_index": N,
                                "best_by_index": {str(n): best_by_index[n] for n in sorted(best_by_index)},
                                "best": {"density": best[0], **best[1]}}
            print(f"  blocking {v} k={k}: best density {best[0]:.4f} at index {best[1]['index']}",
                  flush=True)
    return out


# ─── tiling draw certificates ────────────────────────────────────────────────

def tiling_milp(args):
    """Feasibility of a Λ-periodic family of disjoint collinear m-tiles (m=2 pairs, m=3
    triples) such that every k-window in direction u wholly contains a u-tile."""
    from scipy.optimize import Bounds, LinearConstraint, milp
    (a, b, c), k, variant, m, contiguous, tlim = args
    n = a * c
    red = reducer(a, b, c)
    dirs = DIRS[variant]
    if contiguous:
        shapes = [tuple(range(m))]
    else:
        shapes = [(0,) + s for s in itertools.combinations(range(1, k), m - 1)]
    tiles, index, meta = [], {}, []
    for x in range(a):
        for y in range(c):
            for di, d in enumerate(dirs):
                for sh in shapes:
                    cells = [red(x + o * d[0], y + o * d[1]) for o in sh]
                    if len(set(cells)) < m:
                        continue
                    index[(red(x, y), di, sh)] = len(tiles)
                    tiles.append(cells)
                    meta.append({"start": red(x, y), "dir": di, "shape": list(sh)})
    if not tiles:
        return (a, b, c), False, None
    T = len(tiles)
    cover = np.zeros((n, T))
    for j, cells in enumerate(tiles):
        cover[cells, j] = 1
    rows = []
    for x in range(a):
        for y in range(c):
            for di, d in enumerate(dirs):
                row = np.zeros(T)
                for t in range(k):
                    s = red(x + t * d[0], y + t * d[1])
                    for sh in shapes:
                        if t + sh[-1] <= k - 1 and (s, di, sh) in index:
                            row[index[(s, di, sh)]] = 1
                rows.append(row)
    cons = [LinearConstraint(cover, 0, 1), LinearConstraint(np.array(rows), 1, np.inf)]
    res = milp(np.zeros(T), constraints=cons, integrality=np.ones(T), bounds=Bounds(0, 1),
               options={"time_limit": tlim})
    if res.status != 0 or res.x is None:
        return (a, b, c), False, None
    chosen = [meta[j] for j in range(T) if res.x[j] > 0.5]
    return (a, b, c), True, chosen


def tile_instances(L, tiles, variant, region):
    """Unfold the periodic tile classes into plane tiles whose start lies in region."""
    red = reducer(*L)
    dirs = DIRS[variant]
    starts = {}
    for t in tiles:
        starts.setdefault(t["start"], []).append(t)
    out = []
    for s0 in region:
        for t in starts.get(red(*s0), []):
            d = dirs[t["dir"]]
            out.append((t["dir"], tuple((s0[0] + o * d[0], s0[1] + o * d[1]) for o in t["shape"])))
    return out


def verify_tiling(L, tiles, k, variant, inner_radius=12):
    """Independent plane check: tiles disjoint, and every k-window starting within
    inner_radius, of every direction, wholly contains a tile of that direction.
    Corner directions have hex length 2, so a window spans up to 2k cells of distance."""
    R = inner_radius + 2 * k + 2
    region = hex_disc(R)
    inst = tile_instances(L, tiles, variant, region)
    owner = Counter(c for _, cells in inst for c in cells)
    disjoint = max(owner.values()) == 1
    by_dir_cells = {}
    for di, cells in inst:
        by_dir_cells.setdefault(di, set()).add(cells)
    inner = hex_disc(inner_radius)
    bad = 0
    for c in inner:
        for di, d in enumerate(DIRS[variant]):
            win = [(c[0] + i * d[0], c[1] + i * d[1]) for i in range(k)]
            pos = {x: i for i, x in enumerate(win)}
            if not any(all(x in pos for x in cells) for cells in by_dir_cells.get(di, ())
                       if cells[0] in pos):
                bad += 1
    return {"disjoint": disjoint, "uncovered_windows": bad, "windows_checked": len(inner) * len(DIRS[variant])}


def tiling_lower_bound(m, variant):
    """Disjoint u-tiles of span >= m on every u-line, one inside every k-window:
    per-line tile-cell density >= m/(k-m+1); summing over directions must be <= 1."""
    D = len(DIRS[variant])
    k = m
    while D * m / (k - m + 1) > 1:
        k += 1
    return k


def first_feasible_tiling(k, variant, m, max_index, pool, partition):
    """Contiguous tiles only. At the density threshold (partition=True) this is no loss:
    equality in the counting bound forces span = m and a perfect partition, so m | index."""
    for n in range(1, max_index + 1):
        if partition and n % m:
            continue
        jobs = [(L, k, variant, m, True, 30.0) for L in hnf_lattices(n)]
        for L, ok, chosen in pool.map(tiling_milp, jobs, chunksize=1):
            if ok:
                return {"k": k, "lattice": L, "index": n, "tiles": chosen}
    return None


def run_tilings(quick, pool):
    out = {}
    plan = [("pair", 2, "R3"), ("triple", 3, "R3"), ("pair", 2, "R6"), ("triple", 3, "R6")]
    for name, m, v in plan:
        lb = tiling_lower_bound(m, v)
        max_index = 45 if quick else 90
        found = None
        for k in range(lb, lb + 4):
            found = first_feasible_tiling(k, v, m, max_index, pool, partition=(k == lb))
            if found:
                break
        if found:
            found["verified"] = verify_tiling(tuple(found["lattice"]), found["tiles"], found["k"], v)
        out[f"{name}_{v}"] = {"lower_bound_k": lb, "found": found, "max_index": max_index}
        print(f"  tiling {name} {v}: lower bound k>={lb}, "
              f"periodic certificate at k={found['k'] if found else None}"
              f" {found['verified'] if found else ''}", flush=True)
    return out


# ─── rank ladder and moonshine ───────────────────────────────────────────────

def eis_norm(a, b):
    return a * a - a * b + b * b


def run_ladder(quick):
    out = {}
    # rank 1: A2 = Z[ω]; minimal vectors are the six units = the R3 win directions
    units = [(a, b) for a in range(-2, 3) for b in range(-2, 3) if eis_norm(a, b) == 1]
    out["A2_min_vectors"] = units

    # rank 4: Construction A over Z[ω] from the tetracode mod θ = 1-ω (Z[ω]/θ = F3)
    tetra = {((x) % 3, y % 3, (x + y) % 3, (x + 2 * y) % 3) for x in range(3) for y in range(3)}
    M = 9
    elems = [(a, b) for a in range(-4, 5) for b in range(-4, 5) if eis_norm(a, b) <= M]
    by_norm_res = {}
    for a, b in elems:
        by_norm_res.setdefault(((a + b) % 3), []).append(eis_norm(a, b))
    shells = Counter()
    for word in tetra:
        lists = [by_norm_res[s] for s in word]
        for combo in itertools.product(*lists):
            t = sum(combo)
            if 0 < t <= M:
                shells[t] += 1
    out["E8_eisenstein_shells"] = {str(k): v for k, v in sorted(shells.items())}

    # rank 12: the extended ternary Golay code (mod θ data of the complex Leech lattice)
    A = [[0, 1, 1, 1, 1, 1], [1, 0, 1, 2, 2, 1], [1, 1, 0, 1, 2, 2],
         [1, 2, 1, 0, 1, 2], [1, 2, 2, 1, 0, 1], [1, 1, 2, 2, 1, 0]]
    G = [[1 if i == j else 0 for j in range(6)] + A[i] for i in range(6)]
    we = Counter()
    for coeffs in itertools.product(range(3), repeat=6):
        word = [sum(coeffs[i] * G[i][j] for i in range(6)) % 3 for j in range(12)]
        we[sum(1 for x in word if x)] += 1
    out["ternary_golay_weight_enumerator"] = {str(k): v for k, v in sorted(we.items())}

    # moonshine at 3B, from hexagonal lattice theta series alone
    N = 24 if quick else 40
    a_ser = [0] * (N + 1)        # θ_A2 = Σ q^{|x|²}
    c_ser = [0] * (N + 1)        # θ of A2 shifted to a deep hole, divided by q^{1/3}
    rng_ = range(-N - 2, N + 3)
    for m in rng_:
        for n in rng_:
            e = m * m + m * n + n * n
            if e <= N:
                a_ser[e] += 1
            e2 = e + m + n
            if 0 <= e2 <= N:
                c_ser[e2] += 1
    out["theta_A2"] = a_ser[:16]
    out["theta_hole_over_q13"] = c_ser[:16]
    # T = 27 (a/c)^3 - 15 with c = q^{1/3} c̃  ⇒  (a/c)^3 = q^{-1} (a/c̃)^3

    def mul(x, y):
        r = [0] * (N + 1)
        for i, xi in enumerate(x):
            if xi:
                for j in range(N + 1 - i):
                    r[i + j] += xi * y[j]
        return r

    def inv(x):
        from fractions import Fraction
        r = [Fraction(0)] * (N + 1)
        r[0] = Fraction(1, x[0])
        for k in range(1, N + 1):
            r[k] = -sum(x[i] * r[k - i] for i in range(1, k + 1)) / x[0]
        return r
    ratio = mul(a_ser, inv(c_ser))
    cube = mul(mul(ratio, ratio), ratio)
    T_theta = [27 * v for v in cube]          # coefficients of q^{-1}, q^0, q^1, ...
    T_theta[1] -= 15
    # direct η-quotient: (η(τ)/η(3τ))^12 + 12 = q^{-1} Π(1-q^n)^12/(1-q^{3n})^12 + 12
    pq = [1] + [0] * N
    for nn in range(1, N + 1):
        new = pq[:]
        for i in range(nn, N + 1):
            new[i] -= pq[i - nn]
        pq = new
    p3 = [0] * (N + 1)
    for i, v in enumerate(pq):
        if 3 * i <= N:
            p3[3 * i] = v
    base = mul(pq, inv(p3))
    eta = [1] + [0] * N
    for _ in range(12):
        eta = mul(eta, base)
    T_eta = list(eta)
    T_eta[1] += 12
    out["T3B_from_hex_thetas"] = [int(x) for x in T_theta[:14]]
    out["T3B_from_eta"] = [int(x) for x in T_eta[:14]]
    out["T3B_agree_to_order"] = next((i for i in range(N + 1) if T_theta[i] != T_eta[i]), N + 1) - 1
    out["note"] = ("index 0 is the q^-1 coefficient. Monster: chi_196883(3B) = 53, so the "
                   "q^1 coefficient should be 1 + 53 = 54.")
    return out


# ─── rules audit ─────────────────────────────────────────────────────────────

def run_rules(n=2000):
    sys.path.insert(0, str(ROOT / "competition"))
    from arena import check_win
    rng = random.Random(1)
    out = Counter()
    for _ in range(n):
        base = (rng.randint(-10**6, 10**6), rng.randint(-10**6, 10**6))
        for name, dirs in (("axis", AXIS3), ("vertex", VERTEX3)):
            d = rng.choice(dirs)
            cells = [(base[0] + i * d[0], base[1] + i * d[1]) for i in range(6)]
            stones = {c: 1 for c in cells}
            last = rng.choice(cells)
            out[f"{name}_win_detected"] += bool(check_win(stones, *last, 1))
        d = rng.choice(AXIS3)
        cells = [(base[0] + i * d[0], base[1] + i * d[1]) for i in range(7) if i != 3]
        out["gapped_axis_win_detected"] += bool(check_win({c: 1 for c in cells}, *cells[0], 1))
    return {"trials": n, **dict(out)}


# ─── figures ─────────────────────────────────────────────────────────────────

INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
BLUE, ORANGE, AQUA, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#6250d6", "#e34948"
SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CELL_FILL, CELL_EDGE = "#f0efec", "#d6d5cf"
S3 = math.sqrt(3)


def _style():
    import matplotlib as mpl
    mpl.rcParams.update({
        "font.family": "DejaVu Serif", "mathtext.fontset": "dejavuserif",
        "font.size": 9, "axes.titlesize": 10.5, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "axes.labelcolor": INK2, "axes.edgecolor": "#c3c2b7",
        "xtick.color": MUTED, "ytick.color": MUTED, "text.color": INK,
        "axes.facecolor": SURF, "figure.facecolor": SURF, "savefig.facecolor": SURF,
        "axes.spines.top": False, "axes.spines.right": False, "axes.grid": False,
        "grid.color": GRID, "grid.linewidth": 0.6, "legend.frameon": False,
    })


def xy(c):
    q, r = c
    return (q + r / 2, r * S3 / 2)


def draw_cells(ax, cells, fill=CELL_FILL, edge=CELL_EDGE, colors=None, lw=0.6, z=1):
    from matplotlib.patches import RegularPolygon
    colors = colors or {}
    for c in cells:
        ax.add_patch(RegularPolygon(xy(c), 6, radius=1 / S3, orientation=0,
                                    facecolor=colors.get(c, fill), edgecolor=edge, lw=lw, zorder=z))


def draw_stones(ax, cells, color, z=4, size=0.36, edge=None):
    from matplotlib.patches import Circle
    for c in cells:
        ax.add_patch(Circle(xy(c), size, facecolor=color, edgecolor=edge or color,
                            lw=1.0, zorder=z))


def line_through(ax, cells, color, lw=2.2, ls="-", z=5, alpha=1.0):
    pts = np.array([xy(c) for c in cells])
    ax.plot(pts[:, 0], pts[:, 1], color=color, lw=lw, ls=ls, zorder=z, alpha=alpha,
            solid_capstyle="round")


def finish_board(ax, cells, pad=0.8):
    pts = np.array([xy(c) for c in cells])
    ax.set_xlim(pts[:, 0].min() - pad, pts[:, 0].max() + pad)
    ax.set_ylim(pts[:, 1].min() - pad, pts[:, 1].max() + pad)
    ax.set_aspect("equal")
    ax.axis("off")


def torus_patch(a, b, c, reps=None):
    """Representatives of Z²/Λ laid out as the parallelogram a×c with shear b."""
    return [(x, y) for x in range(a) for y in range(c)]


def periodic_cells(L, sel, region):
    red = reducer(*L)
    sel = set(sel)
    return [c for c in region if red(*c) in sel]


def fig_rules(d):
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 6.0), gridspec_kw={"wspace": 0.08})
    region = hex_disc(7)
    # A: what wins
    ax = axes[0]
    draw_cells(ax, region)
    wins = [((-6, 2), (1, 0)), ((2, -6), (0, 1)), ((-2, 6), (1, -1))]
    for start, d_ in wins:
        cells = [(start[0] + i * d_[0], start[1] + i * d_[1]) for i in range(6)]
        line_through(ax, cells, BLUE, lw=3.2, z=3, alpha=0.35)
        draw_stones(ax, cells, "#1f1f1e")
    ax.plot(*xy((0, 0)), marker="+", ms=11, mew=1.6, color=RED, zorder=6)
    ax.annotate("origin: plays no role", xy((0, 0)), xytext=xy((-6, -1)), color=INK2,
                fontsize=8.5, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_title("A  Wins under the rule (R3)")
    ax.text(0.0, -0.02, "Six adjacent stones along any of the three axes, anywhere.\n"
            "Every line is parallel to a unit of $\\mathbb{Z}[\\omega]$; none needs the origin.",
            transform=ax.transAxes, color=INK2, fontsize=8.5, va="top")
    finish_board(ax, region)
    # B: what doesn't
    ax = axes[1]
    draw_cells(ax, region)
    vert = [(-5 + i, -2 + i) for i in range(6)]              # direction (1,1)
    line_through(ax, vert, ORANGE, lw=1.8, ls=(0, (3, 2)), z=3)
    draw_stones(ax, vert, "#1f1f1e")
    bent = [(1, -6), (2, -6), (3, -6), (3, -5), (3, -4), (3, -3)]
    draw_stones(ax, bent, "#1f1f1e")
    line_through(ax, bent, MUTED, lw=1.4, z=3)
    gap = [(-4 + i, 6) for i in range(7) if i != 3]
    draw_stones(ax, gap, "#1f1f1e")
    draw_cells(ax, [(-1, 6)], colors={(-1, 6): "#ffffff"}, edge=RED, lw=1.4, z=2)
    ax.text(*xy((-7, 1)), "corner-to-corner\n(a win only\nunder R6)", color=ORANGE,
            fontsize=8.5, ha="right", va="center", fontweight="bold")
    ax.text(*xy((4, -4)), "bent", color=INK2, fontsize=8.5, ha="left", va="center")
    ax.text(*xy((-1, 7)), "gap", color=INK2, fontsize=8.5, ha="center", va="bottom")
    r = d["rules"]
    ax.text(0.0, -0.02,
            f"Audit of arena.py check_win, random positions up to 10⁶ from the origin:\n"
            f"axis sixes {r['axis_win_detected']}/{r['trials']} detected, corner sixes {r['vertex_win_detected']}/{r['trials']}, "
            f"gapped {r['gapped_axis_win_detected']}/{r['trials']}.",
            transform=ax.transAxes, color=INK2, fontsize=8.5, va="top")
    ax.set_title("B  Not wins under R3")
    finish_board(ax, region, pad=2.2)
    return fig


def fig_symmetry(d):
    import matplotlib.pyplot as plt
    s = d["symmetry"]
    orders = [12, 6, 4, 3, 2, 1]
    fig, ax = plt.subplots(figsize=(8.4, 3.4))
    plies = [1, 2, 3, 4, 5]
    seq = {12: SEQ[6], 6: SEQ[5], 4: SEQ[4], 3: SEQ[3], 2: SEQ[2], 1: SEQ[0]}
    for i, p in enumerate(plies):
        cnt = {int(k): v for k, v in s[f"ply{p}"].items()}
        tot = sum(cnt.values())
        left = 0.0
        for o in orders:
            w = cnt.get(o, 0) / tot
            if w <= 0:
                continue
            ax.barh(i, w, left=left, height=0.62, color=seq[o], edgecolor=SURF, lw=2)
            if w > 0.06:
                ax.text(left + w / 2, i, f"|Stab|={o}\n{100 * w:.1f}%" if w > 0.16 else f"{o}",
                        ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if o >= 3 else INK)
            left += w
    stones = {1: "1 stone", 2: "3 stones", 3: "5 stones", 4: "7 stones", 5: "9 stones"}
    ax.set_yticks(range(len(plies)), [f"after turn {p}\n({stones[p]})" for p in plies], color=INK2)
    ax.invert_yaxis()
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0", "25%", "50%", "75%", "100%"])
    ax.set_xlabel(f"share of positions (stones in a radius-{s['radius']} disc), by order of stabiliser in p6m")
    ax.set_title("Symmetry is spent immediately: the stabiliser in p6m = $\\mathbb{Z}[\\omega]\\rtimes D_6$ collapses to 1")
    fig.tight_layout()
    return fig


def _torus_draw(ax, n, perm, title, conflict=None, color=BLUE):
    cells = [(q, r) for q in range(n) for r in range(n)]
    colors = {}
    if conflict is not None:
        for (q, r) in cells:
            if (q + r) % n == conflict["hit"]:
                colors[(q, r)] = "#f6d4d3"
            if (q + r) % n == conflict["miss"]:
                colors[(q, r)] = "#ffffff"
    draw_cells(ax, cells, colors=colors)
    stones = [(perm[r], r) for r in range(n)]
    for (q, r) in stones:
        for d_ in AXIS3:
            seg = [((q + t * d_[0]) % n, (r + t * d_[1]) % n) for t in range(n)]
            # draw only the unwrapped part inside the patch
            run = [(q + t * d_[0], r + t * d_[1]) for t in range(-n, n)]
            run = [c for c in run if 0 <= c[0] < n and 0 <= c[1] < n]
            line_through(ax, run, color, lw=1.1, z=2, alpha=0.45)
    draw_stones(ax, stones, "#1f1f1e")
    if conflict is not None:
        bad = [c for c in stones if (c[0] + c[1]) % n == conflict["hit"]]
        draw_stones(ax, bad, RED, size=0.36)
        empty = [c for c in cells if (c[0] + c[1]) % n == conflict["miss"]]
        draw_cells(ax, empty, colors={c: "#ffffff" for c in empty}, edge=RED, lw=1.0, z=1.5)
    ax.set_title(title)
    finish_board(ax, cells)


def fig_hall_paige(d):
    import matplotlib.pyplot as plt
    rk = d["rooks"]
    fig = plt.figure(figsize=(14.0, 5.0))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1.15, 1.3], wspace=0.22)
    ax = fig.add_subplot(gs[0])
    ex5 = next(r["example"] for r in rk["R3"] if r["n"] == 5)
    _torus_draw(ax, 5, ex5, "A  k = 5: perfect blocker exists")
    ax.text(0.0, -0.06, "5×5 torus: one stone on every line of\nall three directions. Tiled over the plane,\ndensity 1/5 hits every 5-window.",
            transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    ax = fig.add_subplot(gs[1])
    best, perm = rk["near_miss_n6_R3"]
    vals = Counter((perm[r] + r) % 6 for r in range(6))
    hit = next(v for v, c in vals.items() if c > 1)
    miss = next(v for v in range(6) if v not in vals)
    _torus_draw(ax, 6, perm, "B  k = 6: impossible (Hall–Paige)", conflict={"hit": hit, "miss": miss})
    ax.text(0.0, -0.06,
            "Best possible: rows and columns exact, but only\n5 of 6 anti-diagonals (red: clash, white: missed).\n"
            "Σ(q+r) = 2·(0+…+5) ≡ 0, but 0+…+5 ≡ 3 (mod 6).",
            transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    ax = fig.add_subplot(gs[2])
    for v, col, lab in (("R3", BLUE, "R3 hex rooks (the rule)"), ("R6", ORANGE, "R6 hex queens (+ corner lines)")):
        ns = [r["n"] for r in rk[v]]
        cs = [r["solutions"] for r in rk[v]]
        pos = [(n, c) for n, c in zip(ns, cs) if c > 0]
        zer = [n for n, c in zip(ns, cs) if c == 0]
        ax.plot([p[0] for p in pos], [p[1] for p in pos], "o", color=col, ms=7,
                mec=SURF, mew=1.5, label=lab, zorder=3)
        ax.plot([p[0] for p in pos], [p[1] for p in pos], color=col, lw=1, ls=(0, (1, 2)), zorder=2)
        ax.scatter(zer, [0.35 if v == "R3" else 0.6] * len(zer), marker="o", s=34, facecolor=SURF,
                   edgecolor=col, lw=1.4, zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(0.25, 3e6)
    ax.axvline(6, color=RED, lw=1, ls=(0, (2, 2)))
    ax.text(6.15, 3e3, "k = 6", color=RED, fontsize=8.5, va="center")
    ax.text(0.98, 0.12, "hollow markers on the floor = no solution", transform=ax.transAxes, ha="right",
            fontsize=8, color=INK2)
    ax.set_xlabel("torus size n (= win length k)")
    ax.set_ylabel("number of perfect placements")
    ax.set_xticks(range(1, max(r["n"] for r in rk["R6"]) + 1))
    ax.yaxis.grid(True)
    ax.legend(loc="upper left", fontsize=8.5, bbox_to_anchor=(0.0, 1.0))
    ax.text(0.03, 0.74, "R3 solvable ⇔ n odd\nR6 solvable ⇔ gcd(n, 30) = 1  (n ≤ %d)" %
            max(r["n"] for r in rk["R6"]), transform=ax.transAxes, fontsize=8.5, color=INK2)
    ax.set_title("C  Toroidal hex rooks (Pólya's queens on $\\mathbb{Z}[\\omega]$)")
    return fig


def fig_blocking(d):
    import matplotlib.pyplot as plt
    lat, blk = d["lattices"], d["blocking"]
    fig = plt.figure(figsize=(12.4, 4.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.1, 1.25, 1.0], wspace=0.28)
    ax = fig.add_subplot(gs[0])
    ks = list(range(2, 17))
    ax.plot(ks, [1 / k for k in ks], color=MUTED, lw=1.2, ls=(0, (2, 2)), label="floor 1/k")
    for v, col, lab in (("R3", BLUE, "R3"), ("R6", ORANGE, "R6")):
        bi = lat[v]["best_index_for_k"]
        dens = [1 / bi[str(k)] if bi[str(k)] else 1.0 for k in ks]
        ax.step(ks, dens, where="mid", color=col, lw=2, label=f"best lattice blocker, {lab}")
    ax.axvline(6, color=RED, lw=1, ls=(0, (2, 2)))
    ax.annotate("k=6: lattice gives 1/5,\nnot 1/6 (2 is inert)", (6, 0.2), (8.2, 0.5), fontsize=8,
                color=INK2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xlabel("win length k")
    ax.set_xticks(range(2, 17, 2))
    ax.text(2.2, 0.96, "R6: no lattice blocker\nuntil k = 7", fontsize=8, color=ORANGE, va="top")
    ax.set_ylabel("density of blocking set")
    ax.set_ylim(0, 1.05)
    ax.yaxis.grid(True)
    ax.legend(fontsize=8, loc="center right")
    ax.set_title("A  Sublattice blockers")
    ax = fig.add_subplot(gs[1])
    for v, col, mk in (("R3", BLUE, "o"), ("R6", ORANGE, "s")):
        b = blk[f"{v}_k6"]["best_by_index"]
        ns = sorted(int(n) for n in b)
        best_so_far, run = 9, []
        for n in ns:
            best_so_far = min(best_so_far, b[str(n)]["density"])
            run.append(best_so_far)
        ax.scatter(ns, [b[str(n)]["density"] for n in ns], s=14, color=col, alpha=0.35, marker=mk, lw=0)
        ax.step(ns, run, where="post", color=col, lw=2, label=f"{v}: best over all lattices of index ≤ N")
    ax.axhline(1 / 6, color=MUTED, lw=1.2, ls=(0, (2, 2)))
    ax.axhline(1 / 5, color=BLUE, lw=0.8, ls=(0, (1, 2)))
    ax.text(ns[-1], 1 / 6 - 0.006, "counting floor 1/6 — unattainable (Hall–Paige)", ha="right", va="top",
            fontsize=8, color=INK2)
    ax.text(ns[-1], 1 / 5 + 0.005, "1/5", ha="right", va="bottom", fontsize=8, color=BLUE)
    ax.set_ylim(0.15, 0.42)
    ax.set_xlabel("period index N = $[\\mathbb{Z}[\\omega]:\\Lambda]$")
    ax.set_ylabel("least density hitting every 6-window")
    ax.yaxis.grid(True)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_title("B  Exact MILP over every period lattice, k = 6")
    ax = fig.add_subplot(gs[2])
    best = blk["R3_k6"]["best"]
    region = hex_disc(6)
    draw_cells(ax, region)
    S = periodic_cells(tuple(best["lattice"]), best["cells"], region)
    draw_stones(ax, S, BLUE, size=0.33)
    ax.set_title(f"C  An optimal R3 blocker (density {best['count']}/{best['index']})")
    ax.text(0.0, -0.04, "Every six-cell window on all three axes\ncontains a blue cell.",
            transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    finish_board(ax, region)
    return fig


def fig_tilings(d):
    import matplotlib.pyplot as plt
    t = d["tilings"]
    fig = plt.figure(figsize=(15.0, 5.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1, 1.25], wspace=0.5)
    tile_cols = {0: BLUE, 1: ORANGE, 2: AQUA}

    def draw_tiling(ax, entry, m, title, R=5):
        region = hex_disc(R)
        draw_cells(ax, region)
        L = tuple(entry["lattice"])
        inst = tile_instances(L, entry["tiles"], "R3", hex_disc(R + 3))
        covered = set()
        for di, cells in inst:
            if all(x in region for x in cells):
                line_through(ax, cells, tile_cols[di], lw=7.5, z=3)
            covered.update(cells)
        draw_stones(ax, [c for c in region if c in covered], "#ffffff", size=0.16, edge=INK2)
        ax.set_title(title)
        finish_board(ax, region)

    ax = fig.add_subplot(gs[0])
    pr = t["pair_R3"]["found"]
    if pr:
        draw_tiling(ax, pr, 2, f"A  Pair tiling, 1-1 turns: k = {pr['k']}")
        ax.text(0.0, -0.04, "Breaker answers each stone with its partner.\nEvery 7-window holds a whole pair.",
                transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    ax = fig.add_subplot(gs[1])
    tr = t["triple_R3"]["found"]
    if tr:
        draw_tiling(ax, tr, 3, f"B  Triple tiling, 1-2-2 turns: k = {tr['k']}")
        ax.text(0.0, -0.04, "Every 11-window holds a whole triple. Maker's two\nstones touch ≤ 2 triples; Breaker's "
                "two stones spoil\nboth. Pairs fail here: Maker takes a whole pair.", transform=ax.transAxes, fontsize=8,
                color=INK2, va="top")
    ax = fig.add_subplot(gs[2])
    rows = [("pair_R3", "pairs, 1-1, R3"), ("triple_R3", "triples, 1-2-2, R3"),
            ("pair_R6", "pairs, 1-1, R6"), ("triple_R6", "triples, 1-2-2, R6")]
    for i, (key, lab) in enumerate(rows):
        e = t[key]
        col = BLUE if key.endswith("R3") else ORANGE
        lb = e["lower_bound_k"]
        f = e["found"]["k"] if e["found"] else None
        ax.plot([6, lb], [i, i], color=GRID, lw=6, solid_capstyle="butt", zorder=1)
        ax.scatter([lb], [i], s=60, facecolor=SURF, edgecolor=col, lw=1.6, zorder=3)
        if f:
            ax.scatter([f], [i], s=60, color=col, zorder=4)
            ax.text(f + 0.5, i, f"certificate at k={f}", va="center", fontsize=8, color=INK2)
        else:
            ax.text(lb + 0.5, i, f"none found (index ≤ {e['max_index']})", va="center", fontsize=8, color=INK2)
    ax.axvline(6, color=RED, lw=1.2)
    ax.text(6.3, -0.45, "HeXO, k = 6", color=RED, fontsize=8.5, va="center")
    ax.set_yticks(range(len(rows)), [r[1] for r in rows], color=INK2)
    ax.set_xlim(4, 27)
    ax.set_ylim(len(rows) - 0.5, -0.8)
    ax.set_xlabel("win length k\n(hollow: counting bound; filled: periodic tiling found)")
    ax.xaxis.grid(True)
    ax.set_title("C  How long must lines be for a tiling draw?")
    return fig


def fig_ladder(d):
    import matplotlib.pyplot as plt
    L = d["ladder"]
    fig = plt.figure(figsize=(14.0, 4.8))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.9, 1.1, 1.3], wspace=0.32)
    ax = fig.add_subplot(gs[0])
    region = hex_disc(2)
    draw_cells(ax, region)
    for (q, r) in [(q, r) for q in (-1, 0, 1) for r in (-1, 0, 1) if q * q + q * r + r * r == 1]:
        x, y = xy((q, r))
        ax.annotate("", (x * 0.92, y * 0.92), (0, 0),
                    arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=2, mutation_scale=12))
    draw_stones(ax, [(0, 0)], "#1f1f1e", size=0.2)
    ax.set_title("A  Rank 1: the board A₂ = $\\mathbb{Z}[\\omega]$")
    ax.text(0.0, -0.04, "Its 6 minimal vectors are the 6 units —\nexactly HeXO's win directions.",
            transform=ax.transAxes, fontsize=8, color=INK2, va="top")
    finish_board(ax, region, pad=0.5)
    ax = fig.add_subplot(gs[1])
    ranks = [1, 4, 12]
    kiss = [6, L["E8_eisenstein_shells"]["3"], 196560]
    names = ["A₂ (board)", "E₈ = tetracode\nover $\\mathbb{Z}[\\omega]^4$", "complex Leech\nover $\\mathbb{Z}[\\omega]^{12}$"]
    cols = [BLUE, BLUE, MUTED]
    ax.bar(range(3), kiss, color=cols, width=0.55, edgecolor=SURF, lw=2)
    ax.set_yscale("log")
    for i, k in enumerate(kiss):
        ax.text(i, k * 1.35, f"{k:,}", ha="center", fontsize=9, color=INK)
    ax.set_xticks(range(3), [f"rank {r}\n{n}" for r, n in zip(ranks, names)], fontsize=8, color=INK2)
    ax.set_ylabel("kissing number (minimal vectors)")
    ax.set_ylim(1, 1e9)
    g = L["ternary_golay_weight_enumerator"]
    ax.text(0.02, 0.97, "computed here (blue): A₂, E₈ shells " + "/".join(str(v) for v in L["E8_eisenstein_shells"].values())
            + f"\nternary Golay weights 1+{g['6']}y⁶+{g['9']}y⁹+{g['12']}y¹²  (Aut = 2·M₁₂)"
            "\nquoted (grey): Leech, Aut = 6·Suz ⊂ … ⊂ $\\mathbb{M}$ via Co₁",
            transform=ax.transAxes, fontsize=7.5, color=INK2, va="top", linespacing=1.5)
    ax.set_yticks([1, 10, 100, 1e3, 1e4, 1e5, 1e6])
    ax.set_title("B  The rank ladder over $\\mathbb{Z}[\\omega]$")
    ax = fig.add_subplot(gs[2])
    th, et = L["T3B_from_hex_thetas"], L["T3B_from_eta"]
    ex = list(range(-1, len(th) - 1))
    ax.axhline(0, color="#c3c2b7", lw=0.8)
    ax.vlines(ex, 0, th, color=BLUE, lw=2)
    ax.scatter(ex, th, s=28, color=BLUE, zorder=3, label="27 (θ_board / θ_holes)³ − 15")
    ax.scatter(ex, et, s=70, facecolor="none", edgecolor=ORANGE, lw=1.4, zorder=4,
               label="(η(τ)/η(3τ))¹² + 12   (Monster 3B)")
    ax.set_yscale("symlog", linthresh=100)
    ax.set_yticks([-1e5, -1e3, 0, 1e3, 1e5], ["−10⁵", "−10³", "0", "10³", "10⁵"])
    ax.annotate("54 = 1 + 53 = 1 + χ₁₉₆₈₈₃(3B)", (1, 54), (2.2, 2.2e4), fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.set_xlabel("power of q")
    ax.set_ylabel("coefficient (symlog)")
    ax.legend(fontsize=8, loc="lower left", bbox_to_anchor=(0.0, 0.08))
    ax.text(0.02, 0.97, f"identical through q$^{{{L['T3B_agree_to_order'] - 1}}}$", transform=ax.transAxes,
            ha="left", va="top", fontsize=8, color=INK2)
    ax.set_title("C  Where the board meets the Monster")
    return fig


def make_figures(data, quick):
    _style()
    import matplotlib.pyplot as plt
    FIGURES.mkdir(parents=True, exist_ok=True)
    suffix = "_quick" if quick else ""
    makers = {"rules": (fig_rules, ["rules"]), "symmetry": (fig_symmetry, ["symmetry"]),
              "hall_paige": (fig_hall_paige, ["rooks"]),
              "blocking": (fig_blocking, ["lattices", "blocking"]),
              "tilings": (fig_tilings, ["tilings"]), "ladder": (fig_ladder, ["ladder"])}
    paths = []
    for name, (fn, need) in makers.items():
        if not all(k in data for k in need):
            continue
        fig = fn(data)
        p = FIGURES / f"fig_eisenstein_{name}{suffix}.png"
        fig.savefig(p, dpi=200, bbox_inches="tight")
        plt.close(fig)
        paths.append(str(p))
    return paths


# ─── main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="rules,symmetry,rooks,lattices,blocking,tilings,ladder")
    ap.add_argument("--plot-only", action="store_true")
    args = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS / ("eisenstein_group_theory_quick.json" if args.quick
                          else "eisenstein_group_theory.json")
    data = json.loads(out_path.read_text()) if out_path.exists() else {}
    timings = data.get("wall_seconds", {})
    if args.plot_only:
        print("\n".join(make_figures(data, args.quick)))
        return
    with Pool() as pool:
        for sec in args.only.split(","):
            t = time.time()
            print(f"[{sec}]", flush=True)
            if sec == "rules":
                data[sec] = run_rules()
            elif sec == "symmetry":
                data[sec] = run_symmetry(args.quick)
            elif sec == "rooks":
                data[sec] = run_rooks(args.quick)
            elif sec == "lattices":
                data[sec] = run_lattices()
            elif sec == "blocking":
                data[sec] = run_blocking(args.quick, pool)
            elif sec == "tilings":
                data[sec] = run_tilings(args.quick, pool)
            elif sec == "ladder":
                data[sec] = run_ladder(args.quick)
            timings[sec] = round(time.time() - t, 1)
            print(f"  done in {timings[sec]}s", flush=True)
            data["wall_seconds"] = timings
            out_path.write_text(json.dumps(data, indent=1, default=str))
    data["config"] = {"quick": args.quick, "seed_rules": 1, "seed_symmetry": 0}
    out_path.write_text(json.dumps(data, indent=1, default=str))
    print("wrote", out_path)
    print("\n".join(make_figures(data, args.quick)))


if __name__ == "__main__":
    main()
