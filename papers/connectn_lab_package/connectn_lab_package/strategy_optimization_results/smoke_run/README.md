# Strategy Optimisation Experiment

Finite D6/Hex Connect6 strategy probe: Black seeds `(0, 0)`, then White and Black alternately place two stones. Each strategy minimizes a different local value over candidate two-stone moves.

This is an empirical invariant test, not a proof of perfect play. The target is to discover which bulk-informed values correlate with `tau > 2` forcing pressure and primitive atom emergence.

## Results

- games: 4
- black wins: 0
- white wins: 2
- no terminal line win by horizon: 2

## Best White Delay Proxies

- `hybrid`: mean turns=5.50, mean final Black obligations=1.50, mean final Black pair atoms=0.00
- `min_tau`: mean turns=5.50, mean final Black obligations=3.00, mean final Black pair atoms=0.00

## Strongest Black Pressure Proxies

- `attacker`: mean final Black obligations=3.00, mean final Black tau=2.00, mean final Black pair atoms=0.00
- `min_bulk`: mean final Black obligations=1.50, mean final Black tau=1.00, mean final Black pair atoms=0.00

## Files

- `game_summary.csv`: one row per strategy pairing.
- `turn_metrics.csv`: per-turn tau, atom, bulk, and family values.
- `strategy_aggregate.csv`: side-wise aggregate performance.
- `strategy_games.json`: complete structured corpus.
- `figures/`: outcome, tau-threshold, pressure, and trajectory figures.
