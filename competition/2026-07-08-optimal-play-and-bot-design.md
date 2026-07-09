# What we actually know about optimal HeXO play, and what it implies for a tournament bot

> Written before building the bot, per the ask: reason first, then build.
> Synthesizes today's theory work plus the existing bake-off history
> (`docs/theory/2026-07-06-search-regime-verdicts.md`,
> `docs/theory/2026-07-08-pairing-thresholds-and-game-values.md`,
> `competition/arena.py`).

## 1. What's actually established

- **No cheap forced draw exists.** No pairing strategy exists for 6-in-a-row
  on the hex lattice at all (proven, `run_pairing_bound.py`), and today's
  deeper pass shows the *next* candidate (k=7, turn-aware) also fails under
  dense multi-front attack. There is no known "safe" passive strategy that
  provably survives forever. Empirically this matches: strong self-play is
  heavily decisive, not drawish (Hamkins-echo experiments, SPEC.md §5). **A
  tournament bot should play to win, not to survive** — passivity has no
  theoretical backing here.
- **Search beats static heuristics, but only if the search is shaped right.**
  The clearest result in the whole programme: `fast_tactical` (score my move
  minus the opponent's best *static* reply) was **worse than no search at
  all** — it lost to plain `greedy_offence`, because scoring against a static
  reply punishes sharp play (a strong threat *raises* the opponent's own
  potential score, since defending it usually means building near your
  stones too). `fast_minimax` fixed this by searching the *actual* alternate
  -turn structure (my remaining placements, then the opponent's real
  2-placement turn, with exact win detection at every node) and it beat
  everything else in Phase 2. **Lesson: depth only helps if the tree shape
  matches the real 1-2-2 turn rule and leaves are evaluated by true
  minimax outcome, not a one-sided static comparison.**
- **Fork/τ-pressure is real but was never actually combined with search.**
  Reading `fast_minimax_d1.1`'s code closely (not just its bake-off score):
  its move ordering (`top_candidates`) and its leaf evaluation (`board_eval`)
  both use *pure* Erdős–Selfridge potential (`4^own_stones` summed over live
  windows) with **no fork term at all** — the τ>2 double-threat bonus that
  `make_fork_aware` uses is simply absent from the champion. This matters
  because pure potential summation actually *undervalues* forks relative to
  single deep threats: two independent 4-stone lines sum to `2×4⁴=512`,
  while one 5-stone line alone is `4⁵=1024` — a real fork can score *lower*
  than a single, single-cell-blockable threat. The only reason this hasn't
  visibly hurt `fast_minimax` yet is that its search *sees* the tactics a
  fork creates a few plies down (an unblockable double threat shows up as a
  won position at the leaf) — but a fork just past the search horizon is
  invisible to it. **This is free strength sitting on the table.**
- **Defence weight has a real, already-measured sweet spot.** The ladder
  (1.0, 1.1, 1.3, 1.6, 2.0) is flat across 1.0–1.6 and measurably worse at
  2.0 (DIRECTION.md). Don't over-defend.
- **Threats are local, and there's no cheap way to manufacture a distant
  one.** Today's gestation-time lemma: any τ>2 obligation needs a hard-floor
  number of stones (roughly a handful of near-complete windows), so a single
  far-away placement can never force anything by itself. Search doesn't need
  to hedge against sudden distant tactics; the frontier of existing stones is
  where the real fight is.
- **Time budget is the binding constraint, and overrunning it is worse than
  playing shallower.** The arena's own design (`competition/arena.py:11-13`):
  a bot that exceeds its per-move budget forfeits the placement to a
  fallback (nearest legal cell) — an unpredictable, often terrible move.
  `fast_minimax`'s time check (`soft_deadline_s`) only fires *between* root
  candidates, not inside the recursion — a single expensive branch can blow
  well past budget before the check ever sees it. **A tournament bot must
  never risk an overrun**, which argues for genuine iterative deepening with
  a check inside the search itself, not a coarse root-level guard.
- **No exploitable opening is known, and no reliable first/second-mover
  edge is established.** The radius-3 opening tablebase found no decisive
  verdict (`papers/.../opening_tablebase_results`, all "U"). P1 advantage
  is actively contested — one large `ca_combo_v2` corpus even points slightly
  the *other* way (SPEC.md P1, second-mover edge, 🟡). **Don't build in an
  opening book or a seat-dependent strategy we don't have real evidence
  for** — tune and validate the bot symmetrically as both P1 and P2.

## 2. What this implies for the bot

1. Keep the exact win/block root guarantees — free, correct, cheap.
2. Keep the true alternate-turn minimax shape (`fast_minimax`'s proven
   structure), not a static-reply comparison.
3. **Add the fork/τ-surplus term to both move ordering and leaf evaluation**
   — the clearest, cheapest, most theoretically-motivated gap found today.
4. **Replace the coarse root-level time check with real iterative deepening**
   — search depth 1, verify time remains, go to depth 2, etc., always
   returning the best move found at the last *completed* depth. This uses
   the time budget better AND removes the overrun risk that the current
   champion carries.
5. Keep defence weight near the already-validated 1.1–1.3 band.
6. Validate any change against `fast_minimax_d1.1` at real sample size
   (randomized openings, enough games for a Wilson CI that actually
   separates from a null) before calling it an improvement — this
   programme's history (the squared-fork-term bug, the `fast_tactical`
   passivity defect) is a repeated lesson that an untested "obviously
   better" heuristic idea is not reliably better in practice.

