# Group theory of HeXO via ℤ[ω]: Hall–Paige, F₄, triple tilings, and where the Monster is (not)

> Status: working theory note. Experiment: [experiments/run_eisenstein_group_theory.py](../../experiments/run_eisenstein_group_theory.py)
> → `evidence/results/eisenstein_group_theory.json`, figures `evidence/figures/fig_eisenstein_*.png`.
> Confidence tags: 🟢 proved (or exact computation + proof), 🟡 computed, not proved, 🔴 open.

## 0. Rule reading, settled first

Two readings of "six in a straight line" are compared throughout:

- **R3, the rule.** Six *adjacent* stones along one of the three axes (1,0), (0,1), (1,−1), at any translate.
  Each line is parallel to a unit of ℤ[ω] (the axes are the three ±-pairs of the six units).
- **R6, a variant.** R3 plus the three corner-to-corner directions (1,1), (2,−1), (1,−2) = √−3 · units.
  These are geometrically straight, but consecutive cells only touch at a vertex.

Audit 🟢: `check_win` at [competition/arena.py:49](../../competition/arena.py:49) is translation-invariant and implements R3 exactly.
At random positions up to 10⁶ cells from the origin: 2000/2000 axis sixes detected, 0/2000 corner sixes, 0/2000 gapped sixes.
The other enumerators read have the same structure: `_windows_through` in `competition/proof_solver.py`, `_all_windows` in `engine/analysis.py`, `winning_lines` in `hexo-complexity/death_hexo.py`.
Overlines (≥ 6) win. **No origin bug.** The R3/R6 question is the only real ambiguity, and it matters: every threshold below roughly doubles under R6.

## 1. Symmetry: p6m, spent by ply 3 🟢

Aut of the window hypergraph = ℤ[ω] ⋊ (μ₆ ⋊ C₂) ≅ p6m, under both R3 and R6.
Overlapping windows chain into lines, so a hypergraph automorphism is an autotopism of the group 3-net of ℤ, hence affine.
Exhaustive count over stones in a radius-3 disc:

| after turn | stones | trivial stabiliser |
|---|---|---|
| 1 | 1 | 0% (\|Stab\| = 12) |
| 2 | 3 | 78.1% |
| 3 | 5 | 98.6% (348,612 / 353,430, exhaustive) |
| 4–5 | 7–9 | > 99.9% (Monte Carlo, 2·10⁵) |

Strategy-stealing rests on monotonicity (an extra stone never hurts), not on symmetry. The group is crystallographic and solvable, and it contains no sporadic group.

## 2. Perfect blockers ⇔ toroidal hex rooks (Hall–Paige) 🟢

**Lemma.** A periodic set S of density exactly 1/k meets every k-window iff the k×k torus (ℤ/k)² carries k points with exactly one on every line of every direction.
Call these *hex rooks* (R3) or *hex queens* (R6).

*Proof.* Each line needs a point in every k consecutive cells, so its density is ≥ 1/k.
Average density = 1/k forces exact spacing k on every line. That makes S invariant under k·u for each direction u, so S is (kℤ)²-periodic.
The converse direction is immediate. ∎

In row-permutation form σ: row r holds the point (σ(r), r). The conditions are:

- **R3:** σ and r ↦ σ(r)+r are both permutations, i.e. σ is a complete mapping of ℤ/k.
- **R6:** additionally σ(r)−r, σ(r)+2r and 2σ(r)+r are permutations.

**Theorem (R3) 🟢.** Hex rooks exist ⇔ k is odd.
- Odd k: take σ = id.
- Even k: Σ(σ(r)+r) = 2·Σi ≡ 0, but Σi ≡ k/2 (mod k).
- This is the cyclic case of the Hall–Paige theorem (Hall–Paige 1955; proved in general by Wilcox, Evans and Bray, 2009).
- Counts for k = 1…13: 1, 0, 3, 0, 15, 0, 133, 0, 2025, 0, 37851, 0, 1030367 = k · A003111.

**Theorem (R6), partial.**
- 🟢 gcd(k, 30) = 1 ⇒ solvable. σ(r) = 2r gives the five functionals 2r, 3r, r, 4r, 5r, all bijective.
- 🟢 2 | k ⇒ unsolvable, by the parity sum above.
- 🟢 3 | k ⇒ unsolvable. Squares are well-defined mod k. Write A = Σσ², B = Σr², C = Σσ·r, S = Σᵢ i².
  The functionals σ+r and σ−r give A+B±2C ≡ S, with A ≡ B ≡ S. So 2C ≡ −S and 2C ≡ S, hence 2S ≡ 0 (mod k).
  But 2S = (k/3)(k−1)(2k−1), and (k−1)(2k−1) ≡ 1 (mod 3) when 3 | k, so k ∤ 2S. This is the hex analogue of Pólya's toroidal-queens argument.
- 🟡 5 | k ⇒ unsolvable: verified for k = 5, 10, 15 by exhaustive search. No proof yet; the quadratic identities only give 6S ≡ 0.
- Exhaustive counts k ≤ 17: solutions only at 1, 7, 11, 13, 17 (1, 14, 66, 442, 204).
- **Conjecture:** hex queens exist ⇔ gcd(k, 30) = 1. Pólya's square-board answer is gcd(k, 6) = 1.

**Corollary for HeXO (k = 6) 🟢.** No periodic set of density 1/6 blocks every 6-window, under either reading.

## 3. Sublattice blockers: the F₄ obstruction 🟢

A sublattice Λ meets every u-line iff u generates ℤ²/Λ. So ℤ²/Λ ≅ ℤ/n, with every direction mapping to a unit.

