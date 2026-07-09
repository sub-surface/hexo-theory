# Building the strongest possible HeXO bot — fresh-start brief

This document is meant to be the ENTIRE context for a new session tasked with
building the strongest possible HeXO-playing bot. It is deliberately written
to give you the rules, the deliverable spec, and everything empirically
learned so far — without prescribing an architecture. Read all of it before
writing any code or picking a language/search paradigm. Where prior work
reached a conclusion, it's stated as a fact to build on; where prior work
made a PROCESS mistake (not a wrong conclusion, a wrong way of working), it's
stated as a pitfall to avoid, not as a reason to avoid the underlying idea.

Reason from principles. Don't assume the previous session's architecture
(iterative-deepening alpha-beta with a hand-tuned linear evaluation) is the
right one just because it's what was tried — it may well be right, but you
should arrive at that conclusion yourself if you do, not inherit it.

---

## 1. The game, exactly

HeXO ("hex" + "connect-6", also called Hex Tic-Tac-Toe / Connect-6 in some
of this repo's reference material) is played on an **infinite hexagonal
lattice**, isomorphic to the Eisenstein integers $\mathbb{Z}[\omega]$.

- **Coordinates**: axial $(q, r)$, both integers, unbounded in every
  direction. A third coordinate $s = -q-r$ is sometimes used (cube
  coordinates) but is redundant with $(q, r)$.
- **Adjacency**: each cell has 6 neighbors, offset by
  $(1,0), (-1,0), (0,1), (0,-1), (1,-1), (-1,1)$.
- **Win lines**: there are exactly **3 axis directions** a line can run
  along: $(1,0)$, $(0,1)$, $(1,-1)$ (each also extends in its negation,
  giving 3 undirected lines through any cell, not 6).
- **Win condition**: **6 stones in an unbroken row**, same color, along any
  one of the 3 axes. (`WIN_LENGTH = 6`, not configurable — it's asserted
  deep in the upstream engine.)
- **Turn structure ("1-2-2")**: Player 1 places a **single** stone on the
  very first move of the game. From then on, **every** turn (both players,
  including player 1's second turn onward) places **exactly 2 stones**.
  This is the single most important rule to get right in any move-search
  logic — code that assumes plain 1-1 alternation (like standard
  tic-tac-toe or Gomoku) will misplay badly.
- **No captures.** A placed stone is permanent. The board only grows;
  positions are monotonically increasing sets. There is no life-and-death,
  no removal, no "resolving" a local fight the way Go does.
- **Legal moves**: any unoccupied cell on the (conceptually infinite)
  board. There is no adjacency requirement for legality — a player may
  place a stone anywhere, including far from all existing stones. (Move-
  generation heuristics that only consider cells near existing stones are
  a *search-space-narrowing choice*, not a game rule — see pitfall list
  below for a real bug this caused.)
- **Draws**: in principle the game is infinite and needn't ever end; in
  practice every test harness in this repo imposes a `max_moves` cutoff
  and calls anything that reaches it a draw. This is a testing artifact,
  not a rule — don't over-read "draw" results from bounded self-play as
  evidence the true infinite game is drawn (see `docs/theory/` for the
  Hamkins-style discussion of this, optional background, not required).

This is structurally a **placement game** (nothing ever moves or is
removed), closer in spirit to Go or Gomoku/Connect-6 than to Chess.

---

## 2. The deliverable

- **Goal**: the strongest bot you can build to play a real match against an
  external opponent — described by the person you're building this for as
  "a 100-simulation MCTS, AlphaZero-style" bot that is already beating a
  real reference engine called SealBot. You do not have direct access to
  that opponent; you have a **real, vendored copy of SealBot** to benchmark
  against instead (see Resources, below) — treat beating SealBot decisively
  as a meaningful bar, not necessarily as "done, ship it."
- **Interface**: something equivalent to
  `choose_move(stones: dict[(int,int), int], turn: int, placed_this_turn: int, stones_per_turn: int) -> (int, int)`
  — pure/stateless, called once per stone placement (so twice per normal
  turn), given the full current board. `stones_per_turn` is 1 only for the
  game's very first placement, 2 always thereafter. The receiving team has
  their own agent and said they can adapt whatever interface you hand them
  — don't over-invest in interface compatibility guesswork, but do document
  your assumptions clearly (axis convention, win length, turn rule) so a
  silent mismatch can be caught quickly.
- **Time budget**: not precisely known — assume something on the order of
  ~1 second per move as a working target, but make the actual budget an
  explicit, easy-to-change parameter, and make sure your search degrades
  gracefully (never overruns) rather than assuming a specific number is
  correct.
- **Delivery form**: whatever you conclude is best after reasoning about
  it — a single portable file, a compiled extension, etc. Don't assume "one
  Python file" or "a Rust binary" is preordained; that's exactly the kind
  of early, unexamined commitment this brief is trying to help you avoid.

---

## 3. What has been empirically validated (treat as facts to build on)

These were established through actual testing (unit tests, controlled
ablations, or real matches against the vendored SealBot), not intuition.
They're facts about *this game*, not endorsements of any particular
codebase or language.

1. **A cheap forced draw does not exist.** No periodic pairing/covering
   defensive strategy exists that guarantees a draw for the defender on
   this lattice (proven for the relevant window-length thresholds below
   $k=7$; a $k=7$, turn-aware candidate defense was also computationally
   falsified — it fails under sufficiently dense, simultaneous multi-front
   attacks). **Passive/defensive play has no theoretical backing here** —
   there is no known way to "just survive." A strong bot should play to
   win.
2. **Comparing your move against the opponent's best *static* reply is
   actively worse than no search at all.** A tested bot using this
   approach (score = my move's heuristic value minus the opponent's best
   one-ply-static heuristic reply) lost even to a bot with no search
   whatsoever, because it systematically punishes sharp/aggressive play
   (a strong threat also raises the position's raw heuristic score, which
   the opponent's "best reply" search then sees and over-penalizes). If
   you build any form of lookahead, make sure it evaluates the actual
   resulting position after real (not one-sided-static) continuation, not
   a comparative delta against a static reply.
3. **A specific "1-2-2 aware" turn-structure atomic tactic is exact and
   computable**: a line with 4 of 6 cells already filled by one player,
   live (no opponent stone in it), is an **unconditional win within a
   single turn** for that player — even though no *single* placement
   completes it, both of that turn's two placements do. Symmetrically, if
   a player holds two or more such "brink" lines that cannot be jointly
   covered by the opponent's 2 placements this turn, the opponent is in a
   **proven, unconditional forced loss**, regardless of anything else on
   the board. This is exact (not heuristic) and cheap to compute (a linear
   scan over existing stones' windows). It is the single most concrete,
   validated piece of game-specific structure discovered so far.
4. **A narrow move-ordering "beam" search can get WORSE, not better, as you
   search deeper, if it isn't tactically complete.** A tested bot that did
   real iterative-deepening minimax over the correct 1-2-2 turn structure,
   with a plausible-looking evaluation, but which only considered a
   narrow top-k (~5) candidates at every node (ranked by a static
   heuristic) and had **no exact check for the tactic in point 3**, LOST
   24 games to 0 against a much simpler, shallower (fixed ~4-ply) bot —
   in a controlled test, at TWO different heuristic-feature configurations
   (with and without an extra soft "double-threat" bonus term), with
   identical results either way. The deeper bot was visiting *more* total
   search nodes (confirmed by wall-clock: its games ran 4-5x longer), not
   fewer — so this was not a "too little search" problem. This is a real,
   measured instance of the classic *minimax pathology / horizon effect*:
   depth amplifies a systematic blind spot in the evaluation/candidate-
   generation rather than smoothing it out. **Whatever search you build,
   make sure a forced tactical continuation (win, block, or unblockable
   fork) can never be silently excluded from the candidates actually
   considered at any node**, at any depth — don't rely on a static
   heuristic ranking alone to surface these.
5. **Adding the exact check from point 3 to the search from point 4 (at
   every node, not just the root) produced a bot that beat the real
   vendored SealBot 28 wins to 2 losses** (30 games, randomized openings,
   1.0s move budget, Wilson 95% CI [0.79, 0.98] on the decisive share).
   This is real signal that exact tactical completeness matters a lot;
   it is NOT proof that the rest of that bot's architecture (iterative
   deepening, the specific linear evaluation, the top-k=5 beam width) is
   optimal — only that fixing the blind spot from point 4 was necessary
   and sufficient to reach a real, external, decisive win rate.
6. **A soft heuristic "fork bonus" (rewarding positions with 2+
   simultaneous near-complete lines, as a scoring term rather than an
   exact check) was ablated and found to make no measurable difference** —
   turning it fully on or fully off against the same opponent gave
   identical results (24-0 both ways) in the test from point 4. It's not
   established that this kind of term is worthless in general, only that
   *this specific implementation* wasn't what was fixing anything — point
   3's *exact* version was.

---

## 4. Open, unresolved questions — don't assume an answer either way

1. **Internal roster ranking vs. external validation disagree.** In a large
   (1260+ game) internal round-robin among several of this project's own
   bots (all sharing the same basic architecture family), a shallower
   fixed-depth searcher beat the deeper, tactically-complete searcher from
   point 5 above by a real margin (roughly 103-110 wins vs 52-73, across
   variants) — even *after* the point-3 exact-tactics fix was added to the
   deeper bot. Yet that same deeper/tactically-complete bot is the one that
   beat the real external SealBot 28-2. It is genuinely unclear whether
   this means (a) the shallower bot would do even better against SealBot,
   (b) internal round-robins among similar-family bots aren't representative
   of strength against a structurally different opponent, or (c) something
   else. This has not been tested — do not assume either bot is "the strong
   one" without checking directly.
2. **A real external reference engine (SealBot) does things this project's
   bots don't yet do at all**, observed by reading its actual source (a
   genuine, independently-developed Connect-6-family engine, not written
   for this project): it searches the two stones of a turn as a **joint
   pair** (not two sequential independent single-stone choices), maintains
   an incrementally-updated transposition table, extends search via
   **quiescence** (keeps searching past the nominal depth limit while
   tactically "loud," only evaluates statically once a position is
   "quiet"), and evaluates leaves via a **pattern-value table mined from
   data** rather than a hand-written formula. None of these have been
   tried in this project yet. It is not established which, if any, would
   help most — they're plausible, not proven.
3. **Whether a learned/mined evaluation would actually help is a real open
   question, not a safe assumption either way.** This project has an
   ~8000-game self-play corpus sitting unused, and also has a documented
   history of a *different* learned-value approach (a neural network value
   head) failing for identifiable, specific reasons (severe class imbalance
   on drawn/neutral positions, sparse positive labels for real threats) —
   that failure doesn't automatically indict a simpler mined lookup table
   over interpretable local patterns (a fundamentally different object,
   different failure mode), but it hasn't been tried, so don't assume it's
   free money either.

---

## 5. Process pitfalls from prior work — avoid repeating the *mistake*, not the *idea*

These are about *how the work was done*, not about which architecture is
correct. Read them as engineering-process warnings.

1. **Maintaining the same search/evaluation logic in two languages at once,
   growing new features in lockstep, caused real, silent divergence** —
   including one caught-by-luck cross-language test disagreement on a
   greedy clustering heuristic (different hash-map iteration order between
   the two languages broke a test that happened to sit on an exact
   boundary value). If you need high performance AND fast iteration, decide
   deliberately how you'll avoid two-implementations-drifting — e.g. commit
   to one language and only reach for a second when you have a specific,
   validated reason, or build a hard, automatic cross-check (identical
   inputs, identical outputs, asserted, in CI/test) from the very first
   feature, not retrofitted after several features already exist in both.
2. **When adapting between two different engines' internal representations,
   a silent type mismatch (an enum vs. a raw int that never compares
   equal) made an entire adapter path semantically inert** without raising
   any exception — the adapted engine's every internal check silently saw
   "no threats anywhere," and this was only caught by directly exercising
   the adapter on a few known positions before trusting it at scale. Any
   time you bridge two independent codebases/engines, write a small, direct
   test that inspects actual behavior on a known position — don't trust
   that "it ran without crashing" means it's semantically correct.
3. **Two engines had different implicit assumptions about what counts as a
   "legal search candidate"** — one only ever proposed cells immediately
   adjacent to existing stones, the other (the real external reference
   engine) legitimately considered a wider radius. A test harness that
   validated "legality" against the narrower engine's candidate list
   silently forfeited the wider engine's genuinely legal moves as
   "illegal," which would have invisibly crippled it in benchmarking. When
   building any legality/validity check in a shared test harness, ground it
   in the actual game rule (any unoccupied cell, per Section 1), not in
   whatever heuristic candidate-narrowing your own search happens to use
   internally.
4. **A plausible-sounding evaluation feature was shipped without being
   ablated against a no-feature baseline**, and turned out (see Section 3,
   point 6) to do nothing measurable — while the actual bug (Section 3,
   point 4) went unnoticed for a while because it was easy to attribute a
   bad bake-off result to "needs more tuning" rather than "there's a
   structural blind spot." **Any new evaluation or search feature should be
   ablated (on vs. off, same opponent, real sample size, ideally with a
   Wilson/binomial confidence interval) before being trusted or combined
   with other new features.** Don't stack multiple untested changes and
   then try to interpret one aggregate result.
5. **External engines' own internal time-management can't be assumed
   reliable.** When integrating the real external SealBot for benchmarking,
   its own per-move time target was occasionally overrun by a large,
   unpredictable margin on some positions (consistent with coarse internal
   time-checking, structurally the same class of bug as pitfall 4 above,
   just in someone else's code) — enough that, combined with genuinely
   long, well-contested games, a batch of matches ran into cloud-function
   timeouts and (worse) a naive "cancel the whole batch if one input
   fails" default silently discarded results from every other in-flight
   game too. If you benchmark against any external or third-party engine,
   (a) don't trust its stated time budget as a hard guarantee, (b) put a
   generous but firm wall-clock ceiling on any individual match from your
   own side, and (c) make sure a single failed/slow match can't cancel or
   invalidate the rest of a batch.
6. **Depth is not free, and "deeper" is not automatically "better," per
   Section 3 point 4** — before spending effort on making search go deeper
   (via a faster language, more compute, etc.), make sure whatever depth
   you do reach is *tactically complete* at every node it visits. A fast,
   deep, blind search can be strictly worse than a slower, shallow, exact
   one.

---

## 6. Resources available (facts, not instructions to use them)

- This repository (`hexo-theory/`) has a **pure-Python, numpy-vectorized**
  rules engine and bot framework at `competition/arena.py`, including a
  round-robin/Wilson-CI bake-off harness (`modal_bakeoff.py`) and several
  previously-built bots of varying strength for comparison.
- A sibling repository (`../hexo`) contains a **compiled Rust engine**
  (`hexgo-rs`, PyO3 bindings) with an undo-stack-based board representation
  (no per-move cloning), already wired up to build cleanly inside a Modal
  container (Linux, unambiguous Python version) — building it *locally* on
  this Windows machine has been unreliable (`maturin`/py-launcher
  environment issues); Modal has been the reliable path for testing any
  Rust-based approach.
- **Modal** (cloud compute) is available with a substantial budget,
  including **GPU-attached containers** — useful for anything genuinely
  parallel/throughput-bound (e.g., mining statistics from a self-play
  corpus, batched self-play generation), not obviously useful for the
  search itself (classical alpha-beta-style search is latency-bound and
  sequential, a poor GPU fit; MCTS with batched leaf evaluation is a
  better GPU fit if that's the direction you go).
- **Local hardware is slow and prone to overheating** — prefer Modal for
  anything beyond a quick, small, few-second correctness check.
- An **~8000-game self-play corpus** already exists
  (`results/modal_moves_python_8000.json`), unused for any pattern-mining
  or data-driven evaluation work so far.
- A **real, vendored copy of SealBot** (an independently-developed
  Connect-6-family engine, not written for this project) is available at
  `papers/misc/hexbot-building-framework/opponents/ramora/` — pure Python,
  no compiled dependencies, directly runnable and readable. Use it both as
  a benchmark opponent and as a source of genuine, working ideas (see
  Section 4, point 2) — but verify anything you borrow from it by testing,
  not by assuming its design choices transfer.
- This project also has a body of **game-theoretic and descriptive-set-
  theoretic research** (`docs/theory/`, `SPEC.md`, `DIRECTION.md`) about
  HeXO's structure — pairing-strategy impossibility results, locality
  arguments, complexity-theoretic positioning. Section 3's point 3 (the
  exact brink/fork tactic) came out of that line of work. It's optional
  background if you want it, not a required foundation for building a
  strong bot — don't feel obligated to adopt its framing or priorities for
  this specific task.

---

## 7. How to proceed

This is process guidance, not architecture guidance:

1. Before writing search/evaluation code, **decide deliberately** what
   language(s) and what overall approach you're committing to, and why —
   and prefer commitments that avoid Section 5's pitfalls (especially
   pitfall 1: don't grow two parallel implementations without a clear plan
   for keeping them honest).
2. Build correctness tests for anything exact (win detection, the brink/
   fork tactic, any other exact check you add) using small, hand-verified
   positions, before trusting it in a real game.
3. Validate any new heuristic or search feature via **ablation** (on vs.
   off, same opponent, real sample size) before combining it with other
   changes or trusting a bake-off result that used it.
4. Use small, cheap, local/quick checks to catch obvious bugs; move to
   Modal for anything resembling a real tournament or statistical
   validation.
5. Benchmark against the real vendored SealBot, not only against this
   project's own bot roster (Section 4, point 1's disagreement is exactly
   why relying on only one of these would be a mistake).
6. Define "done" as: a single, clearly-documented deliverable, with its
   assumptions about the opponent's rules/interface stated explicitly, that
   has beaten SealBot by a real, statistically meaningful margin under a
   realistic time budget — not "passes local smoke tests" and not "beat
   one internal bot once."
