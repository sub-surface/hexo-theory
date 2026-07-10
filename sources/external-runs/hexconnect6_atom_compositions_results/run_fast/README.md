# Atom-composition opening evaluation

This package evaluates Hex Connect-6 openings by compositions of primitive forcing atoms.

A move induces exact/proto obligation hypergraphs. Their integer incidence fingerprints
are looked up as elements in the periodic table; a short minimax search then scores
White openings at several continuation depths.

Key files:
- data/opening_atom_values.csv
- data/principal_variations.csv
- data/atom_compositions.csv
- data/element_values.csv
- data/safest_openings.csv
- data/riskiest_openings.csv

Key figures:
- opening_value_surface_d0.png
- opening_value_surface_d4.png
- opening_value_by_depth.png
- opening_ranking_stability.png
- atom_composition_by_depth.png
- shape_composition_by_ply.png
- opening_shape_vulnerability.png
