# HeXO Theory — Research Direction

> One page. The focused thesis, the single most promising lead, and the pipeline
> from theory to the bot that ships in the garden. For the full distilled findings
> see [SPEC.md](SPEC.md); for the bot competition see [competition/](competition/).

## The focus

Of the many threads explored (quasicrystal/Pisot, epiplexity/MDL, CGT, surreal
numbers, UDC point sets), **one lead is both the most empirically grounded and the
most actionable**:

> **The transversal number τ of the obligation hypergraph is the master variable
> of HeXO. A position forces a win iff some threat family has τ > 2 (the defender's
> 2-stone budget). Everything strong about play reduces to manufacturing τ > 2 and
> denying it.**

Why this one:

- It is **mechanistic**, not just descriptive. The quasicrystal results are a
  beautiful *measurement* of optimal play, but they don't tell you what move to
  make. τ does: pressure = `max(0, τ − 2)` is directly a move-scoring function.
- It is **empirically the strongest signal we have.** The parity law (odd-k → Black
  tempo, even-k → White tempo) and the rail/bridge forcing atoms all fall out of
  τ-thresholding. See SPEC §5 Line B.
- It **bridges the two narratives.** The forcing *atoms* (minimal τ > 2 shapes) are
  exactly the substitution *tiles* the Pisot conjecture needs to be finite. Local
  generator (τ) ⟺ global pattern (quasicrystal). Studying τ feeds both.
- It is **cheap to approximate.** This is the key for the bot (below).

Everything else stays in the repo as supporting evidence and future depth, but the
active research question is now singular:

> **How well can a finitely-bounded, computationally-cheap τ-approximation play
> HeXO — and does the gap to perfect play close as we add atoms?**

## The cheap heuristic (theory → tournament → garden)

The garden's current bot scores a move by the Erdős–Selfridge potential
`Σ_L 4^(own stones in live line L)`. That is already a *soft* τ-proxy: it rewards
near-complete open lines. The theory says the missing ingredient is **forks** —
moves that open *two or more* near-complete lines at once, because a double-threat
is precisely τ > 2 (two stones cannot cover two disjoint threats).

So the single highest-value, near-free upgrade is **fork awareness**:

```
score(move) = ES_potential(own)              # existing soft τ
            + ES_potential(opp) * w_def       # block their potential
            + (own_open4_lines)²   * w_fork    # reward making a fork  (τ>2)
            + (opp_open4_lines)²   * w_fork    # reward breaking a fork
```

`own_open4_lines` = count of length-6 windows through the move that would hold ≥4
own stones and no opponent stone. Squaring makes a 2-fork dominate — exactly the
τ > 2 signal. Cost: one extra O(1) local scan per candidate cell. No search tree,
no network. **This is implemented as `make_fork_aware` in
[competition/arena.py](competition/arena.py).**

## The pipeline

1. **Theory** identifies the cheap signal (τ-fork, above).
2. **[competition/arena.py](competition/arena.py)** pits candidate bots under a
   fixed 1-second-per-move budget in a round-robin. A bot that overruns forfeits —
   so "cheap and strong" wins by construction, matching the browser constraint.
3. The **champion** ports line-for-line to the garden's
   `digital-garden/src/lib/hexo.ts` (`botMove`) — the Python and TS engines are
   deliberately kept identical.
4. New atoms discovered by the τ research (rail/bridge motifs, integrality-gap
   atoms) become new terms in the heuristic → new arena entrants → possibly a new
   champion. The loop closes.

## What success looks like

- A τ-fork heuristic that **beats the plain potential bot** in the arena at
  negligible extra cost.
- A short ladder of cheap bots whose strength rises as atoms are added — an
  empirical curve of "how much of HeXO is capturable by bounded τ-reasoning."
- The garden bot getting visibly sharper without ever needing a neural net.

### Current arena finding (2026-06-15) — honest status

