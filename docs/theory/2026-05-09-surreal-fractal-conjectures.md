# Surreal And Fractal Conjectures For HexGo

*2026-05-09*

This note states a deliberately speculative but testable bridge between HexGo,
surreal numbers, thermographs, and recursive strategy patterns. The aim is not
to claim that the whole infinite game is "a surreal number". It almost certainly
is not. The aim is to identify which quotient of the game admits surreal values,
which invariant might deserve to be called *the* HexGo number, and what kind of
recursive strategy fractal could be checked against the actual length-6 win rule.

## 1. Natural Representation

The most natural representation of a finite HexGo position is:

```text
P = (mu, tau, H_live, Gamma_D6)
```

where:

- `mu` is a finite signed measure on the Eisenstein lattice `Z[omega]`; black
  stones have mass `+1`, white stones have mass `-1`;
- `tau` is the turn phase of the 1-2-2 rule;
- `H_live` is the live length-6 hypergraph whose vertices are empty cells and
  whose hyperedges are unblocked winning windows;
- `Gamma_D6` is the orbit data under the 12 symmetries of the hex lattice.

This is stricter than a board diagram and looser than a game tree. It preserves
the objects that matter:

- the exact win hypergraph from `WIN_LENGTH == 6`;
- the live-line/hot-component projection used by `engine.cgt`;
- the D6 quotient needed for motif mining;
- the two-placement phase that prevents ordinary CGT addition from being exact.

## 2. Conjecture S1: Local Surrealization

Let `C` be a finite connected component of the live-line incidence graph after
discarding all cells below a temperature threshold. If play is restricted to `C`
and both players are forced to answer inside `C` until it cools or terminates,
then `C` has a short partizan value

```text
G(C) = { G(C after a Black local move) | G(C after a White local move) }.
```

In general `G(C)` is not a number. The expected recurring types are:

- hot switches: open five-in-a-row threats;
- infinitesimals: remote forcing obligations;
- tiny/fuzzy games: symmetric blocking races;
- sums of stalks: independent live-line chains;
- switches with followers: forks and ladders.

Prediction:

The hot components produced by `component_summaries()` should cluster into a
small dictionary of thermograph shapes when sampled from strong self-play.

Falsifier:

If component values have no recurring shape distribution after D6
canonicalization, then the surrealization is descriptive but not structural.

## 3. Conjecture S2: HexGo Uses A Two-Handed Sum

Ordinary combinatorial game theory uses the disjunctive sum:

```text
G + H
```

where a move changes exactly one component. HexGo after the opening should
instead be modeled by a two-handed operator:

```text
G (+_2) H.
```

A player may spend both placements in one component, or split the placements
across two components. This operator explains why a pair of lukewarm local games
can outrank a single hotter game: the turn value is a pair allocation, not a
single local choice.

Prediction:

For strong agents, move pairs should be predicted better by the top two local
component options than by the single highest cell temperature.

Falsifier:

If `best_one_move_sum()` and `best_two_move_sum()` make indistinguishable
predictions on held-out strong-agent self-play, the extra algebra is not needed.

## 4. Conjecture S3: The HexGo Number Is Not The Game Value

The global game value is probably too coarse: strategy stealing says the second
player cannot have a strict win, but that does not name the structure of optimal
play. The better candidate for "the HexGo number" is an inflation constant:

```text
lambda_HexGo.
```

This number should be the common limit, if it exists, of four measurements:

```text
lambda_HexGo =
  lambda_epiplexity
  = lambda_diffraction
  = lambda_substitution
  = lambda_birthday.
```

Meanings:

- `lambda_epiplexity`: slope inferred from `S_T(corpus_N)` growth;
- `lambda_diffraction`: peak-spacing ratio in long self-play spectra;
- `lambda_substitution`: Perron-Frobenius eigenvalue of the motif substitution
  matrix;
- `lambda_birthday`: growth rate of canonical local game birthdays under forced
  expansion.

Prediction:

If the Pisot conjecture is right, these estimates should fall in the same Pisot
family interval. The roadmap already sets a strict version:

```text
abs(lambda_epiplexity - lambda_diffraction) < 0.05.
```

Falsifier:

If motif counts grow linearly without a stable substitution spectrum, or if the
four lambda estimates diverge systematically, then there is no single HexGo
number of this type.

## 5. Conjecture S4: Positions Have A Surreal Hahn Shadow

The full board may not be a surreal number, but a finite position may admit a
formal asymptotic shadow:

```text
V(P) = sum_C v(C) * Omega^(-rho(C)).
```

Here:

- `C` ranges over hot live-line components;
- `v(C)` is the local thermographic or surreal value of the component;
- `rho(C)` is its hex distance shell from the strategic origin or last forcing
  center;
- `Omega` is a formal infinite unit, not the Eisenstein root `omega`.

Interpretation:

Near threats dominate far threats, but far threats are not zero. They are
infinitesimal strategic pressure. This matches HexGo tactically: a remote fork
can be irrelevant at one temperature and decisive after the local game cools.

Prediction:

A Hahn-shadow truncation should predict strong moves better as the game enters
late, spatially separated threat regions.

Falsifier:

If far components never improve prediction after conditioning on local
temperature, the Hahn-shadow model is overfitted language.

## 6. Conjecture S5: Strategy Fractals Are Motif Substitutions

A HexGo strategy fractal should not be a decorative point cloud. It should be a
recursive substitution on *verified winning motifs*:

```text
winning motif -> six D6-related descendant motifs at the next shell.
```

The first implementation is intentionally austere:

- start at `(0, 0)`;
- at each center, place one length-6 line along each of the three HexGo axes;
- recurse by translating centers in the six hex directions by `inflation^level`;
- verify every motif against `winning_lines_for_board()`.

The quick run in `results/surreal_fractal_strategy.json` generated:

```text
depth = 2
inflation = 5
stone_count = 614
motif_count = 129
winning_line_count = 321
dimension_estimate = log(6) / log(5) ~= 1.113
```

The important detail is `winning_line_count > motif_count`: the recursive
placement creates additional length-6 windows beyond the motifs explicitly
planted. That is the first weak sign of "strategy interference", the thing a
real substitution theory would need to control.

Prediction:

For some inflation values, the ratio

```text
winning_line_count / motif_count
```

should stabilize across depth. Those values are candidates for strategic
inflation constants. If a stabilizing value is Pisot-compatible, it joins the
`lambda_HexGo` candidate list.

Falsifier:

If all inflations either explode with uncontrolled accidental wins or collapse
to isolated planted motifs, this generator is only a visualization, not a
strategy model.

## 7. Immediate Experiments

1. Sweep `inflation in {2, 3, 4, 5, 6, 7, 8}` and `depth in {1, 2, 3, 4}`.
2. Measure `winning_line_count / motif_count`, stone density by radius, and D6
   orbit counts.
3. Compare the generated patterns to strong-agent self-play motifs using
   `canonical_board_key()`.
4. Replace the rosette motif with hot components mined from `engine.cgt`.
5. Test whether any generated substitution pattern creates robust double threats
   under the two-handed `+_2` model.

The research slogan:

```text
HexGo is not a surreal number.
Its hot components are surreal games.
Its turn rule asks for a two-handed sum.
Its global number, if it has one, is an inflation constant.
```
