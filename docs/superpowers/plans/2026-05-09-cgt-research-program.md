# CGT Research Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Conway/Sloane/Hackenbush thread into reproducible HeXO theory experiments without losing existing data.

**Architecture:** Keep `hexgo-theory` as the research lab and `hexgo` as the production engine. New theory primitives land under `hexgo-theory/engine/`, reproducible scripts under `hexgo-theory/experiments/`, JSON/CSV summaries under `hexgo-theory/evidence/results/`, and PNGs under `hexgo-theory/evidence/figures/`.

**Tech Stack:** Python 3.12, pytest, numpy, matplotlib, existing HeXO engine re-exported through `engine/__init__.py`.

---

## File Map

- Modify: `hexgo-theory/.gitignore`
- Create: `hexgo-theory/docs/ARTIFACTS.md`
- Create: `hexgo-theory/evidence/results/README.md`
- Create: `hexgo-theory/evidence/figures/README.md`
- Create: `hexgo-theory/docs/theory/2026-05-09-cgt-research-program.md`
- Create: `hexgo/docs/research/07_hexgo_theory_bridge.md`
- Create: `hexgo-theory/engine/isomorphisms.py`
- Create: `hexgo-theory/tests/test_isomorphisms.py`
- Create: `hexgo-theory/engine/two_move_sum.py`
- Create: `hexgo-theory/tests/test_two_move_sum.py`
- Create: `hexgo-theory/experiments/run_cgt_sequences.py`
- Create: `hexgo-theory/evidence/results/cgt_sequences.json`
- Create: `hexgo-theory/evidence/results/cgt_sequences.csv`
- Create: `hexgo-theory/evidence/figures/fig_cgt_sequences.png`

## Task 1: Preservation-First Cleanup

**Files:**
- Modify: `hexgo-theory/.gitignore`
- Create: `hexgo-theory/docs/ARTIFACTS.md`
- Create: `hexgo-theory/evidence/results/README.md`
- Create: `hexgo-theory/evidence/figures/README.md`
- Create: `hexgo-theory/docs/theory/2026-05-09-cgt-research-program.md`
- Create: `hexgo/docs/research/07_hexgo_theory_bridge.md`

- [x] **Step 1: Write the research program note**

Add `docs/theory/2026-05-09-cgt-research-program.md` with:

```markdown
# HeXO CGT Research Program

The key new object is the two-move sum: after the opening, HeXO is not an
ordinary disjunctive sum of hot local games because each turn has two placements.
```

- [x] **Step 2: Add artifact ledger**

Add `docs/ARTIFACTS.md` with the current CGT result/script/figure triples and
preservation rules.

- [x] **Step 3: Add result and figure README files**

Add short README files describing naming and regeneration policy.

- [x] **Step 4: Reduce generated-status noise without deleting data**

Add these ignore rules:

```gitignore
pytest-cache-files-*/
.claude/worktrees/
__marimo__/
evidence/corpora/
games/
evidence/results/charlies-artifacts/
```

- [x] **Step 5: Add main-engine bridge note**

Add `../hexgo/docs/research/07_hexgo_theory_bridge.md` explaining that theory
features flow into production only after a primitive, experiment, result, and
figure exist in `hexgo-theory`.

- [x] **Step 6: Verify preservation**

Run:

```powershell
git status --short
```

Expected: only docs, `.gitignore`, and existing unrelated research changes show;
no delete markers appear.

## Task 2: Exact Combinatorial Isomorphisms

**Files:**
- Create: `engine/isomorphisms.py`
- Create: `tests/test_isomorphisms.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_isomorphisms.py`:

```python
from engine import HexGame
from engine.analysis import threat_cells
from engine.isomorphisms import (
    canonical_board_key,
    cube_coords,
    d6_transforms,
    live_line_incidence,
    transform_board,
)


def test_cube_coordinates_sum_to_zero():
    assert cube_coords((3, -5)) == (3, -5, 2)
    assert sum(cube_coords((3, -5))) == 0


def test_d6_transforms_have_twelve_symmetries_off_axis():
    assert len(set(d6_transforms((2, 1)))) == 12


def test_canonical_board_key_identifies_rotated_copy():
    board = {(0, 0): 1, (1, 0): 1, (2, -1): 2}
    transformed = transform_board(board, transform_index=3)
    assert canonical_board_key(board) == canonical_board_key(transformed)


def test_live_line_incidence_exposes_threat_cell():
    game = HexGame()
    for q in range(5):
        assert game.make(q, 0)
    inc = live_line_incidence(game)
    assert (5, 0) in inc.empty_to_lines
    assert (5, 0) in threat_cells(game, player=1)
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_isomorphisms.py -q
```