The first fork-aware bots are *fast enough* (≈31 ms/move vs 16 ms for the plain
heuristic at 60 stones — well inside a 1 s budget). But they are **not yet stronger**:

- `fork_aware_d1.5` (high defence) beats `greedy_offence` and draws the plain
  `heuristic_d1.1`.
- `fork_aware_d1.1` (low defence) actually **loses to pure greedy_offence** — the
  squared self-fork term makes it chase its own threats and miss the opponent's
  steady build.

So the cheap signal is real and affordable, but the *weighting* matters: fork
pressure must be paired with enough defence weight, and the squared term may be too
aggressive.

**Update (2026-06-15, fix landed).** Replaced the squared self-fork term with a
*linear* term on `max(0, threat_count − 1)` — i.e. only the surplus beyond the
first threat scores, so a single near-line (already valued by the ES base) is not
double-rewarded. With that, `fork_aware(def=1.2, bonus=8)` vs plain `ES(d1.1)`:
**12 games → 0–0, all draws.** Reading: the fix removes the old defect (it no
longer *loses* to greedy/ES), but two strong symmetric deterministic players just
draw — a head-to-head can't separate them. **To prove fork value, the test must be
asymmetric**: give one side a constructed fork opportunity, or measure win-margin
vs a *weaker* opponent, not strong-vs-strong self-play. That's the next experiment.
**Still not ported to the garden** — no demonstrated edge yet.

### Is Erdős–Selfridge the best bang-for-buck? (the heuristic landscape)

| Heuristic | Cost/move | Sees forks (τ>2)? | Verdict |
|---|---|---|---|
| Random | ~0 | no | baseline only |
| **ES potential `Σ2^(own−k)`** | low (~100 ops) | **no** (additive, myopic) | cheapest *sound* potential; what ships now |
| ES + linear fork term | low (+1 scan) | **yes** | cheapest *strong* upgrade; drew strong-vs-strong (above) |
| Atom/pattern lookup (rail/bridge) | low (table hit) | yes, structurally | needs the line-B atom table; promising, unbuilt |
| Depth-2 minimax | medium | yes (1-ply lookahead) | `papers/hexconnect6_depth2_minimax`; next rung up |
| MCTS / NN | high | yes | overkill for a browser bot |

Conclusion: **ES is near-optimal on the *cost* axis but blind on the *strength*
axis (no fork awareness) — which is exactly the gap a human exploits to beat it
(set up a double threat).** The cheapest meaningful improvement is ES + an explicit
fork/τ>2 term + a 1-ply opponent-fork block (implemented). Beyond that, the next
real gain is not a cleverer static potential but **shallow (depth-2) search** —
the `papers/` depth-2 atlas is the substrate. The harness catching the squared-term
defect before it shipped is the pipeline working as intended.

## Seed: overwrite mode as finite-space computation (2026-06-15)

The garden's `Progressions` toy (the 2-D AP-building shadow of HeXO) has an
**overwrite** mode where agents may reclaim occupied cells. Empirically this turns
a monotone Maker-Maker *positional* game into a **non-monotone cellular automaton
on a bounded substrate**: play never terminates, the board reaches a dynamic
equilibrium (limit cycle / standing wave), and the dense region develops a
"CRT-scanline" banding — the lattice resonating at the rule's preferred wavenumber
(cf. the Bellman–Turing-instability note, `docs/theory/2026-05-20-*`).

Why it's interesting, and testable:
- **Descriptive-complexity jump.** Permanent-stone HeXO is Σ⁰₁ (open, finite play).
  The overwrite variant is *non-terminating* — a loopy game (Conway) potentially
  far higher in the hierarchy. The two modes literally sit at different levels.
- **ALife resonance.** This is the spatial, 2-player cousin of Agüera y Arcas
  et al. 2024 (*Computational Life: self-replicating programs from simple
  interaction*) — self-replication as an **attractor of a finite-space rewrite
  system**. Here it's local progression-structure copying itself across the lattice
  via the overwrite (rewrite) op, with no fitness function.