## 3. What actually happened when we validated it (2026-07-08, part 2)

Point 6 above was not idle caution — `deep_minimax` (the bot built from §2's
plan: fork/τ term in ordering + leaf eval, real iterative deepening, in-
recursion time check) **lost badly** in its first large validation.

### 3.1 The bake-off result

`modal_bakeoff.py::screen --openings 30 --bots deep_minimax_d1.{1,2,3},
fast_minimax_d1.{1,4},heuristic_d1.1,fork_aware_d1.2` (1260 games,
`results/deep_minimax_validation.json`):

| bot | wins |
|---|---|
| `fast_minimax_d1.1` | 62 |
| `fast_minimax_d1.4` | 61 |
| `deep_minimax_d1.1` | 34 |
| `deep_minimax_d1.2` | 29 |
| `deep_minimax_d1.3` | 28 |
| `heuristic_d1.1` | 20 |
| `fork_aware_d1.2` | 10 |

`deep_minimax` — deeper search, fork-aware ordering and eval, safer time
handling — lost head-to-head to the shallower, fork-blind `fast_minimax`
(e.g. `deep_minimax_d1.1` vs `fast_minimax_d1.1`: 7–16). It also took
**4–5× longer per game** (mean ~220–270s vs ~35–60s): `deep_minimax`
was consistently burning its *entire* 0.70s-per-move budget via iterative
deepening, while `fast_minimax`'s fixed 4-ply search finished almost
instantly. So the loss wasn't for lack of raw search effort. A second,
independent signal pointed the same direction: `fork_aware_d1.2` (the
plain heuristic with the same fork/τ bonus, no search) was the *weakest*
non-random bot in the whole roster — below even plain `heuristic_d1.1`,
despite DIRECTION.md having flagged the fork term as "the single
highest-value upgrade."

### 3.2 Root cause: isolating the fork term

Two live hypotheses: (a) the fork/τ bonus term itself is miscalibrated or
buggy, or (b) something about the iterative-deepening search architecture
is the problem, independent of which eval features it uses. A controlled
local ablation separated them: `make_deep_minimax(fork_bonus=0.0)` makes
the fork term multiply out to exactly zero in both move ordering and leaf
eval, collapsing the formula to `fast_minimax`'s — while keeping iterative
deepening. 24 games/pairing, random openings
(`results/fork_ablation_diagnostic.json`):

