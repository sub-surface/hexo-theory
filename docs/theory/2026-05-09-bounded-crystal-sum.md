# Bounded Crystal Structure, Bellman Sums, And Symmetry Breaking

*2026-05-09*

> **Status (2026-07-05): PARKED — speculative, not yet established.** Interesting
> formal framing (exact Bellman recursion, live-line feature sum, Boltzmannized
> operator) but none of §8's falsifiers have actually been run. See
> [SPEC.md](../../SPEC.md) §6. Not on the critical path until the τ/Pisot spine
> converges or is falsified.

This note turns the "less biased crystal experiment" into a mathematical target.
The guiding question is:

> Can HeXO be represented by an infinite sum whose optimal Bellman fixed point
> has a quasi-crystalline support?

The answer is plausibly yes in representation, but not yet in closed-form
solution. The useful move is to distinguish three levels:

1. exact game recursion;
2. live-line infinite feature sum;
3. observable crystal signatures of approximate fixed-point policies.

## 1. Exact Conway/Bellman Recursion

A finite HeXO position is a finite board `B`, a player-to-move `p`, and a turn
phase `tau in {opening-one-stone, first-of-two, second-of-two}`. Let legal
single placements be `A_1(B)` and legal turn actions be:

```text
A_tau(B) =
  single cells                      if tau = opening-one-stone or second-of-two
  ordered or unordered cell pairs    if tau = first-of-two.
```

Then the exact finite-horizon value satisfies a Bellman recursion:

```text
V_T(B, p, tau) =
  +1                         if Black has six in a row
  -1                         if White has six in a row
  0                          if T = 0 and no winner
  max_{a in A_tau(B)} V_{T-1}(B + a, p', tau')      if p = Black
  min_{a in A_tau(B)} V_{T-1}(B + a, p', tau')      if p = White.
```

This is the minimax/Bellman form of the game. The Conway pregame form is the
same recursion written as:

```text
G(B, tau) = { G(B + a, tau') for Black actions a
            | G(B + a, tau') for White actions a }.
```

The important technical point is that the action set contains *two-placement*
actions on most turns. So even if local threat components look like CGT games,
the global operator is not ordinary disjunctive addition. It is the two-handed
operator introduced in `engine/two_move_sum.py`.

Lean/mathlib already has the right formal substrate: `PGame` is built from Left
and Right move types, with Conway induction; surreal numbers are the numeric
subtype/quotient of these pregames. That means a Lean formalization should start
with `PGame`, not directly with surreal numbers. Most HeXO positions will be
hot or fuzzy games, not numeric surreal numbers.

## 2. Live-Line Infinite Sum

The exact board can be embedded in an infinite coordinate system over all
length-6 axial arithmetic progressions:

```text
L_6 = { (x, x+u, x+2u, ..., x+5u) : x in Z[omega], u in AXES }.
```

Define line features:

```text
phi_l(B) =
  +k     if line l contains k Black stones and no White stones
  -k     if line l contains k White stones and no Black stones
   0     if line l is blocked or empty.
```

Then a finite position has an infinite but finitely supported/live-adjacent
feature sum:

```text
Phi(B) = sum_{l in L_6} phi_l(B) e_l.
```

This is isomorphic to the tactical hypergraph representation: cells are vertices,
live six-lines are hyperedges, and moves update only the finitely many basis
vectors touching the placed cells.

The Bellman fixed point can then be written on this feature space:

```text
V(Phi, p, tau) = Opt_p,a [ R(Phi, a) + gamma V(U(Phi, a), p', tau') ].
```

Here `U` is the local line-feature update and `R` is terminal win reward. For
the actual finite game tree, `gamma = 1`; for empirical fixed-point
approximation, `gamma < 1` or a temperature/entropy regularizer makes the
operator easier to learn.

## 3. Beta Partition Sum

For non-exact experiments, define a Boltzmannized Bellman operator:

```text
Z_beta(Phi, p, tau) =
  sum_{a in A_tau} exp(beta [R(Phi, a) + gamma V(U(Phi, a))]).
```

Then:

```text
V_beta = beta^{-1} log Z_beta
```

and:

```text
lim_{beta -> infinity} V_beta = Bellman optimum.
```

This gives a bridge between "infinite sums" and empirical play. Agents like
`ca_combo_v2`, Rust pure-MCTS, and future neural policies are approximate
samplers from different finite-temperature versions of the same Bellman
landscape. The crystal survey asks whether those approximate fixed points leave
stable large-scale signatures.

## 4. Symmetry Breaking

The rules are invariant under D6 and color/player exchange with turn adjustment.
The opening move breaks translation symmetry. Later play may break or restore
angular symmetry depending on strategy.

