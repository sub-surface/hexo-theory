"""
Modal deployment for HeXO self-play corpus generation.

Built for the DIRECTION.md priority queue (2026-07-05): the Programme D
gzip-MDL proxy, P1/FMA statistics tightening, and the Bellman-Turing
long-horizon re-run all need more decisive self-play games than the local
machine can cheaply produce.

Two backends:

  "rust"   hexo's hexgo-rs pure-rollout MCTS (`parallel_self_play`), compiled
           fresh for Linux inside the image via maturin. Rayon-parallelizes
           internally across every core in ONE call -- no manual seed
           sharding needed within a shard. Uses NO trained net: hexo's
           checkpoint is currently *weaker* than its own greedy baseline
           (Elo ~1200 vs ~1753 in hexo/elo.json -- training regressed, not
           improved), so pure rollout evaluation is the honest choice, and it
           needs no checkpoint file at all. Caveat: hexgo-rs seeds its RNG
           via Rust's `thread_rng()` (OS entropy per thread) -- games are
           independent, not seed-reproducible. Fine for bulk corpus
           statistics; not for a "replay this exact game" claim.

  "python" the existing experiments/harness.py agent registry (ca_combo_v2,
           mirror, fork_aware, combo, ...). Needed whenever the *specific*
           agent behind an existing SPEC.md number matters -- e.g. tightening
           the P1 statistic is specifically about ca_combo_v2 self-play, and
           Rust has no equivalent of it. Sharded across containers with
           non-overlapping seed ranges (seed_base + shard_index * shard_size)
           -- this is the thing to get right; colliding seed ranges across
           shards would silently produce duplicate games (each game's RNG is
           fully determined by its seed, per experiments/harness.py::_play_one).

Both backends return raw per-game (winner, move_count) outcomes. Wilson CIs
and the gzip-MDL proxy are computed ONCE, locally, over the pooled results --
never per-shard-then-averaged, which would silently miscompute both the CI
and the mean length.

Usage (run from hexo-theory/; Modal already authenticated as 'sub-surface'):

    modal run modal_app.py::smoke_test
        # ~$0.01, a couple of games per backend. Verifies both backends
        # actually import and play before the real budget is spent. This
        # file has not been run yet -- do this first.

    modal run modal_app.py::corpus --backend rust --n-games 20000 --sims 64 --max-moves 480
    modal run modal_app.py::corpus --backend python --agent ca_combo_v2 --opponent ca_combo_v2 \\
        --n-games 2000 --max-moves 480 --seed-base 0

Cost/throughput are estimates until smoke_test (and a small real batch) have
actually run -- see DIRECTION.md's compute plan for the reasoning behind the
$30 budget split. Re-check `corpus`'s printed wall_time_s against that
estimate before committing to a large --n-games.
"""
from __future__ import annotations

import gzip
import json
import math
import time
from pathlib import Path

import modal

THEORY_ROOT = Path(__file__).resolve().parent
HEXO_ROOT = THEORY_ROOT.parent / "hexo"

app = modal.App("hexo-selfplay")

# ── Images ───────────────────────────────────────────────────────────────────

# Minimal on purpose: game.py and elo.py are stdlib-only (no torch, no net.py
# dependency -- checked directly, not assumed), so this stays a small, fast
# image. Don't add torch here; that's what makes this backend cheap.
python_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy")
    .add_local_dir(str(THEORY_ROOT / "engine"), "/root/hexo-theory/engine", copy=True)
    .add_local_file(str(THEORY_ROOT / "experiments" / "harness.py"),
                     "/root/hexo-theory/experiments/harness.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "experiments" / "__init__.py"),
                     "/root/hexo-theory/experiments/__init__.py", copy=True)
    .add_local_file(str(HEXO_ROOT / "game.py"), "/root/hexo/game.py", copy=True)
    .add_local_file(str(HEXO_ROOT / "elo.py"), "/root/hexo/elo.py", copy=True)
    .env({"HEXO_ROOT": "/root/hexo"})
)

# hexgo-rs source only (not target/ -- that's the stale Windows build; we
# compile fresh for Linux here, which fixes the staleness as a side effect).
rust_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "build-essential")
    .run_commands("curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y")
    .pip_install("maturin", "numpy")
    .add_local_dir(str(HEXO_ROOT / "hexgo-rs"), "/root/hexgo-rs", copy=True,
                    ignore=["target", ".git"])
    # maturin develop needs a virtualenv (absent in Modal images); build a
    # wheel and pip-install it instead
    .run_commands(". /root/.cargo/env && cd /root/hexgo-rs && maturin build --release"
                  " && pip install target/wheels/*.whl")
)

