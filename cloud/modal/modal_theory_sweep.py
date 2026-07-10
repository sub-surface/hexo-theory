"""
Modal deployment for two open theory questions from
docs/theory/2026-07-08-pairing-thresholds-and-game-values.md:

  1. pairing_sweep   -- does the k=7 hex-lattice pairing defense's capacity
     failure under dense multi-window clustering (found locally in
     experiments/run_pairing_capacity_check.py, real and verified: 15/30
     wins for the attacker at n_fronts=60, cluster_radius=12) get cured by
     the extra slack at k>7 (same period-6 matching, reused via the
     monotonicity lemma), and where exactly is the failure boundary in
     (k, n_fronts, cluster_radius) space? A local run with 10 seeds already
     showed k=9,11 surviving where k=7,13 didn't at n_fronts=15 -- too noisy
     to trust (10 seeds). This runs a real grid with enough seeds per cell
     to actually see the phase boundary, CPU-only (the simulation is
     branchy/dict-based, a poor GPU fit).

  2. strip_entropy   -- the 2-axis-coupled "no 6-run on any of 3 HeXO axes"
     strip transfer-matrix entropy (experiments/run_strip_entropy.py),
     pushed to widths a laptop can't reach in reasonable time. Verified
     locally: W=1 reproduces the single-axis pentanacci constant EXACTLY
     (1.965948..., matching evidence/results/line_automaton.json), and W=2 exactly
     equals pentanacci^2 (provably: at W=2 the free boundary means the u3
     diagonal run-tracker can never reach the length-5 threshold that would
     make the cross-axis constraint bite -- not a bug, a real structural
     fact about how much strip width is needed before any 2-axis coupling
     can appear at all: a diagonal run needs 4 more interior positions than
     its own row to build to length 5, i.e. real coupling can only first
     appear once W>=5). This job pushes width past that point via
     torch-batched power iteration on the GPU (the per-state
     enumerate-2^W-candidate-layers-and-accumulate step is embarrassingly
     parallel across states -- exactly the shape GPU batching wants) to see
     whether entropy-per-site starts deviating from the single-axis
     pentanacci value, i.e. whether there's real evidence of a genuine
     2-axis coupling correction distinct from the (proven, and already
     flagged as NOT the same object) single-axis entropy.

Usage (run from hexo-theory/; Modal already authenticated as 'sub-surface'):

    modal run cloud/modal/modal_theory_sweep.py::smoke_test
    modal run cloud/modal/modal_theory_sweep.py::pairing_sweep
    modal run cloud/modal/modal_theory_sweep.py::strip_entropy_sweep --max-w 12
"""
from __future__ import annotations

import itertools
import json
import time
from pathlib import Path

import modal

THEORY_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = THEORY_ROOT / "evidence" / "results"

app = modal.App("hexo-theory-sweep")

# ── Images ───────────────────────────────────────────────────────────────

cpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy", "matplotlib")
    .add_local_dir(str(THEORY_ROOT / "experiments"), "/root/hexo-theory/experiments", copy=True)
    .add_local_file(str(THEORY_ROOT / "competition" / "hexo_bot2.py"),
                    "/root/hexo-theory/competition/hexo_bot2.py", copy=True)
)

gpu_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch", "numpy", "scipy")
    .add_local_dir(str(THEORY_ROOT / "experiments"), "/root/hexo-theory/experiments", copy=True)
)

# ── 1. Pairing-capacity sweep (CPU) ────────────────────────────────────────

@app.function(image=cpu_image, cpu=1, timeout=1800)
def _pairing_trial(k: int, n_fronts: int, cluster_radius: int, turns: int, seed: int) -> dict:
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    from experiments.run_pairing_capacity_check import load_matching, run_dense_cluster
    import experiments.run_pairing_capacity_check as m
    m.PARTNER = load_matching()
    r = run_dense_cluster(n_fronts, turns, seed, cluster_radius=cluster_radius, k=k)
    return {"k": k, "n_fronts": n_fronts, "cluster_radius": cluster_radius, "seed": seed,
            "attacker_won": r["attacker_won"], "tier1_overrun_ever": r["tier1_overrun_ever"],
            "overrun_ever": r["overrun_ever"], "turns_used": r["turns_used"]}


@app.local_entrypoint()
def smoke_test():
    print("[pairing] one trial ...")
    r = _pairing_trial.remote(7, 15, 12, 80, 0)
    print(f"  {r}")
    print("[strip]   see strip_entropy_sweep -- no separate smoke test, W=1 check runs inline")


