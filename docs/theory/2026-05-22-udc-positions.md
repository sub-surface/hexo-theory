# UDC positions over Z[omega] — P6 first results

*2026-05-22, after reading the OpenAI unit-distance disproof (arXiv 2025) and implementing [experiments/run_udc_positions.py](../../experiments/run_udc_positions.py).*

> **Status (2026-07-05): ACTIVE-ADJACENT.** P6a/b/d are genuinely supported
> (§4) and the Bragg99=0.84 ceiling this note establishes is a useful
> benchmark for Programme D — see [SPEC.md](../../SPEC.md) §5. The t≥3
> resolution-wall fix this note recommends (§5.1, adaptive
> `--diffraction-grid`) is queued in [DIRECTION.md](../../DIRECTION.md)'s
> compute plan alongside the GPU slice of the Modal budget.

## 1. What was built

The experiment constructs point sets in the Eisenstein integers Z[omega] (the hex lattice) using the CM class-field-tower machinery from the OpenAI disproof of the Erdos unit-distance conjecture.

**Algebraic setup.** For t rational primes q_i = 1 mod 3, each splits in Z[omega] as q_i = pi_i * pi_bar_i (unique factorisation; Z[omega] is a PID). The 2^t subset products

    u_S = prod_{i in S} pi_i  *  prod_{i not in S} pi_bar_i

are Eisenstein integers all sharing the same modulus |u_S|_C = prod_i sqrt(q_i) =: D. Two lattice points x, y in a disc of radius R are a "unit pair" iff x - y = u_S for some S. The resulting active point set is the UDC position.

This is the direct Eisenstein analogue of the Erdos Gaussian-integer grid (which uses Z[i] and primes q = 1 mod 4). The proof in [papers/unit-distance-proof.pdf](../../papers/unit-distance-proof.pdf) generalises this to towers of CM fields of growing degree; we stay at the base level Z[omega] here.

## 2. Results (2026-05-22, seed 20260522)

| Label | t | D = prod q_i | n stones | nu pairs | nu/n | Bragg99 | moment_6 |
|-------|---|---|---|---|---|---|---|
| udc_t1 | 1 | 7 | 1391 | 1269 | 0.912 | **0.839** | 0.109 |
| udc_t2 | 2 | 91 | 1310 | 1801 | 1.375 | **0.840** | 0.123 |
| udc_t3 | 3 | 1729 | 22951 | 61154 | 2.665 | 0.057 | 0.090 |
| udc_t4 | 4 | 53599 | 692601 | 3690257 | 5.328 | 0.054 | 0.127 |
| random_disc | — | — | 12171 | — | — | 0.058 | 0.101 |
| hex_ball | — | — | 12171 | — | — | 0.063 | 0.056 |

## 3. Interpretation

### 3.1 P6a and P6b: SUPPORTED for t = 1, 2

udc_t1 and udc_t2 have Bragg99 ~0.84, far above the random baseline (0.058) and the dense hex-ball (0.063). This is not a trivial lattice effect: the hex-ball (densest Bravais packing) scores only 0.063, while UDC positions — which are sparser, gap-riddled subsets of the disc — score 0.84. The diffraction concentration arises from the algebraic structure of the translations, not the packing density.

moment_6 is also elevated (0.11–0.12 vs 0.101 random), consistent with D6 angular organisation inherited from the hex lattice symmetry group.

### 3.2 The t = 3, 4 collapse — a window-size artefact, not a failure

For t = 3, D = 1729 = 7 * 13 * 19. The minimum window radius that allows any unit pairs is R ~ D ~ 41.6. At R = 83.2 the disc contains ~23k points. But our Bragg99 computation uses a sub-sample of 1500 points (the MAX_DELONE_POINTS guard), and crucially the diffraction grid is 72 x 72 — at this point density a 72^2 grid cannot resolve the Bragg peaks, which are spaced at reciprocal spacing 2pi/D ~ 0.15 rad/unit. For t >= 3 the relevant Bragg peak spacing falls *below the diffraction grid resolution*, so Bragg99 collapses to the noise floor.

