# RZ-BDPN relevance-zone benchmark

This folder benchmarks relevance-zone generators for 1-2-2 Infinite Hex Connect-6 on the A2 hex lattice.

The practical question is:

> Can we keep the tactical continuations while deleting most candidate pairs?

The benchmark compares:

- `naive_radius`
- `ap_flow`
- `obligation_support`
- `branching_debt`
- `combo`
- `oracle_upper`

The most important practical result is the efficiency frontier:

```text
forcing recall vs pair reduction
```

## Quick smoke test

```bash
python rz_bdpn_benchmark.py --config configs/smoke.json
```

## Overnight run

From this folder:

```bash
python rz_bdpn_benchmark.py --config configs/overnight.json --resume
```

The run is resumable because each position is generated from a deterministic per-position seed.
If it stops, rerun the same command with `--resume`.

## Outputs

After a run:

```text
data/zone_metrics.csv
data/reference_candidates.csv
data/position_records.csv
data/aggregate_zone_metrics.csv
data/reference_feature_correlations.csv
figures/zone_efficiency_frontier.png
figures/best_value_retention.png
figures/pair_reduction_by_zone.png
figures/feature_correlations.png
report.md
benchmark_manifest.json
resolved_config.json
```

## How to read the results

A good practical zone has:

- high `mean_forcing_recall`
- high `mean_pair_reduction`
- high `mean_best_value_retention`
- low `mean_false_zone_mass`

The expected useful method is `combo`:

```text
AP-flow ∪ obligation-support ∪ branching-debt
```

If `combo` approaches `oracle_upper` recall while keeping much higher pair reduction, the representation is doing real work.

## Scaling notes

To make the overnight run heavier:

- increase `positions`
- increase `reference_candidate_width`
- increase `white_reply_width`
- increase `black_continuation_width`

The largest costs are approximately:

```text
positions × reference_candidate_width × white_reply_width × black_continuation_width
```

Use `checkpoint_every` to control how often partial CSVs are flushed.
