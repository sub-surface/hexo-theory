# Opening Tablebase Corpus

Cached alpha-beta search over canonical D6 White opening pairs. This starts at radius 3 because it is the first finite A2 ball that contains length-6 winning progressions.

## Run

- radius: 3
- depth: 1
- candidate cells per ply: 5
- effective depth after pruning: 1
- effective candidate cells after pruning: 5
- openings: 1
- naive leaf nodes per opening before candidate pruning: 561
- estimated candidate-tree nodes per opening: 11
- total nodes: 11
- transposition hits: 2
- pruning modes: {'alpha_beta': 1}
- classes: {'screened_or_balanced': 1}
- viewer W/L/U: {'U': 1}

## Most Black-Favorable Openings

- `O0001` score=0.98, class=screened_or_balanced, reply=((0, -1), (-1, -1))

## Most White-Favorable / Screened Openings

- `O0001` score=0.98, class=screened_or_balanced, reply=((0, -1), (-1, -1))

## Files

- `opening_tablebase.csv`: flat corpus.
- `opening_tablebase.json`: structured corpus with principal variations for the viewer.
- `figures/`: score, pressure, and class plots.

View with:

```bash
python examples/game_viewer.py --corpus opening_tablebase_results/viewer_run_smoke/opening_tablebase.json
```
