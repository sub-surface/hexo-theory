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
  "positions_sampled": 9,
  "candidate_pairs_evaluated": 1306,
  "positive_pressure_events": 700,
  "raw_templates": 700,
  "minimal_templates": 700,
  "canonical_primitive_templates": 680,
  "radius": 5,
  "candidate_radius": 4,
  "max_candidate_pairs": 160,
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
      "tau": 4,
      "pressure": 2,
      "attacker": [
        [
          -1,
          0
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
      "defender": [],
      "move": [
        [
          0,
          1
        ],
        [
          2,
          -1
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ],
          [
            -3,
            0
          ],
          [
            -2,
            0
          ]
        ],
        [
          [
            -3,
            0
          ],
          [
            -2,
            0
          ],
          [
            2,
            0
          ]
        ],
        [
          [
            -3,
            4
          ],
          [
            -2,
            3
          ],
          [
            -1,
            2
          ]
        ],
        [
          [
            -2,
            0
          ],
          [
            2,
            0
          ],
          [
            3,
            0
          ]
        ],
        [
          [
            -2,
            3
          ],
          [
            -1,
            2
          ],
          [
            3,
            -2
          ]
        ],
        [
          [
            -1,
            2
          ],
          [
            3,
            -2
          ],
          [
            4,
            -3
          ]
        ],
        [
          [
            2,
            0
          ],
          [
            3,
            0
          ],
          [
            4,
            0
          ]
        ],
        [
          [
            3,
            -2
          ],
          [
            4,
            -3
          ],
          [
            5,
            -4
          ]
        ]
      ],
      "canonical_signature": "89187fdcaafa3ae2a058236b301af35da2ed41fe",
      "pair_shape": "(-2, 0)",
      "family": "rail_ladder",
      "terminal": false,
      "source_type": "selfplay"
    },
    {
      "template_id": "T_0002",
      "type": "proto",
      "tau": 4,
      "pressure": 2,
      "attacker": [
        [
          -1,
          0
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
      "defender": [],
      "move": [
        [
          -1,
          2
        ],
        [
          0,
          1
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ],
          [
            -3,
            0
          ],
          [
            -2,
            0
          ]
        ],
        [
          [
            -4,
            5
          ],
          [
            -3,
            4
          ],
          [
            -2,
            3
          ]
        ],
        [
          [
            -3,
            0
          ],
          [
            -2,
            0
          ],
          [
            2,
            0
          ]
        ],
        [
          [
            -3,
            4
          ],
          [
            -2,
            3
          ],
          [
            2,
            -1
          ]
        ],
        [
          [
            -2,
            0
          ],
          [
            2,
            0
          ],
          [
            3,
            0
          ]
        ],
        [
          [
            -2,
            3
          ],
          [
            2,
            -1
          ],
          [
            3,
            -2
          ]
        ],
        [
          [
            2,
            -1
          ],
          [
            3,
            -2
          ],
          [
            4,
            -3
          ]
        ],
        [
          [
            2,
            0
          ],
          [
            3,
            0
          ],
          [
            4,
            0
          ]
        ]
      ],
      "canonical_signature": "a0c7cde98332ebffa3ad47f947205a4badf9588b",
      "pair_shape": "(-1, 0)",
      "family": "adjacent",
      "terminal": false,
      "source_type": "selfplay"
    },
    {
      "template_id": "T_0003",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          -1,
          0
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
      "defender": [],
      "move": [
        [
          0,
          1
        ],
        [
          3,
          -2
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ],
          [
            -3,
            0
          ],
          [
            -2,
            0
          ]
        ],
        [
          [
            -3,
            0
          ],
          [
            -2,
            0
          ],
          [
            2,
            0
          ]
        ],
        [
          [
            -2,
            0
          ],
          [
            2,
            0
          ],
          [
            3,
            0
          ]
        ],
        [
          [
            -2,
            3
          ],
          [
            -1,
            2
          ],
          [
            2,
            -1
          ]
        ],
        [
          [
            -1,
            2
          ],
          [
            2,
            -1
          ],
          [
            4,
            -3
          ]
        ],
        [
          [
            2,
            -1
          ],
          [
            4,
            -3
          ],
          [
            5,
            -4
          ]
        ],
        [
          [
            2,
            0
          ],
          [
            3,
            0
          ],
          [
            4,
            0
          ]
        ]
      ],
      "canonical_signature": "aa3f69646c2e2684aa65397b6b7f8d00bc8da5a7",
      "pair_shape": "(-3, 0)",
      "family": "rail_ladder",
      "terminal": false,
      "source_type": "selfplay"
    },
    {
      "template_id": "T_0004",
      "type": "proto",
      "tau": 3,
      "pressure": 1,
      "attacker": [
        [
          0,
          1
        ],
        [
          1,
          -1
        ],
        [
          1,
          0
        ]
      ],
      "defender": [],
      "move": [
        [
          1,
          -2
        ],
        [
          3,
          -2
        ]
      ],
      "obligations": [
        [
          [
            -2,
            3
          ],
          [
            -1,
            2
          ],
          [
            2,
            -1
          ]
        ],
        [
          [
            -1,
            2
          ],
          [
            2,
            -1
          ],
          [
            4,
            -3
          ]
        ],
        [
          [
            1,
            -5
          ],
          [
            1,
            -4
          ],
          [
            1,
            -3
          ]
        ],
        [
          [
            1,
            -4
          ],
          [
            1,
            -3
          ],
          [
            1,
            1
          ]
        ],
        [
          [
            1,
            -3
          ],
          [
            1,
            1
          ],
          [
            1,
            2
          ]
        ],
        [
          [
            1,
            1
          ],
          [
            1,
            2
          ],
          [
            1,
            3
          ]
        ],
        [
          [
            2,
            -1
          ],
          [
            4,
            -3
          ],
          [
            5,
            -4
          ]
        ]
      ],
      "canonical_signature": "c0ad3e34355200c6c2b0b7766d18c55a87f3a563",
      "pair_shape": "(-2, 0)",
      "family": "rail_ladder",
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
          -1,
          0
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
      "defender": [],
      "move": [
        [
          1,
          -1
        ],
        [
          2,
          -2
        ]
      ],
      "obligations": [
        [
          [
            -4,
            0
          ],
          [
            -3,
            0
          ],
          [
            -2,
            0
          ]
        ],
        [
          [
            -3,
            0
          ],
          [
            -2,
            0
          ],
          [
            2,
            0
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
            -1,
            1
          ]
        ],
        [
          [
            -2,
            0
          ],
          [
            2,
            0
          ],
          [
            3,
            0
          ]
        ],
        [
          [
            -2,
            2
          ],
          [
            -1,
            1
          ],
          [
            3,
            -3
          ]
        ],
        [
          [
            -1,
            1
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
            0
          ],
          [
            3,
            0
          ],
          [
            4,
            0
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
          ],
          [
            5,
            -5
          ]
        ]
      ],
      "canonical_signature": "d95eb706b290b4fef8999b8140184e83517151fb",
      "pair_shape": "(-1, 0)",
      "family": "adjacent",
      "terminal": false,
      "source_type": "selfplay"
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
