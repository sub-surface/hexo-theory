# Hex Threat Manifold Microscope — Rust

A fast, zero-dependency Rust implementation of the visual experiment we discussed for infinite Hex Connect-6 / HexGo:

- axial hex coordinates;
- 1-2-2 board model;
- six-in-a-row wins along the three hex axes;
- scalar threat fields;
- pair-move manifold `Sym²(H)`;
- tiny PCA implementation;
- SVG visual outputs and CSV data.

## Build and run

```bash
cargo run --release -- --radius 8 --candidates 160 --seed 7 --position fork --out out
```

Try other positions:

```bash
cargo run --release -- --position race --out out_race
cargo run --release -- --position random --seed 42 --out out_random
cargo run --release -- --radius 10 --candidates 240 --out out_big
```

## Outputs

- `board.svg` — board layer.
- `threat_heatmap.svg` — cell threat scalar field.
- `pair_latent.svg` — 2D latent map of unordered pair moves.
- `cells.csv` — per-cell tactical features.
- `pairs.csv` — per-pair tactical features.
- `summary.md` — conjectural analysis for the run.
- `metadata.json` — run metadata.

## OOM controls

The legal move space is quadratic in the number of empty cells. This project first scores empty cells, retains the top `--candidates`, and then enumerates unordered pairs only inside that tactical attention set. That is both a practical memory guardrail and an experimental model of the “quiet reservoir” idea.

Approximate pair counts:

- `--candidates 160` → 12,720 pairs.
- `--candidates 240` → 28,680 pairs.
- `--candidates 400` → 79,800 pairs.

## Idea

The experiment treats a move in Connect-6 as an element of the symmetric square of the hex grid:

```text
move = {x, y} ∈ Sym²(H)
```

It then asks whether tactical concepts — win, block, fork, quiet pressure — become visible as geometry in a low-dimensional projection of pair features.