- **Concrete questions.** Does overwrite HeXO have a Garden-of-Eden set? A
  Conway-style loopy-game value? Do self-replicating "progression gliders" emerge
  under specific defence-weights? Measure period/entropy of the limit cycle vs the
  block-weight parameter.

Not on the critical path, but a clean, self-contained side-study with its own
falsifiers.

## Search-regime pivot (2026-07-05)

The τ-fork heuristic below is being folded into a bigger redirect: two
independent from-scratch neural-training attempts (this repo's NCA-zoo,
`../hexo`'s AlphaZero) both plateaued below simple hand-crafted heuristics
(see [SPEC.md](SPEC.md) §6 for the evidence). The new bet is theory-derived,
cheap search over the now-fast Rust MCTS engine (`../hexo/hexgo-rs`),
instead of more from-scratch learning. Full handoff spec — five candidate
evaluators (transfer-matrix Pisot derivation, cube-coordinate 1-D
decomposition, τ-tractability/LP relaxation, FFT threat maps, Eisenstein-
residue covering strategies) plus the bake-off methodology — is in
[docs/theory/2026-07-05-search-regime-handoff.md](docs/theory/2026-07-05-search-regime-handoff.md).
That document supersedes the narrower "just push the fork-aware heuristic"
framing below wherever the two disagree.

**Executed (2026-07-06)** — verdicts for all five candidates, two new theorems
(no pairing strategy exists for k=6, threshold sharp at k=7 with explicit
construction; τ is LP-exact on real positions, LP>2 certifies forcing), the
B+D unified fast evaluator with depth-2 lookahead (`fast_tactical`), residue
bots, arena opening-randomization + budget-forfeit fix, and
[modal_bakeoff.py](modal_bakeoff.py) ready to run. Full write-up:
[docs/theory/2026-07-06-search-regime-verdicts.md](docs/theory/2026-07-06-search-regime-verdicts.md).

**Bake-off Phase 1 ran (2026-07-06, 1,050 games, ~$0.15).** Champion in the
Phase-1 roster: `heuristic_d1.1` — the plain ES bot; naive depth-2
(`fast_tactical`) was *falsified* (passive play), residue ε-bias a perfect
null.

**Bake-off Phase 2 ran (2026-07-06, 1,120 games, ~$0.3): search wins.**
New champion `fast_minimax_d1.1` — true 2-placement-turn minimax over the
exact vectorized evaluator — beats the shipped heuristic head-to-head 4–1 and
sweeps the whole defence-weight ladder (🟡 strong-but-small-n; the game is
deeply drawish). This reverses Phase-1: search *does* help once the policy is
correct minimax, not a static score difference. Defence-weight sweep found no
better static weight than d1.1 (d1.0–1.6 indistinguishable, d2.0 slightly
worse). **Garden-port candidate is now `fast_minimax_d1.1`** but it needs the
vectorized evaluator ported too (~20× per-move cost, still fine at 1 s);
confirm the edge at 🟢 sample size (~$1.5) first. Analytic figures +
per-pairing GIF replays: `figures/fig_bakeoff_*.png`, `figures/replays/`.

**Programme D RAN (2026-07-06) — P3 has a first answer.** 8,000-game
`ca_combo_v2` corpus (Modal, ~$1); `experiments/run_mdl_scaling.py` (lzma,
D6-canonical encoding): **`S_T(N) ~ N^0.929` (sub-linear), cleanly separated
from a random-play null at `N^1.009` (linear)** — marginal bytes/game fall
78→57 for the agent, flat ~118 for random. So P3's sub-linearity premise is
**supported 🟡** (proxy first-read; not yet the Pisot constant — see
[verdicts §Programme D](docs/theory/2026-07-06-search-regime-verdicts.md)).
Same corpus overturned P1: `ca_combo_v2` shows a slight *second*-mover edge
(Black 0.479 [0.467,0.492] of decisive), not first. Total Modal spend to date
≈ $1.5 of $30.

## Next experiments (2026-07-05 priority queue)

An external assessment of this repo (2026-07-05) found the research threads had
outpaced convergence on the one claim that would make Line A publishable, and
that several "Supported" labels didn't survive checking the underlying JSON.
Full detail in SPEC.md's corrected §5/§6. The concrete fix is this ranked queue
— work top to bottom, don't open a new thread until item 1 has a real answer:

1. **Programme D, cheaply.** ✅ **DONE 2026-07-06** — `run_mdl_scaling.py` on
   an 8,000-game `ca_combo_v2` Modal corpus: `S_T(N) ~ N^0.929` sub-linear vs a
   random null at `N^1.009`. P3 sub-linearity premise supported 🟡. *Next rung
   (to reach 🟢):* repeat across agents + push N→10^5 (~$13) and check whether
   β keeps falling or plateaus; then attempt the substitution-tile ⇒ Pisot-λ
   identification (verdicts §A) that the compression exponent alone can't give.
2. **Retest P1 and the Bellman-Turing wavelength at real sample size.**
   P1 ✅ **DONE 2026-07-06** (same corpus): `ca_combo_v2` self-play shows a
   slight *second*-mover edge (Black 0.479 [0.467,0.492] decisive), overturning
   the thin-sample first-mover story. **Bellman-Turing wavelength still open** —
   λ*≈11.8 predicted vs r≈3 measured on 12 games; needs the long-horizon
   corpus (the rust backend or a dedicated `run_bellman_turing` Modal sweep).
3. **Push the τ-fork heuristic to one clean win** — ✅ **superseded 2026-07-06.**
   The bake-off answered the stronger question: `fast_minimax` (true turn-minimax
   over the exact evaluator) beats every static heuristic 🟡; static τ-fork and
   plain ES are indistinguishable. Remaining: confirm the minimax edge at 🟢
   sample size, then garden-port.
4. **Formalize the 3-SAT/NP-hardness reduction** (SPEC.md §7 item 6) — a
   bounded, provable result independent of self-play statistics, and a good
   hedge if the Pisot conjecture doesn't survive item 1. *Still open, and now
   the natural next theory target* — the pairing-threshold and τ-LP theorems
   (verdicts §C, §E) are the same kind of bounded provable result and show the
   machinery is in reach.

The 2026-07-06 pass cleared items 1–3; item 4 (plus the two β/λ follow-ups
above) is the live frontier. Compute plan below still applies for the N→10^5
and long-horizon runs.

## Compute plan (2026-07-05) — Modal cloud budget

$30 of Modal credit is available (Modal CLI already authenticated as
`sub-surface`); local compute is thermally constrained. Before speccing this,
profiled `ca_combo_v2` self-play locally: **~10 core-seconds/game** (20 games,
4 workers, 52s wall). This is CPU-bound, dict-based Python game logic —
embarrassingly parallel *across* games (each game itself is a sequential
Markov chain, so no within-game parallelism) — the same shape of workload
`experiments/harness.py` already parallelizes with `multiprocessing.Pool`.

**Modal pricing** (checked 2026-07-05): CPU $0.0000131/core-second; GPUs from
T4 ($0.000164/s) up to H100 ($0.001097/s); starter-tier concurrency cap is 100
containers. At ~10 core-sec/game with 100 parallel cores (~10 games/sec
aggregate): $N=10^4$ games ≈ 17 min / **≈$1.3**; $N=10^5$ games ≈ 2.8 hr /
**≈$13**. Both fit the budget on plain CPU parallelism alone.

**Is a custom GPU kernel (batched/vectorized self-play engine) worth building?**
Real idea, not a distraction in principle — representing thousands of games as
one board tensor and running the ES-potential heuristic as batched tensor ops
could plausibly beat CPU parallelism by 3-4 orders of magnitude. But: (a) plain
CPU parallelism already delivers the $N=10^5$ corpora items 1-3 need, within
budget, in a few hours; (b) it requires reimplementing win-detection and
live-line tracking as batched tensor ops on an unbounded lattice — multi-day
effort with real correctness risk (a subtly wrong batched win-check silently
corrupts every downstream result); (c) it only pays for itself at a scale
(10^6-10^7 games, or real self-play RL) that only the parked AZ/NCA thread
would need, and that thread is blocked on a data/objective bug, not a compute
ceiling (SPEC.md §6). **Verdict: defer.** Revisit only if the cheap corpora
show a log-trend worth confirming at 10^6+ games, or if the AZ/NCA diagnosis
gets fixed and self-play RL becomes worth scaling.

**Update (2026-07-05, same day): a better substrate was already sitting in
`../hexo`.** `hexo/hexgo-rs` (Rust, PyO3+Rayon) exposes `parallel_self_play` —
pure-rollout MCTS, no trained net needed, parallelizes across every core
*inside a single call* (no manual seed-sharding within a shard). It was
blocked by a stale build (`parallel.rs` was edited ~2.5h after the last
`cargo build`), which resolves itself for free since Modal compiles it fresh
for Linux anyway. hexo's trained checkpoint is **not** used — it's currently
weaker than its own greedy baseline (Elo ~1200 vs ~1753 in `hexo/elo.json`;
training regressed), so pure rollout is both the honest and the only-available
choice, and it needs no checkpoint file. One real gap: `hexgo-rs` seeds via
Rust's `thread_rng()` (OS entropy), so games are independent but not
seed-reproducible — fine for bulk corpus statistics, not for "replay this
exact game." This makes CPU-container throughput for the priority queue
likely *cheaper* than the plain-Python estimate above, though the exact
per-game rate on Modal hasn't been measured yet (that's what `smoke_test`
is for).

