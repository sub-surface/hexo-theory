# D6 Seeded Hypergraph Experiment

This is an OEIS A392177-inspired exploration of normal 1-2-2 Hex Connect6 on the A2 hex lattice.

A392177 uses a square spiral and two colors, placing each next piece at the smallest spiral cell not attacked by the opposite color. Here the square-spiral/knight graph is replaced by a D6 shell spiral and the weighted 2-section of the Connect6 winning-set hypergraph.

## Rule

- Black starts with a single seed at `(0, 0)`.
- White places two stones at the earliest unoccupied non-attacked D6 spiral cells.
- After White's opening response, Black places two stones after each White move.
- A cell is attacked by an opponent stone when both cells co-occur in at least `attack_min_weight` length-6 hex winning progressions.

## Runs

- `r8_t18_k6_w1`: black=29, white=31, final tau B/W=4/2, final obligations B/W=6/4
- `r8_t18_k6_w3`: black=35, white=36, final tau B/W=4/4, final obligations B/W=33/44
- `r8_t18_k6_w5`: black=35, white=36, final tau B/W=4/4, final obligations B/W=44/49

## Outputs

- `run_summary.csv`: one row per threshold run.
- `turn_metrics.csv`: tau, obligation, support, component, and sector metrics per recorded turn.
- `sequence_terms.csv`: OEIS-style spiral-index readout for Black and White stones.
- `shell_counts.csv`: Black/White counts by D6 shell.
- `d6_seeded_hypergraph.json`: full structured corpus.
- `evidence/figures/`: occupancy maps, tau curves, obligation curves, shell/sector imbalance, and sequence scatter.