Expected: import failure for `engine.isomorphisms`.

- [x] **Step 3: Implement minimal module**

Create `engine/isomorphisms.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from engine import AXES, WIN_LENGTH, HexGame

Cell = tuple[int, int]
Board = Mapping[Cell, int]


@dataclass(frozen=True)
class IncidenceGraph:
    lines: tuple[tuple[Cell, ...], ...]
    empty_to_lines: dict[Cell, tuple[int, ...]]
    line_to_empty: tuple[tuple[Cell, ...], ...]


def cube_coords(cell: Cell) -> tuple[int, int, int]:
    q, r = cell
    return (q, r, -q - r)


def _from_cube(x: int, y: int, z: int) -> Cell:
    assert x + y + z == 0
    return (x, y)


def _cube_transforms(x: int, y: int, z: int) -> tuple[tuple[int, int, int], ...]:
    return (
        (x, y, z),
        (-z, -x, -y),
        (y, z, x),
        (-x, -y, -z),
        (z, x, y),
        (-y, -z, -x),
        (y, x, z),
        (-z, -y, -x),
        (x, z, y),
        (-y, -x, -z),
        (z, y, x),
        (-x, -z, -y),
    )


def d6_transforms(cell: Cell) -> tuple[Cell, ...]:
    return tuple(_from_cube(*c) for c in _cube_transforms(*cube_coords(cell)))


def transform_cell(cell: Cell, transform_index: int) -> Cell:
    return d6_transforms(cell)[transform_index]


def transform_board(board: Board, transform_index: int) -> dict[Cell, int]:
    return {transform_cell(cell, transform_index): player for cell, player in board.items()}


def canonical_board_key(board: Board) -> tuple[tuple[int, int, int], ...]:
    if not board:
        return ()
    keys = []
    for idx in range(12):
        transformed = transform_board(board, idx)
        min_q = min(q for q, _ in transformed)
        min_r = min(r for _, r in transformed)
        normalized = sorted((q - min_q, r - min_r, p) for (q, r), p in transformed.items())
        keys.append(tuple(normalized))
    return min(keys)


def _line_cells(start: Cell, axis: Cell) -> tuple[Cell, ...]:
    q, r = start
    dq, dr = axis
    return tuple((q + i * dq, r + i * dr) for i in range(WIN_LENGTH))


def live_line_incidence(game: HexGame) -> IncidenceGraph:
    seen: set[tuple[int, int, int]] = set()
    lines: list[tuple[Cell, ...]] = []
    line_to_empty: list[tuple[Cell, ...]] = []
    empty_to_lines_tmp: dict[Cell, list[int]] = {}
    for sq, sr in game.board:
        for axis_idx, axis in enumerate(AXES):
            dq, dr = axis
            for offset in range(WIN_LENGTH):
                start = (sq - offset * dq, sr - offset * dr)
                key = (axis_idx, start[0], start[1])
                if key in seen:
                    continue
                seen.add(key)
                cells = _line_cells(start, axis)
                players = {game.board[c] for c in cells if c in game.board}
                if len(players) > 1:
                    continue
                empties = tuple(c for c in cells if c not in game.board)
                idx = len(lines)
                lines.append(cells)
                line_to_empty.append(empties)
                for cell in empties:
                    empty_to_lines_tmp.setdefault(cell, []).append(idx)
    empty_to_lines = {c: tuple(v) for c, v in empty_to_lines_tmp.items()}
    return IncidenceGraph(tuple(lines), empty_to_lines, tuple(line_to_empty))
```

- [x] **Step 4: Run tests and confirm pass**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_isomorphisms.py -q
```

Expected: 4 passed.

## Task 3: Two-Move Sum Toy Algebra

**Files:**
- Create: `engine/two_move_sum.py`
- Create: `tests/test_two_move_sum.py`

- [x] **Step 1: Write failing tests**

Create `tests/test_two_move_sum.py`:

```python
from engine.two_move_sum import Component, best_one_move_sum, best_two_move_sum


