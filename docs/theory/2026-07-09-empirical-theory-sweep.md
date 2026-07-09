# Empirical theory sweep: temperature algebra, residue arithmetic, spatial order (2026-07-09)

Five experiments set up and run in one day, each a falsifiable claim from the
2026-07-09 theory discussion (CGT temperature framing, Z[ω] quotient
homomorphisms, Meyer/Pisot gateway). All ran on Modal except pure
re-analyses. Confidence tags per SPEC.md convention.

## Headline results

### 1. 🟢 Temperature is ADDITIVE in the +₂ two-move sum algebra — exact, 40,785 pairs, zero exceptions

[experiments/run_two_move_sum.py](../../experiments/run_two_move_sum.py),
`results/two_move_sum.json`, `results/two_move_sum_full.json`,
[figures/fig_two_move_sum_matrix.png](../../figures/fig_two_move_sum_matrix.png).

Rebuilt the exact ≤32-cell component solver from the paused `+₂` thread
(bitmask transposition keys, no Zobrist — the design kept from
[2026-07-08-two-move-sum-execution-paused.md](2026-07-08-two-move-sum-execution-paused.md)),
both players 2 stones/turn. Components = collinear fragments (length ≤ 9,
≤ 4 attacker stones), unions built at non-interacting offsets.

Define one-turn heat h(C) = max over single placements of the minimal
defender hitting-set size of the resulting brink windows (0, 1, 2, or 3;
computed exactly via `covering_placements`). Over **40,785 exactly solved
pairs** (24,241 with both components drawn in isolation; Modal sweep, 0
shard errors):

> **A draw-draw union is an attacker win ⟺ h(A) + h(B) ≥ 3.**
> Zero false negatives, zero false positives.

The naive form of the conjecture ("both components hot") was refuted by the
solver within minutes — hot(2) + mild(1) pairs win too — and the corrected
additive law then held exactly everywhere. This is Berlekamp-style
temperature theory in its sharpest possible form: heats add across the sum,
and the forced-win threshold sits exactly at the defender's ambient budget
of 2. Minimal non-additive example: two centered open-3s in 8-segments
(stones {2,3,4}: h = 2) — each drawn alone, union a first-player win; and a
centered open-3 (h=2) plus an END-anchored open-3 (h=1) suffices.

**Falsifier for the next round:** components with h computed over one turn
but real heat requiring a building turn (deeper forcing). None appeared up
to L=9/size 4 within the 12-empty union cap; push to L=10-11 or
two-axis (bent) components to hunt a counterexample. A hand proof of the
law for collinear fragments now looks within reach and would be a paper
section.

### 2. 🟢 Split-prime (mod-7) extinction in strong play — the game's arithmetic is printed on its diffraction

[experiments/run_spatial_order.py](../../experiments/run_spatial_order.py),
`results/spatial_order.json`,
[figures/fig_spatial_order_extinction.png](../../figures/fig_spatial_order_extinction.png),
[fig_spatial_order_diffraction.png](../../figures/fig_spatial_order_diffraction.png).

Two exact selection rules on win-windows from Z[ω] quotients:
- **mod 3** (ramified λ, class (q−r) mod 3): every 6-window hits each class
  exactly twice (all axis steps ≡ ±1 mod 3);
- **mod 7** (split π = 3+ω — the repo's own `arena._residue` = (q+2r) mod 7,
  axis steps 1, 2, −1, all invertible): every 6-window carries 6 DISTINCT
  residues, i.e. misses exactly one F₇ class.

Statistic: I_m = |Σ_stones e^{2πic/m}|²/N — the structure factor at the
residue-dual wavevector, per board, at matched stone count N*=27, across
three corpora (strong = hexo_bot2 self-play, weak = ca_combo_v2, random
control).

Result: **strong play suppresses I₇** (median 0.29 vs random 0.38,
Mann-Whitney p = 2.4·10⁻⁴; vs weak p = 1.2·10⁻⁶) **and does NOT suppress
I₃** (p = 0.72). The modulus-specificity is the internal control: mere
geometric compactness would suppress both; only the modulus tied to
WIN_LENGTH's window arithmetic (k windows ↔ k distinct F₇ residues) shows
the extinction, and only for the strong player. Weak play shows an
idiosyncratic *mod-3* hyper-balance instead (I₃ ≈ 0.12, p = 10⁻²³ vs
random) — a heuristic artifact of ca_combo_v2 worth a footnote, not a
game-theoretic effect.

### 3. 🟡 The F₇ blocking set may be a real defense — including at k = 6, the actual game

[experiments/run_residue_defense.py](../../experiments/run_residue_defense.py),
`results/residue_defense.json`,
[figures/fig_residue_defense.png](../../figures/fig_residue_defense.png).

Since a k-window's cells carry k distinct F₇ residues, classes {0,1} form a
**blocking set**: every window contains a class-0 or class-1 cell. Defense:
exact hitting-set tier-1 on brink windows + proactive claims restricted to
the {0,1} sublattice (one stone there poisons every live window through it,
up to 18). This is NOT a pairing, so the k ≥ 2m+1 = 7 impossibility theorem
does not forbid it at k = 6 — where no pairing can exist at all.

