# HeXO CGT Research Program

*2026-05-09*

> **Status (2026-07-05): PARKED (research programme), but its repo-hygiene
> principles are still the standard.** The CGT/Hackenbush/`+₂`-algebra
> conjectures below are speculative and untested (see [SPEC.md](../../SPEC.md)
> §6) — not on the critical path until the τ/Pisot spine converges or is
> falsified. The "preservation first, never delete, index before moving"
> philosophy in the Repository Cleanup Plan below is exactly what the
> 2026-07-05 docs pass followed (status headers added, nothing moved or
> deleted) — that part of this note remains load-bearing.

This note turns the Conway/Sloane/Hackenbush discussion into an execution plan for
the two sibling repositories:

- `../hexgo` is the production engine: rules, AlphaZero training, Rust MCTS, GPU
  inference, dashboard, and model checkpoints.
- `../hexgo-theory` is the research lab: theory notes, experiments, JSON results,
  figures, corpora, and paper-facing synthesis.

The guiding rule is preservation first. Generated data is not clutter until it has
an index, a provenance story, and a decision attached to it. Cleanup therefore
means "make the research state legible" before it means "move files around".

## Current State To Learn From

The current theory repo already contains enough material for a serious empirical
CGT program:

- `engine/analysis.py` has live-line, threat, fork, potential, and fingerprint
  primitives. These are the existing low-level observables.
- `engine/cgt.py` adds the first Hackenbush-like temperature layer over live
  6-line components.
- `experiments/run_cgt_hackenbush.py` measures whether agents play in hot local
  games, whether heat decomposes into components, and whether Erdos-Selfridge
  potential tracks urgency.
- `results/cgt_hackenbush.json` and `figures/fig_cgt_hackenbush_*.png` show the
  first empirical split: stronger agents play high-temperature moves, while
  potential and temperature are correlated but not identical.
- `docs/ROADMAP.md` already frames the wider work through epiplexity, MDL, and
  the Pisot/quasicrystal conjecture.
- `docs/theory/2026-04-17-hamkins-synthesis.md` supplies the falsifiable P1-P5
  table and the descriptive-set-theoretic positioning.

The immediate lesson is that HeXO should be treated as a positional game on a
6-uniform hypergraph, with three compatible quotients:

1. The exact hypergraph quotient: cells are vertices, length-6 axial windows are
   winning hyperedges.
2. The symmetry quotient: D6 identifies positions and motifs up to hex-lattice
   rotations/reflections.
3. The tactical quotient: live-line incidence components behave like hot
   Hackenbush stalks, except the 1-2-2 rule gives each non-opening turn two
   placements, so ordinary disjunctive-sum CGT must be replaced by a 2-move sum.

That last point is the new object worth naming.

## Interest-Ordered Program

### 1. Two-Move Thermographic Algebra

This is the most original direction. Ordinary CGT studies `G + H`, where a player
chooses one component and moves there. HeXO after the opening is closer to a
compound operator `G +_2 H`: a player may spend both placements in one component
or split them across two components.

Conjecture: many HeXO tactical positions are not sums of hot games, but
two-token sums of hot games. This predicts behaviors that ordinary Hackenbush
does not model:

- two lukewarm components can combine into a move that outranks one hotter local
  component;
- double threats are not merely "two threats" but positions whose value changes
  discontinuously under the two-token turn rule;
- defending can be optimal when it preserves the option to split the next move
  across two components.

First experiment:

- Build a toy evaluator for small finite live-line components.
- Compare ordinary one-move sum choices with `+_2` choices.
- Feed sampled HeXO positions from `results/cgt_hackenbush.json` through both
  scoring rules and measure which model better predicts strong-agent moves.

Expected falsifier: if ordinary one-component temperature predicts moves as well
as the 2-move operator, the new algebra is not doing work.

### 2. Exact Combinatorial Isomorphisms

Before adding more measurements, make the quotients explicit.

Planned module:

- `engine/isomorphisms.py`

Core functions:

- `cube_coords(cell)`: axial `(q, r)` to A2 cube coordinates `(q, r, -q-r)`.
- `d6_transforms(cell)`: the 12 hex-lattice symmetries.
- `canonical_board_key(board)`: D6-canonical representation for motif mining.
- `winning_windows(cells)`: enumerate relevant length-6 hyperedges.
- `live_line_incidence(game)`: exact bipartite graph between live lines and cells.

Tests should prove:

- D6 transforms preserve win detection.
- Canonical keys identify rotated/reflected copies.
- Incidence graph cells agree with `engine.analysis.threat_cells`.
- The Hackenbush component projection in `engine.cgt` is a quotient of the exact
  incidence graph, not a separate ad hoc graph.

This is less flashy than the 2-move algebra, but it is the foundation that makes
Sloane-style sequence mining and paper diagrams defensible.

### 3. Sloane Mode: Integer Sequences From Self-Play

Sloane's instinct would be to ask: "What are the sequences?" For every game
prefix, emit integer invariants whose early terms can be inspected, regressed,
clustered, and compared across agents.

Candidate sequences:

