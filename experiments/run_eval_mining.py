"""
Mine evaluation weights for hexo_bot2 from a self-play corpus.

Replays corpus games through competition/hexo_bot2.py's own incremental
Board (so features are definitionally identical to what the bot evaluates),
samples mid-game positions, extracts live-window counts by stone count
(k = 1..5, both sides, mover's perspective), and fits a logistic regression
P(mover wins | features). The fitted weights are the empirical replacement
for the hand-set V table and DEF_W in hexo_bot2 -- the brief's open question
#3 (mined lookup evaluation), done over interpretable window features rather
than the failed NN value head's dense board encoding.

Output: results/eval_mining.json with fitted weights, the implied V-table /
defence-weight ratios, and held-out accuracy vs the hand-set baseline.

    python experiments/run_eval_mining.py --quick   # 1000 games, ~15 s
    python experiments/run_eval_mining.py           # full corpus
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "competition"))
import hexo_bot2  # noqa: E402

CORPUS = ROOT / "results" / "modal_moves_python_8000.json"
OUT = ROOT / "results" / "eval_mining.json"

N_FEATURES = 10  # my windows k=1..5, opp windows k=1..5


def game_features(moves: list, winner: int, rng: random.Random,
                  samples_per_game: int) -> list[tuple[np.ndarray, float]]:
    """Replay one game, snapshot features at sampled placement indices.
    Mover perspective: the player about to place. Label 1 if mover wins."""
    n = len(moves)
    if n < 14:
        return []
    # placement index -> player, per the 1-2-2 rule (placement 0 is P1's
    # single opening stone; thereafter pairs alternate)
    def player_at(i: int) -> int:
        if i == 0:
            return 1
        return 2 if ((i - 1) // 2) % 2 == 0 else 1

    idxs = sorted(rng.sample(range(10, n - 2), min(samples_per_game, n - 12)))
    board = hexo_bot2.Board({})
    out = []
    nxt = 0
    for i, (q, r) in enumerate(moves):
        if nxt < len(idxs) and i == idxs[nxt]:
            mover = player_at(i)
            f = np.zeros(N_FEATURES)
            for pi in (0, 1):
                for wkey in board.warm[pi]:
                    k = board.wc[wkey][pi]
                    col = min(k, 5) - 1
                    off = 0 if (pi + 1) == mover else 5
                    f[off + col] += 1
                # warm only holds k>=2; count k=1 live windows separately
            # k=1 live windows: from wc directly (cheap enough at sample time)
            for wkey, cnt in board.wc.items():
                for pi in (0, 1):
                    if cnt[pi] == 1 and cnt[1 - pi] == 0:
                        off = 0 if (pi + 1) == mover else 5
                        f[off] += 1
            out.append((f, 1.0 if winner == mover else 0.0))
            nxt += 1
        if (q, r) in board.stones:
            break  # corrupt record; drop rest
        board.place((q, r), player_at(i))
        if board.winner:
            break
    return out


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3,
                 iters: int = 25) -> np.ndarray:
    w = np.zeros(X.shape[1] + 1)
    Xb = np.hstack([X, np.ones((len(X), 1))])
    n = len(y)
    for _ in range(iters):
        z = Xb @ w
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        g = Xb.T @ (p - y) / n + l2 * w
        s = np.maximum(p * (1 - p), 1e-6)
        H = (Xb * s[:, None]).T @ Xb / n + l2 * np.eye(len(w))
        w -= np.linalg.solve(H, g)
    return w


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--samples-per-game", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    t0 = time.time()
    corpus = json.loads(CORPUS.read_text())
    games = [g for g in corpus["games"] if g.get("winner") in (1, 2)]
    if args.quick:
        games = games[:1000]
    rng = random.Random(args.seed)

    feats, labels = [], []
    for g in games:
        for f, y in game_features(g["moves"], g["winner"], rng,
                                  args.samples_per_game):
            feats.append(f)
            labels.append(y)
    X = np.array(feats)
    y = np.array(labels)
    # standardize per-feature scale (counts differ by orders of magnitude)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd

    n_tr = int(0.8 * len(X))
    perm = np.random.RandomState(args.seed).permutation(len(X))
    tr, te = perm[:n_tr], perm[n_tr:]
    w = fit_logistic(Xs[tr], y[tr])

    def acc(idx) -> float:
        z = np.hstack([Xs[idx], np.ones((len(idx), 1))]) @ w
        return float((((z > 0) * 1.0) == y[idx]).mean())

    # baseline: hand-set V table as a linear scorer, same split
    V = np.array(hexo_bot2.V[1:6])
    hand = X[:, :5] @ V - hexo_bot2.DEF_W * (X[:, 5:] @ V)
    hand_acc = float((((hand[te] > 0) * 1.0) == y[te]).mean())

    # de-standardized weights: contribution per raw window count
    w_raw = w[:N_FEATURES] / sd
    my_w, opp_w = w_raw[:5], -w_raw[5:]
    # implied V table (normalize so k=1 -> 1) and defence weight
    implied_V = (my_w / my_w[0]).tolist() if my_w[0] > 0 else my_w.tolist()
    implied_def = float(np.mean(opp_w[1:4] / np.maximum(my_w[1:4], 1e-12)))

    out = {
        "n_games": len(games), "n_samples": len(X),
        "train_acc": acc(tr), "test_acc": acc(te),
        "hand_baseline_test_acc": hand_acc,
        "weights_std": w.tolist(),
        "weights_raw_per_count": w_raw.tolist(),
        "implied_V_normalized": implied_V,
        "implied_defence_weight": implied_def,
        "feature_means": mu.tolist(),
        "wall_time_s": round(time.time() - t0, 1),
        "corpus": str(CORPUS.name), "quick": args.quick,
        "seed": args.seed,
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("weights_std", "feature_means")}, indent=2))


if __name__ == "__main__":
    main()
