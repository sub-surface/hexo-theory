# Hex Connect-6 free-energy crystal search

This package tests a free-energy/crystal constraint for adaptive Hex Connect-6 search.

Core free energy:

    G(move) = complexity/surprise - tactical_value - crystal_coherence

where tactical_value includes exact/proto obligation-hypergraph pressure, and crystal
coherence includes line-order and low-frequency axial structure-factor gains.

Key figures:
- free_energy_path_heatmap.png
- free_energy_pair_landscape.png
- free_energy_over_ply.png
- crystal_order_over_ply.png
- pressure_emergence_over_ply.png
- shape_spectrum.png
- rail_bridge_kind_spectrum.png
- phase_diagram_terminal_events.png
- phase_diagram_line_order.png
