# HexGO Theory — Core Findings Spec

> Single source of truth for the HexGO research programme. This file distils the
> material that was previously scattered across `README.md`, `docs/ROADMAP.md`,
> `docs/theory/`, `docs/ARTIFACTS.md`, and the experiment bundles in `papers/`.
> It is written to be self-contained: someone who reads only this file should
> understand the game, the central conjecture, what has been empirically
> established (with numbers and provenance), and what remains open.
>
> Provenance pointers in the form `results/x.json` / `papers/.../README.md` point
> at the artifacts that back each claim. Those artifacts are preserved in the
> repo (code, results, figures, markdown, papers are all kept); this spec is the
> index and the argument, not a replacement for them.

---

## 1. The game

HexGO is **infinite Connect-6 on the hex lattice**, identified with the
Eisenstein integer ring **Z[ω]** where ω = e^(2πi/3).

- **Board:** the infinite hex grid = Z[ω]. No edges.
- **Turn rule (1-2-2):** Player 1 (Black) places **1** stone on turn 1; thereafter
  both players place **2** stones per turn.
- **Win condition:** **6 consecutive stones along any of the three Z[ω] unit axes.**
  A win is exactly a length-6 arithmetic progression in Z[ω] with unit step:

  ```
  u₁ = (1, 0)    q-axis
  u₂ = (0, 1)    r-axis
  u₃ = (1, -1)   diagonal axis
  ```

  So "6 in a row" is a purely number-theoretic object: a unit-step 6-AP in Z[ω].

- **Engine invariant:** `WIN_LENGTH == 6` is asserted deep in the upstream engine
  (`../hexgo/game.py`). Sweeping it requires patching that assertion deliberately.

Two sibling repos:
- `../hexgo` — production engine (rules, AlphaZero, Rust MCTS, GPU inference, dashboard).
- `../hexgo-theory` (this repo) — the research lab.

---

## 2. The central conjecture

> **Perfect play in HexGO produces a quasi-crystalline pattern: aperiodic,
> D6-symmetric, with a substitution structure whose inflation constant is a
> Pisot number.**

The argument (from `README.md`):

1. **No translational symmetry.** Black's opening stone at the origin breaks
   translation invariance; a periodic pattern would expose an exploitable period
   vector, contradicting optimality.
2. **D6 symmetry is preserved.** The full dihedral group D6 (60° rotations,
   reflections) is a symmetry of Z[ω] and of the rules. A unique optimal strategy
   gives the occupied set D6 symmetry radiating from the origin.
3. **Self-similarity from constraint propagation.** A local threat at radius r
   forces responses at r+5 (= WIN_LENGTH − 1), which force further constraints at
   r+10, … If the number of local pattern types (up to D6) is finite, this is a
   substitution tiling system.
4. **Pisot property.** By the Pisot substitution theorem (Thurston–Kenyon), if the
   substitution matrix's Perron–Frobenius eigenvalue is a Pisot number, the tiling
   is aperiodic with pure-point diffraction — a mathematical quasi-crystal.

Pisot candidates flagged in the work: tribonacci ≈ 1.3247, plastic number ≈ 1.3247,
golden ratio ≈ 1.618.

---

## 3. Where HexGO sits (descriptive complexity)

This is the cleanest *settled* theoretical result and it tells us which tools apply.

- HexGO's payoff ("some player has 6 in a row") is **Σ⁰₁ (open)** — a win is
  observable in finite time — so it is **directly determined by Gale–Stewart**.
- Infinite Hex (Hamkins–Leonessi 2022, *Infinite Hex is a draw*,
  `papers/2201.06475v3`) has payoff **Σ⁰₇** (Törnä tightens this): "player has an
  infinite path" is not observable in finite time, needing heavy infinitary
  machinery and yielding a *draw*.
- **HexGO is two-plus levels lower in the Borel hierarchy.** That is *why*
  finite-horizon analysis and measurement (epiplexity, diffraction), not
  Hamkins-style infinitary determinacy, are the right lens here.

Source: `docs/theory/2026-04-17-hamkins-synthesis.md`.

**Strategy-stealing** rules out a second-player win. Empirics (§5) point to a
**first-player (Black) win**, as expected for this family.

---

## 4. Two research lines (and how they fit)

The repo contains **two complementary narratives** that approach "structure of
optimal play" from opposite ends:

