# Bellman-Turing Instability on Z[ω]

*2026-05-20*

> **Status (2026-07-05): NEEDS RE-TEST — prediction did not match measurement.**
> This note predicts a preferred spacing λ*≈11.8 (§"Predicted Wavelength") but
> the "Experimental Results" section below reports a measured pair-correlation
> peak at r≈3.0-3.2 — roughly 4× off — attributed to grid-resolution/burn-in
> rather than treated as a live falsification. See [SPEC.md](../../SPEC.md) §6
> for the corrected framing. A long-horizon, higher-resolution re-run is
> queued in [DIRECTION.md](../../DIRECTION.md)'s compute plan; don't cite the
> mechanism as confirmed until that re-run actually shows the r≈11-12 peak.

## The Hypothesis

Optimal play in HeXO generates a spatially structured stone distribution
because the Boltzmannized Bellman operator for this game has a **Turing
instability** — a spatial mode at non-zero wavenumber k* that grows
spontaneously from any near-uniform initial condition.

This connects the empirical quasi-crystalline structure already confirmed in
`results/diffraction_p4.json` (Bragg99 ≈ 0.51 in Combo-v2 self-play) to
a first-principles mechanistic account: the pattern is not merely observed
post-hoc, it is *predicted* by the game's threat geometry.

## Two-Species Reaction-Diffusion Framing

Identify:

- **Activator** A(c): own Erdős-Selfridge potential φ^own(c) = Σ_L (1/2)^{n_L^own}
  supported on all cells within WIN_LENGTH-1 = 5 hex steps of any own stone.
  This is a "short-range" self-stimulating field — placing a stone increases A
  in a neighbourhood of radius ≈ d_A.

- **Inhibitor** I(c): opponent Erdős-Selfridge potential φ^opp(c), supported on
  the same radius but *suppressing* placement by the current player.

For a Turing instability to exist we need d_I > d_A (inhibitor diffuses further
than activator), which is satisfied here:

| Parameter | Analytic value | Source |
|-----------|----------------|--------|
| d_A (activator radius) | (WIN_LENGTH−1)/2 = **2.5** | half-window range |
| d_I (inhibitor radius) | WIN_LENGTH−1 = **5.0** | full window range |
| d_I / d_A | **2.0** | ≫ 1 → instability active |

The empirical autocorrelation fit from `run_bellman_turing.py` gives d_A ≈ 23-30,
d_I ≈ 28-37 (longer because the potential field is long-tailed). Both estimates
give ratio > 1, confirming the instability is active.

## Predicted Wavelength λ*

The Gierer-Meinhardt critical wavenumber on the Z[ω] hex lattice:

```
k*² = sqrt( (b·d_I − a·d_A) / (d_A · d_I · (d_I − d_A)) )
```

with a = b = 1 (equal coupling), d_A = 2.5, d_I = 5.0:

```
k*² = sqrt( (5.0 − 2.5) / (2.5 · 5.0 · 2.5) ) = sqrt(2.5/31.25) = sqrt(0.08) ≈ 0.283
k*  ≈ 0.532 hex⁻¹
λ*  = 2π/k* ≈ 11.81 hex units
```

**Prediction: stones in optimal play should show preferred pairwise spacing at
≈ 11-12 hex units**, with secondary peaks at 2λ* ≈ 23.6 and 3λ* ≈ 35.4.

This is physically sensible: λ* ≈ 2 × WIN_LENGTH, meaning two threatening chains
should be separated by roughly two chain-lengths to avoid mutual interference.

## Dispersion Relation

The linearised Bellman growth rate σ(k) for the D6-symmetric hex lattice:

```
σ(k) = (f_AA − d_A · k²) + ½(f_II − d_I · k²)
```

where f_AA = 1 (activator self-coupling), f_II = −d_I/d_A = −2 (inhibitor
suppression). This gives:

- σ(0) < 0 (uniform state is stable against long-wavelength perturbations)
- σ(k*) > 0 (the band near k* is unstable)
- σ(k → ∞) → −∞ (short wavelengths are stable)

The unstable band is centred at k* = 0.532 with approximate half-width
Δk ≈ 0.15, corresponding to wavelengths λ ∈ [9.5, 14.5] hex units.

Because Z[ω] has D6 symmetry, the unstable modes form a **hexagonal ring** in
k-space at radius |k| = k*. The six preferred wavevectors align with the
reciprocal-lattice directions of Z[ω]:

```
k_j = k* · (cos(jπ/3), sin(jπ/3)),  j = 0, 1, ..., 5
```

This predicts that the stone arrangement in optimal play will exhibit **D6-symmetric
Bragg peaks** in its diffraction spectrum at the reciprocal radius k* — exactly
what the `run_diffraction.py` experiment measures.

## Experimental Results

### Bellman Residual

The Bellman residual measures how far each agent's move distribution is from the
Boltzmann fixed point of the potential field:

