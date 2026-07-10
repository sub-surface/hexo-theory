"""
Point the epiplexity two-part MDL machinery (engine/epiplexity.py) at the
corpora we already have -- the actual Finzi-style measurement the roadmap's
Programme D observer-net was meant to approximate, one step beyond the raw
gzip-prefix proxy in run_mdl_scaling.py.

For each log-spaced prefix of a move corpus we fit a Markov back-off observer
and report its held-out cross-entropy H_T (bits/token = the epiplexity entropy
term) and program length S_T, plus the gzip observer's bits/token. Run on the
strong-agent corpus AND the random-play null: the epiplexity claim is that
strong play is *more compressible by a bounded observer* -- lower H_T, and
H_T that falls as the observer sees more of the corpus (learnable structure),
versus a flat, high H_T for random play.

Usage:
  python experiments/run_epiplexity_corpus.py \
      --source evidence/results/modal_moves_python_8000.json \
      --control evidence/results/mdl_random_control_3000.json

Output: evidence/results/epiplexity_corpus.json, evidence/figures/fig_epiplexity_corpus.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.epiplexity import Corpus, Game, measure_corpus


def load(path: str) -> Corpus:
    games = json.loads(Path(path).read_text())["games"]
    return Corpus(games=[Game(moves=[tuple(m) for m in g["moves"]],
                              players=[], winner=g.get("winner"))
                         for g in games], manifest={"agent_a": Path(path).stem})


def sweep(corpus: Corpus, points: int, max_order: int) -> list[dict]:
    n_max = len(corpus.games)
    Ns = np.unique(np.round(np.logspace(
        np.log10(max(40, n_max // 60)), np.log10(n_max), points)).astype(int))
    rows = []
    for N in Ns:
        sub = Corpus(games=corpus.games[:N], manifest=corpus.manifest)
        rep = measure_corpus(sub, max_order=max_order)
        rows.append({"N": int(N), "n_tokens": rep.n_tokens,
                     "markov_H_T": round(rep.markov_H_T_bits_per_token, 4),
                     "markov_S_T_bits": rep.markov_S_T_bits,
                     "gzip_bits_per_token": round(rep.gzip_bits_per_token, 4),
                     "two_part_markov_bits": round(rep.two_part_markov_bits(), 1)})
        print(f"  N={N:>5}  H_T={rows[-1]['markov_H_T']:.3f}  "
              f"gzip/tok={rows[-1]['gzip_bits_per_token']:.3f}  "
              f"S_T={rep.markov_S_T_bits} bits")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="evidence/results/modal_moves_python_8000.json")
    ap.add_argument("--control", default="evidence/results/mdl_random_control_3000.json")
    ap.add_argument("--points", type=int, default=10)
    ap.add_argument("--max-order", type=int, default=3)
    args = ap.parse_args()

    print(f"[agent] {args.source}")
    agent_rows = sweep(load(args.source), args.points, args.max_order)
    ctrl_rows = None
    if args.control and Path(args.control).exists():
        print(f"[control] {args.control}")
        ctrl_rows = sweep(load(args.control), args.points, args.max_order)

    a_ht = agent_rows[-1]["markov_H_T"]
    c_ht = ctrl_rows[-1]["markov_H_T"] if ctrl_rows else None
    result = {"source": args.source, "control": args.control if ctrl_rows else None,
              "max_order": args.max_order, "agent_rows": agent_rows,
              "control_rows": ctrl_rows,
              "headline": {
                  "agent_H_T_final": a_ht, "control_H_T_final": c_ht,
                  "H_T_gap_bits_per_token": round(c_ht - a_ht, 3) if c_ht else None,
                  "agent_H_T_falls_with_N": agent_rows[-1]["markov_H_T"] < agent_rows[0]["markov_H_T"]}}
    Path(ROOT / "evidence" / "results" / "epiplexity_corpus.json").write_text(json.dumps(result, indent=2))
    print("\nHEADLINE (Markov-3 observer, held-out cross-entropy):")
    print(f"  agent H_T   = {a_ht:.3f} bits/token")
    if c_ht:
        print(f"  random H_T  = {c_ht:.3f} bits/token  -> gap {c_ht - a_ht:+.3f} "
              f"({'agent more predictable' if a_ht < c_ht else 'no epiplexity edge'})")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    Na = [r["N"] for r in agent_rows]
    ax1.semilogx(Na, [r["markov_H_T"] for r in agent_rows], "o-", color="#cc6677",
                 label="ca_combo_v2 (Markov H_T)")
    ax1.semilogx(Na, [r["gzip_bits_per_token"] for r in agent_rows], "^--", color="#cc6677",
                 alpha=0.5, label="ca_combo_v2 (gzip/tok)")
    if ctrl_rows:
        Nc = [r["N"] for r in ctrl_rows]
        ax1.semilogx(Nc, [r["markov_H_T"] for r in ctrl_rows], "s-", color="#888888",
                     label="random null (Markov H_T)")
        ax1.semilogx(Nc, [r["gzip_bits_per_token"] for r in ctrl_rows], "v--", color="#888888",
                     alpha=0.5, label="random null (gzip/tok)")
    ax1.set_xlabel("corpus size N (games)"); ax1.set_ylabel("entropy H_T (bits / move-token)")
    ax1.set_title("Epiplexity entropy term vs corpus size\n"
                  "lower = bounded observer predicts play better")
    ax1.legend(fontsize=8); ax1.grid(alpha=0.25, which="both")
    ax2.loglog(Na, [r["two_part_markov_bits"] for r in agent_rows], "o-", color="#cc6677",
               label="ca_combo_v2")
    if ctrl_rows:
        ax2.loglog([r["N"] for r in ctrl_rows],
                   [r["two_part_markov_bits"] for r in ctrl_rows], "s-", color="#888888",
                   label="random null")
    ax2.set_xlabel("corpus size N (games)"); ax2.set_ylabel("two-part MDL  S_T + N·H_T  (bits)")
    ax2.set_title("Two-part MDL (program + entropy)")
    ax2.legend(fontsize=8); ax2.grid(alpha=0.25, which="both")
    fig.tight_layout()
    fig.savefig(ROOT / "evidence" / "figures" / "fig_epiplexity_corpus.png", dpi=150)
    print("[saved] evidence/results/epiplexity_corpus.json, evidence/figures/fig_epiplexity_corpus.png")


if __name__ == "__main__":
    main()