- **R3:** n must be odd. Mod 2, the three axes are the three non-zero points of F₂² ≅ F₄ (2 is inert in ℤ[ω]), and no character to F₂ is non-zero on all three.
  Equivalently, 6 is not a norm a² − ab + b².
- **R6:** gcd(n, 30) = 1.
- **Best lattice blocker for k = 6:** density 1/5 (R3); none below density 1 (R6).

**Exact MILP over every period lattice** (Hermite normal form, index ≤ N), minimum hitting set of all k-windows:

| reading, k | best density found | at index | search N |
|---|---|---|---|
| R3, k = 5 | 1/5 | 5 | see JSON |
| R3, **k = 6** | **1/5** | 5 | see JSON |
| R3, k = 7 | 1/7 | 7 | |
| R6, k = 6 | 4/15 (quick, N = 30) | 30 | see JSON |

Under R3 at k = 6, nothing periodic beats the lattice up to the search bound.
🔴 Open: is inf density = 1/5, or can large-period or aperiodic sets get into (1/6, 1/5)?

## 4. Tiling draws: k ≥ 11 is a draw under 1-2-2 🟢

The pairing bound k ≥ 2m+1 ([2026-07-08-pairing-thresholds-and-game-values.md](2026-07-08-pairing-thresholds-and-game-values.md) §1) is for 1-1 alternation.
Under 1-2-2, pairing fails outright: Maker places both halves of a pair in one turn.

**Triple-tiling strategy.**
- *Setup:* a family of disjoint collinear triples, each of some direction u, such that every k-window of direction u wholly contains a u-triple.
- *Breaker's play:* every turn, for each triple that Maker's ≤ 2 new stones touched and that Breaker hasn't yet entered, Breaker takes a free cell of it.
  At most 2 triples need answering, and if both Maker stones hit the same triple, its third cell is still free. So Breaker's 2 stones always suffice.
- *Result:* no triple is ever fully Maker's, so no window is.
- *Opener:* Black's single opening stone needs at most one answer, and as Breaker, Black's own opener is a free extra stone. So **either** colour can run it.

**Counting bound.** Disjoint u-triples of span ≥ 3 need line density ≥ 3/(k−2) in each of m directions, so k ≥ 3m+2. That gives R3: k ≥ 11 and R6: k ≥ 20.
At equality the tiling must be a perfect partition into contiguous triples, so the MILP over contiguous tiles at the threshold loses nothing.

| certificate | counting bound | found at | period lattice | plane check |
|---|---|---|---|---|
| pairs, 1-1, R3 | 7 | **7** | index 12 | disjoint, 0 uncovered windows |
| **triples, 1-2-2, R3** | **11** | **11** | index 27, ⟨(9,0),(3,3)⟩ | disjoint, 0 uncovered |
| pairs, 1-1, R6 | 13 | 14 | index 13 | disjoint, 0 uncovered |
| triples, 1-2-2, R6 | 20 | 21 | index 19 | disjoint, 0 uncovered |

**Theorem 🟢.** HeXO (R3, 1-2-2) with win length k ≥ 11 is a draw: each player has a non-losing strategy.

- I have not searched the literature for this; treat priority as unknown.
- It leaves the band k ∈ {7, …, 10} open, plus k = 6 (HeXO). Pass two of the pairing note found the naive turn-aware k = 7 defense fails under dense clustering.
- Falsifiable next step: a k = 7…10 certificate built from mixed pairs and triples, or a Maker win at k = 10 in the bounded solver (`competition/proof_solver.py`).

## 5. "Rank 12" and the Monster 🟢 (computation) / honest verdict

Rank means rank as a ℤ[ω]-module: the number of Eisenstein coordinates.

- **Rank 1:** A₂ = ℤ[ω], the board. Its 6 minimal vectors are the 6 units, which are exactly the R3 win directions.
- **Rank 4:** Construction A over ℤ[ω] from the tetracode mod θ = 1−ω (ℤ[ω]/θ = F₃) gives E₈. Shells computed: 240 / 2160 / 6720 at norms 3 / 6 / 9.
- **Rank 12:** the complex Leech lattice, mod-θ data the ternary Golay code. Weight enumerator computed: 1 + 264y⁶ + 440y⁹ + 24y¹², Aut = 2·M₁₂.
  Leech's Aut over ℤ[ω] is 6·Suz, which leads through Co₁ to 2^{1+24}·Co₁ = C_𝕄(2B). The Leech-level facts are quoted, not computed here.

**One genuine board–Monster identity, computed from lattice-point counts only.**
Let θ_{A₂} = a(q) count the board cells, and let c(q) be the theta series of the shifted lattice A₂ + (1/3, 1/3), i.e. the triangle centres.
Then, matching the η-quotient through q²³:

  T₃B(τ) = (η(τ)/η(3τ))¹² + 12 = 27 · (a/c)³ − 15 = q⁻¹ + 54q − 76q² − 243q³ + …

The q coefficient 54 = 1 + χ₁₉₆₈₈₃(3B).

**Verdict.** This is a fact about the board's *metric* (counting cells by norm), and HeXO's win condition never consults a norm.
The game's own group theory is p6m, F₄ = ℤ[ω]/2 and Hall–Paige on ℤ/6. No sporadic group appears.

What would change this: positions of some HeXO variant on a torus ℤ[ω]/I where Maker cannot force a win, *closed under addition mod θ or mod 2*.
That would be a Mogul / lexicode phenomenon, the only known route from a game to M₂₄.
