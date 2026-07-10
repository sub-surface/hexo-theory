# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 1
- candidate cells per ply: 8
- openings: 5
- total nodes: 145
- transposition hits: 46
- classes: {'black_bulk_edge': 5}

## Most Black-Favorable Openings

- `O0004` score=2.38, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0005` score=2.38, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0003` score=2.24, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0002` score=2.10, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0001` score=1.89, class=black_bulk_edge, reply=((0, -1), (0, 1))

## Most White-Favorable / Screened Openings

- `O0001` score=1.89, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0002` score=2.10, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0003` score=2.24, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0004` score=2.38, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0005` score=2.38, class=black_bulk_edge, reply=((0, -1), (0, 1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/r3_corpus/opening_tablebase.json
```
