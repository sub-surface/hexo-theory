"""
Modal deployment for the search-regime bake-off (handoff doc §3, Phase 1).

Round-robin between the arena roster (competition/arena.py: existing ladder +
the 2026-07-05 handoff candidates) under a fixed per-move compute budget, with
seeded random openings. Openings are the load-bearing design decision: the
strong arena bots are deterministic, so without opening randomization every
strong-vs-strong pairing replays one canonical draw forever (2026-06-15 arena
finding, reconfirmed 2026-07-06). Each opening seed is played twice with
colours swapped, so per-opening comparisons are paired.

Unlike modal_app.py's rust backend, everything here is fully reproducible:
bots are deterministic and openings are seeded (arena.random_bot is a seeded
LCG, no OS entropy anywhere).

Wilson CIs are computed ONCE, locally, over pooled per-pairing outcomes --
never per-shard-then-averaged (same warning as modal_app.py).

Usage (from hexo-theory/; Modal already authenticated as 'sub-surface'):

    modal run modal_bakeoff.py::smoke_test
        # ~$0.01: one pairing, 2 openings, verifies image + arena import.

    modal run modal_bakeoff.py::screen --openings 25 --budget-s 1.0
        # Phase 1: full roster round-robin, 25 openings x 2 colours per
        # pairing (21 pairings x 50 games = 1050 games). Estimated from local
        # timing (~5-30 s/game on one core): roughly 2-9 core-hours ~ $0.10-
        # $0.45. Re-check the printed wall_time_s before scaling up.

    modal run modal_bakeoff.py::screen --openings 100 --bots fast_tactical,fork_aware_d1.2,heuristic_d1.1
        # Phase 2: survivors only, more games.
"""
from __future__ import annotations

import itertools
import json
import math
import time
from pathlib import Path

import modal

THEORY_ROOT = Path(__file__).resolve().parent
RAMORA_ROOT = THEORY_ROOT / "papers" / "misc" / "hexbot-building-framework" / "opponents"

app = modal.App("hexo-bakeoff")

# Always includes competition/external_bots.py + the vendored SealBot port
# (opponents.ramora, pure stdlib, no build step -- cheap to always mount)
# so "sealbot" and "hexo_bot_standalone" (the actual file handed to the
# opponent's team) are ordinary names in the SAME roster as every Python
# bot, no separate bespoke script needed. deep_minimax_rust is deliberately
# NOT in this image (it needs the compiled hexgo wheel, a real build step)
# -- see modal_rust_bot.py / modal_images.py for that one.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy")
    .add_local_file(str(THEORY_ROOT / "competition" / "arena.py"),
                    "/root/competition/arena.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "competition" / "external_bots.py"),
                    "/root/competition/external_bots.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "competition" / "hexo_bot.py"),
                    "/root/competition/hexo_bot.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "competition" / "hexo_bot2.py"),
                    "/root/competition/hexo_bot2.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "experiments" / "run_residue_defense.py"),
                    "/root/experiments/run_residue_defense.py", copy=True)
    .add_local_dir(str(RAMORA_ROOT), "/root/opponents", copy=True,
                    ignore=["__pycache__", ".git"])
)


