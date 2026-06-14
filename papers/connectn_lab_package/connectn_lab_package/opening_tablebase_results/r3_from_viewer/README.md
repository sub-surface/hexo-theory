# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 10
- candidate cells per ply: 10
- effective depth after pruning: 9
- effective candidate cells after pruning: 4
- openings: 66
- naive leaf nodes per opening before candidate pruning: 5503839380301244269598641
- estimated candidate-tree nodes per opening: 12093235
- total nodes: 2465031
- transposition hits: 364522
- pruning modes: {'beam': 66}
- classes: {'black_bulk_edge': 32, 'screened_or_balanced': 34}
- viewer W/L/U: {'U': 66}

## Most Black-Favorable Openings

- `O0041` score=13225.60, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0066` score=13225.60, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0045` score=6621.80, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0050` score=6621.80, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0065` score=6621.80, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0046` score=6621.80, class=black_bulk_edge, reply=((1, -1), (-1, 1))
- `O0062` score=6621.80, class=black_bulk_edge, reply=((0, -1), (0, 1))
- `O0021` score=6621.80, class=black_bulk_edge, reply=((1, -1), (-1, 1))

## Most White-Favorable / Screened Openings

- `O0040` score=0.00, class=screened_or_balanced, reply=((0, -1), (-1, 0))
- `O0055` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0060` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0049` score=0.00, class=black_bulk_edge, reply=((1, 0), (-1, 0))
- `O0056` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0014` score=0.00, class=screened_or_balanced, reply=((1, -1), (0, -1))
- `O0019` score=0.00, class=screened_or_balanced, reply=((1, 0), (1, -1))
- `O0064` score=0.00, class=screened_or_balanced, reply=((-1, 1), (0, 1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/r3_from_viewer/opening_tablebase.json
```
