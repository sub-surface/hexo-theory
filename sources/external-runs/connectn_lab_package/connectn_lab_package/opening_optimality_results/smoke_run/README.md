# Opening Optimality Atlas

Canonical D6 White opening pairs are enumerated against the normal Black seed `(0, 0)`. Static opening fields are computed in one Torch batch, then a selected frontier of openings is tested by asymmetric Black/White rollout strategies.

## Run

- static opening radius: 2
- exact rollout radius: 5
- static openings: 19
- selected rollout openings: 5
- rollout records: 20
- Torch device: `cuda`
- rollout outcomes: {'none': 20}

## Safest Selected White Openings

- `O0001`: black wins=0, mean Black obligations=0.00, mean turns=2.00
- `O0014`: black wins=0, mean Black obligations=0.00, mean turns=2.00
- `O0011`: black wins=0, mean Black obligations=0.00, mean turns=2.00
- `O0002`: black wins=0, mean Black obligations=0.25, mean turns=2.00
- `O0019`: black wins=0, mean Black obligations=0.25, mean turns=2.00

## Most Black-Favorable Selected Openings

- `O0002`: black wins=0, mean Black obligations=0.25, max Black tau=1
- `O0019`: black wins=0, mean Black obligations=0.25, max Black tau=1
- `O0001`: black wins=0, mean Black obligations=0.00, max Black tau=0
- `O0014`: black wins=0, mean Black obligations=0.00, max Black tau=1
- `O0011`: black wins=0, mean Black obligations=0.00, max Black tau=0

## Interpretation

This atlas is not a perfect-play proof. It is designed to separate opening pairs that merely look central from pairs that suppress Black's conversion from rooted bulk pressure into `tau > 2` obligation debt under asymmetric local strategies.

## Files

- `opening_static.csv`: every canonical opening and GPU-batched static features.
- `opening_rollouts.csv`: exact asymmetric rollout records.
- `opening_aggregate.csv`: per-opening aggregate over strategy pairs.
- `opening_atlas.json`: structured corpus.
- `figures/`: static spectrum, strategy matrix, and rollout pressure figures.
