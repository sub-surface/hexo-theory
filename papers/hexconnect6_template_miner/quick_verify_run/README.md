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
  "positions_sampled": 5,
  "candidate_pairs_evaluated": 196,
  "positive_pressure_events": 12,
  "raw_templates": 12,
  "minimal_templates": 12,
  "canonical_primitive_templates": 12,
  "radius": 4,
  "candidate_radius": 4,
  "max_candidate_pairs": 48,
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
  "minimize": true,
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
            -1,
            -3
          ],
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ]
        ],
        [
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ]
        ],
        [
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ],
          [
            -1,
            4
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
        ],
        [
          [
            0,
            -4
          ],
          [
            0,
            -3
          ],
          [
            0,
            1
          ]
        ],
        [
          [
            0,
            -3
          ],
          [
            0,
            1
          ],
          [
            0,
            2
          ]
        ]
      ],
      "canonical_signature": "d130dc1c0b38b23a4dd6ec6acc5348c8a65a0997",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": false,
      "source_type": "opening"
    },
    {
      "template_id": "T_0002",
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
        ]
      ],
      "defender": [
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
            2
          ],
          [
            -4,
            2
          ],
          [
            0,
            2
          ]
        ],
        [
          [
            -4,
            2
          ],
          [
            0,
            2
          ],
          [
            1,
            2
          ]
        ],
        [
          [
            -1,
            -3
          ],
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ]
        ],
        [
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ]
        ],
        [
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ],
          [
            -1,
            4
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
            2
          ],
          [
            1,
            2
          ],
          [
            2,
            2
          ]
        ]
      ],
      "canonical_signature": "813f6e4fae5803efc738a3cedc1cfcdd08078078",
      "pair_shape": "(-2, 0)",
      "family": "rail_ladder",
      "terminal": false,
      "source_type": "opening"
    },
    {
      "template_id": "T_0003",
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
          1,
          -1
        ]
      ],
      "move": [
        [
          -3,
          2
        ],
        [
          0,
          -2
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
            2
          ],
          [
            -4,
            2
          ],
          [
            0,
            2
          ]
        ],
        [
          [
            -4,
            2
          ],
          [
            0,
            2
          ],
          [
            1,
            2
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
            0,
            -4
          ],
          [
            0,
            -3
          ],
          [
            0,
            1
          ]
        ],
        [
          [
            0,
            -3
          ],
          [
            0,
            1
          ],
          [
            0,
            2
          ]
        ],
        [
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
          ]
        ],
        [
          [
            0,
            2
          ],
          [
            1,
            2
          ],
          [
            2,
            2
          ]
        ]
      ],
      "canonical_signature": "2df0c81bb4eae78ebb0ddff601dc840272849a54",
      "pair_shape": "(-4, 1)",
      "family": "kink_bridge",
      "terminal": false,
      "source_type": "opening"
    },
    {
      "template_id": "T_0004",
      "type": "proto",
      "tau": 4,
      "pressure": 2,
      "attacker": [
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
        ]
      ],
      "defender": [],
      "move": [
        [
          -2,
          1
        ],
        [
          -1,
          0
        ]
      ],
      "obligations": [
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
            -3,
            2
          ]
        ],
        [
          [
            -4,
            3
          ],
          [
            -3,
            2
          ],
          [
            1,
            -2
          ]
        ],
        [
          [
            -3,
            2
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
            -3
          ],
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ]
        ],
        [
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ]
        ],
        [
          [
            -1,
            -1
          ],
          [
            -1,
            3
          ],
          [
            -1,
            4
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
            1,
            -2
          ],
          [
            2,
            -3
          ],
          [
            3,
            -4
          ]
        ]
      ],
      "canonical_signature": "3121a7f9041fece09930de19f0dfa06b6ff1a668",
      "pair_shape": "(-1, 0)",
      "family": "adjacent",
      "terminal": false,
      "source_type": "opening"
    },
    {
      "template_id": "T_0005",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
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
          3
        ],
        [
          0,
          -2
        ]
      ],
      "obligations": [
        [
          [
            -1,
            -2
          ],
          [
            -1,
            -1
          ],
          [
            -1,
            0
          ]
        ],
        [
          [
            -1,
            -1
          ],
          [
            -1,
            0
          ],
          [
            -1,
            4
          ]
        ],
        [
          [
            -1,
            0
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
            -1,
            4
          ],
          [
            -1,
            5
          ],
          [
            -1,
            6
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
            0,
            -4
          ],
          [
            0,
            -3
          ],
          [
            0,
            1
          ]
        ],
        [
          [
            0,
            -3
          ],
          [
            0,
            1
          ],
          [
            0,
            2
          ]
        ]
      ],
      "canonical_signature": "24a8ed1e57b38d530556bb1c13be282944e3093a",
      "pair_shape": "(-5, 1)",
      "family": "kink_bridge",
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

The headline files are also copied to the run root:

- `primitive_templates.csv`
- `template_examples.json`
- `template_frequency_rank.png`
- `tau_vs_obligations.png`
- `template_shape_spectrum.png`
- `top_templates_diagram.pdf`

## Notes

The default candidate policy ranks local frontier pairs and caps them with
`--max-candidate-pairs` so exploratory runs can scale. Set
`--max-candidate-pairs 0` for exhaustive pair enumeration inside
`--candidate-radius`.
