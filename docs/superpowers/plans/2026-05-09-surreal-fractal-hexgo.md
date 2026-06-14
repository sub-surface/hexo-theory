# Surreal Fractal HeXO Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add paper-facing surreal-value conjectures and a reproducible strategy-fractal generator whose patterns are verified against HeXO's length-6 win criterion.

**Architecture:** Put reusable lattice/fractal helpers in `engine/fractal_strategy.py`, keep rendering and JSON emission in `experiments/run_surreal_fractal.py`, and keep conjectural synthesis in `docs/theory/2026-05-09-surreal-fractal-conjectures.md`.

**Tech Stack:** Python 3.12, pytest, matplotlib, existing `HexGame`, `AXES`, `WIN_LENGTH`, and D6 helpers from `engine.isomorphisms`.

---

## File Map

- Create: `engine/fractal_strategy.py`
- Create: `tests/test_fractal_strategy.py`
- Create: `experiments/run_surreal_fractal.py`
- Create: `results/surreal_fractal_strategy.json`
- Create: `figures/fig_surreal_fractal_strategy.png`
- Create: `figures/fig_surreal_fractal_shells.png`
- Create: `docs/theory/2026-05-09-surreal-fractal-conjectures.md`
- Modify: `docs/ARTIFACTS.md`
- Modify: `results/README.md`
- Modify: `figures/README.md`

## Task 1: Verified Fractal Strategy Generator

**Files:**
- Create: `tests/test_fractal_strategy.py`
- Create: `engine/fractal_strategy.py`

- [x] **Step 1: Write failing tests**

Create tests that require:

```python
from engine import WIN_LENGTH
from engine.fractal_strategy import (
    generate_strategy_fractal,
    verify_fractal_wins,
    winning_lines_for_board,
)


def test_base_fractal_contains_verified_length_six_wins():
    fractal = generate_strategy_fractal(depth=0)
    assert fractal.depth == 0
    assert len(fractal.motifs) == 3
    assert all(len(motif.cells) == WIN_LENGTH for motif in fractal.motifs)
    assert verify_fractal_wins(fractal)


def test_deeper_fractal_grows_by_six_eisenstein_branches():
    fractal = generate_strategy_fractal(depth=2, inflation=5)
    levels = [motif.level for motif in fractal.motifs]
    assert levels.count(0) == 3
    assert levels.count(1) == 18
    assert levels.count(2) == 108
    assert len(fractal.shell_counts) == 3
    assert verify_fractal_wins(fractal)


def test_winning_line_detector_matches_generated_motifs():
    fractal = generate_strategy_fractal(depth=1)
    lines = winning_lines_for_board(fractal.board, player=1)
    motif_lines = {motif.cells for motif in fractal.motifs}
    assert motif_lines <= set(lines)
```

- [x] **Step 2: Run tests and confirm red**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_fractal_strategy.py -q -p no:cacheprovider
```

Expected: import failure for `engine.fractal_strategy`.

- [x] **Step 3: Implement generator**

Implement:

- `StrategyMotif(level, center, axis, cells)`
- `StrategyFractal(depth, inflation, board, motifs, centers_by_level, shell_counts)`
- `generate_strategy_fractal(depth=3, inflation=5, player=1)`
- `winning_lines_for_board(board, player=1)`
- `verify_fractal_wins(fractal)`

The generator should:

- start from center `(0, 0)`;
- place one six-stone motif along each of the three HeXO axes at every center;
- recursively create the next centers by translating each center in the six
  hex directions by `inflation ** (level + 1)`;
- use only player `1` stones, so it is a verified strategy pattern rather than a
  legal move-order transcript.

- [x] **Step 4: Run tests and confirm green**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_fractal_strategy.py -q -p no:cacheprovider
```

Expected: 3 passed.

## Task 2: Fractal Experiment And Figures

**Files:**
- Create: `experiments/run_surreal_fractal.py`
- Create: `results/surreal_fractal_strategy.json`
- Create: `figures/fig_surreal_fractal_strategy.png`
- Create: `figures/fig_surreal_fractal_shells.png`

- [x] **Step 1: Add experiment script**

The script should accept:

```text
--depth
--inflation
--quick
```

It should emit JSON containing:

- depth;
- inflation;
- stone count;
- motif count;
- verified winning-line count;
- shell counts;
- conjectural dimension estimate `log(6) / log(inflation)`;
- sample winning lines.

- [x] **Step 2: Smoke run**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" experiments\run_surreal_fractal.py --quick
```

Expected: writes JSON and two PNG figures in under two minutes.

## Task 3: Surreal Conjecture Note

**Files:**
- Create: `docs/theory/2026-05-09-surreal-fractal-conjectures.md`

- [x] **Step 1: Write paper-facing note**

Include:

- natural representation of positions as signed measures on `Z[omega]` plus
  turn phase and live-line hypergraph;
- why whole positions are not usually surreal numbers;
- local surrealization of forced components;
- two-handed `+_2` sum conjecture;
- candidate `lambda_HeXO` number;
- surreal Hahn-series heuristic for far-away threats;
- fractal strategy conjecture and falsifiable tests.

## Task 4: Ledger And Verification

**Files:**
- Modify: `docs/ARTIFACTS.md`
- Modify: `results/README.md`
- Modify: `figures/README.md`

- [x] **Step 1: Update ledgers**

Add rows for the new surreal/fractal module, tests, experiment, result, and figures.

- [x] **Step 2: Verify**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_fractal_strategy.py tests\test_cgt.py tests\test_isomorphisms.py tests\test_two_move_sum.py tests\test_cgt_sequences.py -q -p no:cacheprovider
& "C:\Program Files\Python312\python.exe" -m py_compile engine\fractal_strategy.py experiments\run_surreal_fractal.py
git diff --check
```

Expected: tests and compile pass; diff check has no whitespace errors.