| Line | Question | Home | Lens |
|---|---|---|---|
| **A. Epiplexity / quasicrystal** | Does perfect play's *global* point pattern have Pisot quasicrystalline order? | `docs/`, `engine/`, `results/`, `figures/` | MDL / diffraction / self-play corpora |
| **B. Transversal-atom / forcing** | What is the *local* algebra of forcing — which obligations exceed the defender's budget? | `papers/connectn_lab_package/`, other `papers/*` bundles | Hypergraph transversal number τ, atoms |

The bridge: line B's **forcing atoms** are the local substitution tiles whose
finiteness (line A, point 3) would imply the Pisot structure. Line A measures the
*global* spectrum that finiteness predicts. They are the same object — local
generator vs. global pattern.

### 4.1 Epiplexity unification (line A's framing)

Per Finzi et al. 2026 (*From Entropy to Epiplexity*, the framing paper for
`docs/ROADMAP.md`), every experiment outputs a point `(|P|, H_T)`:

- `S_T(X) = |P*|` — **epiplexity** (structural content): description length of the
  best time-bounded program.
- `H_T(X)` — time-bounded entropy (residual randomness).

The unifying claim: the Pisot inflation constant λ **is** the rate at which
`S_T(corpus_N)` saturates with corpus size N. A finite substitution system ⟺
`S_T` grows like `O(log N)` not `Ω(N)`. So measuring `S_T(N)` is a *spectroscope*
for the Pisot conjecture that sidesteps enumerating the forcing graph by hand.
HexGO's rules are ~200 bytes, so its corpus has trivial Kolmogorov complexity yet
rich emergent structure — a clean, human-tractable instance of "computation
creates information."

---

## 5. Empirical results (established, with numbers)

All from `results/` + `figures/` + `papers/.../README.md`. CIs are Wilson 95%
unless noted.

### Line A — quasicrystal / agent ladder

