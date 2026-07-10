"""
Programme D, the cheap read: is the self-play corpus description length
S_T(N) sub-linear in corpus size N?

This is the claim ROADMAP Programme D / README's Central Conjecture / SPEC.md
P3 call "the headline result the programme is built to settle" -- and which,
as of 2026-07-05, had never actually been run. This is the first honest
measurement (gzip + lzma proxy, not the full observer-net S_T).

Method (single-corpus prefix design):
  * Take one move-sequence corpus of N_max games (from modal_app.py
    corpus_moves, or --quick local generation).
  * Canonicalize each game: translate first move to origin, then pick the
    D6 image whose move tuple is lexicographically smallest -- so the 12-fold
    lattice symmetry is NOT counted as "structure" (a genuine substitution
    corpus must compress beyond its own symmetry group).
  * Encode each game as a compact signed-varint byte stream; concatenate the
    first N canonical games; compress. S_T(N) = compressed bytes.
  * Compress with BOTH gzip (32 KB window -- the named proxy, can only see
    ~local cross-game structure) and lzma (whole-corpus dictionary -- the
    honest long-range read). Divergence between them is itself informative.

Fits, over log-spaced N:
  * linear     S_T = a N + b        (NULL: each game adds ~constant info)
  * power      S_T = c N^beta       (sub-linear iff beta < 1)
  * log        S_T = alpha ln N + b (strong shared structure: marginal -> 0)
Reports R^2 for each, the power-law exponent with its interpretation, and the
marginal bytes/game curve S_T(N)/N (the most direct sub-linearity diagnostic).

Falsifier (SPEC.md P3): beta ~ 1 (marginal bytes/game flat) => corpus has no
super-symmetry shared structure at these sizes => Pisot conjecture gets no
support from MDL scaling. beta < 1 with lzma but ~1 with gzip => structure
exists but is longer-range than the gzip window -- expected, and the reason
lzma is the honest proxy.

Output: evidence/results/mdl_scaling.json, evidence/figures/fig_mdl_scaling.png
"""
from __future__ import annotations

import argparse
import gzip
import json
import lzma
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.isomorphisms import d6_transforms


def canonicalize(moves: list) -> list[tuple[int, int]]:
    """Translation + D6 canonical form of a move sequence (lex-smallest image)."""
    if not moves:
        return []
    best = None
    # d6_transforms(cell) gives the 12 images of one cell in a fixed order;
    # applying image index k to every move gives the k-th image of the game.
    imgs = [d6_transforms((int(q), int(r))) for q, r in moves]
    for k in range(12):
        seq = [imgs[i][k] for i in range(len(moves))]
        q0, r0 = seq[0]
        seq = [(q - q0, r - r0) for q, r in seq]  # translate first move to origin
        t = tuple(seq)
        if best is None or t < best:
            best = t
    return list(best)


def _svarint(n: int, out: bytearray) -> None:
    """Zig-zag signed varint."""
    z = (n << 1) ^ (n >> 31)
    while True:
        b = z & 0x7F
        z >>= 7
        if z:
            out.append(b | 0x80)
        else:
            out.append(b)
            break


def encode_game(moves: list) -> bytes:
    """Compact byte encoding of a canonical game: length then delta-coded moves."""
    out = bytearray()
    _svarint(len(moves), out)
    pq = pr = 0
    for q, r in moves:
        _svarint(q - pq, out)
        _svarint(r - pr, out)
        pq, pr = q, r
    return bytes(out)


def gen_random_control(n: int, max_moves: int, out: Path) -> None:
    """Reproducible random-play null corpus (the P3 control): if strong-agent
    S_T(N) is sub-linear but random play's is linear, the sub-linearity is real
    strategic structure, not a generic lzma-dictionary artifact."""
    sys.path.insert(0, str(ROOT / "competition"))
    import arena
    games = []
    for seed in range(n):
        log: list = []
        w = arena.play_game(arena.random_bot(seed=seed * 2 + 1),
                            arena.random_bot(seed=seed * 2 + 2),
                            budget_s=1.0, max_moves=max_moves, move_log=log)
        games.append({"winner": w, "moves": [[q, r] for (q, r), _, _ in log]})
    out.write_text(json.dumps({"games": games}, separators=(",", ":")))
    print(f"[gen] {n} random-play games -> {out}")


def load_corpus(source: str, quick: bool) -> list:
    if source:
        data = json.loads(Path(source).read_text())
        return data["games"]
    # local generation for pipeline testing (no Modal needed)
    sys.path.insert(0, str(ROOT / "experiments"))
    from harness import _play_one_moves
    n = 200 if quick else 800
    print(f"[local] generating {n} ca_combo_v2 self-play games ...")
    return [_play_one_moves(("ca_combo_v2", "ca_combo_v2", 240, s)) for s in range(n)]


def fit_models(N: np.ndarray, S: np.ndarray) -> dict:
    def r2(y, yhat):
        ss = float(np.sum((y - np.mean(y)) ** 2))
        return 1.0 - float(np.sum((y - yhat) ** 2)) / ss if ss > 0 else 0.0
    # linear
    a, b = np.polyfit(N, S, 1)
    lin_r2 = r2(S, a * N + b)
    # power via log-log
    beta, logc = np.polyfit(np.log(N), np.log(S), 1)
    pow_r2 = r2(np.log(S), beta * np.log(N) + logc)
    # log
    alpha, b2 = np.polyfit(np.log(N), S, 1)
    log_r2 = r2(S, alpha * np.log(N) + b2)
    return {
        "linear": {"a_bytes_per_game": float(a), "b": float(b), "r2": lin_r2},
        "power": {"beta": float(beta), "c": float(np.exp(logc)), "r2_loglog": pow_r2,
                  "interpretation": ("sub-linear (shared structure)" if beta < 0.97
                                     else "linear (no super-symmetry structure)")},
        "log": {"alpha": float(alpha), "b": float(b2), "r2": log_r2},
    }


