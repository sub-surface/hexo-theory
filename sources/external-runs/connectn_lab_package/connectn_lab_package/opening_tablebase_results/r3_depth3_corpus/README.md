# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 3
- candidate cells per ply: 10
- effective depth after pruning: 3
- effective candidate cells after pruning: 10
- openings: 66
- naive leaf nodes per opening before candidate pruning: 176558481
- estimated candidate-tree nodes per opening: 93196
- total nodes: 220149
- transposition hits: 15545
- pruning modes: {'alpha_beta': 66}
- classes: {'black_bulk_edge': 36, 'screened_or_balanced': 30}
- viewer W/L/U: {'U': 66}

## Most Black-Favorable Openings

- `O0040` score=6621.73, class=black_bulk_edge, reply=((1, 0), (1, -1))
- `O0055` score=6621.73, class=black_bulk_edge, reply=((0, -1), (-1, 0))
- `O0060` score=6621.73, class=black_bulk_edge, reply=((0, -1), (-1, 0))
- `O0022` score=6621.73, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0033` score=6621.73, class=screened_or_balanced, reply=((1, 0), (0, 1))
- `O0041` score=6621.66, class=black_bulk_edge, reply=((1, 0), (1, -1))
- `O0045` score=6621.66, class=black_bulk_edge, reply=((1, 0), (1, -1))
- `O0050` score=6621.66, class=black_bulk_edge, reply=((1, 0), (0, 1))

## Most White-Favorable / Screened Openings

- `O0001` score=0.07, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0002` score=1.05, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0007` score=1.12, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0009` score=1.12, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0005` score=1.26, class=screened_or_balanced, reply=((0, -1), (-1, 0))
- `O0010` score=1.47, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0018` score=6620.75, class=screened_or_balanced, reply=((1, 0), (0, 1))
- `O0004` score=6620.82, class=screened_or_balanced, reply=((1, -1), (0, -1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/r3_depth3_corpus/opening_tablebase.json
```
