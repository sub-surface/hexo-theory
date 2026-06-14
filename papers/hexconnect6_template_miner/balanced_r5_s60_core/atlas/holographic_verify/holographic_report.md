# Holographic Boundary Experiment

## Mathematical Setup

The finite local template is treated as a bulk object embedded in the affine A2
hex lattice. Translation symmetry removes absolute position. D6 symmetry
quotients rotations and reflections. The Noether-style charges are line-charge
profiles along the three A2 coordinate foliations. The holographic boundary
data is the exposed colored flux around the occupied patch plus these line
charges and coarse topology.

This is not a theorem yet; it is an empirical test of whether boundary data
nearly determines the forcing physics.

## Headline Results

- Templates analysed: 296
- Exact holographic groups: 296
- Exact holographic compression: 1.0
- Coarse holographic groups: 252
- Coarse holographic compression: 1.174603
- Coarse Noether compression: 1.608696
- Coarse boundary-flux compression: 1.423077
- Abstract-incidence groups: 73
- Abstract-incidence tau purity: 1.0
- Best leave-one-out tau predictor: integer_fingerprint at accuracy 0.962838
- Coarse Noether leave-one-out tau accuracy: 0.638514
- Coarse boundary-flux leave-one-out tau accuracy: 0.668919
- Coarse holographic leave-one-out tau accuracy: 0.584459

## Interpretation

The exact boundary state is almost a coordinate label, so it is not a useful
compression. The coarse boundary states are more interesting: they are weaker
than the abstract-incidence and integer-fingerprint quotients, but still carry
nontrivial predictive information. On this run, the tactical pressure is best
described by an algebraic bulk invariant, while the embedding boundary supplies
a partial "field theory" over motif family and topology.

## Group Metrics

```json
[
  {
    "signature": "size_signature",
    "rows": 296,
    "groups": 73,
    "compression_ratio": 4.054795,
    "mean_group_size": 4.054795,
    "max_group_size": 47,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.702703,
    "manifold_label_purity": 0.804054,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "coarse_noether_signature",
    "rows": 296,
    "groups": 184,
    "compression_ratio": 1.608696,
    "mean_group_size": 1.608696,
    "max_group_size": 15,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.85473,
    "manifold_label_purity": 0.918919,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "noether_line_signature",
    "rows": 296,
    "groups": 296,
    "compression_ratio": 1.0,
    "mean_group_size": 1.0,
    "max_group_size": 1,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 1.0,
    "manifold_label_purity": 1.0,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "coarse_boundary_flux_signature",
    "rows": 296,
    "groups": 208,
    "compression_ratio": 1.423077,
    "mean_group_size": 1.423077,
    "max_group_size": 23,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.915541,
    "manifold_label_purity": 1.0,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "boundary_flux_signature",
    "rows": 296,
    "groups": 240,
    "compression_ratio": 1.233333,
    "mean_group_size": 1.233333,
    "max_group_size": 23,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.945946,
    "manifold_label_purity": 1.0,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "coarse_holographic_signature",
    "rows": 296,
    "groups": 252,
    "compression_ratio": 1.174603,
    "mean_group_size": 1.174603,
    "max_group_size": 6,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.952703,
    "manifold_label_purity": 1.0,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "holographic_boundary_signature",
    "rows": 296,
    "groups": 296,
    "compression_ratio": 1.0,
    "mean_group_size": 1.0,
    "max_group_size": 1,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 1.0,
    "manifold_label_purity": 1.0,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "abstract_signature",
    "rows": 296,
    "groups": 73,
    "compression_ratio": 4.054795,
    "mean_group_size": 4.054795,
    "max_group_size": 47,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.702703,
    "manifold_label_purity": 0.804054,
    "atom_presence_purity": 1.0
  },
  {
    "signature": "integer_fingerprint",
    "rows": 296,
    "groups": 35,
    "compression_ratio": 8.457143,
    "mean_group_size": 8.457143,
    "max_group_size": 132,
    "tau_purity": 1.0,
    "pressure_purity": 1.0,
    "family_purity": 0.577703,
    "manifold_label_purity": 0.743243,
    "atom_presence_purity": 0.844595
  },
  {
    "signature": "family",
    "rows": 296,
    "groups": 5,
    "compression_ratio": 59.2,
    "mean_group_size": 59.2,
    "max_group_size": 160,
    "tau_purity": 0.550676,
    "pressure_purity": 0.550676,
    "family_purity": 1.0,
    "manifold_label_purity": 0.733108,
    "atom_presence_purity": 0.743243
  }
]
```

## Prediction Metrics

