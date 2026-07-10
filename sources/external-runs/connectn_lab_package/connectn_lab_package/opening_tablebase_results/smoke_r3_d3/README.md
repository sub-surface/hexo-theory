# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 3
- candidate cells per ply: 10
- openings: 5
- total nodes: 11514
- transposition hits: 1770
- classes: {'black_bulk_edge': 2, 'screened_or_balanced': 3}

## Most Black-Favorable Openings

- `O0003` score=6621.45, class=screened_or_balanced, reply=((1, -1), (0, -1))
- `O0004` score=6620.82, class=screened_or_balanced, reply=((1, -1), (0, -1))
- `O0005` score=1.26, class=screened_or_balanced, reply=((0, -1), (-1, 0))
- `O0002` score=1.05, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0001` score=0.07, class=black_bulk_edge, reply=((0, -1), (0, 1))

## Most White-Favorable / Screened Openings

- `O0001` score=0.07, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0002` score=1.05, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0005` score=1.26, class=screened_or_balanced, reply=((0, -1), (-1, 0))
- `O0004` score=6620.82, class=screened_or_balanced, reply=((1, -1), (0, -1))
- `O0003` score=6621.45, class=screened_or_balanced, reply=((1, -1), (0, -1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `evidence/figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_evidence/results/r3_corpus/opening_tablebase.json
```