Observable symmetry-breaking channels:

- D6 Jaccard similarity: how close the point set is to its own rotations and
  reflections;
- angular harmonics: `m = 6` and `m = 12` are hex-compatible, while lower
  harmonics reveal directional bias;
- sector entropy: whether stones fill directions evenly;
- Bragg99: reciprocal-space peak concentration;
- Delone bounds: whether nearest-neighbor gaps stay bounded;
- box dimension: whether growth is line-like, area-like, or fractal-like.

These are implemented in `engine/crystal.py` and emitted by
`experiments/run_crystal_survey.py`.

## 5. Busy-Beaver-Style Complexity

The rule specification is tiny. That is not the same as the strategic depth
being tiny.

Let `K_U(HeXO)` be the byte length of the shortest program on a fixed universal
machine that implements:

- `Z[omega]` axial coordinates;
- the 1-2-2 turn rule;
- length-6 win detection;
- legal placement generation.

Then define a HeXO busy-beaver analogue:

```text
BB_HeXO(n) =
  max terminal game length produced by any n-byte deterministic strategy pair
  whose interaction is legal and eventually terminal.
```

Variants:

```text
BB_crystal(n) =
  max Bragg99 or D6-order score produced by an n-byte strategy generator.

BB_depth(n) =
  max Bellman search horizon whose policy is compressed into n bytes.
```

These are not computable in the full busy-beaver sense once arbitrary programs
are admitted. But bounded versions are empirical and useful:

- restrict strategies to this repo's agent registry;
- measure source gzip length as program length;
- plot program length against Bragg99, D6 symmetry, FMA, and win rate.

This turns "small rules create huge structure" into a measurable object, not a
vibe.

## 6. Current Quick Survey

The first quick run compared:

- `random`;
- `greedy`;
- `ca_combo_v2`;
- `rust_pure_mcts`;
- `random_disc`;
- `hex_patch`;
- recursive verified strategy fractal `fractal_d2_i5`.

It emitted:

- `evidence/results/crystal_survey.json`;
- `evidence/figures/fig_crystal_survey_gallery.png`;
- `evidence/figures/fig_crystal_survey_metrics.png`;
- `evidence/figures/fig_crystal_survey_harmonics.png`;
- `evidence/figures/fig_crystal_survey_diffraction.png`;
- `evidence/figures/fig_crystal_survey_fractal_highres.png`.

Early signal, not a conclusion:

- random self-play has low Bragg99;
- random-disc control is higher than random self-play but below structured
  agents/controls;
- greedy, `ca_combo_v2`, hex patch, and the recursive fractal all show
  substantially higher reciprocal concentration;
- the fractal has strong `m = 6` harmonic content, as expected;
- Rust pure-MCTS in the quick `sims=16` setting is more line-like and less
  Bragg-concentrated than the handcrafted compact agents.

## 7. Next Full Run

Recommended command:

```powershell
& "C:\Program Files\Python312\python.exe" experiments\run_crystal_survey.py `
  --agents random greedy potential combo ca_combo_v2 mirror `
  --n-games 24 `
  --max-moves 160 `
  --diffraction-grid 96 `
  --rust-games 12 `
  --rust-sims 96 `
  --fractal-depth 3 `
  --highres-depth 4
```

This is the first serious "free computation" pass. After that:

1. add source-length / gzip-length estimates for each agent;
2. add Bellman residual probes on the live-line feature basis;
3. sweep fractal inflation `{2,3,4,5,6,7,8}`;
4. compare motif spectra against strong self-play via `canonical_board_key()`;
5. attempt a Lean skeleton:

```text
HexPosition -> PGame
numeric local components -> Surreal
non-numeric components -> hot/fuzzy PGame
```

## 8. Falsifiers

The bounded-crystal hypothesis weakens if:

- Bragg99 and D6 metrics fail to separate strong play from matched random
  controls at larger `n`;
- strong play is dominated by low-order angular moments rather than `m = 6` or
  `m = 12`;
- Bellman residuals on live-line features do not improve over raw potential;
- motif spectra grow linearly with no recurrence under D6 canonicalization;
- program length has no relationship to crystal/order metrics.

The research bet is not that every strong policy is pretty. The bet is that the
Bellman fixed point, when projected through the right live-line basis, has a
bounded aperiodic order signature.

## References Used For Formalization Direction

- Lean mathlib4 `SetTheory.PGame`: combinatorial pregames with Conway induction.
- Lean mathlib4 `SetTheory.Surreal.Basic`: surreal numbers built from numeric
  pregames.
- Lean mathlib4 `SetTheory.Game.Birthday` / surreal dyadic material: useful for
  future birthday-growth experiments.
