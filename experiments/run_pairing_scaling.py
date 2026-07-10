"""
n_crit(R) scaling analysis of the pairing-capacity phase diagram.

Re-analysis of evidence/results/pairing_capacity_phase_diagram.json (the Modal grid:
k x n_fronts x cluster_radius, 40 seeds/cell, produced by
modal_theory_sweep.py::pairing_sweep). Question, per
docs/theory/2026-07-08-pairing-thresholds-and-game-values.md 3.2b: how does
the critical front count n_crit (attacker win rate = 50% against the triaged
k-window pairing defense) scale with cluster radius R?

  - n_crit ~ R^0: pure COUNT limit -- the defender's global 2-stones/turn
    budget is the binding constraint, geometry irrelevant.
  - n_crit ~ R^1: perimeter-limited.
  - n_crit ~ R^2: constant critical DENSITY -- overload is a local
    overlap/packing phenomenon (windows sharing cells), consistent with the
    super-additive-temperature reading of the dense-cluster counterexample.

Output: evidence/results/pairing_scaling.json,
        evidence/figures/fig_pairing_scaling_curves.png (k=7 win-rate curves per R),
        evidence/figures/fig_pairing_scaling_ncrit.png (log-log n_crit vs R per k).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "evidence" / "results" / "pairing_capacity_phase_diagram.json"
# supplementary sweep (2026-07-09): n_fronts 60-200 at R=24,32, turns=450 --
# un-censors the k=7/k=13 R=24 cells and extends the radius range. Where a
# cell exists in both, the ext (longer-horizon) value wins; the turns
# mismatch (300 vs 450) slightly favours the attacker in ext cells, so the
# merged curves are conservative UPPER envelopes on n_crit only.
SRC_EXT = ROOT / "evidence" / "results" / "pairing_capacity_phase_diagram_ext.json"
OUT = ROOT / "evidence" / "results" / "pairing_scaling.json"

# dataviz reference palette (categorical order, light mode)
C = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"


def n_crit_interp(nf: list[int], wr: list[float]) -> float | None:
    """First 0.5 crossing by linear interpolation; None if never crossed."""
    for i in range(1, len(nf)):
        lo, hi = wr[i - 1], wr[i]
        if lo < 0.5 <= hi:
            t = (0.5 - lo) / (hi - lo)
            return nf[i - 1] + t * (nf[i] - nf[i - 1])
    return None


def main() -> None:
    d = json.loads(SRC.read_text())
    cells = list(d["phase_diagram"])
    if SRC_EXT.exists():
        cells.extend(json.loads(SRC_EXT.read_text())["phase_diagram"])
    ks = sorted({c["k"] for c in cells})
    radii = sorted({c["cluster_radius"] for c in cells})

    table: dict = {}
    for c in cells:  # later (ext) entries overwrite duplicates
        table[(c["k"], c["cluster_radius"], c["n_fronts"])] = c["attacker_win_rate"]

    ncrit: dict = {}
    nfs_all = sorted({key[2] for key in table})
    for k in ks:
        for R in radii:
            pts = [(n, table[(k, R, n)]) for n in nfs_all if (k, R, n) in table]
            ncrit[(k, R)] = n_crit_interp([p[0] for p in pts],
                                          [p[1] for p in pts])
    nfs = nfs_all

    # log-log fit n_crit ~ R^alpha per k (only radii with a real crossing)
    fits = {}
    for k in ks:
        pts = [(R, ncrit[(k, R)]) for R in radii if ncrit[(k, R)] is not None]
        if len(pts) >= 3:
            lx = np.log([p[0] for p in pts])
            ly = np.log([p[1] for p in pts])
            alpha, logc = np.polyfit(lx, ly, 1)
            resid = ly - (alpha * lx + logc)
            fits[k] = {"alpha": float(alpha), "c": float(math.exp(logc)),
                       "n_points": len(pts),
                       "rmse_log": float(np.sqrt((resid ** 2).mean()))}

    # ---- figure 1: win-rate curves vs n_fronts, one panel per k, series = R
    fig, axes = plt.subplots(1, len(ks), figsize=(3.1 * len(ks), 3.4),
                             sharey=True, facecolor="#fcfcfb")
    for ax, k in zip(axes, ks):
        ax.set_facecolor("#fcfcfb")
        for i, R in enumerate(radii):
            pts = [(n, table[(k, R, n)]) for n in nfs if (k, R, n) in table]
            if not pts:
                continue
            ax.plot([p[0] for p in pts], [p[1] for p in pts], color=C[i],
                    lw=2, marker="o", ms=4, label=f"R = {R}")
        ax.axhline(0.5, color=MUTED, lw=1, ls="--")
        ax.set_title(f"k = {k}", color=INK, fontsize=11)
        ax.set_xlabel("fronts n", color=MUTED)
        ax.grid(color=GRID, lw=0.6)
        ax.tick_params(colors=MUTED)
        for s in ax.spines.values():
            s.set_color(GRID)
    axes[0].set_ylabel("attacker win rate", color=MUTED)
    axes[0].legend(frameon=False, fontsize=8, labelcolor=INK)
    fig.suptitle("Triaged pairing defense vs dense multi-front attack "
                 "(40 seeds/cell)", color=INK, fontsize=12)
    fig.tight_layout()
    f1 = ROOT / "evidence" / "figures" / "fig_pairing_scaling_curves.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)

    # ---- figure 2: n_crit vs R, log-log, series = k, reference slopes
    fig, ax = plt.subplots(figsize=(5.6, 4.4), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for i, k in enumerate(ks):
        pts = [(R, ncrit[(k, R)]) for R in radii if ncrit[(k, R)] is not None]
        if not pts:
            continue
        xs, ys = zip(*pts)
        lbl = f"k = {k}"
        if k in fits:
            lbl += f"  (α = {fits[k]['alpha']:.2f})"
        ax.plot(xs, ys, color=C[i], lw=2, marker="o", ms=5, label=lbl)
    # reference slopes anchored at the smallest radius
    R0 = radii[0]
    y0 = min(v for v in ncrit.values() if v is not None)
    rr = np.array([radii[0], radii[-1]], dtype=float)
    ax.plot(rr, y0 * (rr / R0), color=MUTED, lw=1, ls=":",)
    ax.plot(rr, y0 * (rr / R0) ** 2, color=MUTED, lw=1, ls="--")
    ax.text(rr[-1], y0 * (rr[-1] / R0), " ∝R", color=MUTED, fontsize=9,
            va="center")
    ax.text(rr[-1], y0 * (rr[-1] / R0) ** 2, " ∝R²", color=MUTED, fontsize=9,
            va="center")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("cluster radius R", color=MUTED)
    ax.set_ylabel("critical front count  n_crit", color=MUTED)
    ax.set_title("Defender collapse scaling: n_crit(R)", color=INK)
    ax.grid(color=GRID, lw=0.6, which="both")
    ax.tick_params(colors=MUTED, which="both")
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    fig.tight_layout()
    f2 = ROOT / "evidence" / "figures" / "fig_pairing_scaling_ncrit.png"
    fig.savefig(f2, dpi=150)
    plt.close(fig)

    out = {
        "source": SRC.name,
        "ks": ks, "radii": radii, "n_fronts": nfs,
        "n_crit": {f"k{k}_R{R}": ncrit[(k, R)] for k in ks for R in radii},
        "loglog_fits": {f"k{k}": v for k, v in fits.items()},
        "interpretation": {
            "alpha~0": "global 2/turn budget binds (pure count)",
            "alpha~1": "perimeter-limited",
            "alpha~2": "constant critical density (local overlap/packing)",
        },
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k != "n_crit"}, indent=2))
    print("n_crit:", out["n_crit"])
    print(f"[saved] {OUT}, {f1.name}, {f2.name}")


if __name__ == "__main__":
    main()
