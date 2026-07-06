"""
Candidate A of the 2026-07-05 search-regime handoff: the per-line transfer
matrix, built and diagonalized exactly -- with its scope corrected.

The automaton (states = current run descriptor) for one axis line:

  binary draw shift  -- {B, W} sequences with no 6-run of either colour
                        (a fully-contested line in a drawn game);
  ternary draw shift -- {E, B, W}, empties unconstrained, no 6-run of B or W.

Exact results (this script verifies numerically):

  * binary Perron eigenvalue = pentanacci constant ~ 1.965948 (largest root of
    x^5 = x^4 + x^3 + x^2 + x + 1: maximal runs are compositions into parts
    1..5, i.e. WIN_LENGTH - 1 forced directly by the ruleset). All conjugates
    lie inside the unit circle, so the entropy base IS a Pisot number.
  * ternary Perron eigenvalue ~ 2.9945 (barely below alphabet size 3: the
    no-6-run constraint removes almost no entropy once empties are allowed).

SCOPE CORRECTION (against the handoff brief, per its own instruction to check
the math): the brief proposed reading a quasicrystal inflation constant lambda
off this spectrum. That conflates two different operators. A TRANSFER matrix's
Perron eigenvalue is a growth rate of the number of legal words (topological
entropy base); a SUBSTITUTION matrix's Perron eigenvalue is a tile-inflation
multiplier. They coincide only for very special substitutions. The honest
route from this automaton to the Pisot conjecture is via Line B's forcing
atoms (candidate substitution tiles), not via this spectrum. Composing the
three axis automata into a global operator hits a second wall: the composite
object is a 2-D shift of finite type, and 2-D SFT entropies are not computable
from 1-D spectra in general (Hochman-Meyerovitch). Both hypotheses offered in
the brief (Kronecker composition, RG coupling) would need to evade that
barrier and neither does. So candidate A is delivered as: a correct 1-D
automaton + an exact Pisot entropy constant + a negative verdict on the
"compose to get lambda" step.

Falsifiable link kept alive: IF optimal-play corpora inherit per-line
substitution structure, the pentanacci constant (or a power/conjugate) should
appear in diffraction peak-position ratios. Checkable against
results/diffraction_p4.json peak tables without new theory.

Output: results/line_automaton.json, figures/fig_line_automaton_spectrum.png
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MAX_RUN = 5  # WIN_LENGTH - 1


def binary_transfer() -> np.ndarray:
    states = [(c, k) for c in (0, 1) for k in range(1, MAX_RUN + 1)]
    t = np.zeros((len(states), len(states)))
    for i, (c, k) in enumerate(states):
        for j, (c2, k2) in enumerate(states):
            if (c2 == c and k2 == k + 1) or (c2 != c and k2 == 1):
                t[i, j] = 1
    return t


def ternary_transfer() -> np.ndarray:
    states = [("E",)] + [(c, k) for c in "BW" for k in range(1, MAX_RUN + 1)]
    t = np.zeros((len(states), len(states)))
    for i, s in enumerate(states):
        for j, s2 in enumerate(states):
            if s2 == ("E",):
                t[i, j] = 1
            elif s != ("E",) and s2[0] == s[0] and s2[1] == s[1] + 1:
                t[i, j] = 1
            elif s2[1] == 1 and (s == ("E",) or s2[0] != s[0]):
                t[i, j] = 1
    return t


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")  # exact + instant anyway
    ap.parse_args()

    tb = binary_transfer()
    tt = ternary_transfer()
    ev_b = np.linalg.eigvals(tb)
    ev_t = np.linalg.eigvals(tt)
    lam_b = float(max(ev_b.real[np.abs(ev_b.imag) < 1e-9]))
    lam_t = float(max(ev_t.real[np.abs(ev_t.imag) < 1e-9]))

    # pentanacci polynomial x^5 - x^4 - x^3 - x^2 - x - 1
    roots = np.roots([1, -1, -1, -1, -1, -1])
    pent = float(max(roots.real[np.abs(roots.imag) < 1e-9]))
    conj_moduli = sorted(float(abs(r)) for r in roots if abs(r - pent) > 1e-9)

    results = {
        "binary_perron": lam_b,
        "pentanacci": pent,
        "binary_equals_pentanacci": bool(abs(lam_b - pent) < 1e-9),
        "pentanacci_conjugate_moduli": conj_moduli,
        "pentanacci_is_pisot": bool(all(m < 1 for m in conj_moduli)),
        "ternary_perron": lam_t,
        "readme_pisot_candidates": {"plastic": 1.324718, "golden": 1.618034,
                                    "tribonacci": 1.839287},
        "note_on_readme": "README labels ~1.3247 'tribonacci'; that value is "
                          "the plastic number -- tribonacci is ~1.8393",
        "scope": "Perron eigenvalue = entropy base of the line shift, NOT a "
                 "substitution inflation constant; see module docstring",
    }
    print(json.dumps(results, indent=2))
    out = ROOT / "results" / "line_automaton.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"[saved] {out}")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    th = np.linspace(0, 2 * np.pi, 200)
    ax.plot(np.cos(th), np.sin(th), "k--", lw=0.7, label="unit circle")
    ax.scatter(roots.real, roots.imag, s=45, color="#cc6677", zorder=3,
               label="pentanacci roots")
    ax.scatter(ev_t.real, ev_t.imag, s=18, color="#4477aa", alpha=0.6,
               label="ternary shift spectrum")
    ax.axhline(0, color="gray", lw=0.5); ax.axvline(0, color="gray", lw=0.5)
    ax.set_aspect("equal")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Line-automaton spectra: Perron root %.4f is Pisot\n"
                 "(all conjugates strictly inside the unit circle)" % pent)
    figp = ROOT / "figures" / "fig_line_automaton_spectrum.png"
    fig.savefig(figp, dpi=150, bbox_inches="tight")
    print(f"[saved] {figp}")


if __name__ == "__main__":
    main()