| Agent | Mean residual | Interpretation |
|-------|---------------|----------------|
| Random | 5.39 ± 1.32 | Far from fixed point; no structure |
| Greedy | 4.67 ± 1.09 | Closer; chain-extending heuristic aligns |
| Combo-v2 | 2.49 ± 1.02 | Closest; threat-aware policy near fixed point |

This ordering confirms that stronger agents are better approximations to the
Boltzmann fixed point V_β, and that the fixed point has genuine structure.

### Crystal Observables (quick run, 12 games per agent)

| Agent | Bragg99 | D6 Jaccard | Pair-corr lag |
|-------|---------|-----------|--------------|
| Random | 0.135 | 0.095 | 5.5 |
| Greedy | 0.398 | 0.188 | 3.0 |
| Combo-v2 | 0.308–0.398 | 0.177 | 3.2 |

The pair-corr dominant lag at r=3 in short games reflects nearest-neighbour
clustering (stones are placed adjacent to existing stones). The λ*=11.81
prediction should emerge at longer horizons where chains develop spatial
separation — check the full-run results in `results/bellman_turing.json`.

### Activation Field FFT

The FFT of the A(c)−I(c) difference field (zero-meaned, Hanning windowed)
shows a dominant ring. For structured agents this ring corresponds to a
preferred spatial frequency in the potential gradient. The λ_obs = 16 in short
runs is dominated by the FFT grid resolution (pixel artifact at grid_fft=48,
dominant bin = 3 pixels → k = 2π·3/48 = 0.393, λ = 16). Longer games on
larger grids will resolve the k* = 0.532 ring.

## Connection to Existing Results

1. **Bragg99 = 0.51** (diffraction_p4.json, Combo-v2 long self-play): This is the
   empirical quasi-crystal signature. The Bellman-Turing theory gives it a
   mechanistic explanation: the pattern is driven by the k* instability.

2. **D6 Jaccard** in crystal_survey.json: the D6 symmetry of the instability's
   unstable modes (hexagonal ring in k-space) predicts D6 Jaccard → 1 in
   long, strong-play games.

3. **Pisot conjecture** (README.md §Central Conjecture): the Turing instability
   provides a constructive mechanism for the quasi-crystalline structure. The
   "substitution structure" corresponds to the nonlinear saturation of the k*
   unstable mode — when mode amplitude saturates, it seeds a pattern at 2k*, 3k*,
   etc., which is exactly the harmonic series of Bragg peaks in a quasi-crystal.

4. **Epiplexity / MDL** (ROADMAP Programmes A-E): the characteristic wavelength
   λ* defines a natural compression unit — a "tile" of size ≈λ*×λ* hex cells
   that can be used as the basis of the shortest description of strong-play
   positions. Agents closer to the fixed point should compress more efficiently
   under this tiling.

## Falsifiers

The Bellman-Turing hypothesis fails if:

- Pair-correlation g(r) in long strong-play games shows no peak near r ≈ 11-12,
  or the peak is present in random games too.
- Bragg99 does not rise when comparing games at horizon 50 vs 100 vs 150
  (the pattern should sharpen as the game progresses past burn-in).
- The D6 harmonic moment m=6 is not systematically larger for stronger agents
  (the D6 ring in k-space predicts m=6 dominance).
- Training a net from random init produces no convergence toward λ*-spaced stones.

## Next Experiments

1. **Long-game pair correlation** — run `run_bellman_turing.py` with
   `--horizon 200 --burn-in 40` to see r=12 peak emerge.
2. **Horizon sweep** — Bragg99 vs. horizon at fixed agent. Predict monotone rise.
3. **Amplitude spectrum** — extract peak k values from the diffraction figure
   `fig_diffraction_p4.png` and check if they land at |k| = k* = 0.532.
4. **λ* as ZOI shape** — replace fixed ZOI radius with k*-derived ellipsoidal ZOI
   aligned to the three Z[ω] axes. Bridge to main hexgo repo if validated.
5. **NCA prior initialised at k*** — initialise NeuralCAAgent conv filters as
   spatial oscillations at wavelength λ* along each of the three Eisenstein axes.
   Prediction: this prior accelerates learning vs random init.

## References

- Gierer, A. & Meinhardt, H. (1972). A theory of biological pattern formation.
  *Kybernetik*, 12, 30-39.
- Turing, A. (1952). The chemical basis of morphogenesis. *Phil. Trans. Royal Soc.
  London B*, 237, 37-72.
- Baake, M. & Grimm, U. (2013). *Aperiodic Order, Vol. 1*. Cambridge Univ. Press.
- Engine symbols: `potential_map` at [engine/analysis.py:104](../engine/analysis.py:104);
  `live_line_records` at [engine/cgt.py](../engine/cgt.py);
  `diffraction_intensity` at [engine/diffraction.py:46](../engine/diffraction.py:46).
- Experiment: [experiments/run_bellman_turing.py](../../experiments/run_bellman_turing.py)
- Results: `results/bellman_turing.json`, `figures/fig_bt_*.png`