# ── Backends (one shard each; sharding/seed logic lives in `corpus` below) ──

@app.function(image=rust_image, cpu=8, timeout=3600)
def _play_shard_rust(n_games: int, sims: int, max_moves: int) -> list[tuple[int, int]]:
    """Rayon parallelizes n_games across every core of this container."""
    import hexgo
    results = hexgo.parallel_self_play(n_games, sims, 1.5, 0.2, max_moves)
    return [(int(r.winner or 0), int(r.num_moves)) for r in results]


@app.function(image=python_image, cpu=1, timeout=3600)
def _play_shard_python(agent: str, opponent: str, max_moves: int,
                        seeds: list[int]) -> list[tuple[int, int]]:
    """One game per seed -- seeds must be pre-assigned non-overlapping by the caller."""
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    from experiments.harness import _play_one
    return [_play_one((agent, opponent, max_moves, s)) for s in seeds]


@app.function(image=python_image, cpu=1, timeout=3600)
def _play_shard_python_moves(agent: str, opponent: str, max_moves: int,
                             seeds: list[int]) -> list[dict]:
    """Move-recording variant for the Programme D corpus (returns move seqs)."""
    import sys
    sys.path.insert(0, "/root/hexo-theory")
    from experiments.harness import _play_one_moves
    return [_play_one_moves((agent, opponent, max_moves, s)) for s in seeds]


@app.function(image=rust_image, cpu=8, timeout=3600)
def _play_shard_rust_moves(n_games: int, sims: int, max_moves: int) -> list[dict]:
    """Rust pure-rollout self-play returning full move sequences (GameResult.moves)."""
    import hexgo
    results = hexgo.parallel_self_play(n_games, sims, 1.5, 0.2, max_moves)
    return [{"winner": int(r.winner or 0),
             "moves": [[int(q), int(r_)] for (q, r_) in r.moves]} for r in results]


# ── Analysis (local, once, over the pooled outcomes from all shards) ───────

def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _mdl_proxy_bytes(outcomes: list[tuple[int, int]]) -> int:
    """Cheap Programme-D proxy: gzip length of the canonical outcome stream.
    Not the observer-net S_T from the roadmap -- a first log-vs-linear read
    without building that infrastructure. See DIRECTION.md priority queue #1."""
    blob = json.dumps(outcomes, separators=(",", ":")).encode()
    return len(gzip.compress(blob, compresslevel=9))


def _summarize(outcomes: list[tuple[int, int]], **meta) -> dict:
    n = len(outcomes)
    wins_b = sum(1 for w, _ in outcomes if w == 1)
    wins_w = sum(1 for w, _ in outcomes if w == 2)
    lens = [length for _, length in outcomes]
    decisive = wins_b + wins_w
    lo, hi = _wilson(wins_b, decisive)
    return {
        "n_games": n,
        "wins_black": wins_b,
        "wins_white": wins_w,
        "unfinished": n - decisive,
        "mean_length": sum(lens) / max(1, n),
        "black_share_decisive": wins_b / max(1, decisive),
        "ci_black_decisive_95": [lo, hi],
        "mdl_proxy_bytes": _mdl_proxy_bytes(outcomes),
        **meta,
    }


# ── Entry points ─────────────────────────────────────────────────────────────

@app.local_entrypoint()
def smoke_test():
    """~$0.01. Run this before anything else -- verifies both images build
    and both backends actually play games, before the real budget is spent."""
    print("[rust]   building image + playing 2 games (sims=16, this call also")
    print("         pays the one-time cargo/maturin build cost) ...")
    t0 = time.time()
    rust_out = _play_shard_rust.remote(2, 16, 60)
    print(f"  outcomes={rust_out}  ({time.time() - t0:.1f}s)")

    print("[python] playing 2 games of ca_combo_v2 self-play ...")
    t0 = time.time()
    py_out = _play_shard_python.remote("ca_combo_v2", "ca_combo_v2", 60, [0, 1])
    print(f"  outcomes={py_out}  ({time.time() - t0:.1f}s)")

    print("\nBoth backends returned outcomes -- safe to run `corpus` at scale.")
    print("Per-game timing here is dominated by cold-start/build cost, not")
    print("steady-state throughput -- run a `corpus` call with a modest")
    print("--n-games to get a real per-game estimate before committing budget.")


