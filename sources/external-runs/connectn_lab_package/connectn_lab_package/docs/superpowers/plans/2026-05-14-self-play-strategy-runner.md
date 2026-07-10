# Self-Play Strategy Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reproducible self-play corpus runner that compares many Hex Connect6 strategies and estimates finite-radius neural-network scale.

**Architecture:** Put reusable game generation, aggregation, and model-size estimation in `connectn_lab/self_play.py`. Put CLI file/figure/report generation in `examples/self_play_experiment.py`. Keep output JSON viewer-loadable through the existing `games` shape.

**Tech Stack:** Python dataclasses, existing `strategy_optimization` and `opening_optimality` modules, CSV/JSON, matplotlib for figures, pytest.

---

### Task 1: Tests

**Files:**
- Create: `tests/test_self_play.py`

- [ ] **Step 1: Write failing tests**

Create tests for `estimate_network_size`, `play_self_play_game`, `run_self_play_corpus`, `summarise_matchups`, and `game_to_viewer_record`.

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests\test_self_play.py`

Expected: import failure because `connectn_lab.self_play` does not exist.

### Task 2: Core Module

**Files:**
- Create: `connectn_lab/self_play.py`

- [ ] **Step 1: Implement dataclasses**

Add `SelfPlayConfig`, `SelfPlayRecord`, `StrategyMatchupSummary`, and `NetworkSizeEstimate`.

- [ ] **Step 2: Implement game runner**

Add `play_self_play_game` using existing `choose_strategy_move`, `position_metrics`, and `has_connect_win`.

- [ ] **Step 3: Implement corpus and summaries**

Add `run_self_play_corpus`, `summarise_matchups`, and `game_to_viewer_record`.

- [ ] **Step 4: Implement network estimates**

Add `estimate_network_size` and `network_size_sweep`.

- [ ] **Step 5: Verify tests**

Run: `python -m pytest tests\test_self_play.py`

Expected: all self-play tests pass.

### Task 3: CLI Experiment

**Files:**
- Create: `examples/self_play_experiment.py`

- [ ] **Step 1: Implement CLI**

Parse radius, radius-to, turns, candidate-limit, opening-limit, strategy lists, and output directory.

- [ ] **Step 2: Write artifacts**

Write JSON, CSV, figures, and README from the core module outputs.

- [ ] **Step 3: Smoke run**

Run: `python examples\self_play_experiment.py --radius 3 --turns 2 --candidate-limit 5 --opening-limit 2 --out self_play_results\smoke`

Expected: JSON, CSV, figures, and README are created.

### Task 4: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Compile check**

Run: `python -m py_compile connectn_lab\self_play.py examples\self_play_experiment.py`

- [ ] **Step 2: Full tests**

Run: `python -m pytest tests`

- [ ] **Step 3: Inspect smoke output**

Load `self_play_results\smoke\self_play_games.json` through `examples.game_viewer.load_games`.
