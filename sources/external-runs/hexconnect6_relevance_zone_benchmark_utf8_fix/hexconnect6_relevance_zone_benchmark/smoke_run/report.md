# RZ-BDPN relevance-zone benchmark

## Purpose

This benchmark tests whether relevance-zone generators inspired by AP-flow, obligation support,
and branching debt retain tactical continuations while reducing the pair search space.

The reference target is:

```text
Black candidate -> White replies -> Black continuations
```

and the key metrics are:

- **pair reduction**: fraction of legal candidate pairs removed by the zone;
- **forcing recall**: fraction of reference forcing continuations retained;
- **terminal recall**: fraction of terminal continuations retained;
- **best value retention**: best in-zone future value divided by best reference future value;
- **false zone mass**: zone cells not appearing in reference useful support.

## Manifest

```json
{
  "config": {
    "out": "/mnt/data/hexconnect6_relevance_zone_benchmark/smoke_run",
    "resume": false,
    "radius": 5,
    "candidate_radius": 4,
    "max_spread": 6,
    "positions": 8,
    "seed": 260517,
    "checkpoint_every": 2,
    "min_position_plies": 4,
    "max_position_plies": 7,
    "generation_pool": 35,
    "generation_reservoir": 10,
    "generation_top_k": 4,
    "generation_temperature": 1.12,
    "reference_candidate_width": 5,
    "candidate_pool": 65,
    "candidate_reservoir": 20,
    "white_reply_width": 2,
    "black_continuation_width": 3,
    "reply_pool": 45,
    "reply_reservoir": 12,
    "zone_naive_radius": 2,
    "zone_ap_cells": 20,
    "zone_branch_moves": 5,
    "zone_oracle_moves": 3
  },
  "attempted_this_run": 8,
  "completed_this_run": 7,
  "skipped_terminal_this_run": 1,
  "elapsed_seconds": 2.582042044001355,
  "hitting_cache": "CacheInfo(hits=28619, misses=1457, maxsize=1000000, currsize=1457)"
}
```

## Aggregate zone metrics

| zone               |   positions |   mean_zone_cells |   mean_zone_cell_fraction |   mean_zone_pairs |   mean_baseline_pairs |   mean_pair_reduction |   mean_terminal_recall |   mean_forcing_recall |   mean_best_recall |   mean_best_value_retention |   mean_false_zone_mass |
|:-------------------|------------:|------------------:|--------------------------:|------------------:|----------------------:|----------------------:|-----------------------:|----------------------:|-------------------:|----------------------------:|-----------------------:|
| branching_debt     |           7 |           6.28571 |                 0.127023  |          17.1429  |               990.714 |              0.982245 |              0.142857  |             1         |           1        |                    1        |               0        |
| combo              |           7 |          24.7143  |                 0.499761  |         260       |               990.714 |              0.730046 |              0.142857  |             1         |           1        |                    1        |               0.745272 |
| naive_radius       |           7 |          39.4286  |                 0.795554  |         665.286   |               990.714 |              0.31932  |              0.142857  |             1         |           1        |                    1        |               0.83968  |
| oracle_upper       |           7 |           4.42857 |                 0.0893466 |           7.85714 |               990.714 |              0.991934 |              0.107143  |             0.685714  |           1        |                    1        |               0        |
| ap_flow            |           7 |          20       |                 0.403137  |         167.714   |               990.714 |              0.828301 |              0.142857  |             0.514286  |           0.571429 |                    0.994618 |               0.785714 |
| obligation_support |           7 |           9.42857 |                 0.192322  |          36.8571  |               990.714 |              0.960347 |              0.0357143 |             0.0571429 |           0        |                    0.161428 |               0.74571  |

## Interpretation guide

A strong zone lies near the top-right of the efficiency frontier:

```text
high forcing recall + high pair reduction
```

The expected winning family is not the expensive `oracle_upper`, but the practical `combo` zone:

```text
AP-flow ∪ obligation-support ∪ branching-debt
```

That would validate the architecture:

```text
flow proposes relevance;
branching debt focuses threat candidates;
transversal pressure verifies proof obligations.
```
