# Opening Optimality Atlas

Canonical D6 White opening pairs are enumerated against the normal Black seed `(0, 0)`. Static opening fields are computed in one Torch batch, then a selected frontier of openings is tested by asymmetric Black/White rollout strategies.

## Run

- static opening radius: 5
- exact rollout radius: 6
- static openings: 371
- selected rollout openings: 29
- rollout records: 464
- Torch device: `cuda`
- rollout outcomes: {'black': 2, 'none': 442, 'white': 20}

## Safest Selected White Openings

- `O0009`: black wins=0, mean Black obligations=0.12, mean turns=4.00
- `O0023`: black wins=0, mean Black obligations=0.12, mean turns=4.00
- `O0122`: black wins=0, mean Black obligations=0.12, mean turns=4.00
- `O0316`: black wins=0, mean Black obligations=0.19, mean turns=3.94
- `O0370`: black wins=0, mean Black obligations=0.25, mean turns=4.00
- `O0131`: black wins=0, mean Black obligations=0.25, mean turns=4.00
- `O0031`: black wins=0, mean Black obligations=0.38, mean turns=4.00
- `O0119`: black wins=0, mean Black obligations=0.38, mean turns=4.00

## Most Black-Favorable Selected Openings

- `O0001`: black wins=2, mean Black obligations=1.50, max Black tau=3
- `O0309`: black wins=0, mean Black obligations=2.25, max Black tau=2
- `O0005`: black wins=0, mean Black obligations=2.12, max Black tau=2
- `O0371`: black wins=0, mean Black obligations=2.00, max Black tau=2
- `O0015`: black wins=0, mean Black obligations=1.75, max Black tau=2
- `O0364`: black wins=0, mean Black obligations=1.38, max Black tau=2
- `O0010`: black wins=0, mean Black obligations=1.25, max Black tau=2
- `O0249`: black wins=0, mean Black obligations=1.25, max Black tau=2

## Interpretation

This atlas is not a perfect-play proof. It is designed to separate opening pairs that merely look central from pairs that suppress Black's conversion from rooted bulk pressure into `tau > 2` obligation debt under asymmetric local strategies.

## Files

- `opening_static.csv`: every canonical opening and GPU-batched static features.
- `opening_rollouts.csv`: exact asymmetric rollout records.
- `opening_aggregate.csv`: per-opening aggregate over strategy pairs.
- `opening_atlas.json`: structured corpus.
- `figures/`: static spectrum, strategy matrix, and rollout pressure figures.
