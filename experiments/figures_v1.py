"""
Generate figures from rigor_v1 results (and the earlier epiplexity_scan).

Outputs PNGs into evidence/figures/.
"""
from __future__ import annotations
import json, math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "evidence" / "results"
FIG = RES / "figures"
FIG.mkdir(exist_ok=True)

AGENT_ORDER = ["random", "greedy", "fork_a2", "fork_a4", "potgrad", "combo"]
AGENT_COLOR = {
    "random":  "#9e9e9e",
    "greedy":  "#1976d2",
    "fork_a2": "#43a047",
    "fork_a4": "#2e7d32",
    "potgrad": "#e65100",
    "combo":   "#b71c1c",
}


def load_rigor():
    p = RES / "rigor_v1.json"
    if not p.exists(): return None
    return json.loads(p.read_text())


def load_scan():
    p = RES / "epiplexity_scan.json"
    if not p.exists(): return None
    return json.loads(p.read_text())


# ── fig 1: scaling ─────────────────────────────────────────────────────────

def fig_scaling(data):
    if not data or "scaling" not in data:
        print("  (skip scaling — no data)")
        return
    sc = data["scaling"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    axes[0].set_title("Markov H_T (bits/token) vs N")
    axes[1].set_title("Markov S_T (bits) vs N")
    axes[2].set_title("gzip bits/token vs N")
    for name in AGENT_ORDER:
        if name not in sc: continue
        rows = sc[name]
        by_N = {}
        for r in rows:
            by_N.setdefault(r["N"], []).append(r)
        Ns = sorted(by_N)
        means = lambda key: [np.mean([r[key] for r in by_N[N]]) for N in Ns]
        stds  = lambda key: [np.std( [r[key] for r in by_N[N]]) for N in Ns]
        for ax, key in zip(axes, ["markov_H", "markov_S_bits", "gzip_bpt"]):
            m, s = np.array(means(key)), np.array(stds(key))
            ax.errorbar(Ns, m, yerr=s, marker="o", label=name,
                        color=AGENT_COLOR.get(name), capsize=3, lw=1.5)
    for ax in axes:
        ax.set_xscale("log")
        ax.set_xlabel("N (games)")
        ax.grid(alpha=0.3)
    axes[0].legend(loc="best", fontsize=8)
    axes[1].set_yscale("log")
    plt.tight_layout()
    out = FIG / "01_scaling.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  wrote {out}")


# ── fig 2: orderings ──────────────────────────────────────────────────────

def fig_orderings(data):
    if not data or "orderings" not in data:
        print("  (skip orderings — no data)")
        return
    ords = data["orderings"]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    order_names = ["temporal", "reverse", "radial_in", "radial_out", "axis", "d6_canonical"]
    for ax, corpus_name in zip(axes, list(ords.keys())):
        rows = ords[corpus_name]
        H = [rows[o]["H_T"] for o in order_names]
        Hs = [rows[o]["H_shannon_bits"] for o in order_names]
        x = np.arange(len(order_names))
        w = 0.4
        ax.bar(x - w/2, H,  w, label="Markov H_T", color="#1f77b4")
        ax.bar(x + w/2, Hs, w, label="Shannon H (unigram)", color="#999999", alpha=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(order_names, rotation=25, ha="right")
        ax.set_ylabel("bits/token")
        ax.set_title(f"{corpus_name} corpus — 6 orderings")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3, axis="y")
    plt.tight_layout()
    out = FIG / "02_orderings.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  wrote {out}")


# ── fig 3: pareto ─────────────────────────────────────────────────────────

