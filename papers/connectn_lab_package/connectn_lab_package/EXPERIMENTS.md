# Experiment suite design

## 1. Family sweep

Sweep:

```text
lattice:      Z2_rook, Z2_diag, A2_hex
k:            4, 5, 6, 7, 8
p:            1, 2, 3
q:            0, 1, ..., p
seed:         none, central-root, symmetric-pair, random, adversarial
radius:       4, 5, 6, 7, 8
```

Core game spec:

```text
Connect(L, D, k, p, q, seed)
```

For each generated position:

```text
extract live k-progressions
extract urgent obligations
compute tau and tau*
if tau > p:
    shrink to atom witness
    canonicalise under lattice symmetries
    add to atlas
```

## 2. Metrics

### Tactical metrics

```text
tau(O)
tau*(O)
integrality_gap = tau - tau*
obligation count
support size
component count
edge overlap signature
automorphism/canonical key
```

### Relevance-zone metrics

```text
tau-threshold retention:
    does zone preserve tau(O) > p?

atom recall:
    does zone preserve all minor-minimal tau > p witnesses?

pair reduction:
    1 - C(|zone|,2) / C(|universe|,2)

false tactical compression:
    tau(full) > p but tau(zone) <= p
```

### Seed asymmetry metrics

```text
first tau>p generation depth
minimum support size of first atom
atom diversity by q
direction entropy of urgent progressions
root-distance distribution of obligations
```

## 3. Lattice-isomorphism tests

For every atom mined on A2, attempt to realise it on Z2. For every atom mined on Z2, attempt to realise it on A2.

Classification:

```text
universal atom:      embeds naturally on both A2 and Z2
hex-native atom:     cheap on A2, impossible or costly on Z2
square-native atom:  cheap on Z2, impossible or costly on A2
distorted atom:      embeds on both with different support/generation depth
```

## 4. Failure-to-atom loop

The benchmark should not discard failures. It should mine them.

```text
zone failure
-> missed obligation family
-> tau>p witness
-> shrink to atom
-> canonicalise
-> name or add to atlas
-> improve zone generator
```

This converts search errors into a growing periodic table of tactical structures.

## 5. Minimal implementation targets

The current package implements enough to begin:

```bash
python examples/atom_mining_demo.py
python examples/zone_failure_demo.py
python examples/family_sweep_demo.py
python examples/seed_asymmetry_demo.py
```

The next heavier implementation should add:

```text
random legal position generation
small local minimax / proof-number validation
canonical graph-isomorphism labelling
parallel sweeps over specs
CSV reports and phase diagrams
```
