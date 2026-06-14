# Wolfram-inspired Hex Connect-6 hypergraph experiment

This folder contains a Wolfram-style multiway/hypergraph analysis of a finite-window
Hex Connect-6 position.

Objects:
- `multiway_states.csv`: retained board states by ply
- `multiway_events.csv`: two-stone update events
- `branchial_edges.csv`: same-ply state similarity edges based on obligation hypergraphs
- `causal_edges.csv`: event-event causal overlaps
- `rulial_scan.csv`: small rule-space scan over pressure/heuristic scoring weights

Key definition:
    pressure(move) = max(0, tau(obligation_hypergraph_after_move) - 2)

where tau is the hitting number required to block urgent threats.

Main figures are in `figures/`.
