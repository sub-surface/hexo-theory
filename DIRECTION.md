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

## Explicitly out of scope (for now)

Kept in the repo, not on the critical path: neural-CA training, the full Pisot
S_T(N) measurement, diffraction reruns, CGT/surreal threads. They are depth to
return to once the τ pipeline is mature — or once the τ-fork bot plateaus and we
need search/learning to go further.
