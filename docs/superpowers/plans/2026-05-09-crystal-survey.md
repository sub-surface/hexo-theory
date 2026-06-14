# Crystal Survey Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a less biased, multi-representation survey of large-scale HexGo crystal structure across agents, controls, recursive constructions, and symmetry metrics.

**Architecture:** Put reusable observables in `engine/crystal.py`; put data collection, Rust detection, controls, JSON, and figures in `experiments/run_crystal_survey.py`; put the exact-sum/symmetry-breaking conjectures in `docs/theory/2026-05-09-bounded-crystal-sum.md`.

**Tech Stack:** Python 3.12, pytest, numpy, matplotlib, torch-backed diffraction via `engine.diffraction`, existing theory agents through `experiments.harness.default_registry`.

---

## File Map

- Create: `engine/crystal.py`
- Create: `tests/test_crystal.py`
- Create: `experiments/run_crystal_survey.py`
- Create: `results/crystal_survey.json`
- Create: `figures/fig_crystal_survey_gallery.png`
- Create: `figures/fig_crystal_survey_metrics.png`
- Create: `figures/fig_crystal_survey_harmonics.png`
- Create: `figures/fig_crystal_survey_diffraction.png`
- Create: `figures/fig_crystal_survey_fractal_highres.png`
- Create: `docs/theory/2026-05-09-bounded-crystal-sum.md`
- Modify: `docs/ARTIFACTS.md`
- Modify: `results/README.md`
- Modify: `figures/README.md`

## Task 1: Crystal Observables

- [x] **Step 1: Write failing tests**

`tests/test_crystal.py` should assert that:

- a six-direction hex ring has high 6-fold harmonic moment;
- a full D6 orbit has perfect D6 Jaccard symmetry;
- a line has lower sector entropy than a hex ring;
- box-count dimension is positive for nonempty point sets.

- [x] **Step 2: Implement `engine/crystal.py`**

Functions:

- `axial_to_xy_cell(cell)`
- `hex_distance(cell)`
- `sector_counts(cells, n_sectors=6)`
- `sector_entropy(cells, n_sectors=6)`
- `harmonic_moments(cells, orders=range(1, 13))`
- `d6_jaccard(cells)`
- `box_count_dimension(cells, scales=(1, 2, 4, 8))`
- `delone_bounds(cells)`
- `crystal_observables(cells, diffraction_grid=64)`

## Task 2: Multi-Modal Survey Experiment

- [x] **Step 1: Implement `experiments/run_crystal_survey.py`**

The script should collect:

- self-play from agents: `random`, `greedy`, `potential`, `ca_combo_v2`, `mirror`;
- controls: random disc, hex patch, previous strategy fractal;
- optional Rust pure-MCTS samples when `hexgo.parallel_self_play` is importable.

The script should emit:

- `results/crystal_survey.json`;
- gallery plot;
- metrics heatmap;
- harmonic moment plot;
- Bragg99 bar plot;
- high-resolution fractal plot.

- [x] **Step 2: Add `--quick` mode**

Quick mode should run a small survey in under a few minutes.

## Task 3: Exact Sum / Busy Beaver Theory Note

- [x] **Step 1: Write `docs/theory/2026-05-09-bounded-crystal-sum.md`**

Include:

- exact Conway pregame recursion for finite HexGo positions;
- live-line infinite-sum representation over all length-6 APs;
- two-handed Bellman/Conway operator;
- beta-to-infinity partition sum as an optimal-play approximation;
- symmetry-breaking observables;
- busy-beaver-style specification complexity and strategic-depth definitions;
- experimental falsifiers.

## Task 4: Ledger And Verification

- [x] **Step 1: Update artifact docs**

Add the new script/result/figures/note to `docs/ARTIFACTS.md`, `results/README.md`,
and `figures/README.md`.

- [ ] **Step 2: Verify**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_crystal.py tests\test_fractal_strategy.py tests\test_cgt.py tests\test_isomorphisms.py tests\test_two_move_sum.py tests\test_cgt_sequences.py -q -p no:cacheprovider
& "C:\Program Files\Python312\python.exe" -m py_compile engine\crystal.py experiments\run_crystal_survey.py
git diff --check
```