**Implementation:** [modal_app.py](modal_app.py) — two backends (`rust` =
hexo's MCTS, `python` = this repo's existing agent registry via
`experiments/harness.py`, needed whenever the exact agent behind an existing
SPEC.md number matters, e.g. tightening P1 specifically means more
`ca_combo_v2` self-play, which Rust has no equivalent of). Both return raw
per-game outcomes; Wilson CIs and the gzip-MDL proxy are computed once,
locally, over the pooled results.

**Nothing has been run yet.** Next step is `modal run modal_app.py::smoke_test`
(~$0.01) to verify both backends actually work before committing the budget,
then a modest `corpus` call to get a real games/sec number and re-derive the
allocation below from measured, not estimated, throughput.

**Draft budget allocation** (unchanged in shape, likely conservative given
the Rust path above — confirm via smoke_test before deploying):
- **~$15-18, CPU containers:** corpora for queue items 1-3 above — `rust`
  backend where the agent doesn't need to be a specific existing one
  (Programme D proxy, Bellman-Turing long-horizon), `python` backend where it
  does (P1 tightening on `ca_combo_v2` specifically).
- **~$5-8, one small GPU (T4/L4 — no need for anything bigger at this scale):**
  UDC-positions resolution fix (`--diffraction-grid` scaled to the note's own
  recommended `4*D` per t) and a diffraction re-run on the larger corpora.
  Not yet built into `modal_app.py` — CPU corpus generation is the priority.
- **~$5-7 buffer.**

## Explicitly out of scope (for now)

Kept in the repo, not on the critical path: neural-CA/AlphaZero training
(actively blocked on a diagnosed data bug, not just deprioritized — see SPEC.md
§6), the *full* observer-net Pisot S_T(N) measurement from ROADMAP Programme D
(superseded for now by the cheap gzip-MDL proxy in the queue above), CGT/surreal
threads. They are depth to return to once the τ pipeline is mature — or once the
τ-fork bot plateaus and we need search/learning to go further.
