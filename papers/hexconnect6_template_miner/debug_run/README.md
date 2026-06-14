# Hex Connect-6 Primitive Template Miner

This run mines local forcing events for infinite Hex Connect-6 by evaluating the
urgent obligation hypergraph induced by candidate two-stone moves.

For each candidate move, exact pressure is:

```text
pressure = max(0, tau(O(P,m)) - 2)
```

where `tau` is the minimum hitting-set size of the urgent obligation hypergraph.
Positive pressure means the defender's two-stone reply capacity is exceeded.

## Run Summary

```json
{
  "positions_sampled": 1,
  "candidate_pairs_evaluated": 2,
  "positive_pressure_events": 4,
  "raw_templates": 4,
  "minimal_templates": 4,
  "canonical_primitive_templates": 4,
  "radius": 4,
  "candidate_radius": 4,
  "max_candidate_pairs": 24,
  "generators": [
    "adversarial"
  ],
  "pressure_modes": [
    "exact",
    "proto"
  ],
  "minimize": true,
  "canonicalize": true,
  "seed": 20260510,
  "top_templates": [
    {
      "template_id": "T_0001",
      "type": "exact",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -1,
          1
        ],
        [
          0,
          -3
        ],
        [
          0,
          -2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ],
        [
          0,
          1
        ],
        [
          1,
          1
        ]
      ],
      "defender": [
        [
          -2,
          1
        ]
      ],
      "move": [
        [
          0,
          2
        ],
        [
          2,
          1
        ]
      ],
      "obligations": [
        [
          [
            0,
            -4
          ]
        ],
        [
          [
            0,
            3
          ]
        ],
        [
          [
            3,
            1
          ],
          [
            4,
            1
          ]
        ]
      ],
      "canonical_signature": "4bb0974ddca9e32abeb9c73f8ef7e2c496e6198c",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": true,
      "source_type": "adversarial"
    },
    {
      "template_id": "T_0002",
      "type": "proto",
      "tau": 5,
      "pressure": 3,
      "attacker": [
        [
          -3,
          1
        ],
        [
          -1,
          1
        ],
        [
          0,
          -3
        ],
        [
          0,
          -2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ],
        [
          0,
          1
        ],
        [
          2,
          -2
        ]
      ],
      "defender": [],
      "move": [
        [
          0,
          2
        ],
        [
          2,
          1
        ]
      ],
      "obligations": [
        [
          [
            0,
            -4
          ]
        ],
        [
          [
            0,
            3
          ]
        ],
        [
          [
            -2,
            1
          ],
          [
            1,
            1
          ]
        ],
        [
          [
            -5,
            1
          ],
          [
            -4,
            1
          ],
          [
            -2,
            1
          ]
        ],
        [
          [
            -3,
            3
          ],
          [
            -2,
            2
          ],
          [
            1,
            -1
          ]
        ],
        [
          [
            -2,
            2
          ],
          [
            1,
            -1
          ],
          [
            3,
            -3
          ]
        ],
        [
          [
            1,
            -1
          ],
          [
            3,
            -3
          ],
          [
            4,
            -4
          ]
        ],
        [
          [
            1,
            1
          ],
          [
            3,
            1
          ],
          [
            4,
            1
          ]
        ]
      ],
      "canonical_signature": "7b8a12dffb8606770a5237c4555fc84db73c3495",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": true,
      "source_type": "adversarial"
    },
    {
      "template_id": "T_0003",
      "type": "exact",
      "tau": 4,
      "pressure": 2,
      "attacker": [
        [
          -1,
          1
        ],
        [
          0,
          -3
        ],
        [
          0,
          -2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ],
        [
          0,
          1
        ],
        [
          2,
          -2
        ]
      ],
      "defender": [],
      "move": [
        [
          0,
          2
        ],
        [
          1,
          -1
        ]
      ],
      "obligations": [
        [
          [
            0,
            -4
          ]
        ],
        [
          [
            0,
            3
          ]
        ],
        [
          [
            -3,
            3
          ],
          [
            -2,
            2
          ]
        ],
        [
          [
            -2,
            2
          ],
          [
            3,
            -3
          ]
        ],
        [
          [
            3,
            -3
          ],
          [
            4,
            -4
          ]
        ]
      ],
      "canonical_signature": "60dcc0b9ff668622d200297acdf266599d123a07",
      "pair_shape": "(-3, 1)",
      "family": "kink_bridge",
      "terminal": true,
      "source_type": "adversarial"
    },
    {
      "template_id": "T_0004",
      "type": "proto",
      "tau": 6,
      "pressure": 4,
      "attacker": [
        [
          -2,
          0
        ],
        [
          -1,
          1
        ],
        [
          0,
          -3
        ],
        [
          0,
          -2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ],
        [
          0,
          1
        ],
        [
          1,
          1
        ]
      ],
      "defender": [],
      "move": [
        [
          0,
          2
        ],
        [
          1,
          -1
        ]
      ],
      "obligations": [
        [
          [
            0,
            -4
          ]
        ],
        [
          [
            0,
            3
          ]
        ],
        [
          [
            -4,
            1
          ],
          [
            -3,
            1
          ],
          [
            -2,
            1
          ]
        ],
        [
          [
            -4,
            4
          ],
          [
            -3,
            3
          ],
          [
            -2,
            2
          ]
        ],
        [
          [
            -3,
            1
          ],
          [
            -2,
            1
          ],
          [
            2,
            1
          ]
        ],
        [
          [
            -3,
            3
          ],
          [
            -2,
            2
          ],
          [
            2,
            -2
          ]
        ],
        [
          [
            -2,
            1
          ],
          [
            2,
            1
          ],
          [
            3,
            1
          ]
        ],
        [
          [
            -2,
            2
          ],
          [
            2,
            -2
          ],
          [
            3,
            -3
          ]
        ],
        [
          [
            2,
            -2
          ],
          [
            3,
            -3
          ],
          [
            4,
            -4
          ]
        ],
        [
          [
            2,
            1
          ],
          [
            3,
            1
          ],
          [
            4,
            1
          ]
        ]
      ],
      "canonical_signature": "5b7474d5c6477877c22b0d40c2b973a08294aa3f",
      "pair_shape": "(-3, 1)",
      "family": "kink_bridge",
      "terminal": true,
      "source_type": "adversarial"
    }
  ]
}
```

## Main Outputs

- `data/positions.csv`
- `data/candidate_moves.csv`
- `data/positive_pressure_events.csv`
- `data/raw_templates.csv`
- `data/minimal_templates.csv`
- `data/canonical_templates.csv`
- `data/primitive_templates.csv`
- `data/template_frequencies.csv`
- `data/template_examples.json`
- `figures/tau_vs_obligations.png`
- `figures/template_frequency_rank.png`
- `figures/template_shape_spectrum.png`
- `figures/top_templates_diagram.pdf`
- `template_diagrams/`

## Notes

The default candidate policy ranks local frontier pairs and caps them with
`--max-candidate-pairs` so exploratory runs can scale. Set
`--max-candidate-pairs 0` for exhaustive pair enumeration inside
`--candidate-radius`.
