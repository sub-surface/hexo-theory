# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 2
- candidate cells per ply: 10
- openings: 66
- total nodes: 17533
- transposition hits: 1013
- classes: {'black_bulk_edge': 38, 'screened_or_balanced': 28}

## Most Black-Favorable Openings

- `O0022` score=0.21, class=screened_or_balanced, reply=((1, 0), (-1, 0))
- `O0033` score=0.21, class=screened_or_balanced, reply=((1, 0), (-1, 0))
- `O0064` score=0.21, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0013` score=0.14, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0020` score=0.14, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0021` score=0.14, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0023` score=0.14, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0025` score=0.14, class=screened_or_balanced, reply=((1, 0), (-1, 0))

## Most White-Favorable / Screened Openings

- `O0001` score=-0.35, class=screened_or_balanced, reply=((-1, -1), (-2, 1))
- `O0002` score=-0.35, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0003` score=-0.35, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0018` score=-0.35, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0016` score=-0.28, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0052` score=-0.28, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0057` score=-0.28, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0006` score=-0.14, class=screened_or_balanced, reply=((0, -1), (-1, 1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/r3_corpus/opening_tablebase.json
```
