# Self-Play Strategy Corpus

Seeded 1-2-2 Hex Connect6 strategy comparison over canonical White opening pairs. This is empirical self-play, not a perfect-play proof.

## Run

- radius: 3
- turns after opening: 4
- candidate cells per move: 8
- opening limit: 8
- black strategies: debt_builder, attacker, hybrid, min_bulk
- white strategies: screen_counter, min_tau, min_bulk, min_family

## Strongest Black Matchups

- `attacker` vs `min_bulk`: edge=0.00, games=8, mean score=0.0
- `debt_builder` vs `min_bulk`: edge=0.00, games=8, mean score=0.0
- `debt_builder` vs `min_family`: edge=0.00, games=8, mean score=0.0
- `hybrid` vs `min_bulk`: edge=0.00, games=8, mean score=0.0
- `hybrid` vs `min_family`: edge=0.00, games=8, mean score=0.0
- `hybrid` vs `min_tau`: edge=0.00, games=8, mean score=0.0
- `hybrid` vs `screen_counter`: edge=0.00, games=8, mean score=0.0
- `min_bulk` vs `min_bulk`: edge=0.00, games=8, mean score=0.0

## Strongest White Screens

- `min_tau` against `debt_builder`: edge=-0.25, games=8, mean score=2391.2
- `min_tau` against `attacker`: edge=-0.25, games=8, mean score=2391.2
- `screen_counter` against `attacker`: edge=-0.12, games=8, mean score=1609.2
- `screen_counter` against `debt_builder`: edge=-0.12, games=8, mean score=1609.2
- `min_family` against `attacker`: edge=0.00, games=8, mean score=-0.3
- `min_bulk` against `attacker`: edge=0.00, games=8, mean score=0.0
- `min_bulk` against `debt_builder`: edge=0.00, games=8, mean score=0.0
- `min_family` against `debt_builder`: edge=0.00, games=8, mean score=0.0

## Neural-Scale Interpretation

The estimator separates full pair-policy size from a factorized pair-policy head. The full policy grows quadratically in board cells; the factorized head keeps the policy tied to local cell logits and a learned pair coupling, which is the only plausible route to radius transfer.

- r=3: cells=37, full actions=666, factorized params=134849, architecture=tiny_factorized_mlp, regime=memorisation_dominated, boundary/bulk=0.486
- r=4: cells=61, full actions=1830, factorized params=423969, architecture=small_residual_hex_cnn, regime=opening_transfer, boundary/bulk=0.393
- r=5: cells=91, full actions=4095, factorized params=426849, architecture=small_residual_hex_cnn, regime=opening_transfer, boundary/bulk=0.330
- r=6: cells=127, full actions=8001, factorized params=980993, architecture=local_message_passing, regime=local_atom_generalisation, boundary/bulk=0.283
- r=7: cells=169, full actions=14196, factorized params=986369, architecture=local_message_passing, regime=local_atom_generalisation, boundary/bulk=0.249
- r=8: cells=217, full actions=23436, factorized params=2707905, architecture=d6_equivariant_message_passing, regime=infinite_proxy, boundary/bulk=0.221

## Files

- `self_play_games.json`: viewer-loadable move corpus.
- `self_play_games.csv`: flat per-game records.
- `strategy_matrix.csv`: per-matchup aggregates.
- `network_size_estimates.csv`: radius-wise functional model-size estimates.
- `evidence/figures/`: outcome matrix, tactical score distribution, and neural-size scaling.

View with:

```powershell
python examples\game_viewer.py --corpus self_play_evidence/results/r3_strategy_grid/self_play_games.json
```
