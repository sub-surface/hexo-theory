# HeXO Theory

Research lab for **HeXO**: infinite hexagonal Connect-6 on the Eisenstein
lattice `Z[omega]`. The sibling repo `../hexo` contains the production engine;
this repo contains the theory, experiments, arena bots, Modal runs, and
paper-facing evidence.

For the freshest handoff, read
[docs/2026-07-09-status-and-direction.md](docs/2026-07-09-status-and-direction.md).
For the durable synthesis, read [SPEC.md](SPEC.md). For current priorities, read
[DIRECTION.md](DIRECTION.md). This README is the external map and was updated
after the latest local commit trail ending at `efa8012`.

## The Game

HeXO is played on the infinite hex grid, identified with `Z[omega]`, where
`omega = exp(2*pi*i/3)`. The turn rule is **1-2-2**: Black places one opening
stone, then both players place two stones per turn. A player wins by occupying
six consecutive cells along any of the three Eisenstein unit axes:

```text
u1 = (1, 0)     q-axis
u2 = (0, 1)     r-axis
u3 = (1, -1)    diagonal axis
```

A win is a unit-step length-6 arithmetic progression in `Z[omega]`.

Strategy stealing still rules out a second-player win, but the empirical
first-player story has been corrected. The old thin Combo-v2 sample suggested a
Black edge, but later corpora do not support citing that as established:
`ca_combo_v2` over 8,000 Modal games shows Black at `0.479 [0.467, 0.492]` of
decisive games, and the 400-game `hexo_bot2` self-play corpus is near parity
(`204-196`) under 12-stone random openings. Strict first-player advantage remains
open.

## Current Findings

### 1. `hexo_bot2` is the current deliverable bot

[competition/hexo_bot2.py](competition/hexo_bot2.py) is a pure-Python,
stdlib-only fresh-start bot with the same `choose_move` interface as the
incumbent. It uses an incremental window-count board, exact hitting-set tactics
over brink windows, joint-pair depth-2+ alpha-beta, brink-resolution quiescence,
and strictly sound threat-space search.

Latest committed bake-off results:

| Pairing | Result | Evidence |
|---|---:|---|
| `hexo_bot2` vs vendored SealBot | **23-1** | `evidence/results/bakeoff_hexo_bot2_v3.json` |
| `hexo_bot2` vs incumbent `hexo_bot.py` | **20-4** | `evidence/results/bakeoff_hexo_bot2_v3.json` |
| `hexo_bot2` vs `fast_tactical` | **10-0** with 14 draws | `evidence/results/bakeoff_hexo_bot2_v1.json` |

Design and ablations:
[competition/2026-07-09-hexo-bot2-results.md](competition/2026-07-09-hexo-bot2-results.md).
The core lesson is that strength lives in exact tactics and fast search, not in
soft fork bonuses or weak-corpus evaluation mining.

### 2. Temperature is additive in the two-move sum algebra

For disjoint collinear fragments under the balanced `(2:2)` turn rule, the exact
solver found:

```text
draw-draw union wins iff h(A) + h(B) >= 3
```

This held with **zero exceptions across 40,785 exact solves**. It is the cleanest
local algebra result in the repo so far and gives a paper-ready bridge between
combinatorial game theory and HeXO's two-stone turn rule.

Evidence:
[experiments/run_two_move_sum.py](experiments/run_two_move_sum.py),
`evidence/results/two_move_sum_full.json`, and
[docs/theory/2026-07-09-empirical-theory-sweep.md](docs/theory/2026-07-09-empirical-theory-sweep.md).

### 3. Strong play carries an arithmetic fingerprint

Strong `hexo_bot2` self-play suppresses the `F7` split-prime residue structure
factor at matched stone count, while not suppressing the mod-3 control. This
matters because length-6 windows in `Z[omega]` interact cleanly with the split
prime over 7: every 6-window carries six distinct `F7` residues and misses one.

Headline: strong play suppresses `I7` versus random (`p = 2.4e-4`) and versus
weak `ca_combo_v2` (`p = 1.2e-6`), but shows no mod-3 suppression (`p = 0.72`).

Evidence:
[experiments/run_spatial_order.py](experiments/run_spatial_order.py),
`evidence/results/spatial_order.json`, and
`evidence/figures/fig_spatial_order_*.png`.

### 4. Cheap reactive defenses are not enough

The exact hitting-set reactive defense shuts out the scripted multi-front
attacker suite at `k=6`, up to 120 dense fronts. But the same defense loses
**24-0, zero draws** to `hexo_bot2`.

The interpretation is now sharper than the earlier pairing/capacity notes:
pre-committed disjoint fronts only add heat at a coverable rate, while adaptive
search stacks windows through shared cells and creates hitting-set demand faster
than a bounded reactive rule can discharge.

Evidence:
[experiments/run_residue_defense.py](experiments/run_residue_defense.py),
`evidence/results/residue_defense_sweep.json`,
`evidence/results/bakeoff_residue_blocker.json`.

### 5. Collapse scaling and local entropy are more subtle than the old story

Dense-front defender collapse scales as approximately:

