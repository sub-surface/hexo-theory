# Self-Play Strategy Runner Design

## Goal

Build a minimal, traditional self-play layer for seeded 1-2-2 Hex Connect6 that can compare many asymmetric strategies and estimate radius-wise neural-network scale for finite-radius approximations to the infinite game.

## Architecture

The feature has two layers.

`connectn_lab/self_play.py` is the reusable library layer. It plays strategy-versus-strategy games from the normal Black seed and optional canonical White opening pairs, records viewer-loadable move lists, aggregates matchup outcomes, and estimates model size from radius, board cells, pair-action space, candidate-pruned action space, tactical feature channels, and boundary-to-bulk ratio.

`examples/self_play_experiment.py` is the experiment layer. It parses CLI arguments, runs a corpus, writes CSV/JSON artifacts, generates figures, and writes a short empirical report. The viewer can already load the generated `games` JSON shape, so no extra viewer code is needed for the first pass.

## Data Model

`SelfPlayConfig` records radius, turns, candidate limit, opening limit, strategy lists, and connect length. `SelfPlayRecord` records one game: strategy pair, opening ID, winner/WLU, moves, final tactical metrics, max tau, first tau-threshold crossing, terminal ply, and tactical score. `StrategyMatchupSummary` aggregates records by strategy pair. `NetworkSizeEstimate` records radius-wise board/action/model-size estimates.

## Self-Play Semantics

Every game starts with Black seed `(0, 0)`. If an opening pair is supplied, White's first move is that canonical pair and Black moves next. If no opening pair is supplied, White's first move is selected by its strategy. After that, both sides place two stones per move. A game terminates on a six-in-row win, no legal two-stone move, or the configured turn horizon.

## Neural-Size Analysis

The estimator is intentionally analytic rather than trained-model based. It reports board cells, full pair-action count, candidate-pruned pair count, recommended feature channels, trunk width, residual/message-passing blocks, factorized-policy parameter estimate, full-policy parameter estimate, and a boundary-to-bulk generalization index. The infinite-game hypothesis is that useful generalization begins when local tactical feature channels become more predictive than radius-specific memorization, while the boundary ratio falls enough that interior atom ecology is stable.

## Outputs

The CLI writes:

- `self_play_games.json`: structured corpus with viewer-loadable `games`.
- `self_play_games.csv`: flat per-game rows.
- `strategy_matrix.csv`: aggregate matchup rows.
- `network_size_estimates.csv`: radius sweep estimates.
- `figures/`: outcome matrix, tactical score distribution, and model-size scaling.
- `README.md`: run configuration and empirical interpretation.

## Testing

Tests cover game generation, viewer JSON shape, matchup aggregation, and monotone network-size estimates. A CLI smoke run verifies that artifacts are produced and loadable.
