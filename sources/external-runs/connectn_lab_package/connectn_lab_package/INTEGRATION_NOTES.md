# Integration notes for the previous RZ-BDPN benchmark

The earlier Hex Connect6 benchmark was specialised to `p=2` and A2. This package generalises the key operations.

## Replace hardcoded tau > 2 with tau > p

Old:

```python
threshold_preserved = (tau_full > 2) == (tau_zone > 2)
```

New:

```python
threshold_preserved = (tau_full > p) == (tau_zone > p)
```

Or use:

```python
from connectn_lab.relevance import zone_report
report = zone_report(obligations, zone=zone_cells, p=config.p, universe=candidate_universe)
```

## Generalise game config

Add:

```json
{
  "lattice": "A2_hex",
  "k": 6,
  "p": 2,
  "q": 1,
  "seed": "central-root"
}
```

Then sweep over:

```text
A2_hex, Z2_diag, Z2_rook
k = 4..8
p = 1..3
q = 0..p
```

## Add atom mining to failures

When a zone fails threshold retention:

```python
missed = report.missed_atom_edges
name = report.missed_atom_name
```

Store:

```text
position_id
zone_method
full_tau
zone_tau
missed_atom_name
missed_atom_fingerprint
missed_atom_edges
```

This turns relevance-zone failure into atlas growth.

## Dashboard additions

Recommended new live metrics:

```text
tau-threshold retention
atom recall
false tactical compression rate
most common missed atom
integrality-gap atom rate
mean support size of missed atoms
```