```text
n_crit(R) ~ R^alpha, alpha ~= 0.6-0.9
```

This excludes both constant-density and pure-count mechanisms. It points to a
mixed phenomenon: local window-overlap packing plus stochastic synchronization
against the defender's global two-stone budget.

Patch entropy is also non-monotone in strength at radius 1:

```text
weak 7.87 bits < strong 8.76 bits < random 9.04 bits
```

So "stronger play is always more locally ordered" is false. Strong play is more
locally diverse than weak play while still below random.

Evidence:
[experiments/run_pairing_scaling.py](experiments/run_pairing_scaling.py),
`evidence/results/pairing_scaling.json`,
[experiments/run_spatial_order.py](experiments/run_spatial_order.py).

### 6. Epiplexity/Pisot remains promising but not settled

The long-range conjecture remains:

> Perfect play in HeXO may produce a D6-symmetric, aperiodic, quasi-crystalline
> pattern with finite substitution structure and a Pisot-like inflation law.

The best current evidence is methodological rather than conclusive:

- Gzip/MDL proxy on the 8,000-game `ca_combo_v2` corpus gives
  `S_T(N) ~ N^0.929`, separated from random at `N^1.009`.
- A Markov observer measurement gives agent `H_T` falling from **9.30 to 6.68
  bits/token**, while the random null stays flat around **7.91 bits/token**.

This supports learnable strategic structure, but it does not identify a
substitution system or prove a Pisot inflation constant. The single-axis
no-6-run transfer matrix gives the pentanacci constant, which is an entropy base
for a 1-D proxy, not yet the 3-axis HeXO inflation constant.

Evidence:
[experiments/run_mdl_scaling.py](experiments/run_mdl_scaling.py),
[experiments/run_epiplexity_corpus.py](experiments/run_epiplexity_corpus.py),
[docs/theory/2026-07-08-hexanacci-and-mdl-policy-prior.md](docs/theory/2026-07-08-hexanacci-and-mdl-policy-prior.md).

## Recent Commit Trail

- `efa8012` - 2026-07-08/09 sessions: `hexo_bot2`, SealBot bake-offs, additive
  temperature law, spatial-order theory sweep.
- `3a40dde` - search-regime pivot: candidate verdicts, Modal bake-off,
  Programme D MDL proxy.
- `75f7b4e` - arena fork-term fix and DIRECTION findings.
- `9a677e0` - DIRECTION.md, competition arena, and final `hexo` rename cleanup.
- `05c3583` - consolidated SPEC.md.

## What To Work On Next

The active research program is no longer "train a stronger neural CA and hope
the global pattern clarifies." The center is:

1. Exact local algebra: temperature, hitting sets, tau-pressure, and
   two-placement sums.
2. Adaptive search: why `hexo_bot2` beats defenses that scripted attackers
   cannot.
3. Arithmetic signatures: which residue/quotient structures survive strong play.
4. Epiplexity as measurement: use it to detect learnable structure, not as a
   substitute for the local forcing mechanism.

Immediate queue from the latest handoff:

- Fix `(p:q)` heat to use p-relative brink definitions and rerun `(1:1)`.
- Generate bent/interleaved two-axis fragments to find the super-additivity
  boundary beyond the collinear additive law.
- Build a Beck-null model for the observed `n_crit(R)` scaling.
- Extract win-depth families toward Hamkins-style transfinite values.
- Cross-check split-prime extinction on other lattices.

## Repository Map

```text
hexo-theory/
  README.md                         this map
  SPEC.md                           durable findings and confidence levels
  DIRECTION.md                      current priorities
  docs/
    2026-07-09-status-and-direction.md
    ROADMAP.md
    theory/                         working theory notes
  engine/                           reusable theory layer
  experiments/                      reproducible experiment entrypoints
  competition/                      arena, deliverable bots, opponent adapters
  apps/
    desktop/                        PySide dashboard and widgets
    marimo/                         interactive notebooks
  cloud/modal/                      Modal entrypoints and image factories
  evidence/
    results/                        JSON/CSV outputs
    figures/                        PNG/GIF figures
    corpora/                        raw/self-play corpora
    games/                          raw trajectories
  sources/
    literature/                     PDFs and source notes
    bundles/                        original external zip bundles
    external-runs/                  extracted/generated provenance bundles
```

Prefer `paths.py` for new path constants. New experiments should write summaries
to `evidence/results/` and figures to `evidence/figures/`.

## Useful Commands

```powershell
python competition/hexo_bot2.py
python -m pytest tests -q
python -m compileall engine experiments competition apps tools cloud paths.py
```

For Modal runs, use the entrypoints under `cloud/modal/`, for example:

```powershell
modal run cloud/modal/modal_bakeoff.py::screen
```

## References

- Finzi et al. (2026). *From Entropy to Epiplexity*.
- Hamkins and Leonessi (2022). *Infinite Hex is a draw*.
- Berlekamp, Conway, Guy (1982). *Winning Ways*.
- Beck and Erdos-Selfridge biased positional-game theory.
- Baake and Grimm (2013). *Aperiodic Order*.
- Bode-Harborth achievement games and k-in-a-row threshold literature.
