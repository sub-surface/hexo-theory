"""AlphaZero-style agent wrapping a trained UnifiedNet.

Phase 1 variant (no MCTS):
    Encode current position -> UnifiedNet -> policy logits over encoded
    grid -> mask to empty+legal cells -> softmax (optionally temperatured)
    -> argmax or sample.

Phase 2 variant (with MCTS):
    Same net but used as (prior, value) pair inside a PUCT search. NOT
    yet wired up in this file -- see engine/mcts.py for the tree.

Minimal-interface: the agent has `name: str` and
`choose_move(game) -> (q, r)`. This matches the protocol used by
engine.agents.* and the harness in experiments/harness.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from engine import HexGame
from engine.alphazero import UnifiedNet
from engine.observer import encode_position


def load_unified_net(
    checkpoint_path: str | Path,
    device: str = "cuda",
) -> UnifiedNet:
    """Load a trained UnifiedNet from a checkpoint dict."""
    ck = torch.load(str(checkpoint_path), map_location=device, weights_only=False)
    model = UnifiedNet(hidden=ck["hidden"], depth=ck["depth"]).to(device)
    model.load_state_dict(ck["state_dict"])
    # Freeze -- inference-only. (Using train(False) + requires_grad_(False)
    # to match observer's freezing idiom.)
    model.train(False)
    for p in model.parameters():
        p.requires_grad_(False)
    return model


class AlphaZeroAgent:
    """Policy-head agent (no MCTS). Sample from masked softmax.

    Optional 1-ply value-aware tie-break: when `value_topk > 0`, take the
    top-K logit candidates, apply each to a clone of the game, run the
    trunk once per candidate, and pick by V(s') (corrected for whose turn
    it is in s'). This is NOT MCTS -- it's a single lookahead step used
    to break the pathological determinism of `temperature=0` self-play
    (see docs/theory/2026-04-18-unified-agent-design.md §12.1).

    The value-aware path is mutually exclusive with the temperature-
    sampling path: value-aware acts in place of argmax when t <= 0.
    At t > 0 we already have stochasticity from softmax and do NOT
    re-run the net K times per move (cost would grow linearly in K).
    """

    def __init__(
        self,
        model: UnifiedNet,
        *,
        name: str = "az_policy",
        temperature: float = 1.0,
        device: str = "cuda",
        seed: int | None = None,
        value_topk: int = 0,
    ):
        self.model = model
        self.name = name
        self.temperature = float(temperature)
        self.device = device
        self.rng = np.random.default_rng(seed)
        self.value_topk = int(value_topk)

    def _value_of(self, game: HexGame) -> float:
        """Encode `game` from its to-move POV and return scalar V(s)."""
        arr, _ = encode_position(game, to_move=game.current_player, pad=4)
        x = torch.from_numpy(arr[None]).to(self.device)
        with torch.no_grad():
            out = self.model(x)
        return float(out["value"][0].cpu())

    def choose_move(self, game: HexGame) -> tuple[int, int]:
        arr, origin = encode_position(game, to_move=game.current_player, pad=4)
        q_min, r_min, H, W = origin

        x = torch.from_numpy(arr[None]).to(self.device)
        with torch.no_grad():
            out = self.model(x)
        logits = out["policy"][0].cpu().numpy()  # (H, W)

        # mask: allow only (empty cells in encoded grid) AND (legal move on the infinite board)
        empty_plane = arr[0] > 0.5
        mask = np.full_like(logits, -np.inf, dtype=np.float32)

        cands = list(game.candidates)
        any_legal = False
        legal_cells: list[tuple[int, int, int, int]] = []  # (row, col, q, r)
        if cands:
            for (q, r) in cands:
                col = q - q_min
                row = r - r_min
                if 0 <= row < H and 0 <= col < W and empty_plane[row, col]:
                    mask[row, col] = 0.0
                    any_legal = True
                    legal_cells.append((row, col, q, r))
        if not any_legal:
            # opening: play the centre of the encoded grid.
            return (0, 0)

        logits = logits + mask

        # Value-aware tie-break: run the trunk once per top-K candidate and
        # adjust by V(s'). Only active at temperature <= 0 (otherwise we
        # already have softmax stochasticity and pay 1x net eval per move).
        if self.temperature <= 0 and self.value_topk > 0 and len(legal_cells) > 1:
            self_player = game.current_player
            # Rank legal candidates by logit, take top-K.
            scored = sorted(
                legal_cells,
                key=lambda rc: float(logits[rc[0], rc[1]]),
                reverse=True,
            )
            k = min(self.value_topk, len(scored))
            top = scored[:k]
            best_score = -float("inf")
            best_move: tuple[int, int] = (top[0][2], top[0][3])
            for (_row, _col, q, r) in top:
                g2 = game.clone()
                g2.make(q, r)
                if g2.winner is not None:
                    # Immediate win -- treat V = +1 from self_player POV.
                    v_self = 1.0 if g2.winner == self_player else -1.0
                else:
                    v_tomove = self._value_of(g2)
                    # If s' is still my turn, v_tomove is already from my POV;
                    # otherwise it's from opponent's POV so I want -v_tomove.
                    v_self = v_tomove if g2.current_player == self_player else -v_tomove
                if v_self > best_score:
                    best_score = v_self
                    best_move = (q, r)
            return best_move

        # temperature + softmax
        if self.temperature <= 0:
            flat = logits.flatten()
            best = int(np.argmax(flat))
        else:
            scaled = logits / max(1e-8, self.temperature)
            scaled = scaled - np.max(scaled)
            probs = np.exp(scaled)
            probs = probs / max(1e-12, probs.sum())
            flat = probs.flatten()
            best = int(self.rng.choice(flat.size, p=flat))

        row = best // W
        col = best % W
        q = col + q_min
        r = row + r_min
        return (int(q), int(r))


def make_az_agent(
    ckpt: str | Path = "artifacts/checkpoints/az_pretrain.pt",
    *,
    name: str = "az_policy",
    temperature: float = 0.0,
    device: str | None = None,
    seed: int | None = None,
    value_topk: int = 0,
) -> AlphaZeroAgent:
    """Convenience factory for AlphaZeroAgent."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = load_unified_net(ckpt, device=device)
    return AlphaZeroAgent(
        model, name=name, temperature=temperature, device=device, seed=seed,
        value_topk=value_topk,
    )
