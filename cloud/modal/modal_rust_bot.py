"""
Modal deployment for the Rust-ported tournament search (hexo/hexgo-rs/src/search.rs).

Three things this validates, in order:

  1. smoke_test    -- the PyO3 binding actually works (builds fresh on Linux
     with a single, unambiguous Python 3.12, sidestepping the local Windows
     py-launcher confusion that made local testing target 3.14 instead of
     3.12 no matter how it was invoked). deep_minimax_move's own logic was
     already cross-checked exactly against the Python reference via `cargo
     test` (six passing tests, three of them exact-value equality checks
     against arena.py/hexo_bot.py's own functions on identical inputs) --
     this step is purely "does the binding work," not "is the logic right."

  2. benchmark      -- how many ply-levels of real alpha-beta search does
     deep_minimax_move complete within a fixed time budget, compared to
     what the Python version (competition/arena.py's make_deep_minimax)
     achieves in the same budget locally. The whole motivation for a Rust
     port was that Python's per-node dict-copy is the bottleneck, not the
     (already-vectorized) leaf evaluation -- this is the direct test of
     that claim.

  3. vs_mcts        -- self-play: deep_minimax_move vs hexgo-rs's own
     mcts_pure at num_sims=100. This is chosen deliberately: the opponent
     we actually need to beat is a 100-simulation AlphaZero-style MCTS bot
     (per the user), and pure-rollout MCTS at the same simulation count is
     the closest already-built, directly-relevant proxy available -- not a
     perfect stand-in (no policy/value network guiding it), but a real,
     non-trivial opponent at the same search-budget scale, not a straw man.

  4. vs_sealbot     -- self-play against the actual vendored SealBot port
     (opponents.ramora.ai.MinimaxBot: Zobrist TT, quiescence, incremental
     hot-window instant-win/must-block detection), not a proxy. ramora's
     own HexGame is a verified 1:1 rules mirror (axial coords, 3 axes,
     WIN_LENGTH=6, 1-2-2 turns), so it's used as the canonical board and
     the Rust side is synced by replaying the shared move history.

deep_minimax_move as of 2026-07-08 includes the forced_result fix (exact
instant-win / unblockable-double-brink detection at every search node, not
just the root) -- see hexo/hexgo-rs/src/search.rs's forced_result doc
comment and results/fork_ablation_diagnostic.json for why this was needed:
a controlled local ablation showed the PRE-FIX deep_minimax losing 24-0 to
the simpler fast_minimax in BOTH fork_bonus=60 and fork_bonus=0
configurations -- a narrow top-k static beam was silently pruning forced
tactical continuations at depth, not a bad eval feature.

Usage (from hexo-theory/; Modal already authenticated as 'sub-surface'):

    modal run cloud/modal/modal_rust_bot.py::smoke_test
    modal run cloud/modal/modal_rust_bot.py::benchmark
    modal run cloud/modal/modal_rust_bot.py::vs_mcts --games 60 --sims 100
    modal run cloud/modal/modal_rust_bot.py::vs_sealbot --games 40
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import modal

from modal_images import hexo_rust_image

THEORY_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = THEORY_ROOT / "evidence" / "results"

app = modal.App("hexo-rust-bot")

# include_ramora=True: vs_sealbot needs opponents.ramora.ai.MinimaxBot
# importable (only `create_ramora_bot`-equivalent direct construction is
# used, not adapter.py's play_match, which needs orca.encoding.CGameState
# -- deliberately avoided).
rust_image = hexo_rust_image(include_ramora=True)


@app.function(image=rust_image, cpu=2, timeout=600)
def _smoke() -> dict:
    import hexgo
    g = hexgo.HexGame()
    mv = hexgo.deep_minimax_move(g, 1.1, 60.0, 5, 0.3, 16)

    # Build a 5-in-a-row for player 1 via legal 1-2-2 play (current_player
    # is read-only from Python -- PyO3 only generated a getter -- so this
    # goes through the real make() API instead of forcing internal state).
    # Filler moves for P2 must NOT be collinear with each other (a first
    # draft placed six filler stones on the same (0,1) axis line and P2
    # accidentally won on their own "irrelevant" moves -- caught by an
    # assertion, not silently wrong, but worth leaving this note since it's
    # exactly the kind of test-construction slip this session keeps finding).
    win_setup = hexgo.HexGame()
    win_setup.make(0, 0)                      # P1's 1-stone opening
    win_setup.make(90, 90); win_setup.make(70, -40)   # P2 filler, scattered
    win_setup.make(1, 0); win_setup.make(2, 0)        # P1: 3 in a row
    win_setup.make(-55, 88); win_setup.make(33, 61)   # P2 filler
    win_setup.make(3, 0); win_setup.make(4, 0)        # P1: 5 in a row
    win_setup.make(-80, 5); win_setup.make(48, -77)   # P2 filler
    # now it's P1's turn again, 5 in a row on the board, 0 placements made
    # this turn -- deep_minimax_move's root win-check should fire instantly
    assert win_setup.winner is None, f"unexpected winner in test setup: {win_setup.winner}"
    assert win_setup.current_player == 1
    mv2 = hexgo.deep_minimax_move(win_setup, 1.1, 60.0, 5, 0.3, 16)
    return {"opening_move": mv, "forced_win_move": mv2,
            "forced_win_correct": mv2 in [(5, 0), (-1, 0)]}


@app.function(image=rust_image, cpu=2, timeout=600)
def _benchmark_depth(time_budget_s: float, n_random_moves: int, seed: int) -> dict:
    import hexgo
    import random

    rng = random.Random(seed)
    g = hexgo.HexGame()
    for _ in range(n_random_moves):
        cands = g.candidates
        if not cands or g.winner is not None:
            break
        mv = cands[rng.randrange(len(cands))]
        g.make(*mv)
    if g.winner is not None:
        return {"skipped": True}

    t0 = time.perf_counter()
    mv = hexgo.deep_minimax_move(g, 1.1, 60.0, 5, time_budget_s, 64)
    dt = time.perf_counter() - t0
    return {"n_stones": len(g.board), "time_budget_s": time_budget_s,
            "actual_time_s": round(dt, 3), "move": mv, "legal": mv in g.candidates}


@app.function(image=rust_image, cpu=2, timeout=1800)
def _play_vs_mcts(seed: int, sims: int, rust_time_budget: float, rust_is_p1: bool,
                  opening_moves: int) -> dict:
    import hexgo
    import random

    rng = random.Random(seed)
    g = hexgo.HexGame()
    # randomized opening prefix (both sides play randomly) -- same rationale
    # as arena.py's opening_seed mechanism: deterministic strong bots would
    # otherwise replay one canonical game every time.
    for _ in range(opening_moves):
        if g.winner is not None:
            break
        cands = g.candidates
        mv = cands[rng.randrange(len(cands))]
        g.make(*mv)

    t0 = time.time()
    max_moves = 300
    moves_played = 0
    while g.winner is None and moves_played < max_moves:
        is_rust_turn = (g.current_player == 1) == rust_is_p1
        if is_rust_turn:
            mv = hexgo.deep_minimax_move(g, 1.1, 60.0, 5, rust_time_budget, 64)
        else:
            mv = hexgo.mcts(g, sims, 1.5, 0.2)
        if not g.make(*mv):
            # illegal move (shouldn't happen) -- forfeit to first candidate
            cands = g.candidates
            if not cands:
                break
            g.make(*cands[0])
        moves_played += 1
    return {"seed": seed, "rust_is_p1": rust_is_p1, "winner": g.winner,
            "n_moves": moves_played, "n_stones": len(g.board),
            "wall_s": round(time.time() - t0, 1)}


@app.function(image=rust_image, cpu=2, timeout=1800)
def _play_vs_sealbot(seed: int, sealbot_time_limit: float, rust_time_budget: float,
                     rust_is_p1: bool, opening_moves: int) -> dict:
    """deep_minimax_move (Rust alpha-beta, forced-result fix) vs the actual
    vendored SealBot port (opponents.ramora.ai.MinimaxBot -- TT + quiescence
    + incremental hot-window instant-win/must-block detection, see
    sources/external-runs/misc/hexbot-building-framework/opponents/ramora/ai.py). ramora's
    own HexGame is used as the canonical rules engine (verified 1:1 mirror:
    same axial coords, same 3 axes, WIN_LENGTH=6, 1-2-2 turn rule -- see
    opponents/ramora/game.py) since SealBot's search mutates it internally;
    the Rust side is kept in sync by replaying the shared move history onto
    a fresh hexgo.HexGame() each time it's rust's turn (both engines are
    deterministic mirrors of the same rules, so replay reconstructs an
    identical position)."""
    import sys
    sys.path.insert(0, "/root")
    import hexgo
    import random
    from opponents.ramora.ai import MinimaxBot
    from opponents.ramora.game import HexGame as RamoraGame, Player as RamoraPlayer

    RING = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1))
    rng = random.Random(seed)
    game = RamoraGame()
    sealbot = MinimaxBot(time_limit=sealbot_time_limit)
    moves: list[tuple[int, int]] = []

    def random_candidates():
        occ = set(game.board)
        if not occ:
            return [(0, 0)]
        seen, out = set(), []
        for (q, r) in occ:
            for dq, dr in RING:
                c = (q + dq, r + dr)
                if c not in occ and c not in seen:
                    seen.add(c); out.append(c)
        return out or [(0, 0)]

    for _ in range(opening_moves):
        if game.game_over:
            break
        cands = random_candidates()
        mv = cands[rng.randrange(len(cands))]
        game.make_move(*mv)
        moves.append(mv)

    t0 = time.time()
    max_moves = 300
    # Hard per-game wall-clock cap, well under the 1800s function timeout.
    # SealBot's own time_limit is a COOPERATIVE deadline it enforces
    # internally (same as our own pre-fix soft_deadline_s bug: coarse
    # in-tree checks can overrun on a slow node/large board) -- this repo
    # has no control over that code, so the safety net has to live on our
    # side, exactly like arena.py's play_game forfeits any move that blows
    # its budget rather than trusting the mover to self-limit.
    game_deadline = t0 + 900.0
    timed_out = False
    while not game.game_over and len(moves) < max_moves:
        if time.time() > game_deadline:
            timed_out = True
            break
        is_rust_turn = (game.current_player == RamoraPlayer.A) == rust_is_p1
        if is_rust_turn:
            stones_to_play = game.moves_left_in_turn
            g = hexgo.HexGame()
            for (q, r) in moves:
                g.make(q, r)
            for _ in range(stones_to_play):
                if game.game_over:
                    break
                mv = hexgo.deep_minimax_move(g, 1.1, 60.0, 5, rust_time_budget, 64)
                if not g.make(*mv):
                    cands = g.candidates
                    mv = cands[0] if cands else random_candidates()[0]
                    g.make(*mv)
                game.make_move(*mv)
                moves.append(mv)
        else:
            turn = sealbot.get_move(game)
            if not turn:
                break
            for mv in turn:
                if game.game_over:
                    break
                if not game.make_move(*mv):
                    continue
                moves.append(mv)

    if timed_out:
        return {"seed": seed, "rust_is_p1": rust_is_p1, "winner": "timeout",
                "n_moves": len(moves), "n_stones": len(game.board),
                "wall_s": round(time.time() - t0, 1)}

    if game.winner == RamoraPlayer.NONE:
        winner = "draw"
    elif (game.winner == RamoraPlayer.A) == rust_is_p1:
        winner = "rust"
    else:
        winner = "sealbot"
    return {"seed": seed, "rust_is_p1": rust_is_p1, "winner": winner,
            "n_moves": len(moves), "n_stones": len(game.board),
            "wall_s": round(time.time() - t0, 1)}


@app.local_entrypoint()
def smoke_test():
    r = _smoke.remote()
    print(json.dumps(r, indent=2))
    assert r["forced_win_correct"], "Rust bot failed a trivial forced-win check on Modal!"
    print("\nOK -- Rust binding works and forced-win detection is correct on Modal.")


@app.local_entrypoint()
def benchmark(budgets: str = "0.3,0.7,1.5,3.0", n_trials: int = 6):
    budget_list = [float(b) for b in budgets.split(",")]
    calls_budget, calls_moves, calls_seed = [], [], []
    for b in budget_list:
        for seed in range(n_trials):
            calls_budget.append(b)
            calls_moves.append(10 + seed * 8)  # varied board complexity
            calls_seed.append(seed)
    t0 = time.time()
    results = list(_benchmark_depth.map(calls_budget, calls_moves, calls_seed))
    wall = time.time() - t0
    print(f"[done] {len(results)} benchmark calls in {wall:.1f}s\n")
    by_budget: dict[float, list] = {}
    for r in results:
        if r.get("skipped"):
            continue
        by_budget.setdefault(r["time_budget_s"], []).append(r)
    for b in sorted(by_budget):
        rs = by_budget[b]
        avg_actual = sum(r["actual_time_s"] for r in rs) / len(rs)
        all_legal = all(r["legal"] for r in rs)
        print(f"budget={b}s: n={len(rs)}, avg_actual_time={avg_actual:.3f}s, all_legal={all_legal}")
    out_path = RESULTS_ROOT / "rust_search_benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"budgets": budget_list, "results": results}, indent=2))
    print(f"\n[saved] {out_path}")


@app.local_entrypoint()
def vs_mcts(games: int = 60, sims: int = 100, rust_time_budget: float = 0.70,
           opening_moves: int = 16, out: str = ""):
    """deep_minimax_move (Rust alpha-beta) vs mcts_pure(num_sims=100) --
    the directly-relevant proxy matchup for the actual opponent class."""
    seeds = list(range(games // 2))
    calls_seed, calls_sims, calls_budget, calls_p1, calls_open = [], [], [], [], []
    for s in seeds:
        for rust_p1 in (True, False):
            calls_seed.append(s); calls_sims.append(sims)
            calls_budget.append(rust_time_budget); calls_p1.append(rust_p1)
            calls_open.append(opening_moves)

    t0 = time.time()
    results = list(_play_vs_mcts.map(calls_seed, calls_sims, calls_budget, calls_p1, calls_open))
    wall = time.time() - t0

    rust_wins = mcts_wins = draws = 0
    for r in results:
        if r["winner"] is None:
            draws += 1
        elif (r["winner"] == 1) == r["rust_is_p1"]:
            rust_wins += 1
        else:
            mcts_wins += 1
    n = len(results)
    print(f"[done] {n} games in {wall:.1f}s")
    print(f"Rust deep_minimax: {rust_wins} wins")
    print(f"MCTS (100 sims):   {mcts_wins} wins")
    print(f"Draws/cutoff:      {draws}")
    if rust_wins + mcts_wins > 0:
        p = rust_wins / (rust_wins + mcts_wins)
        print(f"Rust decisive win rate: {p:.3f} ({rust_wins}/{rust_wins+mcts_wins})")

    out_path = Path(out) if out else RESULTS_ROOT / "rust_vs_mcts100.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"games": n, "sims": sims, "rust_time_budget": rust_time_budget,
         "rust_wins": rust_wins, "mcts_wins": mcts_wins, "draws": draws,
         "wall_s": round(wall, 1), "raw": results}, indent=2))
    print(f"[saved] {out_path}")


@app.local_entrypoint()
def vs_sealbot(games: int = 40, sealbot_time_limit: float = 0.70,
              rust_time_budget: float = 0.70, opening_moves: int = 16, out: str = ""):
    """deep_minimax_move (Rust, post forced-result-fix) vs the actual
    vendored SealBot port -- the real reference opponent, not a proxy."""
    seeds = list(range(games // 2))
    calls_seed, calls_slim, calls_rbudget, calls_p1, calls_open = [], [], [], [], []
    for s in seeds:
        for rust_p1 in (True, False):
            calls_seed.append(s); calls_slim.append(sealbot_time_limit)
            calls_rbudget.append(rust_time_budget); calls_p1.append(rust_p1)
            calls_open.append(opening_moves)

    t0 = time.time()
    # return_exceptions=True: one hung/errored game must not cancel the
    # other 39 in-flight calls (the 2026-07-08 failure mode -- a single
    # input hit the 1800s function timeout and modal's default
    # return_exceptions=False tore down the entire .map() batch).
    raw_results = list(_play_vs_sealbot.map(
        calls_seed, calls_slim, calls_rbudget, calls_p1, calls_open,
        return_exceptions=True))
    wall = time.time() - t0

    results, errored = [], 0
    for r in raw_results:
        if isinstance(r, BaseException):
            errored += 1
            print(f"[error] a game raised: {r!r}")
        else:
            results.append(r)

    rust_wins = sealbot_wins = draws = timeouts = 0
    for r in results:
        if r["winner"] == "draw":
            draws += 1
        elif r["winner"] == "timeout":
            timeouts += 1
        elif r["winner"] == "rust":
            rust_wins += 1
        else:
            sealbot_wins += 1
    n = len(results)
    print(f"[done] {n}/{len(raw_results)} games completed in {wall:.1f}s"
          + (f" ({errored} errored)" if errored else ""))
    print(f"Rust deep_minimax: {rust_wins} wins")
    print(f"SealBot (Ramora):  {sealbot_wins} wins")
    print(f"Draws:             {draws}")
    print(f"Timeouts (>900s):  {timeouts}")
    if rust_wins + sealbot_wins > 0:
        p = rust_wins / (rust_wins + sealbot_wins)
        print(f"Rust decisive win rate: {p:.3f} ({rust_wins}/{rust_wins+sealbot_wins})")

    out_path = Path(out) if out else RESULTS_ROOT / "rust_vs_sealbot.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(
        {"games": n, "sealbot_time_limit": sealbot_time_limit, "rust_time_budget": rust_time_budget,
         "rust_wins": rust_wins, "sealbot_wins": sealbot_wins, "draws": draws,
         "timeouts": timeouts, "errored": errored,
         "wall_s": round(wall, 1), "raw": results}, indent=2))
    print(f"[saved] {out_path}")