def test_two_lukewarm_components_can_beat_one_hot_component():
    components = (
        Component("hot", moves=(10.0,)),
        Component("warm_a", moves=(6.0,)),
        Component("warm_b", moves=(6.0,)),
    )
    assert best_one_move_sum(components).score == 10.0
    best = best_two_move_sum(components)
    assert best.score == 12.0
    assert best.components == ("warm_a", "warm_b")


def test_two_move_sum_allows_spending_both_moves_in_one_component():
    components = (
        Component("ladder", moves=(7.0, 6.5)),
        Component("single", moves=(8.0,)),
    )
    best = best_two_move_sum(components)
    assert best.score == 13.5
    assert best.components == ("ladder", "ladder")
```

- [x] **Step 2: Run tests and confirm failure**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_two_move_sum.py -q
```

Expected: import failure for `engine.two_move_sum`.

- [x] **Step 3: Implement minimal toy algebra**

Create `engine/two_move_sum.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Component:
    name: str
    moves: tuple[float, ...]


@dataclass(frozen=True)
class Choice:
    components: tuple[str, ...]
    score: float


def best_one_move_sum(components: tuple[Component, ...]) -> Choice:
    best = max(((c.name, c.moves[0]) for c in components if c.moves), key=lambda item: item[1])
    return Choice((best[0],), float(best[1]))


def best_two_move_sum(components: tuple[Component, ...]) -> Choice:
    choices: list[Choice] = []
    for i, first in enumerate(components):
        if not first.moves:
            continue
        for j, second in enumerate(components):
            if i == j:
                if len(first.moves) < 2:
                    continue
                choices.append(Choice((first.name, first.name), first.moves[0] + first.moves[1]))
            elif second.moves:
                names = tuple(sorted((first.name, second.name)))
                choices.append(Choice(names, first.moves[0] + second.moves[0]))
    return max(choices, key=lambda choice: choice.score)
```

- [x] **Step 4: Run tests and confirm pass**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_two_move_sum.py -q
```

Expected: 2 passed.

## Task 4: Sloane-Style Sequence Mining

**Files:**
- Create: `experiments/run_cgt_sequences.py`
- Create: `evidence/results/cgt_sequences.json`
- Create: `evidence/results/cgt_sequences.csv`
- Create: `evidence/figures/fig_cgt_sequences.png`

- [x] **Step 1: Create experiment script**

Use existing helpers from `engine.cgt`, `engine.analysis`, and
`experiments.harness.default_registry`. The script must expose:

```python
DEFAULT_AGENTS = ["random", "greedy", "potential", "ca_combo_v2", "mirror"]
```

It must collect per-sampled-ply sequences:

```python
{
    "ply": ply,
    "agent": agent_name,
    "live_lines": len(live_line_records(game)),
    "hot_components": summary["component_count"],
    "max_temperature": summary["top_temperature"],
    "thermal_entropy": summary["thermal_entropy"],
    "candidate_count": summary["candidate_count"],
}
```

- [x] **Step 2: Add a quick mode**

The command:

```powershell
& "C:\Program Files\Python312\python.exe" experiments\run_cgt_sequences.py --quick
```

Expected: finishes in under two minutes and writes all three outputs.

- [x] **Step 3: Run focused smoke**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" experiments\run_cgt_sequences.py --agents random greedy --n-games 1 --max-moves 36 --sample-stride 6
```

Expected: `evidence/results/cgt_sequences.json`, `evidence/results/cgt_sequences.csv`, and
`evidence/figures/fig_cgt_sequences.png` exist and contain both agents.

## Task 5: Verification And Research Decision

**Files:**
- Read: `evidence/results/cgt_sequences.json`
- Read: `evidence/results/cgt_hackenbush.json`
- Modify: `docs/ARTIFACTS.md`

- [x] **Step 1: Run tests**

Run:

```powershell
& "C:\Program Files\Python312\python.exe" -m pytest tests\test_cgt.py tests\test_isomorphisms.py tests\test_two_move_sum.py -q
```

Expected: all focused tests pass.

- [x] **Step 2: Update artifact ledger**

Add `cgt_sequences` rows to `docs/ARTIFACTS.md`.

- [ ] **Step 3: Choose next paper section**

Decision rule:

- If the 2-move model predicts strong-agent choices better than scalar
  temperature, next section is "Two-Move Thermography".
- If D6 motif/sequence counts stabilize cleanly first, next section is
  "A Sloane Catalog For HeXO".
- If neither separates strong from random play, pivot to coding-theory blockers.
