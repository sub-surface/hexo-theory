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
  "positions_sampled": 4,
  "candidate_pairs_evaluated": 305,
  "positive_pressure_events": 20,
  "raw_templates": 20,
  "minimal_templates": 20,
  "canonical_primitive_templates": 20,
  "radius": 5,
  "candidate_radius": 4,
  "max_candidate_pairs": 80,
  "generators": [
    "random",
    "rail",
    "opening",
    "selfplay",
    "adversarial"
  ],
  "pressure_modes": [
    "exact",
    "proto"
  ],
  "minimize": false,
  "canonicalize": true,
  "seed": 20260510,
  "top_templates": [
    {
      "template_id": "T_0001",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -4,
          -1
        ],
        [
          -3,
          0
        ],
        [
          -3,
          4
        ],
        [
          2,
          -5
        ]
      ],
      "defender": [
        [
          -1,
          0
        ]
      ],
      "move": [
        [
          -3,
          -1
        ],
        [
          -2,
          -1
        ]
      ],
      "obligations": [
        [
          [
            -6,
            -1
          ],
          [
            -5,
            -1
          ],
          [
            -1,
            -1
          ]
        ],
        [
          [
            -5,
            -1
          ],
          [
            -1,
            -1
          ],
          [
            0,
            -1
          ]
        ],
        [
          [
            -3,
            1
          ],
          [
            -3,
            2
          ],
          [
            -3,
            3
          ]
        ],
        [
          [
            -1,
            -2
          ],
          [
            0,
            -3
          ],
          [
            1,
            -4
          ]
        ],
        [
          [
            -1,
            -1
          ],
          [
            0,
            -1
          ],
          [
            1,
            -1
          ]
        ]
      ],
      "canonical_signature": "2c1dab8afc09ff2f12d8d7b4997b2f50837424a2",
      "pair_shape": "(-1, 0)",
      "family": "adjacent",
      "terminal": false,
      "source_type": "random"
    },
    {
      "template_id": "T_0002",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -3,
          2
        ],
        [
          -2,
          2
        ],
        [
          0,
          -2
        ],
        [
          0,
          0
        ]
      ],
      "defender": [
        [
          -1,
          2
        ],
        [
          0,
          1
        ],
        [
          1,
          0
        ]
      ],
      "move": [
        [
          -1,
          1
        ],
        [
          0,
          -1
        ]
      ],
      "obligations": [
        [
          [
            -5,
            5
          ],
          [
            -4,
            4
          ],
          [
            -3,
            3
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
            1,
            -1
          ]
        ],
        [
          [
            -3,
            3
          ],
          [
            1,
            -1
          ],
          [
            2,
            -2
          ]
        ],
        [
          [
            0,
            -5
          ],
          [
            0,
            -4
          ],
          [
            0,
            -3
          ]
        ],
        [
          [
            1,
            -1
          ],
          [
            2,
            -2
          ],
          [
            3,
            -3
          ]
        ]
      ],
      "canonical_signature": "3a10c094a80d22016523477748170589e613f515",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": false,
      "source_type": "rail"
    },
    {
      "template_id": "T_0003",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -3,
          2
        ],
        [
          -2,
          2
        ],
        [
          0,
          0
        ]
      ],
      "defender": [
        [
          -1,
          2
        ],
        [
          0,
          1
        ],
        [
          1,
          0
        ]
      ],
      "move": [
        [
          -4,
          2
        ],
        [
          -1,
          1
        ]
      ],
      "obligations": [
        [
          [
            -7,
            2
          ],
          [
            -6,
            2
          ],
          [
            -5,
            2
          ]
        ],
        [
          [
            -5,
            5
          ],
          [
            -4,
            4
          ],
          [
            -3,
            3
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
            1,
            -1
          ]
        ],
        [
          [
            -3,
            3
          ],
          [
            1,
            -1
          ],
          [
            2,
            -2
          ]
        ],
        [
          [
            1,
            -1
          ],
          [
            2,
            -2
          ],
          [
            3,
            -3
          ]
        ]
      ],
      "canonical_signature": "2b77a85e0aaf20959b2ba9eb5c32161bd10e6e21",
      "pair_shape": "(-3, 1)",
      "family": "kink_bridge",
      "terminal": false,
      "source_type": "rail"
    },
    {
      "template_id": "T_0004",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -2,
          2
        ],
        [
          -1,
          1
        ],
        [
          -1,
          2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ]
      ],
      "defender": [
        [
          -1,
          -1
        ],
        [
          0,
          1
        ],
        [
          0,
          2
        ],
        [
          0,
          3
        ],
        [
          1,
          -1
        ]
      ],
      "move": [
        [
          -1,
          0
        ],
        [
          0,
          -2
        ]
      ],
      "obligations": [
        [
          [
            -5,
            5
          ],
          [
            -4,
            4
          ],
          [
            -3,
            3
          ]
        ],
        [
          [
            -1,
            3
          ],
          [
            -1,
            4
          ],
          [
            -1,
            5
          ]
        ],
        [
          [
            0,
            -5
          ],
          [
            0,
            -4
          ],
          [
            0,
            -3
          ]
        ]
      ],
      "canonical_signature": "65a1c7260726d997eb4cef33b4e2d7fba4d15a80",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": false,
      "source_type": "opening"
    },
    {
      "template_id": "T_0005",
      "type": "proto",
      "tau": 4,
      "pressure": 2,
      "attacker": [
        [
          -2,
          2
        ],
        [
          -1,
          1
        ],
        [
          -1,
          2
        ],
        [
          0,
          -1
        ],
        [
          0,
          0
        ]
      ],
      "defender": [
        [
          -1,
          -1
        ],
        [
          0,
          1
        ],
        [
          0,
          2
        ],
        [
          0,
          3
        ],
        [
          1,
          -1
        ],
        [
          2,
          -2
        ]
      ],
      "move": [
        [
          -3,
          2
        ],
        [
          -1,
          0
        ]
      ],
      "obligations": [
        [
          [
            -6,
            2
          ],
          [
            -5,
            2
          ],
          [
            -4,
            2
          ]
        ],
        [
          [
            -5,
            4
          ],
          [
            -4,
            3
          ],
          [
            -2,
            1
          ]
        ],
        [
          [
            -5,
            5
          ],
          [
            -4,
            4
          ],
          [
            -3,
            3
          ]
        ],
        [
          [
            -4,
            3
          ],
          [
            -2,
            1
          ],
          [
            1,
            -2
          ]
        ],
        [
          [
            -2,
            1
          ],
          [
            1,
            -2
          ],
          [
            2,
            -3
          ]
        ],
        [
          [
            -1,
            3
          ],
          [
            -1,
            4
          ],
          [
            -1,
            5
          ]
        ]
      ],
      "canonical_signature": "78b1eec5a02a1ca4a9bfea6c6ebe862734dbeccd",
      "pair_shape": "(-2, 0)",
      "family": "rail_ladder",
      "terminal": false,
      "source_type": "opening"
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