@app.function(image=image, cpu=1, timeout=3600)
def _play_pairing_shard(name_a: str, name_b: str, opening_seeds: list[int],
                        budget_s: float, max_moves: int,
                        opening_placements: int) -> list[dict]:
    """Each opening seed -> two games (colours swapped). Returns raw outcomes."""
    import sys
    sys.path.insert(0, "/root/competition")
    sys.path.insert(0, "/root")
    import arena
    import external_bots

    roster = arena.bot_registry()
    roster.update(external_bots.external_bot_registry(include_rust=False))
    bot_a, bot_b = roster[name_a], roster[name_b]
    out = []
    # Wall-clock safety net, well under this function's 3600s timeout:
    # arena.play_game's budget_s only forfeits a slow MOVE after the fact
    # (measured, not preemptive) -- it can't stop a single bot() call from
    # itself taking a long time before that check even fires. External
    # engines with their own (possibly coarse) internal time-checking, e.g.
    # SealBot's MinimaxBot, are exactly the risk here: one such call already
    # ran a game to 1800s and hit a Modal function timeout, which (with the
    # default return_exceptions=False on .starmap()) cancelled every OTHER
    # in-flight shard too. Bailing out of remaining games in THIS shard and
    # returning partial results is strictly better than risking that again.
    shard_deadline = time.time() + 3000.0
    for seed in opening_seeds:
        for a_is_black in (True, False):
            if time.time() > shard_deadline:
                return out
            b1, b2 = (bot_a, bot_b) if a_is_black else (bot_b, bot_a)
            t0 = time.time()
            w, n_stones = arena.play_game(
                b1, b2, budget_s=budget_s, max_moves=max_moves,
                opening_seed=seed, opening_placements=opening_placements,
                return_stats=True)
            a_won = (w == 1) == a_is_black and w != 0
            out.append({"seed": seed, "a_black": a_is_black, "winner_raw": w,
                        "result": "a" if (w != 0 and a_won) else ("b" if w != 0 else "draw"),
                        "n_stones": n_stones,
                        "game_s": round(time.time() - t0, 2)})
    return out


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _run(bot_names: list[str], openings: int, budget_s: float,
         max_moves: int, seed_base: int, shard_openings: int, out: str,
         opening_placements: int) -> None:
    pairings = list(itertools.combinations(bot_names, 2))
    calls, keys = [], []
    for a, b in pairings:
        seeds = list(range(seed_base, seed_base + openings))
        for i in range(0, len(seeds), shard_openings):
            calls.append((a, b, seeds[i:i + shard_openings], budget_s, max_moves,
                          opening_placements))
            keys.append((a, b))
    t0 = time.time()
    # return_exceptions=True: one hung/errored shard (an external engine
    # like SealBot with its own, possibly coarse, internal time-checking
    # is the realistic risk) must not cancel every other in-flight shard --
    # the default return_exceptions=False did exactly that on 2026-07-08.
    raw_shards = list(_play_pairing_shard.starmap(calls, return_exceptions=True))
    wall = time.time() - t0

    shards, shard_errors = [], 0
    for key, shard in zip(keys, raw_shards):
        if isinstance(shard, BaseException):
            shard_errors += 1
            print(f"[error] shard for {key} raised: {shard!r}")
            shards.append([])
        else:
            shards.append(shard)
    if shard_errors:
        print(f"[warn] {shard_errors}/{len(raw_shards)} shards errored -- results below are partial")

    # pool once, per pairing, then compute CIs over the pooled outcomes
    pooled: dict[tuple, list[dict]] = {}
    for key, shard in zip(keys, shards):
        pooled.setdefault(key, []).extend(shard)
    table, wins_total = [], {n: 0 for n in bot_names}
    for (a, b), games in pooled.items():
        aw = sum(1 for g in games if g["result"] == "a")
        bw = sum(1 for g in games if g["result"] == "b")
        dr = len(games) - aw - bw
        dec = aw + bw
        lo, hi = _wilson(aw, dec)
        wins_total[a] += aw
        wins_total[b] += bw
        table.append({"a": a, "b": b, "a_wins": aw, "b_wins": bw, "draws": dr,
                      "a_share_decisive": (aw / dec) if dec else None,
                      "wilson95": [round(lo, 3), round(hi, 3)] if dec else None,
                      "mean_game_s": round(sum(g["game_s"] for g in games) / len(games), 2)})
        print(f"{a:>18} vs {b:<18} {aw}-{bw} ({dr}d)  "
              + (f"CI[{lo:.2f},{hi:.2f}]" if dec else "no decisive games"))
    print("\nLeaderboard (pooled decisive wins):")
    for n, w in sorted(wins_total.items(), key=lambda kv: -kv[1]):
        print(f"  {w:>4}  {n}")

    summary = {"bots": bot_names, "openings": openings, "budget_s": budget_s,
               "max_moves": max_moves, "seed_base": seed_base,
               "opening_placements": opening_placements,
               "n_games": sum(len(g) for g in pooled.values()),
               "wall_time_s": round(wall, 1), "wins_total": wins_total,
               "pairings": table}
    out_path = Path(out) if out else THEORY_ROOT / "results" / "modal_bakeoff_screen.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {**summary, "raw": {f"{a}|{b}": g for (a, b), g in pooled.items()}}, indent=2))
    print(f"\n[saved] {out_path}  (wall {wall:.0f}s)")


@app.local_entrypoint()
def smoke_test():
    """~$0.01: one pairing, 2 openings -- verifies the image and arena import."""
    _run(["fast_tactical", "heuristic_d1.1"], openings=2, budget_s=1.0,
         max_moves=400, seed_base=0, shard_openings=2,
         out=str(THEORY_ROOT / "results" / "modal_bakeoff_smoke.json"),
         opening_placements=16)


@app.local_entrypoint()
def screen(openings: int = 25, budget_s: float = 1.0, max_moves: int = 400,
           seed_base: int = 0, shard_openings: int = 5, bots: str = "", out: str = "",
           opening_placements: int = 16):
    """Phase 1 round-robin (or Phase 2 with --bots survivor list).

    opening_placements defaults to 16, not 6: the 2026-07-06 local screens
    measured decisive shares between top bots of 0/48 at 6 random opening
    stones, 1/12 at 12, 3/12 at 16 -- competent 2-stone-per-turn defence holds
    from shallow perturbations, so decisive statistics need deep ones (and
    win-rate-vs-weaker remains the primary top-bot discriminator).
    """
    if bots:
        bot_names = [b.strip() for b in bots.split(",")]
    else:
        bot_names = ["random", "greedy_offence", "heuristic_d1.1", "fork_aware_d1.2",
                     "fast_tactical", "residue_bias", "residue_static"]
    _run(bot_names, openings, budget_s, max_moves, seed_base, shard_openings, out,
         opening_placements)
