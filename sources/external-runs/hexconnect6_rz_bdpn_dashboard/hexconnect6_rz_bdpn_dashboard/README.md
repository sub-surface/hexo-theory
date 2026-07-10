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


## Windows note

This version writes generated reports with `encoding="utf-8"` so PowerShell / CP1252 Python environments do not fail on mathematical symbols such as `∪`.


## CLI dashboard

Start the dashboard:

```bash
python dashboard.py
```

Useful commands:

```text
show
set positions 300
set zone_margin_ap_cells 10
start
status
summary
watch 15
stop
exit
```

`stop` writes a `STOP` marker into the active run folder and also terminates the subprocess
if the dashboard launched it. The benchmark also checks for `STOP` between positions, so
you can stop gracefully from another terminal:

```bash
echo stop > rz_bdpn_overnight_run/STOP
```

## New zone: branching_plus_ap_margin

This release adds:

```text
branching_plus_ap_margin =
    branching_debt core
    ∪ top N AP-flow cells
    ∪ current obligation support
```

The intended result is to sit between `branching_debt` and full `combo`:

```text
higher recall than branching_debt
much higher pair reduction than combo
```

Tune it with:

```json
"zone_margin_ap_cells": 8,
"zone_margin_branch_moves": 10
```

## Quick monitoring without the dashboard

```bash
python monitor.py rz_bdpn_overnight_run/data/zone_metrics.csv
```