| matchup | result |
|---|---|
| `fast_minimax_d1.1` vs `deep_minimax_fork` (bonus=60) | 24–0 |
| `fast_minimax_d1.1` vs `deep_minimax_nofork` (bonus=0) | 24–0 |
| `deep_minimax_fork` vs `deep_minimax_nofork` | 12–12 |

Clean result: removing the fork term entirely made **no difference**
(24–0 either way; the two deep_minimax variants tied against each other).
Hypothesis (a) is dead. The architecture itself was the bug.

### 3.3 The actual mechanism, found by reading SealBot's source

`deep_minimax` visits *more* nodes than `fast_minimax` (per §3.1's timing),
yet plays worse — the signature of *minimax pathology* / the horizon
effect: both bots prune every node down to a narrow top-k (4 or 5)
candidates ranked by a static heuristic. `fast_minimax` only searches 4
plies, so a forced tactical move is unlikely to have been static-ranked
out of the top-6 root candidates yet. `deep_minimax` searches 6, 8, 10+
plies with the *same* narrow beam at *every* internal node, so the odds
that some single forced continuation gets pruned away at *some* point
along the longer path compound with depth — and the static leaf eval then
gets trusted at an even more misleading, mid-tactic position.

Confirmation came from reading the actual vendored SealBot port
(`papers/misc/hexbot-building-framework/opponents/ramora/ai.py`, a real
external Connect-6-family engine, not a proxy). It never relies on static-
heuristic beam pruning for tactics: `_find_instant_win` does an exact scan
for immediate wins at *every* node via incrementally maintained "hot
window" tracking; `_filter_turns_by_threats` restricts candidate move-pairs
to only those covering every unblockable opponent threat when one exists;
and — the most interesting piece — `_minimax` has an exact forced-loss
short-circuit: if the opponent holds ≥2 live brink windows (4-of-6 filled,
live) whose empty cells can't be jointly covered by 2 cells, it returns a
proven loss immediately, no search needed. That is a direct algorithmic
implementation of this project's own pairing/fork theory (τ(O) exceeding
defensive covering capacity ⇒ forced loss, `docs/theory/2026-07-08-
pairing-thresholds-and-game-values.md`) as an **exact tree-pruning rule**,
rather than the soft heuristic bonus `fork_bonus` was approximating.

### 3.4 The fix

Added `_hot_windows` / `_forced_result` to `competition/arena.py` (ported
1:1 to `hexo/hexgo-rs/src/search.rs`'s `hot_windows`/`forced_result`,
cross-checked via `cargo test` against hand-verified fixtures): an exact,
non-heuristic check, run at **every** search node, for whether the mover
has an unconditional win within their remaining placements this turn, or
is facing an unblockable opponent fork. This also closed a real
completeness gap in the *original* root-level win/block guarantee: a live
window with exactly 2 empty cells and 4 existing stones is an
unconditional win *this turn* (both remaining placements fill it) that the
old single-placement `check_win` loop could never see — only search could
find it, and a narrow top-k beam could silently prune the second cell away
before search ever tried it. `bot()`'s root now checks this directly
(`_hot_windows(..., min_own=WIN_LENGTH-2)`) in addition to the plain
one-move win/block checks.

A tiny local smoke check (4 games, not a statistical claim) went from
`deep_minimax` losing all 4 pre-fix to winning 3/4 post-fix — encouraging,
not conclusive. Real validation (bake-off re-run at 40 openings, Rust vs
the actual SealBot port, Rust vs MCTS-100) was sent to Modal per Leon's
"local hardware is slow, use Modal for tests" instruction (2026-07-08);
see §3.5.

### 3.5 Modal validation results

<!-- filled in once the 2026-07-08 vs_sealbot / vs_mcts / bakeoff-v2 Modal runs complete -->