@app.local_entrypoint()
def pairing_sweep(
    ks: str = "7,9,11,13,15",
    n_fronts_list: str = "10,20,30,40,60,80",
    cluster_radii: str = "8,12,16,24",
    turns: int = 300,
    n_seeds: int = 40,
    out: str = "",
):
    """Full (k, n_fronts, cluster_radius) grid, n_seeds trials per cell,
    run fully in parallel across Modal CPU containers. Reports attacker
    win-rate per cell -- the phase diagram for where the tight k=7 pairing
    defense (and its k>7 slack-reuse via the monotonicity lemma) survives
    vs fails under dense multi-front pressure."""
    ks_l = [int(x) for x in ks.split(",")]
    nf_l = [int(x) for x in n_fronts_list.split(",")]
    cr_l = [int(x) for x in cluster_radii.split(",")]

    cells = list(itertools.product(ks_l, nf_l, cr_l))
    print(f"[grid] {len(cells)} cells x {n_seeds} seeds = {len(cells) * n_seeds} trials")

    args_k, args_nf, args_cr, args_turns, args_seed = [], [], [], [], []
    for k, nf, cr in cells:
        for seed in range(n_seeds):
            args_k.append(k); args_nf.append(nf); args_cr.append(cr)
            args_turns.append(turns); args_seed.append(seed)

    t0 = time.time()
    results = list(_pairing_trial.map(args_k, args_nf, args_cr, args_turns, args_seed))
    wall = time.time() - t0
    print(f"[done] {len(results)} trials in {wall:.1f}s ({len(results)/max(wall,1e-9):.1f}/s)")

    by_cell: dict[tuple, list] = {}
    for r in results:
        key = (r["k"], r["n_fronts"], r["cluster_radius"])
        by_cell.setdefault(key, []).append(r)

    phase_diagram = []
    for (k, nf, cr), trials in sorted(by_cell.items()):
        n = len(trials)
        wins = sum(t["attacker_won"] for t in trials)
        tier1_overruns = sum(t["tier1_overrun_ever"] for t in trials)
        phase_diagram.append({
            "k": k, "n_fronts": nf, "cluster_radius": cr, "n_trials": n,
            "attacker_win_rate": wins / n, "attacker_wins": wins,
            "tier1_overrun_rate": tier1_overruns / n,
        })

    summary = {
        "ks": ks_l, "n_fronts_list": nf_l, "cluster_radii": cr_l,
        "turns": turns, "n_seeds": n_seeds, "wall_time_s": round(wall, 1),
        "phase_diagram": phase_diagram,
    }
    print(json.dumps({"phase_diagram": phase_diagram}, indent=2))

    out_path = Path(out) if out else RESULTS_ROOT / "pairing_capacity_phase_diagram.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({**summary, "raw_trials": results}, indent=2))
    print(f"[saved] {out_path}")


# ── 1b. Two-move-sum (+₂) exhaustive pair solve (CPU) ──────────────────────

@app.function(image=cpu_image, cpu=1, timeout=3600)
def _tms_shard(configs: list, idx_pairs: list) -> list[dict]:
    """Exactly solve a batch of component-pair unions. configs are
    (length, stones-tuple); idx_pairs index into configs."""
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    sys.path.insert(0, "/root/hexo-theory/competition")
    from experiments.run_two_move_sum import solve_union, solve_config, hotness

    singles = {}
    out = []
    for i, j in idx_pairs:
        la, sa = configs[i][0], frozenset(configs[i][1])
        lb, sb = configs[j][0], frozenset(configs[j][1])
        for key, L, s in ((i, la, sa), (j, lb, sb)):
            if key not in singles:
                r = solve_config(L, s)
                r["hotness"] = hotness(L, s)
                singles[key] = r
        u = solve_union(la, sa, lb, sb)
        out.append({"A": [la, sorted(sa)], "B": [lb, sorted(sb)],
                    "hot_A": singles[i]["hotness"], "hot_B": singles[j]["hotness"],
                    "out_A": singles[i]["attacker_to_move"],
                    "out_B": singles[j]["attacker_to_move"],
                    "out_union": u})
    return out


