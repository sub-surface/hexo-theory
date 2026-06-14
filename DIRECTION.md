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
aggressive. **Do not port fork_aware to the garden yet.** Next: sweep
`(defence_weight, fork_bonus)` in the arena, and try a *linear* fork term
(count, not count²) so a single near-fork doesn't dominate. The harness catching
this before it shipped is the pipeline working as intended.

## Explicitly out of scope (for now)

Kept in the repo, not on the critical path: neural-CA training, the full Pisot
S_T(N) measurement, diffraction reruns, CGT/surreal threads. They are depth to
return to once the τ pipeline is mature — or once the τ-fork bot plateaus and we
need search/learning to go further.
