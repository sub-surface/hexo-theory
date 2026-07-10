# Self-Play Strategy Corpus

Seeded 1-2-2 Hex Connect6 strategy comparison over canonical White opening pairs. This is empirical self-play, not a perfect-play proof.

## Run

- radius: 3
- turns after opening: 2
- candidate cells per move: 6
- opening limit: 3
- black strategies: debt_builder, attacker, hybrid, min_bulk
- white strategies: screen_counter, min_tau, min_bulk, min_family

## Strongest Black Matchups

- `debt_builder` vs `min_bulk`: edge=0.00, games=3, mean score=0.0
- `hybrid` vs `min_bulk`: edge=0.00, games=3, mean score=0.0
- `min_bulk` vs `min_bulk`: edge=0.00, games=3, mean score=0.0
- `hybrid` vs `screen_counter`: edge=0.00, games=3, mean score=-0.0
- `min_bulk` vs `screen_counter`: edge=0.00, games=3, mean score=-0.0
- `debt_builder` vs `min_family`: edge=0.00, games=3, mean score=-0.5
- `hybrid` vs `min_family`: edge=0.00, games=3, mean score=-0.5
- `min_bulk` vs `min_family`: edge=0.00, games=3, mean score=-0.5

## Strongest White Screens

- `min_tau` against `attacker`: edge=-0.33, games=3, mean score=4290.7
- `min_tau` against `debt_builder`: edge=-0.33, games=3, mean score=4290.7
- `screen_counter` against `attacker`: edge=-0.33, games=3, mean score=4291.2
- `screen_counter` against `debt_builder`: edge=-0.33, games=3, mean score=4291.2
- `min_bulk` against `attacker`: edge=0.00, games=3, mean score=-2203.9
- `min_family` against `attacker`: edge=0.00, games=3, mean score=-2202.4
- `min_tau` against `hybrid`: edge=0.00, games=3, mean score=-0.5
- `min_tau` against `min_bulk`: edge=0.00, games=3, mean score=-0.5

## Neural-Scale Interpretation

The estimator separates full pair-policy size from a factorized pair-policy head. The full policy grows quadratically in board cells; the factorized head keeps the policy tied to local cell logits and a learned pair coupling, which is the only plausible route to radius transfer.

- r=3: cells=37, full actions=666, factorized params=134849, architecture=tiny_factorized_mlp, regime=memorisation_dominated, boundary/bulk=0.486
- r=4: cells=61, full actions=1830, factorized params=423969, architecture=small_residual_hex_cnn, regime=opening_transfer, boundary/bulk=0.393
- r=5: cells=91, full actions=4095, factorized params=426849, architecture=small_residual_hex_cnn, regime=opening_transfer, boundary/bulk=0.330
- r=6: cells=127, full actions=8001, factorized params=980993, architecture=local_message_passing, regime=local_atom_generalisation, boundary/bulk=0.283

## Files

- `self_play_games.json`: viewer-loadable move corpus.
- `self_play_games.csv`: flat per-game records.
- `strategy_matrix.csv`: per-matchup aggregates.
- `network_size_estimates.csv`: radius-wise functional model-size estimates.
- `figures/`: outcome matrix, tactical score distribution, and neural-size scaling.

View with:

```powershell
python examples\game_viewer.py --corpus self_play_results/smoke/self_play_games.json
```
