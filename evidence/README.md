# Evidence

Paper-facing outputs and raw generated evidence live here.

- `evidence/results/`: tracked JSON/CSV summaries.
- `evidence/figures/`: tracked PNG/GIF/PDF visual summaries and replays.
- `evidence/corpora/`: raw/generated self-play corpora; ignored by default.
- `games/`: raw game trajectories; ignored by default.

New experiments should write summaries to `evidence/results/` and figures to
`evidence/figures/`. Use `paths.py` where possible.
