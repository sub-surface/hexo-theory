# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 4
- candidate cells per ply: 12
- effective depth after pruning: 4
- effective candidate cells after pruning: 7
- openings: 4
- naive leaf nodes per opening before candidate pruning: 99049307841
- estimated candidate-tree nodes per opening: 204205
- total nodes: 6951
- transposition hits: 700
- pruning modes: {'beam': 4}
- classes: {'black_bulk_edge': 2, 'screened_or_balanced': 2}
- viewer W/L/U: {'U': 4}

## Most Black-Favorable Openings

- `O0004` score=0.00, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0003` score=0.00, class=screened_or_balanced, reply=((1, -1), (0, 1))
- `O0002` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0001` score=0.00, class=black_bulk_edge, reply=((0, -1), (0, 1))

## Most White-Favorable / Screened Openings

- `O0004` score=0.00, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0003` score=0.00, class=screened_or_balanced, reply=((1, -1), (0, 1))
- `O0002` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0001` score=0.00, class=black_bulk_edge, reply=((0, -1), (0, 1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/prune_probe/opening_tablebase.json
```
