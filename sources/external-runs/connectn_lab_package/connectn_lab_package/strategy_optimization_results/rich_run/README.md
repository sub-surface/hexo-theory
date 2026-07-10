# Strategy Optimisation Experiment

Finite D6/Hex Connect6 strategy probe: Black seeds `(0, 0)`, then White and Black alternately place two stones. Each strategy minimizes a different local value over candidate two-stone moves.

This is an empirical invariant test, not a proof of perfect play. The target is to discover which bulk-informed values correlate with `tau > 2` forcing pressure and primitive atom emergence.

## Results

- games: 24
- black wins: 4
- white wins: 5
- no terminal line win by horizon: 15

## Best White Delay Proxies

- `min_atoms`: mean turns=14.50, mean final Black obligations=1.75, mean final Black pair atoms=0.00
- `min_family`: mean turns=14.50, mean final Black obligations=1.75, mean final Black pair atoms=0.00
- `min_bulk`: mean turns=13.25, mean final Black obligations=0.75, mean final Black pair atoms=0.00
- `hybrid`: mean turns=12.75, mean final Black obligations=0.75, mean final Black pair atoms=0.00
- `min_tau`: mean turns=12.75, mean final Black obligations=1.50, mean final Black pair atoms=0.00

## Strongest Black Pressure Proxies

- `attacker`: mean final Black obligations=2.83, mean final Black tau=1.83, mean final Black pair atoms=0.00
- `min_bulk`: mean final Black obligations=1.17, mean final Black tau=0.83, mean final Black pair atoms=0.00
- `hybrid`: mean final Black obligations=1.00, mean final Black tau=0.83, mean final Black pair atoms=0.00
- `min_atoms`: mean final Black obligations=0.33, mean final Black tau=0.17, mean final Black pair atoms=0.00

## Files

- `game_summary.csv`: one row per strategy pairing.
- `turn_metrics.csv`: per-turn tau, atom, bulk, and family values.
- `strategy_aggregate.csv`: side-wise aggregate performance.
- `strategy_games.json`: complete structured corpus.
- `figures/`: outcome, tau-threshold, pressure, and trajectory figures.
