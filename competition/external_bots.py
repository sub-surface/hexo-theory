"""
Adapters that make external engines look like plain arena.py Bots
(state -> Cell), so modal_bakeoff.py's one round-robin/Wilson-CI tool can
compare them against the whole Python roster directly -- instead of the
bespoke one-off Modal scripts (modal_rust_bot.py's vs_mcts/vs_sealbot) that
hand-rolled pairing/win-counting/JSON logic modal_bakeoff.py already does
generically. See competition/2026-07-08-optimal-play-and-bot-design.md
section 4 for why this exists: every new deep_minimax feature was getting
written twice (numpy-vectorized Python, loop-based Rust) and had already
produced one real cross-language test disagreement.

Deliberately NOT imported by arena.py itself -- arena.py's own docstring
commits to staying dependency-free/standalone (portable line-for-line to
TypeScript). hexgo and opponents.ramora are only ever available inside the
Modal Rust image (see modal_images.py), so both imports here are lazy,
inside each factory function, exactly like arena.py's own bot factories
lazily `import numpy as np`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arena  # noqa: E402

Bot = arena.Bot
State = arena.State
Cell = arena.Cell


def make_rust_bot(defence_weight: float = 1.1, fork_bonus: float = 60.0, top_k: int = 5,
                  time_budget_s: float = 0.70, check_every: int = 64,
                  race_weight: float = 0.0, front_bonus: float = 0.0,
                  front_warm_min: int = 3, front_radius: float = 12.0) -> Bot:
    """hexgo.deep_minimax_move (hexo/hexgo-rs/src/search.rs) wrapped as a
    plain Bot. Position sync uses HexGame.set_position (a small, deliberate
    Rust addition -- game.rs's set_position pymethod) rather than replaying
    move history: arena.State already tracks whose turn it is and how many
    placements remain directly, so there's no need to re-derive it, and
    replaying would require threading full move history through arena.py's
    core loop, which doesn't otherwise need it."""
    import hexgo

    g = hexgo.HexGame()

    def bot(state: State) -> Cell:
        stones = [(q, r, p) for (q, r), p in state.stones.items()]
        g.set_position(stones, state.turn, state.placed_this_turn)
        return hexgo.deep_minimax_move(
            g, defence_weight, fork_bonus, top_k, time_budget_s, check_every,
            race_weight, front_bonus, front_warm_min, front_radius)
    return bot


def make_sealbot(time_limit: float = 0.70) -> Bot:
    """The actual vendored SealBot port (opponents.ramora.ai.MinimaxBot --
    Zobrist TT, quiescence, incremental hot-window instant-win/must-block
    detection), not a proxy. ramora.HexGame's fields are plain, mutable
    Python (a @dataclass, unlike hexgo's PyO3-read-only fields), so syncing
    it to an arena.State is a direct field assignment -- no analogue of
    hexgo's set_position needed on this side.

    get_move returns a JOINT pair (or single move on the game's opening) --
    arena's Bot protocol returns one cell per call (called once per stone),
    so the second cell of a pair is cached and returned on the next call
    for the SAME state.stones (i.e. the second half of the same turn).

    ramora.Player is a plain Enum, NOT IntEnum -- `1 == Player.A` is False.
    game.board's values MUST be Player.A/Player.B instances, not the raw
    1/2 ints arena.State uses, or every win/threat check inside get_move
    (all written as `cp == Player.A`) silently sees zero matches -- caught
    before ever running a real match, not after."""
    from opponents.ramora.ai import MinimaxBot
    from opponents.ramora.game import HexGame as RamoraGame, Player as RamoraPlayer

    sealbot = MinimaxBot(time_limit=time_limit)
    game = RamoraGame()
    pending: list[Cell] = []
    to_ramora = {1: RamoraPlayer.A, 2: RamoraPlayer.B}

    def bot(state: State) -> Cell:
        game.board = {cell: to_ramora[p] for cell, p in state.stones.items()}
        game.current_player = RamoraPlayer.A if state.turn == 1 else RamoraPlayer.B
        game.moves_left_in_turn = state.stones_per_turn - state.placed_this_turn
        game.game_over = False
        game.winner = RamoraPlayer.NONE

        if pending:
            return pending.pop(0)
        turn = sealbot.get_move(game)
        if not turn:
            cells = arena.candidates(state.stones)
            return cells[0]
        pending.extend(turn[1:])
        return turn[0]
    return bot


def make_hexo_bot_wrapper() -> Bot:
    """competition/hexo_bot.py's choose_move -- the standalone file actually
    handed to the opponent's team -- wrapped as a plain Bot, so its real
    strength can be measured the same way as everything else in this file
    instead of taken on faith. Pure Python/numpy, no lazy import needed
    beyond hexo_bot itself."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hexo_bot

    def bot(state: State) -> Cell:
        return hexo_bot.choose_move(state.stones, state.turn,
                                    state.placed_this_turn, state.stones_per_turn)
    return bot


def make_hexo_bot2_wrapper(time_budget_s: float = 0.70, use_tss: bool = True) -> Bot:
    """competition/hexo_bot2.py (2026-07-09 fresh-start rebuild: incremental
    window counts, exact hitting-set tactics, threat-space search, joint-pair
    alpha-beta) wrapped as a plain Bot. use_tss=False is the ablation arm."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import hexo_bot2

    def bot(state: State) -> Cell:
        return hexo_bot2.choose_move(state.stones, state.turn,
                                     state.placed_this_turn,
                                     state.stones_per_turn,
                                     time_budget_s=time_budget_s,
                                     use_tss=use_tss)
    return bot


def make_residue_blocker() -> Bot:
    """The F7 blocking-set defense (experiments/run_residue_defense.py)
    playing the REAL k=6 game as a pure defender: exact hitting-set tier-1
    blocks, proactive {0,1}-residue-class claims in maturing windows, and a
    nearest-to-the-action blocking-set cell when nothing is urgent. Never
    tries to win -- its success metric is the draw. Exists to test whether
    the blocking-set structure that survived the scripted multi-front
    attacker also survives a real search attacker (hexo_bot2)."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "experiments"))
    from run_residue_defense import (residue_defender_move, State as RState,
                                     residue, TARGET_CLASSES)

    pending: list[Cell] = []

    def bot(state: State) -> Cell:
        if pending:
            c = pending.pop(0)
            if c not in state.stones:
                return c
        me = state.turn
        st = RState()
        st.att = {c for c, p in state.stones.items() if p != me}
        st.dfn = {c for c, p in state.stones.items() if p == me}
        remaining = state.stones_per_turn - state.placed_this_turn
        placements, _, _ = residue_defender_move(st, 6, budget=remaining)
        placements = [c for c in placements if c not in state.stones][:remaining]
        if len(placements) < remaining and st.att:
            # idle stones: claim blocking-set cells nearest the action
            cq = sum(q for q, _ in st.att) / len(st.att)
            cr = sum(r for _, r in st.att) / len(st.att)
            cands = []
            for (q, r) in st.att:
                for dq in range(-2, 3):
                    for dr in range(-2, 3):
                        c = (q + dq, r + dr)
                        if (c not in state.stones and c not in placements
                                and residue(*c) in TARGET_CLASSES):
                            cands.append(c)
            cands.sort(key=lambda c: (c[0] - cq) ** 2 + (c[1] - cr) ** 2)
            for c in cands:
                if len(placements) >= remaining:
                    break
                if c not in placements:
                    placements.append(c)
        if not placements:
            placements = [arena.candidates(state.stones)[0]]
        pending.clear()
        pending.extend(placements[1:])
        return placements[0]
    return bot


def external_bot_registry(include_rust: bool = True) -> dict[str, Bot]:
    """Only resolvable inside the Modal Rust image (modal_images.hexo_rust_
    image(include_ramora=True)) -- make_rust_bot lazily imports hexgo, so
    this dict itself is cheap to build, but calling any bot it returns will
    raise ImportError anywhere else. include_rust=False skips deep_minimax_
    rust for callers (e.g. a plain numpy+ramora image with no compiled
    hexgo wheel) that only need sealbot / hexo_bot_standalone."""
    reg = {
        "sealbot": make_sealbot(),
        "hexo_bot_standalone": make_hexo_bot_wrapper(),
        "hexo_bot2": make_hexo_bot2_wrapper(),
        "hexo_bot2_no_tss": make_hexo_bot2_wrapper(use_tss=False),
        "residue_blocker": make_residue_blocker(),
    }
    if include_rust:
        reg["deep_minimax_rust"] = make_rust_bot()
    return reg
