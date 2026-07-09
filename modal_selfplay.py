"""
Generate a strong self-play corpus: hexo_bot2 vs hexo_bot2 on Modal.

Feeds the 2026-07-09 theory experiments (patch complexity, residue
extinction -- claims about ORDER IN STRONG PLAY need strong play, the
existing 8,000-game corpus is weak ca_combo_v2 self-play) plus any future
eval mining / epiplexity dose-response run.

Same corpus schema as results/modal_moves_python_8000.json: games as
{winner, moves[[q,r],...]} in placement order under the 1-2-2 rule, with
seeded random openings recorded in-band (opening_placements field says how
many leading placements were the seeded opener's).

    modal run modal_selfplay.py::generate --n-games 400 --budget-s 0.5
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import modal

THEORY_ROOT = Path(__file__).resolve().parent

app = modal.App("hexo-selfplay")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("numpy")
    .add_local_file(str(THEORY_ROOT / "competition" / "arena.py"),
                    "/root/competition/arena.py", copy=True)
    .add_local_file(str(THEORY_ROOT / "competition" / "hexo_bot2.py"),
                    "/root/competition/hexo_bot2.py", copy=True)
)


@app.function(image=image, cpu=1, timeout=3600)
def _selfplay_shard(seeds: list[int], budget_s: float, max_moves: int,
                    opening_placements: int) -> list[dict]:
    import sys
    sys.path.insert(0, "/root/competition")
    import arena
    import hexo_bot2

    def make_bot():
        def bot(state):
            return hexo_bot2.choose_move(
                state.stones, state.turn, state.placed_this_turn,
                state.stones_per_turn, time_budget_s=budget_s * 0.7)
        return bot

    out = []
    shard_deadline = time.time() + 3200.0
    for seed in seeds:
        if time.time() > shard_deadline:
            break
        hexo_bot2._pending.clear()
        log: list = []
        t0 = time.time()
        w, n = arena.play_game(make_bot(), make_bot(), budget_s=budget_s,
                               max_moves=max_moves, opening_seed=seed,
                               opening_placements=opening_placements,
                               return_stats=True, move_log=log)
        out.append({"seed": seed, "winner": w, "n_stones": n,
                    "moves": [[c[0], c[1]] for c, _, _ in log],
                    "game_s": round(time.time() - t0, 1)})
    return out


@app.local_entrypoint()
def generate(n_games: int = 400, budget_s: float = 0.5, max_moves: int = 400,
             opening_placements: int = 12, shard_size: int = 8,
             seed_base: int = 500000, out: str = ""):
    seeds = list(range(seed_base, seed_base + n_games))
    shards = [seeds[i:i + shard_size] for i in range(0, len(seeds), shard_size)]
    print(f"[selfplay] {n_games} games in {len(shards)} shards")
    t0 = time.time()
    raw = list(_selfplay_shard.starmap(
        [(s, budget_s, max_moves, opening_placements) for s in shards],
        return_exceptions=True))
    wall = time.time() - t0
    games, errors = [], 0
    for shard in raw:
        if isinstance(shard, BaseException):
            errors += 1
        else:
            games.extend(shard)
    wins = {0: 0, 1: 0, 2: 0}
    for g in games:
        wins[g["winner"]] += 1
    summary = {
        "agent": "hexo_bot2", "opponent": "hexo_bot2",
        "n_games": len(games), "wins_black": wins[1], "wins_white": wins[2],
        "unfinished": wins[0],
        "mean_length": round(sum(g["n_stones"] for g in games) / max(len(games), 1), 1),
        "budget_s": budget_s, "max_moves": max_moves,
        "opening_placements": opening_placements, "seed_base": seed_base,
        "shard_errors": errors, "wall_time_s": round(wall, 1),
        "games": games,
    }
    out_path = Path(out) if out else THEORY_ROOT / "results" / "hexo_bot2_selfplay.json"
    out_path.write_text(json.dumps(summary))
    print(f"[saved] {out_path}: {len(games)} games "
          f"(B {wins[1]} / W {wins[2]} / draw {wins[0]}), "
          f"mean len {summary['mean_length']}, wall {wall:.0f}s")