def measure(games: list, points: int) -> tuple[list, dict]:
    """Canonicalize, encode, compress log-spaced prefixes; fit models."""
    n_max = len(games)
    encoded = [encode_game(canonicalize(g["moves"])) for g in games]
    Ns = np.unique(np.round(np.logspace(
        np.log10(max(20, n_max // 100)), np.log10(n_max), points)).astype(int))
    rows = []
    for N in Ns:
        blob = b"".join(encoded[:N])
        rows.append({"N": int(N), "raw_bytes": len(blob),
                     "gzip_bytes": len(gzip.compress(blob, 9)),
                     "lzma_bytes": len(lzma.compress(blob, preset=9))})
    N = np.array([r["N"] for r in rows], float)
    fits = {codec: fit_models(N, np.array([r[f"{codec}_bytes"] for r in rows], float))
            for codec in ("gzip", "lzma")}
    return rows, fits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="", help="move corpus JSON (modal_moves_*.json)")
    ap.add_argument("--control", default="", help="null corpus (e.g. random play) to overlay")
    ap.add_argument("--gen-control", type=int, default=0,
                    help="generate an N-game random-play control at --control path, then use it")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--points", type=int, default=12)
    args = ap.parse_args()

    if args.gen_control:
        gen_random_control(args.gen_control, 240, Path(args.control))

    games = load_corpus(args.source, args.quick)
    print(f"[corpus] {len(games)} games; canonicalizing + compressing prefixes ...")
    rows, fits = measure(games, args.points)
    for r in rows:
        print(f"  N={r['N']:>6}  raw={r['raw_bytes']:>9}  "
              f"gzip={r['gzip_bytes']:>8}  lzma={r['lzma_bytes']:>8}")

    ctrl_rows = ctrl_fits = None
    if args.control:
        cgames = json.loads(Path(args.control).read_text())["games"]
        print(f"[control] {len(cgames)} games ...")
        ctrl_rows, ctrl_fits = measure(cgames, args.points)

    beta = fits["lzma"]["power"]["beta"]
    result = {
        "n_games": len(games), "source": args.source or "local_ca_combo_v2",
        "control_source": args.control or None,
        "rows": rows, "fits": fits,
        "control_rows": ctrl_rows, "control_fits": ctrl_fits,
        "headline": {
            "lzma_beta": beta, "gzip_beta": fits["gzip"]["power"]["beta"],
            "verdict": fits["lzma"]["power"]["interpretation"],
            "control_lzma_beta": ctrl_fits["lzma"]["power"]["beta"] if ctrl_fits else None,
            "beta_below_control": (beta < ctrl_fits["lzma"]["power"]["beta"] - 0.02)
                                  if ctrl_fits else None,
        },
    }
    (ROOT / "evidence" / "results" / "mdl_scaling.json").write_text(json.dumps(result, indent=2))
    print("\nHEADLINE (lzma, whole-corpus dictionary):")
    print(f"  S_T(N) ~ N^{beta:.3f}  -> {fits['lzma']['power']['interpretation']}")
    print(f"  (gzip proxy, 32KB window: beta={fits['gzip']['power']['beta']:.3f})")
    if ctrl_fits:
        cb = ctrl_fits["lzma"]["power"]["beta"]
        print(f"  CONTROL (random play): N^{cb:.3f} -> {ctrl_fits['lzma']['power']['interpretation']}")
        print(f"  => structure is {'REAL (agent beta below random null)' if beta < cb - 0.02 else 'NOT distinguishable from null'}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    Nn = np.array([r["N"] for r in rows], float)
    S = np.array([r["lzma_bytes"] for r in rows], float)
    ax1.loglog(Nn, S, "o-", color="#cc6677", label=f"ca_combo_v2 (lzma): N^{beta:.3f}")
    ax2.semilogx(Nn, S / Nn, "o-", color="#cc6677", label="ca_combo_v2")
    if ctrl_rows:
        Nc = np.array([r["N"] for r in ctrl_rows], float)
        Sc = np.array([r["lzma_bytes"] for r in ctrl_rows], float)
        cb = ctrl_fits["lzma"]["power"]["beta"]
        ax1.loglog(Nc, Sc, "s--", color="#888888", label=f"random null (lzma): N^{cb:.3f}")
        ax2.semilogx(Nc, Sc / Nc, "s--", color="#888888", label="random null")
    ax1.set_xlabel("corpus size N (games)"); ax1.set_ylabel("S_T(N) = compressed bytes (lzma)")
    ax1.set_title("Programme D: corpus description length vs size\n"
                  "log-log slope < 1 = sub-linear = shared substitution structure")
    ax1.legend(fontsize=8); ax1.grid(alpha=0.25, which="both")
    ax2.set_xlabel("corpus size N (games)"); ax2.set_ylabel("marginal bytes / game  S_T(N)/N")
    ax2.set_title("Marginal description cost per game\n"
                  "falling (agent) vs flat (random null) is the P3 signal")
    ax2.legend(fontsize=8); ax2.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(ROOT / "evidence" / "figures" / "fig_mdl_scaling.png", dpi=150)
    print(f"[saved] evidence/results/mdl_scaling.json, evidence/figures/fig_mdl_scaling.png")


if __name__ == "__main__":
    main()