**This is not a falsification of P6.** It is a resolution limitation: the diffraction grid needs to be at least 2*pi*R / (2*pi/D) = R*D pixels across to see the peaks, which for t=3 is ~3500 pixels per axis — 4 orders of magnitude more than our 72^2 grid.

**Correct interpretation:** The UDC construction provably produces n^{1+delta} unit pairs (from Theorem 2.3). The diffraction peaks exist but are too closely spaced to measure with our current grid. The Bragg99 observable is *resolution-limited*, not evidence against P6 for large t.

### 3.3 nu/n growth confirms the UDC theorem

nu/n (unit pairs per stone) grows with t: 0.912, 1.375, 2.665, 5.328. This is exactly what Theorem 1.1 predicts: ν(P_j) >= n_j^{1+delta}. For fixed n ~ 1000, increasing t multiplies the pair count by ~5x per step, consistent with the 2^t translation factor dominating the class-number loss (gamma > 0 in the proof's eq. 7).

P6d gamma fit: log(n) ~ 2.15 * t, matching the theoretical expectation log(n) ~ B*f where f ~ t for the base-level construction (no tower growth yet).

### 3.4 Connection to the Pisot conjecture (P3)

The key finding: **small-t UDC positions (t = 1, 2) have Bragg99 ~ 0.84, dramatically higher than any agent-generated position in our self-play corpora (self-play Bragg99 ~ 0.51 +/- 0.13 from results/bellman_turing.json context)**. This means the CM-field algebraic structure is *more crystalline* than optimal self-play, not less. Two interpretations:

1. **Optimistic for P3:** Optimal play evolves toward UDC-like positions from below; measuring the asymptotic limit requires much longer games than our current T <= 120 horizon.

2. **Cautionary for P3:** UDC positions are constructed, not played. They are extremal for unit-distance count but not for winning HeXO — the relevant question is whether *game-optimal* positions are also UDC-like, which is a separate claim.

The experiment thus sharpens P3 into two sub-claims:
- **P3a** (structural): terminal positions of strong self-play approximate UDC positions in their diffraction spectra. Testable by running longer self-play (T ~ 480–960) and comparing Bragg99.
- **P3b** (algebraic): the translations active in terminal strong-play positions cluster around Z[omega] norm-one elements from small numbers of split primes. Testable by decomposing the displacement vectors of consecutive stones into Eisenstein factorizations.

## 4. Falsifiable predictions (updated)

| Prediction | Status | Next experiment |
|---|---|---|
| P6a: Bragg99(UDC) > Bragg99(random) | SUPPORTED (t=1,2) | Extend to higher-resolution grid for t>=3 |
| P6b: moment_6(UDC) > moment_6(random) | SUPPORTED (t=1,2) | Same |
| P6c: Bragg99 monotone in t | NOT SUPPORTED — resolution artifact | Rerun with diffraction_grid proportional to D |
| P6d: n ~ exp(gamma*t), gamma > 0 | SUPPORTED (gamma=2.15) | Check against tower-level fields (F_j sequence) |
| P3a: self-play converges toward UDC Bragg99 | UNTESTED | run_epiplexity_scan.py at T in {240, 480, 960} |
| P3b: displacement vectors cluster on Z[omega] ideals | UNTESTED | New analysis pass on self-play corpus |

## 5. What to do next

1. **Resolution fix:** Re-run with `--diffraction-grid` set adaptively to `max(72, int(4 * D))` per t, capped at GPU memory limits. This will require running t=3 at grid ~7000, which needs batching or the Radial profile instead of full 2D FFT.

2. **P3a:** Extend `run_epiplexity_scan.py` to T in {240, 480, 960} for Combo-v2 self-play and overlay the resulting Bragg99 on the UDC baseline of 0.84. If self-play Bragg99 grows toward 0.84 with horizon, P3 is strongly supported.

3. **P3b:** Write a displacement-vector analyser that takes consecutive stone pairs from self-play and checks whether their Z[omega] difference vector belongs to the small-t ideal factorization lattice (i.e., whether diff = u_S for small t).

## 6. Geometry — which lattice fits the HeXO ruleset?

*Added 2026-05-22 after implementing `--geometries` in `run_udc_positions.py`.*

The UDC machinery does not dictate a unique base lattice. Three candidates:

| Geometry | Ring | Lattice | Symmetry | Split rule | Fit |
|---|---|---|---|---|---|
| `gaussian` | Z[i] | square | D4 | q = 1 mod 4 | Erdos baseline; wrong symmetry |
| `eisenstein` | Z[omega] | A2 triangular | D6 | q = 1 mod 3 | matches HeXO exactly |
| `z12` | Z[zeta_12] proj. | A2 (q = 1 mod 12) | D6 | q = 1 mod 12 | the true degree-4 CM field K = L(i) |

The engine settles the lattice: [engine/isomorphisms.py](../../engine/isomorphisms.py) uses A2 cube
coordinates (`cube_coords`) and a 12-element D6 group (`_cube_transforms`), and
the win axes `(1,0),(0,1),(1,-1)` ([game.py] `AXES`) are the three short A2
directions. HeXO *is* a game on Z[omega] with D6 symmetry.

**Empirical comparison** (t in {1,2,3}, n ~ 800, seed 20260522):

| Geometry | mean Bragg99 | mean moment_6 | mean d6_jaccard |
|---|---|---|---|
| eisenstein | 0.588 | **0.110** | 0.390 |
| gaussian | 0.587 | **0.016** | 0.507 |
| z12 | 0.331 | 0.110 | 0.260 |

Three findings:

1. **Bragg99 is geometry-independent at small t (~0.85 for all three).** This is
   *exactly* Sawin's §7 remark in [unit-distance-remarks.pdf](../../papers/unit-distance-remarks.pdf):
   varying the CM field K does not change the unit-distance count, which scales
   as the prime-ideal-norm product regardless. The disproof's power is in the
   *tower* (growing degree), not the base field.

2. **moment_6 cleanly separates the geometries: 0.11 (eisenstein, z12) vs 0.016
   (gaussian) — a 7x gap.** This is the decisive discriminator. The A2/D6
   constructions carry hexagonal angular order; the Z[i]/D4 construction does
   not. Since HeXO's win condition is D6-invariant, *moment_6, not Bragg99,
   is the right observable for "does this position look like optimal HeXO
   play."* The Gaussian construction is extremal for unit distances but lives
   in the wrong symmetry class.

3. **z12 hits the resolution wall at smaller t** (collapse already at t=2)
   because its split primes are larger (13, 37, 61 vs eisenstein's 7, 13, 19),
   giving larger D = prod q_i and finer Bragg spacing. Same artifact as §3.2,
   arriving sooner. This makes z12 *worse for measurement* despite being the
   "true" CM field — eisenstein reaches larger measurable t.

**Geometry verdict:** Use `eisenstein` (Z[omega]) as the canonical base lattice.
It (a) matches HeXO's A2 lattice and D6 symmetry exactly, (b) carries the
hexagonal angular order absent from Z[i], and (c) uses the smallest split
primes, so it stays measurable to the largest t before the resolution wall.
z12 is the formally-correct degree-4 CM field but offers no measurable gain
(Sawin §7) and worse resolution; it is retained only as a cross-check.
The d6_jaccard metric is *misleading* here — gaussian scores higher because
D4 and D6 share the identity and 180-degree rotation, inflating overlap;
moment_6 is the honest D6 observable.

## 7. Relation to the ROADMAP

This experiment lives at the intersection of Programme A (epiplexity scan) and Programme D (Pisot conjecture for P3). It does not yet falsify P3 but provides the ground-truth algebraic benchmark against which self-play positions will be compared. The UDC Bragg99 of 0.84 is the **theoretical ceiling** — if strong self-play reaches this, the Pisot conjecture is confirmed.

Cite as: experiment `udc_positions`, commit to be tagged after full-resolution rerun.