| Finding | Number | Provenance |
|---|---|---|
| **First-player advantage exists** (Combo-v2 as Black) | Black share = **0.53 [0.42, 0.64]** (fixed from v1's 0.37 centre-bias defect) | `results/combo_defect.json`, `run_combo_defect.py` |
| **Pairing strategy works** (MirrorAgent, c ↦ −c) | non-loss vs Random = **1.00**; P2-wins vs Combo-v2 = 0.14 | `results/mirror_agent.json`, `run_mirror_agent.py` |
| **Quasi-crystalline order in self-play** | Bragg99 = **0.51 ± 0.13** (n=9) vs random control **0.055** | `results/diffraction_p4.json`, `engine/diffraction.py` |
| **Delone (Meyer-set) property** | d_min bounded; corr(N, d_max) = **+0.07** (uncorrelated) | `results/diffraction_p4.json` |
| **Strong play is decisive, not drawish** | draw fraction does *not* rise with horizon (Hamkins-echo) — consistent with Σ⁰₁ | `results/hamkins_echo*.json`, `run_hamkins_echo*.py` |
| **Hand-crafted ladder plateaus** | ca_combo_v2 ≈ combo (p_B = 0.44 [0.31, 0.58]); motivates NCA zoo | `results/fma_curve.json` |
| **Untrained NeuralCA baseline** | 12.2k params, 53 ms/move on RTX 2060 | `results/neural_ca_benchmark.json`, `engine/neural_ca.py` |

**P1–P5 falsifiable propositions** (`docs/theory/2026-04-17-hamkins-synthesis.md`):

| Prop | Claim | Status |
|---|---|---|
| P1 | First-mover (Black) advantage | **Supported** (combo_defect 0.53) |
| P2 | A Connect-6 pairing strategy exists | **Supported** (MirrorAgent both clauses) |
| P3 | Pisot / sub-linear S_T(N) | **Preliminary** — the open headline |
| P4 | Pure-point diffraction component | **Supported** (Bragg99 0.51) |
| P5 | Delone / Meyer-set bounds | **Supported** (d_max stable) |

### Line B — transversal-atom framework (`papers/`)

Defender budget `p = 2` (the 1-2-2 rule). **Pressure = max(0, τ(O) − p)** where
τ is the transversal number (min hitting set) of the obligation hypergraph O. A
position forces iff some obligation family has **τ(O) > p**.

| Finding | Detail | Provenance |
|---|---|---|
| **Parity is the dominant opening law** | Odd k puts the urgent layer on Black's rooted stone (tempo=Black); even k on White's rhythm (tempo=White). For Connect-k sweep k=3..10. | `papers/connectn_lab_package/.../connect_k_parity_results/.../README.md` |
| **Primality is a second-order effect** | prime-k Black first-reply τ>2 openings = 48 vs composite = 47 (near-tie); Connect-5/7 are the clean prime laboratories (k=3 collapses at seed) | same |
| **Seeded asymmetry** | the q=1,p=2 opening creates a rooted symmetry-breaking *charge*, not just material balance (CONJECTURES §2) | `CONJECTURES.md` |
| **Opening tablebase (alpha-beta, A2 radius 3)** | first finite A2 ball containing length-6 wins; depth-10 beam search, 2.46M nodes, classes {black_bulk_edge, screened_or_balanced}; no decisive opening (all "U") | `papers/connectn_lab_package/.../opening_tablebase_results/*/README.md` |
| **Opening optimality atlas (GPU rollouts)** | 371 static openings, 29 rolled out; outcomes overwhelmingly drawn under bounded local strategies (e.g. 442 none / 20 white / 2 black) | `papers/connectn_lab_package/.../opening_optimality_results/rich_run/README.md` |
| **D6 seeded-hypergraph spiral** | OEIS A392177-style D6 spiral on the Connect-6 winning-set hypergraph; produces shell/sector imbalance sequences | `papers/connectn_lab_package/.../d6_seeded_hypergraph_results/*/README.md` |
| **Primitive forcing atom miner** | mines minimal τ>2 obligation hypergraphs ("atoms"); rail/bridge motifs; bulk-vs-boundary τ prediction | `papers/hexconnect6_atom_miner_results/.../README.md` |
| **Atom-composition opening eval** | scores openings by *compositions* of primitive atoms looked up in a periodic-table fingerprint index; minimax over continuation depth | `papers/hexconnect6_atom_compositions_results/.../README.md` |
| **Depth-2 minimax proto-pressure atlas** | White open → max Black reply → min White defence → max Black continuation; rail→bridge shape transitions, continuation shape attractors | `papers/hexconnect6_depth2_minimax_results/.../README.md` |

### Line B' — UDC positions (algebraic point sets on Z[ω])

Construction of Eisenstein point sets via the CM class-field-tower machinery from
the 2025 disproof of the Erdős unit-distance conjecture. Subset-products of split
primes q ≡ 1 mod 3 give Eisenstein integers of equal modulus.

| Label | t | D = ∏qᵢ | n stones | ν/n | Bragg99 |
|---|---|---|---|---|---|
| udc_t1 | 1 | 7 | 1391 | 0.912 | **0.839** |
| udc_t2 | 2 | 91 | 1310 | 1.375 | **0.840** |
| udc_t3 | 3 | 1729 | 22951 | 2.665 | 0.057 |
| udc_t4 | 4 | 53599 | 692601 | 5.328 | 0.054 |
| random_disc | — | — | 12171 | — | 0.058 |

Small towers (t=1,2) produce **strongly Bragg-ordered** point sets (0.84) — an
*algebraically-generated* quasicrystal on the same lattice; large towers wash out
to noise. Source: `docs/theory/2026-05-22-udc-positions.md`, `results/udc_positions.json`.

---

## 6. Speculative threads (testable, not yet established)

These live in `docs/theory/` and `papers/.../CONJECTURES.md`. Each has a falsifier.

- **Bellman–Turing instability** (`2026-05-20`): the Boltzmannised Bellman operator
  on Z[ω] has a Turing (reaction-diffusion) instability at non-zero wavenumber k*,
  giving a *first-principles* mechanism for the quasicrystal — pattern is
  *predicted*, not just observed. Activator = own Erdős–Selfridge potential,
  inhibitor = opponent potential. Backed by FFT/dispersion figures (`fig_bt_*`).
- **Surreal / fractal conjectures** (`2026-05-09`): which quotient of HexGO admits
  surreal values; a verified recursive *strategy fractal* (depth-2, inflation-5:
  614 stones, 321 winning lines) checked against the length-6 rule. `engine/fractal_strategy.py`.
- **Bounded crystal / Bellman sum** (`2026-05-09`): can HexGO be written as an
  infinite live-line sum whose optimal Bellman fixed point has quasicrystalline
  support? Three levels: exact recursion → live-line feature sum → observable
  crystal signatures. `engine/crystal.py`, `results/crystal_survey.json`.
- **CGT / Hackenbush** (`2026-05-09`): empirical temperature/thermography layer
  over live 6-line components; the two-move sum `+₂` is *not* ordinary disjunctive
  CGT. `engine/cgt.py`, `engine/two_move_sum.py`.
- **Transversal-threshold universality** (CONJECTURES §1): τ(O) > p mediates local
  forcing for *any* lattice connect-n game; atoms vary, threshold is invariant.
- **Atom algebra** (CONJECTURES §7): when is τ(A ∪ B) = τ(A) + τ(B)? The
  Conway/BCG route to a calculus of local play.

---

## 7. Open questions (the real frontier)

1. **P3 — is S_T(N) sub-linear?** Fit `S_T ∼ α log N + β` vs linear on
   Combo-v2 / NCA-champion self-play across N ∈ {10², …, 10⁵}. Sub-log ⇒ finite
   substitution ⇒ Pisot supported; linear ⇒ **Pisot conjecture empirically refuted**.
   This is the headline result the programme is built to settle.
2. **λ convergence.** Does λ estimated from epiplexity scaling match λ read off
   diffraction peak spacings to within ±0.05 (or at least the same Pisot interval)?
   Two independent routes to the same constant = the strongest possible evidence.
3. **Is the forcing graph finite?** Finitely many local pattern types up to D6 under
   optimal play. This is line B's atom-finiteness = line A's substitution-finiteness.
4. **Inflation constant value.** Which Pisot number — tribonacci, plastic, golden?
5. **Critical density.** Occupied fraction within radius R as R→∞ — is it irrational?
6. **NP-hardness (NOT yet in the repo).** A Discord contributor sketched a
   reduction from **3-SAT** to show HexGO is NP-hard. **No formal proof exists in
   this repo** — the repo's complexity story is *descriptive-set-theoretic* (Σ⁰₁),
   a different axis from computational hardness (NP). Formalising the 3-SAT
   reduction (likely: variable gadgets as forced ladders, clause gadgets as
   shared threat cells, τ>2 as the satisfiability witness) is a genuinely open and
   high-value direction. The transversal-atom framework (line B) is the natural
   substrate for it.

---

## 8. Toolbox (what's in `engine/` and `experiments/`)

- `engine/analysis.py` — live_lines, potential, fork, fingerprint primitives.
- `engine/agents.py` — ForkAware, PotentialGradient, Combo, Mirror.
- `engine/ca_policy.py` — CAAgent framework; `make_combo_v2_ca`.
- `engine/neural_ca.py` — NeuralCAAgent (torch+CUDA hex-conv stack).
- `engine/diffraction.py` — GPU diffraction / Bragg-peak analyser.
- `engine/cgt.py`, `engine/two_move_sum.py`, `engine/isomorphisms.py` — CGT layer,
  +₂ algebra, exact A2/D6 quotients.
- `engine/crystal.py`, `engine/fractal_strategy.py` — crystal observables, strategy fractal.
- `experiments/run_*.py` — one self-contained experiment each; output to
  `results/<name>.json` + `figures/fig_<name>_*.png`. `--quick` flag for dev.
- `experiments/harness.py` — parallel match harness (mp.Pool, Wilson CIs, agent registry).
- `papers/connectn_lab_package/.../connectn_lab/` — the τ-atom framework (atoms,
  obligations, transversals, opening_tablebase, self_play, theory_book).

Reproducibility convention: seed everything; results + figures are tracked in git
(reproducibility > repo size); each result regenerable from its `run_*.py`.

---

## 9. References

- Finzi et al. (2026). *From Entropy to Epiplexity*. arXiv:2601.03220 — `papers/`.
- Hamkins, J. D., & Leonessi (2022). *Infinite Hex is a draw*. arXiv:2201.06475 — `papers/`.
- Baake, M., & Grimm, U. (2013). *Aperiodic Order, Vol. 1*. CUP. (Pisot/diffraction.)
- Berlekamp, Conway, Guy (1982). *Winning Ways*. (CGT.)
- Erdős, P., & Selfridge, J. (1973). On a combinatorial game. *JCTA* 14, 298–301.
- Kenyon, R. (1996). The construction of self-similar tilings. *GAFA* 6, 471–488.
- Thurston, W. (1989). *Groups, tilings, and finite state automata*. AMS.
- Wu, I.-C., & Huang, D.-Y. (2006). A new family of k-in-a-row games. *ICGA J.* 29(1).
- OpenAI (2025). Disproof of the Erdős unit-distance conjecture. (CM tower construction — line B'.)

---

*Distilled from the full repo on 2026-06-14. The artifacts behind every claim
(code, JSON results, figures, theory notes, paper bundles) remain in the repo;
this spec is the map.*
