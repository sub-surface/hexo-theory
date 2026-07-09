# `+₂` two-move CGT algebra — execution attempt, paused mid-build

> **Status (2026-07-08): PAUSED.** Leon reconsidered the execution approach
> partway through implementation and asked to stop, clean up, and redirect —
> this note exists so the research direction and the ideas aren't lost, not
> because the underlying research question (does HeXO's `+₂` two-move
> disjunctive-sum algebra diverge from ordinary Conway one-move sums?) was
> resolved or abandoned. Read this before picking the thread back up, whatever
> shape the next attempt takes.

## The ask

Push on [docs/theory/2026-05-09-cgt-research-program.md](2026-05-09-cgt-research-program.md)
item 1 (the `+₂` two-move disjunctive-sum algebra — HeXO's 1-2-2 turn rule lets
a turn split its two placements across components, which ordinary Conway
`G + H` sum theory doesn't model), with three execution constraints:

1. Write the solver in Rust/C++, not Python, for real search speed.
2. Benchmark against **SealBot** (github.com/Ramora0/SealBot, author "Ramora")
   — a real, independently-developed strong bot, as an external validity check
   uncorrelated with our own agents' blind spots.
3. Run compute on Modal, not locally (thermal constraints on Leon's hardware).

A full plan was written (`~/.claude/plans/fluttering-brewing-snowglobe.md` —
harness-local, not part of this repo) and approved, then paused during
implementation. What follows is what was learned along the way, kept because
it's real research value independent of whether the specific
Rust+Modal+SealBot-adapter execution shape is what gets built next.

## What was discovered (durable, keep regardless of direction)

### SealBot is already indirectly in this repo, and its interface is now confirmed

`papers/misc/hexbot-building-framework/opponents/ramora/ai.py` — inside a
vendored clone of a *different* rival framework (`Saiki77/hexbot-building-framework`,
home of the "Orca" bot, itself built for the same public game at
hexo.did.science) — is a Python snapshot of Ramora's algorithm: iterative-
deepening alpha-beta, Zobrist-hashed transposition table, quiescence/threat-
extension search, and a learned pattern-table evaluation. It was already
confirmed (by reading the code, not just the WebFetch summary) to play HeXO's
*exact* ruleset: infinite hex grid, axial `(q, r)`, Player A places 1 stone
then both alternate 2 per turn, 6-in-a-row across 3 axes.

The real repo (`https://github.com/Ramora0/SealBot`) was cloned fresh to
`../SealBot` (sibling to `../hexo`, **not** committed into `hexo-theory` —
no LICENSE file upstream, so it's kept local-only for research benchmarking,
never vendored into this repo's git history). It confirms:

- Current implementation is **C++ with a pybind11 binding** (`current/minimax_bot.cpp`,
  built via `python setup.py build_ext --inplace` → `minimax_cpp*.so`), not
  pure Python — the vendored Ramora snapshot is an earlier/parallel port.
- Algorithm: iterative-deepening alpha-beta, 729 ternary pattern evaluations
  over 6-cell windows, Zobrist TT, quiescence search for mate threats,
  candidate generation within hex-distance 2 — same family as the vendored
  reference, more developed.
- **Interface gotcha worth remembering**: `minimax_bot.cpp`'s
  `extract_game_state` does `item.second.is(PyA)` — an **identity check**
  against SealBot's own `game.Player.A` enum instance. Calling
  `MinimaxBot.get_move(game)` requires an actual instance of SealBot's own
  `game.HexGame`/`Player` classes, not just any duck-typed object with
  matching attribute names. Any future adapter must construct a real
  `SealBot/game.HexGame`, translating our board representation into it, not
  pass our own state object through.
- `.get_move(game)` returns a list of 1 or 2 `(q, r)` tuples (`pair_moves`
  behavior — it reasons about both stones of a turn jointly, same as the
  vendored reference). Any arena-style integration calling it once-per-stone
  (as `competition/arena.py`'s `Bot` interface does) needs a pair-caching
  wrapper, not two independent single-cell calls — decomposing a joint
  decision into two sequential ones would defeat the point of testing a bot
  whose strength comes from joint-turn reasoning (the same class of mistake
  that made `fast_tactical` passive in the 2026-07-06 bake-off, per
  [docs/theory/2026-07-06-search-regime-verdicts.md](2026-07-06-search-regime-verdicts.md)
  Phase-1 finding 3).

### Existing repo machinery that any future attempt should reuse, not rebuild

- `engine/cgt.py::component_summaries(game, player, min_temperature)` already
  computes disjoint connected components of the live-line incidence graph —
  exactly the component-finder the CGT program note's "first experiment" needs.
- `engine/isomorphisms.py::live_line_incidence`, `cube_coords`, `d6_transforms`,
  `canonical_board_key` — exact incidence graph + D6 symmetry reduction.
- `experiments/run_tau_lp_gap.py::mine_positions` — a working pattern for
  mining real mid-game positions from arena self-play with randomized openings.
- `results/modal_moves_python_8000.json` — an 8,000-game move corpus; replaying
  prefixes is a free source of realistic positions for any future sweep.
- `modal_app.py` / `modal_bakeoff.py` — established Modal patterns (rust_image
  via curl-rustup/maturin-build/pip-install, smoke-test-before-scale discipline,
  Wilson CIs computed once over pooled shard results).

### A working exact-solver design, built and validated, then removed

A Rust crate (`cgt_solver/`, PyO3 bindings, mirroring `hexo/hexgo-rs`'s
dependency versions — pyo3 0.28, rustc-hash 2) was built implementing an exact
solver for small bounded HeXO "local game" components: negamax with alpha-beta
over {Win, Loss, Draw}, and — the one design choice worth remembering even
without the code — **since the component's cell set is small and fixed
(≤32 cells), the transposition-table key can just be the raw occupancy
bitmask pair `(occ_p1, occ_p2, to_move)` directly, with no Zobrist hashing
needed.** That's a genuine simplification relative to how SealBot/the vendored
Ramora reference do it (they need Zobrist because their board is effectively
unbounded); ours doesn't, because the whole point of a "component" is that
it's small by construction.

The other design point worth keeping: **"isolated" and "joint" (the actual
`+₂` question) don't need to be two algorithms.** Solving one component alone
vs. solving the union of two components under the true splittable-turn rule is
the *same* solve function, called with a different cell-set argument (the
concatenation of both components' cells). The interesting research question
reduces to: does `solve(A ∪ B)` ever produce a different — better —
outcome than `max(solve(A), solve(B))` would predict, and can the divergent
cases be characterized?

All 6 unit tests passed (forced-win detection, full-board draw detection,
joint cell-union correctness, oversized-input rejection, honest
budget-exhaustion reporting). A live smoke test via `maturin develop` found
that an **isolated single empty 6-cell line, solved exactly under alternating
2-stone turns, is a draw** — which independently reproduces
[2026-07-06-search-regime-verdicts.md](2026-07-06-search-regime-verdicts.md)
§B's finding ("the isolated 1-D subgame is a trivial pairing draw") via a
completely different method (exhaustive game-tree search vs. a hand-written
pairing argument). Two independent methods agreeing on a nontrivial claim is
exactly the kind of cross-validation this repo's epistemics value — worth
citing even though the code that produced it is gone.

## What was cleaned up

- `hexo-theory/cgt_solver/` (the Rust crate above) — deleted. It was never
  committed to git (confirmed via `git status` before removal), so nothing
  is lost from version history; the design is preserved in this note instead.
- The `maturin develop`-installed `cgt_solver` dev package was uninstalled
  from the local `.venv`.
- `../SealBot` (the sibling clone) was **left in place** — it's inert
  reference material outside this repo's git tree, harmless to keep, and
  likely still useful if a future attempt benchmarks against SealBot in any
  form. Not vendored into `hexo-theory` regardless (no upstream LICENSE).

## Why paused

Leon flagged partway through implementation that he wasn't liking the
direction — this was a live redirect during coding, not a finding that
invalidated the approach. No verdict on Rust-vs-something-else, or
Modal-vs-something-else, or SealBot-as-benchmark-vs-not, should be read into
this pause. Next step is whatever direction Leon gives next.
