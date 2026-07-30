# Death HeXO

This directory is a self-contained research lab for a capture variant of HeXO:
infinite Connect-6 on the hexagonal lattice with the 1-2-2 placement rule.

After each atomic placement, every stone bracketed by enemy stones on an
opposite neighbour pair (`x-o-x`) dies. Deaths are simultaneous. Friendly
brackets do nothing. A win is checked after cleanup, and a suicidal placement
still consumes one of the turn's placements.

The canonical rule, reference engine, exact solvers, local agents, and analysis
primitives are in [death_hexo.py](death_hexo.py). The full synthesis is
[FINDINGS.md](FINDINGS.md).

## Headline results

- White can always sandwich and remove Black's unique opening stone on the
  first reply turn, leaving two White stones and Black to move.
- The game is genuinely loopy: a four-placement sequence can return the entire
  board, player, and turn phase to the same state.
- One placement can kill six enemies and itself: seven simultaneous deaths and
  a net material change of -6.
- Stable fully occupied line colorings grow with the golden ratio. Stable line
  words with vacancies grow with the Pisot root `2.831177...` of
  `x^3 - 2x^2 - 2x - 1`.
- An explicit irrational-height construction gives an open family of
  aperiodic, death-stable, Connect-6-free configurations with pure-point
  diffraction and arbitrary-order erasure repair.
- A wrong-color point invasion is automatically rejected on exact phase
  measure `1 - sqrt(3)/4 = 0.566987...`; surviving invasions expose the frozen
  defects a genuinely adversarial repair strategy must solve.
- Exact finite-line games include forced White wins, so ordinary monotone
  strategy-stealing does not transfer automatically.
- In 312 exploratory local-policy games, death turnover ranged from 0.27 to
  0.78 deaths per placement and exact state revisits appeared in capture-aware
  play.

These claims have different confidence levels. The report separates analytic
facts, exhaustive finite results, and exploratory self-play.

## Reproduce

```powershell
python -m pytest tests -q
python experiments/run_death_hexo.py --quick
python experiments/run_death_hexo.py
python experiments/run_aperiodic_repair.py
```

The full run uses multiprocessing, writes
`evidence/results/death_hexo.json`, and regenerates every PNG under
`evidence/figures/`. `--workers N` controls parallelism. The full run includes
the exact length-10/11 Connect-6 boundary audit; `--exact-extension` exists only
to upgrade an older result without rerunning the Monte Carlo section.

## Artifacts

- [Machine-readable evidence](evidence/results/death_hexo.json)
- [Capture mechanics](evidence/figures/fig_death_hexo_mechanics.png)
- [Stable-shift entropy](evidence/figures/fig_death_hexo_stable_entropy.png)
- [Exact finite-line phase diagram](evidence/figures/fig_death_hexo_exact_phase.png)
- [Matched empirical dynamics](evidence/figures/fig_death_hexo_empirical.png)
- [Representative endpoints](evidence/figures/fig_death_hexo_samples.png)
- [Aperiodic sanctuary analysis](evidence/figures/fig_aperiodic_repair.png)
- [Capture-driven recurrent game GIF](evidence/figures/gif_death_hexo_capture_loop.gif)
- [Aperiodic sanctuary growth GIF](evidence/figures/gif_death_hexo_aperiodic_growth.gif)

The policies use adjacent-frontier move generation as a finite experimental
instrument. That is not a restriction in the mathematical definition of the
infinite game.