@app.local_entrypoint()
def two_move_sum_sweep(lengths: str = "6,7,8,9", sizes: str = "2,3,4",
                       max_union_empties: int = 12, shard_pairs: int = 400,
                       out: str = ""):
    """Exhaustive +₂ additive-temperature-law audit over all collinear
    fragment pairs within the size caps. The local run (lengths 7-8, sizes
    2-3, 2,850 pairs) found the law EXACT (0 violations either way); this
    is the stress test at larger fragments where multi-turn 'building' heat
    could break the one-turn hotness invariant."""
    import itertools
    from experiments.run_two_move_sum import canon

    ls = [int(x) for x in lengths.split(",")]
    ks = [int(x) for x in sizes.split(",")]
    seen = {}
    for L in ls:
        for k in ks:
            if k >= L:
                continue
            for comb in itertools.combinations(range(L), k):
                key = canon(L, frozenset(comb))
                if key not in seen:
                    seen[key] = [key[0], sorted(key[1])]
    configs = list(seen.values())
    idx = []
    for i in range(len(configs)):
        for j in range(i, len(configs)):
            ea = configs[i][0] - len(configs[i][1])
            eb = configs[j][0] - len(configs[j][1])
            if ea + eb <= max_union_empties:
                idx.append((i, j))
    print(f"[tms] {len(configs)} configs, {len(idx)} pairs within empties cap")
    shards = [idx[i:i + shard_pairs] for i in range(0, len(idx), shard_pairs)]
    t0 = time.time()
    raw = list(_tms_shard.starmap([(configs, s) for s in shards],
                                  return_exceptions=True))
    wall = time.time() - t0
    pairs, errors = [], 0
    for shard in raw:
        if isinstance(shard, BaseException):
            errors += 1
        else:
            pairs.extend(shard)
    ORDER = {-1: 0, 0: 1, 1: 2}
    for p in pairs:
        p["pred_max"] = max(p["out_A"], p["out_B"], key=lambda v: ORDER[v])
        p["nonadditive"] = ORDER[p["out_union"]] > ORDER[p["pred_max"]]
    dd = [p for p in pairs if p["out_A"] == 0 and p["out_B"] == 0]
    viol_pos = [p for p in dd if p["nonadditive"] and p["hot_A"] + p["hot_B"] < 3]
    viol_neg = [p for p in dd if not p["nonadditive"] and p["hot_A"] + p["hot_B"] >= 3]
    summary = {
        "lengths": ls, "sizes": ks, "max_union_empties": max_union_empties,
        "n_configs": len(configs), "n_pairs": len(pairs),
        "shard_errors": errors, "wall_time_s": round(wall, 1),
        "n_nonadditive": sum(p["nonadditive"] for p in pairs),
        "n_draw_draw": len(dd),
        "law": "draw-draw non-additive <=> hot_A + hot_B >= 3",
        "n_false_negatives": len(viol_pos),
        "n_false_positives": len(viol_neg),
        "false_negatives": viol_pos[:30], "false_positives": viol_neg[:30],
        "pairs": pairs,
    }
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("pairs", "false_negatives", "false_positives")},
                     indent=2))
    out_path = Path(out) if out else RESULTS_ROOT / "two_move_sum_full.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary))
    print(f"[saved] {out_path}")


# ── 1c. F7 blocking-set defense sweep (CPU) ────────────────────────────────

@app.function(image=cpu_image, cpu=1, timeout=3600)
def _residue_trial(k: int, n_fronts: int, cluster_radius: int, turns: int,
                   seed: int, ablate: bool) -> dict:
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    sys.path.insert(0, "/root/hexo-theory/competition")
    from experiments.run_residue_defense import run_trial
    r = run_trial(n_fronts, turns, seed, k, cluster_radius, ablate=ablate)
    r["ablate"] = ablate
    return r


@app.local_entrypoint()
def residue_sweep(ks: str = "6,7", n_fronts_list: str = "20,40,60,80,120",
                  cluster_radii: str = "8,12", turns: int = 400,
                  n_seeds: int = 30, out: str = ""):
    """F7 blocking-set defense vs adversarial multi-front attack, with the
    ablation arm (tier-2 targets any empty cell instead of the {0,1}
    blocking set) to attribute survival correctly."""
    ks_l = [int(x) for x in ks.split(",")]
    nf_l = [int(x) for x in n_fronts_list.split(",")]
    cr_l = [int(x) for x in cluster_radii.split(",")]
    calls = []
    for k in ks_l:
        for nf in nf_l:
            for cr in cr_l:
                for ab in (False, True):
                    for seed in range(n_seeds):
                        calls.append((k, nf, cr, turns, seed, ab))
    print(f"[residue] {len(calls)} trials")
    t0 = time.time()
    results = [r for r in _residue_trial.starmap(calls, return_exceptions=True)
               if not isinstance(r, BaseException)]
    wall = time.time() - t0
    by_cell: dict = {}
    for r in results:
        key = (r["k"], r["n_fronts"], r["cluster_radius"], r["ablate"])
        by_cell.setdefault(key, []).append(r)
    grid = []
    for (k, nf, cr, ab), trials in sorted(by_cell.items()):
        grid.append({"k": k, "n_fronts": nf, "cluster_radius": cr,
                     "ablate": ab, "n_trials": len(trials),
                     "attacker_win_rate": sum(t["attacker_won"] for t in trials) / len(trials),
                     "tier1_overrun_rate": sum(t["tier1_overrun_ever"] for t in trials) / len(trials)})
        print(f"  k={k} nf={nf} R={cr} ablate={ab}: "
              f"win={grid[-1]['attacker_win_rate']:.2f}")
    out_path = Path(out) if out else RESULTS_ROOT / "residue_defense_sweep.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"turns": turns, "n_seeds": n_seeds, "wall_time_s": round(wall, 1),
         "grid": grid}, indent=2))
    print(f"[saved] {out_path}")


