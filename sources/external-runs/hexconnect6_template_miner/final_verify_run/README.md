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
  "candidate_pairs_evaluated": 147,
  "positive_pressure_events": 8,
  "raw_templates": 8,
  "minimal_templates": 8,
  "canonical_primitive_templates": 8,
  "radius": 4,
  "candidate_radius": 4,
  "max_candidate_pairs": 36,
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
      "type": "exact",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -3,
          0
        ],
        [
          -2,
          0
        ],
        [
          -1,
          -1
        ],
        [
          -1,
          0
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
          1,
          0
        ],
        [
          2,
          -1
        ]
      ],
      "defender": [
        [
          3,
          -1
        ]
      ],
      "move": [
        [
          1,
          -1
        ],
        [
          2,
          0
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ]
        ],
        [
          [
            3,
            0
          ]
        ],
        [
          [
            -3,
            -1
          ],
          [
            -2,
            -1
          ]
        ]
      ],
      "canonical_signature": "72d3766319ae5d23ea19972e4f6a583655d7c85d",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
      "terminal": true,
      "source_type": "adversarial"
    },
    {
      "template_id": "T_0005",
      "type": "proto",
      "tau": 6,
      "pressure": 4,
      "attacker": [
        [
          -3,
          0
        ],
        [
          -2,
          0
        ],
        [
          -1,
          -1
        ],
        [
          -1,
          0
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
          1,
          0
        ]
      ],
      "defender": [
        [
          2,
          -4
        ],
        [
          3,
          -1
        ]
      ],
      "move": [
        [
          1,
          -1
        ],
        [
          2,
          0
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ]
        ],
        [
          [
            3,
            0
          ]
        ],
        [
          [
            -5,
            3
          ],
          [
            -4,
            2
          ],
          [
            -3,
            1
          ]
        ],
        [
          [
            -4,
            -1
          ],
          [
            -3,
            -1
          ],
          [
            -2,
            -1
          ]
        ],
        [
          [
            -4,
            2
          ],
          [
            -3,
            1
          ],
          [
            1,
            -3
          ]
        ],
        [
          [
            -3,
            -1
          ],
          [
            -2,
            -1
          ],
          [
            2,
            -1
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
        ]
      ],
      "canonical_signature": "c898af67438ae02a84f803cedcbd3bd3ff177454",
      "pair_shape": "(-2, 1)",
      "family": "bridge_fork",
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
