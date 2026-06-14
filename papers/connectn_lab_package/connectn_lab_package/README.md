# Connect-n Lab: seeded biased progression-hypergraph games

This package generalises the earlier Hex Connect6 CGT scaffold from one game to a small family:

```text
Connect(L, D, k, p, q, seed)
```

where:

- `L` is a lattice, currently `A2_hex`, `Z2_diag`, or `Z2_rook`;
- `D` is the set of permitted progression directions;
- `k` is the line length required to win;
- `p` is the normal per-turn stone budget;
- `q` is the first-player opening budget;
- `seed` records whether the game begins with a central singleton, balanced pair, no seed, etc.

The conceptual shift is:

```text
The board is not the state.
The live progression hypergraph is the state.
The obligation transversal structure is the tactical value.
The lattice embedding is the geometry of possible realisations.
```

## Quick start

From the package root:

```bash
python examples/atom_mining_demo.py
python examples/zone_failure_demo.py
python examples/family_sweep_demo.py
python examples/seed_asymmetry_demo.py
python -m tests.test_smoke
```

You can also use the small CLI:

```bash
python -m connectn_lab.cli --demo atom
python -m connectn_lab.cli --demo zone
```

No required dependencies beyond the Python standard library. If `scipy` is installed, the package will also compute fractional hitting numbers `tau*` for small obligation hypergraphs.

## Why this exists

Hex Connect6, ordinary Connect-n on a square grid, Gomoku-like games, and many relaxed variants can all be treated as biased positional games on a hypergraph of lattice arithmetic progressions.

A local tactical event is represented by an obligation family `O`: each edge is a set of cells the defender must hit to prevent a near-term completion. If the defender has `p` stones per turn, the key threshold is:

```text
tau(O) > p
```

where `tau` is the transversal / hitting number. This package mines, names, and compares such obligation atoms.

## Important files

```text
connectn_lab/
    lattices.py       # A2, Z2 with directions and symmetry actions
    progressions.py   # k-term progression enumeration
    obligations.py    # live progressions and urgent obligation extraction
    hypergraph.py     # tau, tau*, fingerprints, components
    atoms.py          # shrink, canonicalise, name motifs
    relevance.py      # zone tau-retention and missed-atom reports
    experiments.py    # game specs and small sweep stats
    seeds.py          # central-root and symmetric seed utilities
examples/
    atom_mining_demo.py
    zone_failure_demo.py
    family_sweep_demo.py
    seed_asymmetry_demo.py
THEORY.md
EXPERIMENTS.md
CONJECTURES.md
```

## Core metric

The main benchmark metric is not pair reduction alone. It is pair reduction subject to preservation of the tactical threshold:

```text
tau-threshold retention:
    does the zone preserve whether tau(O) > p?
```

A stronger metric is atom recall:

```text
atom recall:
    does the zone preserve every minor-minimal tau(O) > p witness?
```

## Suggested next integration

The previous RZ-BDPN benchmark can import `connectn_lab.relevance.zone_report` and replace its Connect6-specific `tau > 2` checks by the general `tau > p` condition. This allows A2 Connect6, square-grid Connect6, Gomoku-like variants, and seeded/unseeded openings to be compared in one experimental language.
