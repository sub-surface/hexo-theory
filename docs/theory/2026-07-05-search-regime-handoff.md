# HeXO search-regime handoff — build brief for a fresh agent

*2026-07-05. Written for a new agent session with clean context (no memory of
the conversation that produced this). Read this file fully before touching
code. It is a strong scaffold, not a rigid spec — see §0 for how to use it.*

---

## 0. How to use this document

You are being handed a pivot: this project spent months on two independent
from-scratch neural-training efforts, both of which plateaued below simple
hand-crafted heuristics (evidence in §1.3 — read it, don't skip it, so you
don't repeat the mistake). The new mandate is to stop trying to *learn*
strength and instead *derive* it from the game's actual mathematical
structure, using a newly-available fast search substrate.

§2 lays out five theoretical candidates (A–E) for cheap, theory-grounded
move evaluation, each with as much derivation as was worked out before
handoff. **Some of this math is solid and verified (marked ✅); some is a
correct partial result with an open construction question (marked 🔶); none
of it should be treated as finished.** Your job is not to implement these
as given — it's to:

1. **Check the math.** Re-derive anything marked 🔶 yourself; if you find an
   error in anything marked ✅, that's valuable, say so explicitly and fix it.
2. **Improve or replace weak ideas.** If a candidate doesn't survive contact
   with your own reasoning, cut it and substitute something better — but
   write down *why* you cut it (a null result is still a result here; see
   the project's own honesty culture in §1.4).
3. **Feel free to go further than what's written.** The person who wrote
   this brief explicitly wants creative, deep theoretical work here, not
   just implementation of a checklist. If you see a sharper reformulation
   of the ruleset, a better algebraic structure, a cleverer reduction —
   pursue it. The five candidates are a floor, not a ceiling.
4. **Then, and only then, build the bake-off** (§3) to test whatever
   candidates survive your own scrutiny, using the infrastructure in §4.

Maintain the project's existing research discipline throughout (this is not
optional — it's why the last research pass was worth doing): every claim
gets a falsifiable prediction; every result gets an honest confidence level
(🟢 solid / 🟡 directional-not-significant / 🔴 not yet established — see
`SPEC.md` §5 for the convention already in use); cite real file:line symbols,
not vague descriptions; small-n self-play claims get flagged as such, not
rounded up to "Supported."

---

## 1. Context brief

### 1.1 The game

HeXO = Connect-6 on the infinite hex lattice, identified with the Eisenstein
integers **Z[ω]**, ω = e^(2πi/3). Turn rule is **1-2-2**: Black places 1
stone on move 1, then both players place 2 stones per turn. Win = 6
consecutive stones along any of 3 axes:

```
u1 = (1, 0)     u2 = (0, 1)     u3 = (1, -1)      (axial q,r coordinates)
```

`WIN_LENGTH == 6` is asserted deep in the engine
(`../hexo/game.py:147`) — don't touch this without flagging it explicitly.
Descriptive-set-theoretic positioning (solid, keep relying on it): the
payoff "someone has 6 in a row" is **Σ⁰₁** (open, directly Gale-Stewart
determined) — two levels simpler than Hamkins-Leonessi's infinite Hex at
**Σ⁰₇**. This is why finite-horizon, constructive analysis (not infinitary
determinacy machinery) is the right tool here.

### 1.2 Repo layout

Two sibling repos on disk, both under `C:\Users\Leon\Desktop\Psychograph\`:

- **`hexo/`** — production engine. Plain Python `game.py`/`elo.py`
  (stdlib-only, no heavy deps), plus a Rust engine `hexo/hexgo-rs/`
  (PyO3 + Rayon) exposing, among others:
  - `hexgo.parallel_self_play(num_games, num_sims=200, c_puct=1.5, fpu_reduction=0.2, max_moves=200) -> Vec<GameResult>`
    — pure-rollout MCTS (`mcts_pure`, no trained net), Rayon-parallelizes
    `num_games` independent games across every core **inside one call**.
    `GameResult` has `.winner` (Optional[1|2]), `.moves` (list of (q,r)),
    `.num_moves`. Source: `hexo/hexgo-rs/src/parallel.rs`.
  - `hexgo.parallel_eisenstein_games(...)` — MCTS vs. a native Rust
    reimplementation of `EisensteinGreedyAgent` (`parallel.rs::eisenstein_choose`).
  - **Caveat:** uses Rust's `thread_rng()` internally (`mcts.rs:51,282`) —
    OS-entropy-seeded per thread, so games are independent but **not
    reproducible from a passed seed**. Fine for bulk statistics; not for
    "replay this exact game."
  - The compiled Windows `.dll` in `hexgo-rs/target/release/` was stale as
    of 2026-07-05 (source edited ~2.5h after the last build, so
    `parallel_self_play` wasn't actually in the binary). This resolves
    itself for free if you build fresh for Linux (which any Modal
    deployment does anyway) — don't waste time debugging around it, just
    rebuild (`maturin develop --release` after installing a Rust
    toolchain).
  - The trained checkpoint (`hexo/checkpoints/net_gen*.pt`) is **not
    useful and should not be used**: `hexo/elo.json` shows the net at
    Elo ~1180-1200 after 230 generations, vs. its own greedy baseline
    (`eisenstein_def`) at ~1753 — training regressed, it did not improve.
    Pure-rollout MCTS needs no checkpoint at all, which sidesteps this.

- **`hexo-theory/`** (this repo) — the research lab. Key files:
  - `engine/` — game-analysis primitives (`analysis.py`: live_lines,
    potential, fork detection; `agents.py`, `ca_policy.py`: the
    hand-crafted agent ladder; `isomorphisms.py`: D6/cube-coordinate
    utilities — **see §2.2, this is under-exploited**; `diffraction.py`:
    GPU FFT-based diffraction/Bragg-peak analysis — **see §2.4, reusable
    for a different purpose**; `cgt.py`, `two_move_sum.py`: an empirical
    Hackenbush-style temperature layer over live-line components).
  - `competition/arena.py` — a standalone (deliberately dependency-free)
    mirror of the game engine, built specifically for bot tournaments
    under a **fixed compute budget per move** (default 1.0s; overrun
    forfeits to a fallback move). This "cheap-and-strong wins by
    construction" philosophy is the right frame for the bake-off in §3 —
    reuse it, don't reinvent it.
  - `modal_app.py` — an already-built Modal deployment with two backends
    (`rust` = hexo's MCTS; `python` = this repo's agent registry via
    `experiments/harness.py`) for **corpus generation**, not evaluator
    comparison. It has not been run yet. You'll likely want a new,
    adjacent Modal script for the bake-off (§3/§4) rather than repurposing
    this one, since the job shape is different (round-robin comparison,
    not raw corpus dumping) — but reuse its image-build patterns
    (env-var `HEXO_ROOT`, `copy=True` on `add_local_dir`, the Rust image
    recipe) rather than re-deriving them.
  - `SPEC.md` — consolidated findings with honest confidence levels
    (🟢/🟡/🔴 convention — follow it). `DIRECTION.md` — current priority
    queue. `docs/ROADMAP.md` — the long-range plan (Programme D = the
    still-unmeasured Pisot/epiplexity headline claim, see §1.4).
  - Modal is already authenticated (profile `sub-surface`). Budget: **$30**,
    partially earmarked already in `DIRECTION.md`'s compute plan for
    corpus generation — coordinate with whoever's running that, or check
    current spend, before assuming the full $30 is available for this.

### 1.3 Why neural training is off the table (read this before proposing more of it)

Two independent from-scratch attempts, in two different repos, both
plateaued **below** a simple hand-crafted greedy heuristic:

- `hexo`'s AlphaZero-style training: 65+ generations logged in
  `hexo/metrics.jsonl`, net Elo ~1180-1200 vs. greedy baseline's ~1753
  (`hexo/elo.json`). Self-play throughput is the actual bottleneck
  (`sp_time_s` is 65-70% of every generation's wall time, ~1.2-2 games/sec
  despite a batched-GPU pipeline) — **not** the ELO evaluation step, which
  is deliberately lightweight (`hexo/train.py:885`, "every 10 generations,"
  n_games=6, ~2% overhead). If you're tempted to blame slow evaluation for
  weak play, the logs don't support it — the self-play/search step itself
  is what's expensive and what isn't producing a strong policy.
- `hexo-theory`'s NCA-zoo / AlphaZero-lite: documented, honest series of
  negative results in
  [2026-04-18-unified-agent-design.md](2026-04-18-unified-agent-design.md)
  §10-13 — draw-collapse under self-play, a value head that never
  discriminates above chance (sign-acc 0.51-0.60), and plugging that value
  head in as a tie-break *collapsing* the self-play decisive rate from
  0.70 to 0.00.

Read as: at the compute budgets actually available here (consumer GPUs,
days not months), learning a value/policy net from scratch is not
out-producing hand-crafted heuristics, and troubleshooting *why* has
already eaten a lot of effort without a payoff. The bet this brief is
asking you to make is that the game's actual algebraic/combinatorial
structure (§1.1, §2) can produce a better evaluator *without* gradient
descent, cheaply enough to run inside MCTS as a rollout policy or leaf
value. If your own investigation concludes otherwise, say so plainly —
that's a legitimate outcome, not a failure to find something.

### 1.4 The central conjecture, and what's actually been measured (vs. hoped)

README.md's Central Conjecture: perfect play produces a **Pisot
quasicrystal** — aperiodic, D6-symmetric, substitution structure with
inflation constant λ a Pisot number (candidates flagged: tribonacci
≈1.3247, plastic ≈1.3247, golden ≈1.618). This is empirically supported in
part (Bragg99 = 0.51 vs. 0.055 control, `results/diffraction_p4.json`) but
the **headline claim — is `S_T(N)` (corpus description length) sub-linear
in corpus size N? — has never actually been measured**, despite being
called "the headline result the programme is built to settle" in
`docs/ROADMAP.md` Programme D. `engine/epiplexity.py` exists but was never
pointed at a real sweep. `SPEC.md` §5 has the full, corrected confidence
table — read it before citing any existing number as "established."

This matters for you because **Candidate A below (§2.1) is a proposal to
derive λ analytically from the ruleset, instead of only measuring it from
data** — if it works, it would settle the open question in §7.2 of `SPEC.md`
("does λ from epiplexity match λ from diffraction?") from a third,
independent, first-principles direction.

---

## 2. Five theoretical candidates

Each: the setup, what's been derived and verified vs. what's open, a
concrete deliverable, and a falsifiable prediction. Work through your own
judgment on each before building anything — see §0.

### 2.1 Candidate A — per-line transfer-matrix automaton → analytic Pisot λ

**Setup.** Restrict to a single axis-line (one of the 3 directions). The
win/threat structure through any point is a function of a *bounded* local
window of cells (this is why `hexo/game.py`'s win-check only walks outward
from the last-placed piece — the structure is genuinely local). This means
the relevant "state" for computing potential/threat statistics is a
sliding window of fixed width (enough to cover overlapping 6-windows —
likely width 10-11), giving a finite-state transfer matrix M: states are
run-descriptors (own-run-length, opp-run-length, blocked-flags), and M's
action over a sequence of moves computes aggregate line statistics exactly
— the same machinery as the Goulden-Jackson cluster method / transfer-matrix
method for pattern-avoiding words.

**What's solid (✅):** the locality argument itself, and the existence of
*some* finite automaton capturing single-line threat statistics — this is
standard combinatorics-on-words machinery, not speculative.

**What's open (🔶 — the real work):**
1. Formally define the automaton (state space, transitions) and compute
   its transfer matrix M explicitly. Mechanical but needs to actually be
   done — don't hand-wave the state space, write it out.
2. **The hard, genuinely open modeling question:** how do the three
   axis-automata *compose* into a single global operator whose Perron-
   Frobenius eigenvalue is a candidate λ? Two starting hypotheses to try,
   neither verified:
   - A tensor/Kronecker construction respecting the incidence structure
     (each cell touches one line from each of the 3 axis-families
     simultaneously via the cube-coordinate decomposition, §2.2).
   - A renormalization-group / activator-inhibitor coupling, following the
     Bellman-Turing note's reaction-diffusion framing
     ([2026-05-20-bellman-turing-instability.md](2026-05-20-bellman-turing-instability.md)
     — note that note's own predicted wavelength (λ*≈11.8) did *not*
     match its quick-run measurement (r≈3), an open discrepancy worth
     understanding before reusing its framework uncritically).
   Try both, or something better if you find it; compare whichever
   eigenvalue(s) result against the empirically-hinted Pisot family.

**Deliverable:** a module (suggest `engine/line_automaton.py`, but use
your judgment on placement) implementing the per-line transfer matrix, a
script computing its spectrum, and — critically — a comparison against
`results/cgt_sequences.json` (an existing "Sloane mode" sequence-mining
result tracking live-line counts over real self-play) and against whatever
Programme D's cheap gzip-MDL proxy eventually measures (see
`DIRECTION.md`'s priority queue #1 — check whether that's been run yet by
the time you start).

**Falsifier:** if the derived spectrum isn't close to any Pisot-family
candidate, either the local alphabet is too small (need a wider window) or
the substitution-tiling story is wrong at the level this automaton
operates at — report as a real negative result, not a reason to keep
tuning until something Pisot-shaped falls out.

### 2.2 Candidate B — cube-coordinate decoupling into three 1-D subgames

**Setup — verified ✅.** Axial → cube coordinates: $(q,r) \mapsto
(x,y,z) = (q, r, -q-r)$, already implemented at
`engine/isomorphisms.py:22` (`cube_coords`) but currently used only for D6
canonicalization. Checking each axis direction's effect on $(x,y,z)$:

| axis | $(dq,dr)$ | $(dx,dy,dz)$ | fixed coordinate |
|---|---|---|---|
| $u_1=(1,0)$ | | $(1,0,-1)$ | $y=r$ |
| $u_2=(0,1)$ | | $(0,1,-1)$ | $x=q$ |
| $u_3=(1,-1)$ | | $(1,-1,0)$ | $z=-q-r$ |

Each axis direction holds exactly one cube coordinate fixed and moves the
other two in lockstep with opposite sign. So **the entire threat landscape
decomposes into three independent families of 1-D lines** — every cell
sits on exactly one $x$-line, one $y$-line, one $z$-line, and each family's
6-in-a-row structure is a 1-D problem, decoupled from the other two
families except through shared cell occupancy. Verify this yourself before
building on it (it's simple algebra, but it's foundational — don't take
it on faith from this doc).

**What's open (🔶):**
1. Does an isolated 1-D "6-in-a-row on an infinite line" game have a
   closed-form or small-lookup-table value as a function of the local
   run-descriptor near the point of play? This is checkable computationally:
   brute-force the Grundy/game value (or a suitable potential) for
   increasing line lengths and look for eventual periodicity — many
   positional/octal games on a path have provably-periodic value sequences.
   Actually do this computation; don't assume the answer.
2. Given a per-line value function, how should the three lines through a
   candidate cell be *combined* into a single move score? A naive sum
   ignores exactly the interaction that makes forks dangerous — a stone
   that's merely good on 3 separate lines independently is different from
   a stone that creates a *double threat* (τ>2 in the existing
   transversal framework, `DIRECTION.md`). Think about whether the
   combination needs a fork-correction cross-term, and whether that
   connects cleanly to the existing τ-pressure formula
   (`pressure = max(0, τ(O) - 2)`, `competition/arena.py`) — unifying
   this with the existing τ-fork thread rather than introducing a
   parallel, uncoordinated heuristic would be a good outcome if it holds
   up.

**Deliverable:** an evaluator (module suggestion: `engine/cube_evaluator.py`)
usable as an MCTS rollout policy or leaf value, wired into the Rust engine
(as a leaf/rollout policy — check whether it's cheaper to reimplement in
Rust for the bake-off, or to call out to Python; that's an engineering
tradeoff for you to make) or as a Python-side move-scorer for a first,
faster-to-validate pass.

**Falsifier:** should beat pure-random-rollout MCTS and be competitive with
`ca_combo_v2` at equal or lower compute. If a naive per-line sum loses to
`ca_combo_v2`, that's evidence the cross-line coupling (forks) is
load-bearing and the decomposition needs the fork-correction term from
point 2 above — report which failure mode you hit.

### 2.3 Candidate C — is τ actually tractable, not just heuristic?

**Setup.** `SPEC.md` §7 item 6 flags an *unformalized* 3-SAT reduction
implying worst-case NP-hardness of transversal-number computation — but
that almost certainly requires an adversarially-constructed, unbounded-
radius obligation hypergraph. Real obligation hypergraphs arising from
bounded-radius play near the frontier are a much more restricted object.

**What's open (🔶 — and check existing work first):** does the LP
relaxation of the minimum-hitting-set problem have zero integrality gap on
*real* (bounded-radius) obligation hypergraphs mined from self-play? If
so, τ is exactly computable via a small LP rather than the current
linear/heuristic approximation in `competition/arena.py`.

**Before deriving anything here, read what already exists:**
`papers/hexconnect6_atom_compositions_results/.../README.md` is referenced
in `SPEC.md`'s Line B provenance table as covering "integrality-gap
atoms" — this document's author has *not* read that bundle themselves, so
it may already answer this question, partially or fully. Check
`papers/hexconnect6_atom_miner_results/` too (mines minimal τ>2 obligation
hypergraphs — likely already computes τ exactly for small instances by
brute force, which is exactly the ground truth you'd check an LP
relaxation against).

**Deliverable:** either (a) a summary of what the existing atom-mining
work already established about integrality gaps, correctly cited, or (b)
if genuinely novel, an LP-relaxation implementation checked against
brute-force τ on mined obligation hypergraphs from real self-play corpora
(the Rust engine, §1.2, is a cheap source of these).

**Falsifier:** nonzero integrality gap on a nontrivial fraction of mined
instances kills the "τ is cheaply exact" hope; report the gap distribution
either way.

### 2.4 Candidate D — FFT/convolution threat-density maps

**Setup.** Z[ω] has exactly 6 units (±1, ±ω, ±ω²), one per hex direction —
not a coincidence, it's the unit group of the Eisenstein integers. "Count
of open k-windows through every cell" is, along each axis, a correlation
of the occupancy indicator with a length-6 kernel — an $O(N\log N)$
convolution computable for the **whole board at once**. `engine/diffraction.py`
already implements FFT machinery on this lattice for a different purpose
(measuring global Bragg/diffraction structure over a *finished* game's
point set, via `diffraction_intensity` — check the exact entry point
yourself, cited loosely here as of last read). The proposal: repurpose
that machinery to compute a per-cell **threat-density map** for a
*live, in-progress* board, evaluated once per move (or once per several
candidate moves) instead of scanning windows per candidate.

**What's open (🔶 — a real implementation subtlety, not just an
engineering task):** naive convolution computes *sums* (counts), but the
quantity you actually want is "own-stone count in this window, AND
zero opponent stones in this window" (live/dead distinction) — not a
single linear convolution. You need (at minimum) two separate convolutions
— own-occupancy and opponent-occupancy — combined elementwise afterward
(window is dead if opponent-count > 0, else potential = weight(own-count)).
Don't ship a version that conflates these; verify the combined output
against a small, hand-checked board before trusting it in the bake-off.

**Deliverable:** a live threat-map function (suggest extending
`engine/diffraction.py` or a sibling module) usable as a fast static
evaluator or MCTS leaf value; a correctness check against
`engine/analysis.py`'s existing (presumably slower, per-cell-scan) threat/
potential functions on a battery of hand-constructed and real self-play
positions.

**Falsifier:** if the FFT-based map disagrees with the existing scan-based
`engine/analysis.py` functions on real positions, it's a bug, not a
finding — fix before using it in the bake-off.

### 2.5 Candidate E — Eisenstein-residue covering/pairing strategies

**Setup — the algebra here is verified ✅, worked out in full below; the
game-theoretic construction on top of it is 🔶 open.** Pick a rational
prime $p \equiv 1 \pmod 3$; it splits in $\mathbb{Z}[\omega]$ as $p = \pi
\bar\pi$, giving $\mathbb{Z}[\omega]/(\pi) \cong \mathbb{F}_p$ (this is the
same construction `experiments/run_udc_positions.py` already uses for a
different purpose — unit-distance point sets — with $p=7$ at $t=1$).

Reduction mod $\pi$ sends rational integers to their ordinary residue mod
$p$, and sends $\omega$ to a primitive cube root of unity in
$\mathbb{F}_p$ (which exists exactly because $p \equiv 1 \pmod 3$). Since
$\mathbb{F}_p$ is a prime field, **every nonzero element has additive
order exactly $p$** — so stepping in *any* of the 6 unit directions
(±1, ±ω, ±ω², all nonzero mod $\pi$ since units aren't divisible by the
non-unit prime $\pi$) cycles through all $p$ residues with full period $p$
before repeating.

Consequence, worked out precisely: take $p=7$ (smallest valid, and already
in use elsewhere in this repo). Any 6 consecutive cells along any axis
occupy 6 *consecutive* residues mod 7 out of the 7 available — by
pigeonhole, this excludes **exactly one** residue class, and *which* class
is excluded depends on the window's starting position (it is not a fixed
class — verify this yourself, it's a one-line mod-7 computation). Because
of this, **no single fixed residue class hits every possible window** —
but **any 2 residue classes, chosen so their cyclic gaps mod 7 are both
≤6 (e.g. $\{0, 6\}$), hit every window**, since a window excludes only 1
class and 2 classes can't both be the excluded one.

**What this gives you (solid, ✅):** a genuine covering-code fact — a
fixed density-$2/7$ sublattice (per axis; combine across all 3 axes and
the D6 orbit for the full 2-D version) that is *guaranteed* to intersect
every possible forming 6-window, no matter where or when it forms.

**What this does NOT yet give you (🔶 — the open construction problem):**
this is a *covering* guarantee, not a *move-pairing* guarantee like
`MirrorAgent`'s point-reflection ($c \mapsto -c$, `engine/agents.py`) — it
tells you *where* a defensive stone would need to land to interrupt any
given threat, but not *when*, or that a legal, tempo-respecting response
exists in time. The open question, stated sharply: **can this covering
structure be turned into an actual pairing/response strategy — extending
`MirrorAgent`'s single global involution to a residue-class-indexed family
of involutions — that provides a provable non-losing guarantee (even for
a restricted class of positions), the way point-reflection does?** Or,
failing a full proof, does biasing move selection toward this fixed
density-$2/7$ sublattice *empirically* improve defensive play at
negligible cost? Both are worth pursuing; be honest in whichever direction
you get results (or don't).

**Deliverable:** (a) a from-scratch verification of the algebra above (redo
it, don't just trust this document); (b) either a genuine pairing-strategy
construction with a correctness argument, or an empirical test of the
density-biased defensive heuristic; (c) if you find the construction
doesn't close, say precisely where it breaks — that's real information
about how far pairing-strategy arguments generalize beyond the
point-reflection case.

**Falsifier:** the cheapest possible test — implement the residue-biased
static strategy (O(1) per move, no search) and check whether it ever loses
to `RandomAgent` at minimum, and how it fares against the existing ladder.
A strategy this cheap either earns its place in the bake-off or is quickly
and honestly ruled out.

---

## 3. The bake-off methodology

Two phases, following `competition/arena.py`'s existing "fixed compute
budget per move, overrun forfeits" philosophy — extend that design, don't
replace it with something unrelated.

**Phase 1 — Screen.** Round-robin, modest game count, fixed per-move time
budget, every surviving candidate from §2 (plus baselines: pure-random-
rollout MCTS via `hexgo.parallel_self_play`, the existing `ca_combo_v2`
and τ-fork-aware heuristics, and `hexgo.parallel_eisenstein_games` as an
existing reference point). Cheap by design — this is what the Rust
engine's internal parallelism makes affordable. Goal: identify which 2-3
candidates are worth deeper investment, and which can be honestly cut.

**Phase 2 — Narrow.** The survivors, many more games, real Wilson 95% CIs
computed once over pooled outcomes (not per-shard-then-averaged — see the
warning in `modal_app.py`'s docstring about exactly this mistake). Apply
the same 🟢/🟡/🔴 honesty standard from `SPEC.md` §5 from the start — don't
let a CI-straddles-the-null result get written up as "the winner."

Both phases should produce a Pareto-style comparison (strength vs.
compute cost per move — this project already has a `(|P|, H_T)` MDL-plane
convention in `docs/ROADMAP.md`; either reuse that framing or propose
something better suited to comparing search-time-bounded evaluators
specifically, and justify the choice).

---

## 4. Practical / engineering notes

- Modal: already authenticated (`sub-surface`). Check current spend
  against the $30 budget before assuming it's fully available — some may
  already be committed to corpus generation per `DIRECTION.md`'s compute
  plan. CPU pricing $0.0000131/core-sec; GPUs from T4 ($0.000164/s); 100-
  container concurrency on the starter tier.
- `engine/__init__.py`'s `_resolve_hexo_root()` (env var → relative
  sibling → hardcoded fallback) is the correct, current pattern for
  cross-environment path resolution — don't reintroduce a hardcoded
  Windows path shim per-file; that's exactly the fragility that was just
  cleaned up (see CLAUDE.md "Import path").
- `modal_app.py`'s image-build patterns (Rust toolchain install via
  rustup, `maturin develop --release`, `copy=True` on `add_local_dir` so
  files exist for subsequent `run_commands` at build time) are verified
  and worth reusing directly for any new Modal script this work needs.
- Reproducibility conventions this repo already follows and you should
  keep: seed everything where the backend supports it (note Rust's
  `thread_rng()` caveat, §1.2 — don't claim reproducibility you don't
  have); `--quick` flag for fast dev iteration; results to `results/`,
  figures to `figures/`, both tracked in git; one experiment per
  `experiments/run_*.py` (or, given this is a substantially new research
  thread, consider whether a dedicated subdirectory is cleaner than
  scattering into the existing flat `experiments/` — your call, just be
  consistent and say what you chose and why).

---

## 5. Definition of done

- Each of A-E has an honest verdict: built-and-validated, built-and-
  falsified, or explicitly cut with reasoning — not left ambiguous.
- The bake-off (§3) has run, with a clear Pareto comparison and at least
  one champion (not necessarily a dominant one) carried forward.
- `SPEC.md` and `DIRECTION.md` are updated to reflect whatever this work
  established, using the existing 🟢/🟡/🔴 convention — don't leave this
  thread's findings only in this file or in a chat transcript.
- If you found something better than A-E, it's written up with the same
  rigor (setup, what's verified, what's open, deliverable, falsifier) as
  the candidates here, not just left as code with no documentation.