- number of live 6-lines;
- number of D6-canonical local motifs by radius;
- hot component count;
- maximum component temperature;
- number of cells tied for maximum temperature;
- thermal entropy numerator after rational binning;
- fork count by axis profile;
- D6 orbit count of legal candidates;
- MDL proxy length of the canonical move prefix;
- diffraction peak count above threshold.

First experiment:

- Add `experiments/run_cgt_sequences.py`.
- Output `results/cgt_sequences.json` and `results/cgt_sequences.csv`.
- Plot `figures/fig_cgt_sequences.png` with per-agent trajectories.

Expected falsifier: if canonical motif counts grow linearly without stabilization
or recurrence across all strong agents, the finite-substitution/Pisot story is
weakened.

### 4. Threat Thermographs

The temperature map is currently a scalar heuristic. The next CGT step is a
thermograph-like profile: how does a local component's value change as the
temperature threshold is cooled?

First experiment:

- For sampled components, sweep `min_temperature`.
- Track when components split, vanish, or merge.
- Compare strong-agent moves to component cooling breakpoints.

Expected falsifier: if cooling breakpoints do not distinguish strong from random
play, thermography is decorative rather than explanatory.

### 5. Coding-Theory And Covering Bounds

The defensive side of HeXO resembles a covering-code problem on the A2 lattice:
block every length-6 arithmetic progression with as few stones as possible.

First experiment:

- On finite radius balls, solve or greedily approximate minimum blockers for all
  length-6 windows.
- Compare blocker density to actual White stones in strong-agent games.

Expected falsifier: if strong defensive play has no relationship to low-density
blocker covers, the coding-theory analogy is weak.

### 6. Pisot/Diffraction Cross-Check

This remains the paper-facing long arc. Use the CGT observables to choose better
positions for diffraction and epiplexity scans.

First experiment:

- Condition diffraction measurements on high thermal entropy versus concentrated
  heat.
- Ask whether Bragg peaks strengthen when the tactical game decomposes cleanly.

Expected falsifier: if Bragg intensity is independent of CGT decomposition, the
quasicrystal and Hackenbush stories may be parallel narratives rather than one
mechanism.

### 7. Main Engine Feedback

Only feed theory back into `../hexgo` when an observable survives falsification.

Candidate feedback paths:

- D6 canonical motif features as replay-buffer diagnostics.
- 2-move temperature as an auxiliary policy target.
- hot-component count as a curriculum signal for self-play.
- blocker-cover density as an evaluation feature for White.

Rule: no production-engine feature should land from theory unless it has a JSON
result and a figure in `hexgo-theory`.

## Repository Cleanup Plan

### Phase 0: Preservation Index

Status: start now.

Actions:

- Add this research program note.
- Update `.gitignore` to hide generated caches, local worktrees, marimo runtime
  state, and corpora.
- Do not delete or move any research artifacts.
- Create a tracked artifact ledger that lists important result/figure/script
  triples and identifies which untracked directories are generated data.

### Phase 1: Theory Repo Structure

Keep the existing layout:

- `engine/` for reusable theory primitives;
- `experiments/run_*.py` for one reproducible experiment each;
- `results/` for tracked JSON/CSV summaries;
- `figures/` for tracked PNG outputs;
- `docs/theory/` for synthesis notes;
- `papers/` for source PDFs;
- `corpora/`, `data/`, `artifacts/`, `checkpoints/` for generated heavy data.

Add only indexes and manifests at first:

- `docs/ARTIFACTS.md`: human-readable provenance index.
- `results/README.md`: result naming and regeneration policy.
- `figures/README.md`: figure naming and source-result mapping.

No moving until those docs make it obvious what is duplicate, stale, or orphaned.

### Phase 2: Main HeXO Repo Structure

Keep `../hexgo` focused on the playing/training system.

Recommended additions:

- `docs/research/HEXGO_THEORY_BRIDGE.md`: explain how theory results are allowed
  to flow into production heuristics.
- Link to `../hexgo-theory/docs/theory/2026-05-09-cgt-research-program.md`.
- Avoid copying theory experiment outputs into the main engine repo.

### Phase 3: Reproducibility Pass

For every experiment we keep:

- it has a `--quick` mode;
- it writes one JSON/CSV result under `results/`;
- it writes one or more PNGs under `figures/`;
- the JSON contains config, seed, git commit if available, wall time, and summary;
- the script can regenerate the named outputs without hidden notebook state.

### Phase 4: Archive Without Loss

Only after the ledger is complete:

- mark stale outputs as superseded in docs;
- if moving is useful, move with `git mv` when tracked and plain `Move-Item` when
  untracked;
- never delete raw corpora, checkpoints, or game records unless they have a
  verified copy elsewhere and the user explicitly approves deletion.

## Next Concrete Steps

1. Create `docs/ARTIFACTS.md` in `hexgo-theory`.
2. Implement `engine/isomorphisms.py` with tests.
3. Implement the toy `+_2` evaluator and compare it to the current scalar
   temperature model.
4. Add sequence mining as `experiments/run_cgt_sequences.py`.
5. Use the sequence results to decide whether the next paper section should be
   "2-move thermography" or "Sloane-style invariant catalog".

The deliberately Conway-ish slogan for the next week is:

> Do not ask whether HeXO is Hackenbush. Ask which quotient of HeXO becomes
> Hackenbush, and which part refuses because each turn has two hands.