@app.local_entrypoint()
def corpus(
    backend: str = "rust",
    agent: str = "ca_combo_v2",
    opponent: str = "ca_combo_v2",
    n_games: int = 10_000,
    sims: int = 64,
    max_moves: int = 480,
    seed_base: int = 0,
    shard_size: int = 500,
    out: str = "",
):
    """Generate a self-play corpus, sharded across Modal containers.

    max_moves defaults to 480, not the repo's usual 240 -- Hamkins-echo data
    (results/hamkins_echo_combined.json) shows decisive share rising with
    horizon (0.74 at h=480 vs ~0.73 at h=240 for combo_vs_combo), so this
    default wastes fewer games as "unfinished" for the same spend.
    """
    n_shards = math.ceil(n_games / shard_size)
    shard_counts = [min(shard_size, n_games - i * shard_size) for i in range(n_shards)]
    t0 = time.time()

    if backend == "rust":
        shards = list(_play_shard_rust.map(
            shard_counts, [sims] * n_shards, [max_moves] * n_shards))
        agent_label = opponent_label = "rust_pure_mcts"
    elif backend == "python":
        seed_ranges, cursor = [], seed_base
        for count in shard_counts:
            seed_ranges.append(list(range(cursor, cursor + count)))
            cursor += count
        shards = list(_play_shard_python.map(
            [agent] * n_shards, [opponent] * n_shards, [max_moves] * n_shards, seed_ranges))
        agent_label, opponent_label = agent, opponent
    else:
        raise ValueError(f"unknown backend {backend!r} (use 'rust' or 'python')")

    outcomes = [pair for shard in shards for pair in shard]
    wall = time.time() - t0

    summary = _summarize(
        outcomes,
        backend=backend, agent=agent_label, opponent=opponent_label,
        sims=sims if backend == "rust" else None,
        max_moves=max_moves,
        seed_base=seed_base if backend == "python" else None,
        n_shards=n_shards, shard_size=shard_size,
        wall_time_s=round(wall, 1),
        games_per_sec=round(len(outcomes) / max(wall, 1e-9), 3),
    )
    print(json.dumps(summary, indent=2))

    out_path = Path(out) if out else THEORY_ROOT / "results" / f"modal_corpus_{backend}_{n_games}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({**summary, "raw_outcomes": outcomes}, indent=2))
    print(f"[saved] {out_path}")


@app.local_entrypoint()
def corpus_moves(
    backend: str = "python",
    agent: str = "ca_combo_v2",
    opponent: str = "ca_combo_v2",
    n_games: int = 10_000,
    sims: int = 64,
    max_moves: int = 480,
    seed_base: int = 0,
    shard_size: int = 250,
    out: str = "",
):
    """Programme D corpus: generate ONE move-sequence corpus, saved whole.

    The MDL scaling proxy (experiments/run_mdl_scaling.py) then compresses
    log-spaced *prefixes* of this single corpus locally -- no need for
    separate runs per N. Default backend is python/ca_combo_v2 because the
    Pisot S_T claim (ROADMAP Programme D, SPEC.md P3) is specifically about
    the combo agent's self-play, which the rust MCTS has no equivalent of.
    """
    n_shards = math.ceil(n_games / shard_size)
    shard_counts = [min(shard_size, n_games - i * shard_size) for i in range(n_shards)]
    t0 = time.time()

    if backend == "rust":
        games = [g for shard in _play_shard_rust_moves.map(
            shard_counts, [sims] * n_shards, [max_moves] * n_shards) for g in shard]
        agent_label = opponent_label = "rust_pure_mcts"
    elif backend == "python":
        seed_ranges, cursor = [], seed_base
        for count in shard_counts:
            seed_ranges.append(list(range(cursor, cursor + count)))
            cursor += count
        games = [g for shard in _play_shard_python_moves.map(
            [agent] * n_shards, [opponent] * n_shards,
            [max_moves] * n_shards, seed_ranges) for g in shard]
        agent_label, opponent_label = agent, opponent
    else:
        raise ValueError(f"unknown backend {backend!r} (use 'rust' or 'python')")

    wall = time.time() - t0
    outcomes = [(g["winner"], len(g["moves"])) for g in games]
    summary = _summarize(
        outcomes, backend=backend, agent=agent_label, opponent=opponent_label,
        sims=sims if backend == "rust" else None, max_moves=max_moves,
        seed_base=seed_base if backend == "python" else None,
        n_shards=n_shards, shard_size=shard_size,
        wall_time_s=round(wall, 1),
        games_per_sec=round(len(games) / max(wall, 1e-9), 3),
    )
    print(json.dumps(summary, indent=2))
    out_path = Path(out) if out else THEORY_ROOT / "results" / f"modal_moves_{backend}_{n_games}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({**summary, "games": games}, separators=(",", ":")))
    print(f"[saved] {out_path}  ({out_path.stat().st_size / 1e6:.1f} MB)")