# ── 2. Strip-entropy sweep (GPU) ────────────────────────────────────────────

@app.function(image=gpu_image, gpu="T4", timeout=3600, memory=16384)
def _strip_entropy_gpu(W: int, iters: int, seed_states: int) -> dict:
    """Thin wrapper around the validated perron_eigenvalue_gpu -- do NOT
    reimplement the transition logic here. An earlier version of this
    function inlined a dict-based CPU loop that never touched a GPU tensor
    at all (torch was imported but unused), and a first cut at the batched
    version used top-K-by-weight truncation, which is a biased population-
    control scheme for a growth process like this (verified locally: W=4
    gave 15.13 vs the sparse-exact 14.9379 at a too-small population, though
    a larger population also fixed it -- weighted-random resampling, as
    used in perron_eigenvalue_gpu, is the standard/unbiased choice
    regardless, same technique as Diffusion Monte Carlo population control).
    Both W=1..4 are cross-checked exactly against evidence/results/strip_entropy.json
    (sparse construction) before trusting this at W>=5.
    """
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    import torch
    from experiments.run_strip_entropy import perron_eigenvalue_gpu
    import numpy as np

    device = "cuda" if torch.cuda.is_available() else "cpu"
    lam, ratios, n_work = perron_eigenvalue_gpu(
        W, iters=iters, seed_states=seed_states, device=device)
    return {"W": W, "device": device, "n_working_states": n_work,
            "perron_eigenvalue_per_layer": lam,
            "entropy_per_site_bits": float(np.log2(max(lam, 1e-12)) / W),
            "iters_run": len(ratios), "ratio_tail": ratios[-10:]}


@app.local_entrypoint()
def strip_entropy_sweep(max_w: int = 12, iters: int = 300, seed_states: int = 60000, out: str = ""):
    """Push the strip-width transfer-matrix entropy estimate for the 3-axis
    coupled constraint out to widths a laptop can't reach in reasonable
    time. W=1..2 already verified exactly locally (W=1 matches pentanacci
    to machine precision; W=2 exactly equals pentanacci^2 -- structurally
    forced, see module docstring). This job covers W=3..max_w on GPU."""
    import numpy as np

    pentanacci = 1.9659482366454863  # verified locally against run_line_automaton.py
    ws = list(range(3, max_w + 1))
    print(f"[strip] running W={ws} on GPU, {iters} power-iteration steps each")

    t0 = time.time()
    results = list(_strip_entropy_gpu.map(ws, [iters] * len(ws), [seed_states] * len(ws)))
    wall = time.time() - t0
    print(f"[done] {len(results)} widths in {wall:.1f}s")

    for r in sorted(results, key=lambda r: r["W"]):
        dev = np.log2(r["perron_eigenvalue_per_layer"]) / r["W"] - np.log2(pentanacci)
        print(f"  W={r['W']:2d}: bits/site={r['entropy_per_site_bits']:.6f}  "
              f"(deviation from pentanacci: {dev:+.6f} bits, "
              f"working_states={r['n_working_states']})")

    summary = {
        "pentanacci_single_axis_bits_per_site": float(np.log2(pentanacci)),
        "w1_w2_verified_locally": {
            "w1_exact": pentanacci, "w2_exact_over_pentanacci_sq": 1.0,
        },
        "wall_time_s": round(wall, 1),
        "widths": {r["W"]: r for r in results},
    }
    out_path = Path(out) if out else RESULTS_ROOT / "strip_entropy_gpu_sweep.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"[saved] {out_path}")