def fig_pareto(data):
    if not data or "pareto" not in data:
        print("  (skip pareto — no data)")
        return
    p = data["pareto"]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, ref in zip(axes, p["ref_corpora"]):
        xs, ys, names = [], [], []
        for name in AGENT_ORDER:
            if name not in p["agents"]: continue
            row = p["agents"][name]
            h = row["H_T_on"].get(ref)
            if h is None: continue
            xs.append(row["prog_bytes"])
            ys.append(h)
            names.append(name)
        colors = [AGENT_COLOR.get(n, "#000") for n in names]
        ax.scatter(xs, ys, c=colors, s=90, zorder=3)
        for x, y, n in zip(xs, ys, names):
            ax.annotate(n, (x, y), xytext=(6, 4), textcoords="offset points", fontsize=9)
        # pareto frontier (lower is better on both axes)
        pts = sorted(zip(xs, ys))
        frontier_x, frontier_y = [], []
        best = float("inf")
        for x, y in pts:
            if y < best:
                frontier_x.append(x); frontier_y.append(y); best = y
        ax.plot(frontier_x, frontier_y, ls="--", color="grey", alpha=0.6, zorder=2,
                label="Pareto frontier")
        ax.set_xlabel("|P| — gzipped agent source (bytes)")
        ax.set_ylabel("H_T on " + ref + "-corpus (bits/move)")
        ax.set_title(f"Pareto: (|P|, H_T on {ref})")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9)
    plt.tight_layout()
    out = FIG / "03_pareto.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  wrote {out}")


# ── fig 4: matchup heatmap ─────────────────────────────────────────────────

def fig_matchups(data):
    if not data or "matchups" not in data:
        print("  (skip matchups — no data)")
        return
    m = data["matchups"]["matrix"]
    names = list(m.keys())
    n = len(names)
    win = np.zeros((n, n))
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if a == b:
                win[i, j] = np.nan
                continue
            games = m[a][b]["games"]
            if games:
                win[i, j] = m[a][b]["wins"] / games
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(win, cmap="RdBu_r", vmin=0, vmax=1)
    ax.set_xticks(range(n)); ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_yticks(range(n)); ax.set_yticklabels(names)
    ax.set_xlabel("opponent (B)")
    ax.set_ylabel("agent (A)")
    ax.set_title("A plays P1 vs B — winrate for A")
    for i in range(n):
        for j in range(n):
            if i == j: continue
            v = win[i, j]
            c = "white" if v < 0.3 or v > 0.7 else "black"
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color=c, fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.85)
    plt.tight_layout()
    out = FIG / "04_matchups.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  wrote {out}")


# ── fig 5: pareto from old scan (fallback if rigor has no pareto yet) ───────

def fig_scan_pareto(scan):
    if not scan or "pareto" not in scan:
        return
    pr = scan["pareto"]
    fig, ax = plt.subplots(figsize=(8, 6))
    xs, ys, names = [], [], []
    for name, v in pr.items():
        xs.append(v["prog_bytes"])
        ys.append(v["H_T_bits"])
        names.append(name)
    colors = [AGENT_COLOR.get(n, "#000") for n in names]
    ax.scatter(xs, ys, c=colors, s=100, zorder=3)
    for x, y, n in zip(xs, ys, names):
        ax.annotate(n, (x, y), xytext=(6, 4), textcoords="offset points", fontsize=10)
    pts = sorted(zip(xs, ys))
    fx, fy, best = [], [], float("inf")
    for x, y in pts:
        if y < best: fx.append(x); fy.append(y); best = y
    ax.plot(fx, fy, ls="--", color="grey", alpha=0.6, label="Pareto frontier")
    ax.set_xlabel("|P| (bytes)")
    ax.set_ylabel("H_T (bits/token)")
    ax.set_title("Pareto (from epiplexity_scan.json — legacy)")
    ax.grid(alpha=0.3)
    ax.legend()
    plt.tight_layout()
    out = FIG / "00_legacy_pareto.png"
    plt.savefig(out, dpi=130)
    plt.close()
    print(f"  wrote {out}")


def main():
    data = load_rigor()
    scan = load_scan()
    print(f"rigor loaded: {data is not None}   scan loaded: {scan is not None}")
    fig_scan_pareto(scan)
    fig_scaling(data)
    fig_orderings(data)
    fig_pareto(data)
    fig_matchups(data)


if __name__ == "__main__":
    main()