```json
[
  {
    "signature": "size_signature",
    "target": "tau",
    "accuracy": 0.905405,
    "covered_fraction": 0.888514
  },
  {
    "signature": "size_signature",
    "target": "pressure",
    "accuracy": 0.905405,
    "covered_fraction": 0.888514
  },
  {
    "signature": "size_signature",
    "target": "family",
    "accuracy": 0.554054,
    "covered_fraction": 0.888514
  },
  {
    "signature": "size_signature",
    "target": "atom_presence",
    "accuracy": 0.983108,
    "covered_fraction": 0.888514
  },
  {
    "signature": "coarse_noether_signature",
    "target": "tau",
    "accuracy": 0.638514,
    "covered_fraction": 0.503378
  },
  {
    "signature": "coarse_noether_signature",
    "target": "pressure",
    "accuracy": 0.638514,
    "covered_fraction": 0.503378
  },
  {
    "signature": "coarse_noether_signature",
    "target": "family",
    "accuracy": 0.577703,
    "covered_fraction": 0.503378
  },
  {
    "signature": "coarse_noether_signature",
    "target": "atom_presence",
    "accuracy": 0.918919,
    "covered_fraction": 0.503378
  },
  {
    "signature": "noether_line_signature",
    "target": "tau",
    "accuracy": 0.550676,
    "covered_fraction": 0.0
  },
  {
    "signature": "noether_line_signature",
    "target": "pressure",
    "accuracy": 0.550676,
    "covered_fraction": 0.0
  },
  {
    "signature": "noether_line_signature",
    "target": "family",
    "accuracy": 0.540541,
    "covered_fraction": 0.0
  },
  {
    "signature": "noether_line_signature",
    "target": "atom_presence",
    "accuracy": 0.743243,
    "covered_fraction": 0.0
  },
  {
    "signature": "coarse_boundary_flux_signature",
    "target": "tau",
    "accuracy": 0.668919,
    "covered_fraction": 0.439189
  },
  {
    "signature": "coarse_boundary_flux_signature",
    "target": "pressure",
    "accuracy": 0.668919,
    "covered_fraction": 0.439189
  },
  {
    "signature": "coarse_boundary_flux_signature",
    "target": "family",
    "accuracy": 0.594595,
    "covered_fraction": 0.439189
  },
  {
    "signature": "coarse_boundary_flux_signature",
    "target": "atom_presence",
    "accuracy": 0.858108,
    "covered_fraction": 0.439189
  },
  {
    "signature": "boundary_flux_signature",
    "target": "tau",
    "accuracy": 0.597973,
    "covered_fraction": 0.266892
  },
  {
    "signature": "boundary_flux_signature",
    "target": "pressure",
    "accuracy": 0.597973,
    "covered_fraction": 0.266892
  },
  {
    "signature": "boundary_flux_signature",
    "target": "family",
    "accuracy": 0.557432,
    "covered_fraction": 0.266892
  },
  {
    "signature": "boundary_flux_signature",
    "target": "atom_presence",
    "accuracy": 0.804054,
    "covered_fraction": 0.266892
  },
  {
    "signature": "coarse_holographic_signature",
    "target": "tau",
    "accuracy": 0.584459,
    "covered_fraction": 0.236486
  },
  {
    "signature": "coarse_holographic_signature",
    "target": "pressure",
    "accuracy": 0.584459,
    "covered_fraction": 0.236486
  },
  {
    "signature": "coarse_holographic_signature",
    "target": "family",
    "accuracy": 0.540541,
    "covered_fraction": 0.236486
  },
  {
    "signature": "coarse_holographic_signature",
    "target": "atom_presence",
    "accuracy": 0.804054,
    "covered_fraction": 0.236486
  },
  {
    "signature": "holographic_boundary_signature",
    "target": "tau",
    "accuracy": 0.550676,
    "covered_fraction": 0.0
  },
  {
    "signature": "holographic_boundary_signature",
    "target": "pressure",
    "accuracy": 0.550676,
    "covered_fraction": 0.0
  },
  {
    "signature": "holographic_boundary_signature",
    "target": "family",
    "accuracy": 0.540541,
    "covered_fraction": 0.0
  },
  {
    "signature": "holographic_boundary_signature",
    "target": "atom_presence",
    "accuracy": 0.743243,
    "covered_fraction": 0.0
  },
  {
    "signature": "abstract_signature",
    "target": "tau",
    "accuracy": 0.905405,
    "covered_fraction": 0.888514
  },
  {
    "signature": "abstract_signature",
    "target": "pressure",
    "accuracy": 0.905405,
    "covered_fraction": 0.888514
  },
  {
    "signature": "abstract_signature",
    "target": "family",
    "accuracy": 0.554054,
    "covered_fraction": 0.888514
  },
  {
    "signature": "abstract_signature",
    "target": "atom_presence",
    "accuracy": 0.983108,
    "covered_fraction": 0.888514
  },
  {
    "signature": "integer_fingerprint",
    "target": "tau",
    "accuracy": 0.962838,
    "covered_fraction": 0.962838
  },
  {
    "signature": "integer_fingerprint",
    "target": "pressure",
    "accuracy": 0.962838,
    "covered_fraction": 0.962838
  },
  {
    "signature": "integer_fingerprint",
    "target": "family",
    "accuracy": 0.47973,
    "covered_fraction": 0.962838
  },
  {
    "signature": "integer_fingerprint",
    "target": "atom_presence",
    "accuracy": 0.844595,
    "covered_fraction": 0.962838
  },
  {
    "signature": "family",
    "target": "tau",
    "accuracy": 0.543919,
    "covered_fraction": 1.0
  },
  {
    "signature": "family",
    "target": "pressure",
    "accuracy": 0.543919,
    "covered_fraction": 1.0
  },
  {
    "signature": "family",
    "target": "family",
    "accuracy": 1.0,
    "covered_fraction": 1.0
  },
  {
    "signature": "family",
    "target": "atom_presence",
    "accuracy": 0.743243,
    "covered_fraction": 1.0
  }
]
```