Full Modal sweep (`results/residue_defense_sweep.json`, 1,200 trials, 30
seeds/cell, adversarial attacker that reserves exactly the defender's
target cells for a same-turn double placement): **0% attacker wins
everywhere** — k ∈ {6,7}, R ∈ {8,12}, up to 120 dense-packed fronts, where
the domino triaged defense was losing ~half its trials at 60.

**But the ablation arm reassigns the credit**: tier-2 targeting ANY empty
window cell instead of the blocking set survives almost identically (worst
cell 1/30 attacker wins). So the load-bearing element is not the F₇
structure — it is the **exact hitting-set tier-1** (cover ALL brink windows
via minimal hitting sets, triggering at k−2, any-cell poisoning), i.e. the
same exactness upgrade that fixed the bot. Corrected reading of the
2026-07-08 dense-cluster counterexample: it falsified a defense whose
tier-1 blocked single 6-of-7 cells one at a time, NOT turn-aware reactive
defense in general. The scripted multi-front attacker class — the strongest
attack constructed by this project so far — **cannot beat an
exact-tier-1 reactive defense at k=6 at all.**

The arena test then closed the loop (`results/bakeoff_residue_blocker.json`):
**hexo_bot2 beats the same defense 24-0, zero draws** (`residue_blocker` in
[competition/external_bots.py](../../competition/external_bots.py), 12
seeded openings × both colours). So the day's clean dichotomy:

- scripted multi-front attackers (pre-committed, non-overlapping window
  fronts, incl. the adversarial reserve-grab class): **0% wins** against an
  exact-tier-1 reactive defense, k=6, up to 120 fronts;
- an adaptive search attacker: **100% wins** against the identical defense.

Mechanistically this is the super-additivity from result #1 turned into a
weapon: disjoint fronts only ever ADD heat (the additive law), and additive
heat ≤ 2/turn is exactly coverable — but an adaptive attacker stacks
windows through shared cells, generating hitting-set demand faster than
any bounded-lookahead reactive rule can discharge. "Passive play has no
theoretical backing" (fresh-start brief, fact 1) is now demonstrated at a
new level: not just for periodic pairings, but for exact-reactive
strategies at the real k=6, against a real search attacker. A cheap draw
does not merely lack a construction; the entire cheap-reactive class now
has a concrete refuting attacker.

### 4. 🟢 Defender collapse scales sub-linearly: n_crit(R) ~ R^α, α ≈ 0.6–0.9

[experiments/run_pairing_scaling.py](../../experiments/run_pairing_scaling.py),
`results/pairing_scaling.json`,
[figures/fig_pairing_scaling_ncrit.png](../../figures/fig_pairing_scaling_ncrit.png).

Re-analysis + supplementary Modal sweep (un-censoring at n_fronts up to 200,
radii extended to R=32) of the dense-cluster phase diagram. Across k ∈
{7,9,11,13,15}: α ∈ [0.60, 0.87] — **decisively excluding both constant
critical density (α=2) and pure count (α=0)**. Reading: collapse mixes
local window-overlap packing with stochastic synchronization of front
maturities against the defender's GLOBAL 2/turn budget — two mechanisms,
intermediate exponent. (Caveat: merged cells mix 300- and 450-turn
horizons; ext cells use the longer horizon, so fitted n_crit is a
conservative envelope.)

### 5. 🟡 Patch entropy is NON-monotone in strength

[figures/fig_spatial_order_patches.png](../../figures/fig_spatial_order_patches.png).
At matched N=27 stones, radius-1 hex-ball patch entropy: weak 7.87 bits <
strong 8.76 < random 9.04. The naive "stronger ⇒ more locally ordered"
story is wrong: strong play is *more* locally diverse than weak play
(richer tactical vocabulary) while still below random. Radius ≥ 2 numbers
are sample-limited (they saturate the log₂(instances) ceiling) — only r=1
is informative at 400-game scale; a 4,000-game strong corpus would open
r=2. Bears directly on the epiplexity narrative: H_T of a *spatial* local
observer does not decrease monotonically with strength, unlike the
*sequential* Markov H_T measured in
[2026-07-08-hexanacci-and-mdl-policy-prior.md](2026-07-08-hexanacci-and-mdl-policy-prior.md) §0.

## Supporting data generated

- `results/hexo_bot2_selfplay.json` — 400-game strong self-play corpus
  (modal_selfplay.py; all decisive, B 204 / W 196, mean 41.5 stones).
  Note the near-parity: no measurable P1 edge in strong self-play at
  12-stone random openings (Wilson CI would include 0.5) — relevant to the
  P1-advantage thread (SPEC.md P1).
- `results/pairing_capacity_phase_diagram_ext.json` — supplementary sweep.
- `results/eval_mining.json` — mined eval weights UNDERPERFORM the hand
  prior (0.594 vs 0.610 test acc; signal concentrated at brink level) —
  the brief's open question #3 answered negative for weak-corpus mining.

## Corrections to the 2026-07-09 theory discussion made by the data

1. The "both components hot" temperature conjecture was wrong; the
   additive law replaced it (stronger and cleaner).
2. The mod-3 class map must be (q−r) mod 3, not (q+r) — embedding matters
   ((q+r) degenerates on the (1,−1) axis).
3. No mod-3 extinction exists in strong play — the ramified-prime selection
   rule does not leave a diffraction signature; the split-prime one does.
4. "Stronger ⇒ more ordered" fails at patch level (see §5).
