# Repository Map

This repo is organized by role rather than by artifact age.

- `engine/` is the canonical reusable theory layer: agents, analysis helpers,
  crystal/diffraction observables, CGT utilities, and the bridge to `../hexo`.
- `experiments/` contains reproducible experiment entrypoints. The convention is
  still one `run_*.py` per experiment, with focused helper modules kept local.
- `competition/` contains the standalone browser-bot arena and deliverable bots.
- `apps/desktop/` contains the PySide dashboard and its widgets.
- `apps/marimo/` contains interactive notebooks and legacy marimo scratchpads.
- `cloud/modal/` contains Modal entrypoints and shared image factories.
- `evidence/` contains tracked paper-facing evidence and ignored raw corpora:
  `results/`, `figures/`, `corpora/`, and `games/`.
- `sources/literature/` contains PDFs and source notes.
- `sources/bundles/` contains original external zip bundles.
- `sources/external-runs/` contains extracted external or generated research
  bundles used as provenance for the theory notes.

Prefer importing paths from `paths.py` when adding new scripts. Existing
experiments may still use direct `Path("evidence/...")` literals, but new code
should not recreate root-level `results/`, `figures/`, `corpora/`, `games/`, or
`papers/` directories.
