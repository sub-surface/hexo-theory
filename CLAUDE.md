# CLAUDE.md — onboarding for Claude agents working on hexo-theory

You are joining a solo research project by Leon. This file is your orientation. Read it once, act on it always.

## What this project is

**hexo-theory** is the theoretical sibling of the `hexo` game engine (sits at `../hexo` relative to this directory on disk — the sibling repo was renamed from `hexgo` to `hexo` on disk; see note under "Import path" below). The engine plays Connect-6 on the infinite hex lattice ($\mathbb{Z}[\omega]$, win = 6 stones in a row along any of 3 axes). The theoretical goal is to **characterise the structure of optimal play** — its symmetries, tiling properties, descriptive-set-theoretic complexity, and whether perfect play exhibits quasi-crystalline order.

**Priority layer:** [DIRECTION.md](DIRECTION.md) is the current single source of truth for *what to work on next* — read it before ROADMAP.md. [SPEC.md](SPEC.md) is the current source of truth for *what has been established*, with honest confidence levels. ROADMAP.md below is the long-range plan that both are built on; it is not deprecated, but DIRECTION.md's priority queue supersedes its ordering.

The **final output** is a publishable paper / long-form blog post combining:
- epiplexity (time-bounded MDL, per Finzi et al. 2026) as the measurement framework
- combinatorial-game-theoretic results (strategy-stealing, pairing strategies, Hales-Jewett-style bounds)
- topological / descriptive-set-theoretic positioning (where does HeXO sit in the Borel hierarchy)
- empirical validation via self-play corpora + diffraction analysis

Everything in this repo should be either feeding that write-up or falsifying part of its thesis.

## Read this first — in order

1. **[README.md](README.md)** — the external framing and central "Pisot quasicrystal" conjecture
2. **[docs/ROADMAP.md](docs/ROADMAP.md)** — canonical 12-month plan, organised around the Finzi epiplexity paradoxes
3. **[docs/theory/](docs/theory/)** — living synthesis of individual theoretical threads (Hamkins paper synthesis, complexity positioning, etc.). Append here when you develop an idea; don't scatter theory across random files.
4. **[papers/](papers/)** — PDFs we build on. Currently: Finzi et al. (epiplexity, 2026), Hamkins–Leonessi (Infinite Hex is a draw, 2022).

## Agent expectations

### Research-mode defaults
- Ideation MUST cite real repo symbols with file:line refs — e.g. `live_lines` at [engine/analysis.py:47](engine/analysis.py:47). Vague handwaving is rejected.
- Every theoretical claim needs a **falsifiable prediction** you can tie to an experiment in `experiments/`.
- Unify narratives rather than stacking them. If your proposed direction doesn't land on the `(|P|, H_T)` MDL plane of the ROADMAP, explain why it's still worth the detour.
- Cite **Hamkins-style descriptive set theory** (Σ⁰ₙ, Π⁰ₙ, analytic, projective) where it clarifies; don't invoke it for flavour.
- Write at post-graduate level. Leon reads these synthesis notes carefully; they should be tight.

### What to build and not build
- `engine/` — game mechanics, agents, analysis helpers. Keep small and focused. Upstream game code lives in `../hexo/`; we re-export via [engine/__init__.py](engine/__init__.py).
- `experiments/run_*.py` — one file per self-contained experiment. Must produce `results/<name>.json` and `figures/fig_<name>_*.png`. Existing examples: [run_epiplexity_scan.py](experiments/run_epiplexity_scan.py), [run_hamkins_echo.py](experiments/run_hamkins_echo.py).
- Don't create a new module just to hold one function. Prefer existing files.
- Don't add backward-compat shims, feature flags, or speculative abstractions.
- Don't write comments that restate what the code does. Comments only for *why* non-obvious decisions are the way they are.

### Experiments convention
- One entry point per experiment: `experiments/run_<topic>.py`.
- `--quick` flag for dev iteration (~1 min), full sweep as default.
- Output JSON to `results/`, PNG to `figures/` — both are tracked in git (reproducibility > repo size for this project).
- Seed everything. Reproducibility is a prerequisite for every claim.
- **Use GPU / parallelism where it helps.** Leon has a 5GB RTX 2060. For any compute that scales with corpus size — self-play batching, diffraction FFTs, tensor ops, MCTS rollouts — default to torch+CUDA. For embarrassingly parallel game-playing, use `multiprocessing.Pool` or `joblib`. Fall back to sequential CPU only when CUDA is unavailable or the problem is trivially small. Budget VRAM carefully (5GB is tight — prefer float32, small batches). Report wall time so speedups are visible.

### Import path
Resolved once, centrally, in [engine/__init__.py](engine/__init__.py)'s `_resolve_hexo_root()` — checks the `HEXO_ROOT` env var first, then the sibling directory relative to this file, then a hardcoded dev-machine fallback (for the worktree case, where the relative computation resolves wrong). **Do not duplicate the old per-file "worktree shim"** (`_REAL_HEXGO = Path(r"C:\...\hexo")` + sys.path.insert) — every `experiments/run_*.py` used to carry its own copy of that shim, which is exactly what let the `hexgo`→`hexo` directory rename silently break ~24 files at once (fixed 2026-07-05). If you're on a machine or container where neither the env var nor the relative path apply, set `HEXO_ROOT` rather than re-adding a hardcoded path. `experiments/run_crystal_survey.py` is the one intentional exception — it still needs its own `_REAL_HEXGO` for the Rust-module sys.path swap in `_try_rust_parallel_self_play`.

## Current research state (keep this updated)

**Last updated: 2026-07-05.** For the full picture read [SPEC.md](SPEC.md) (established results, honest confidence) and [DIRECTION.md](DIRECTION.md) (what's active now and why). This section is a pointer, not a duplicate — don't let it drift out of sync with those two again like it did between 2026-04-17 and 2026-07-05.

### The one-paragraph state of play
Two research lines run in parallel: **Line A** (quasicrystal/Pisot/epiplexity — the global-pattern story) and **Line B** (transversal-atom/τ forcing — the local-mechanism story, now the active focus per DIRECTION.md). The headline claim that would make Line A publishable — is $S_T(N)$ sub-linear in corpus size (P3)? — has **not actually been measured yet** despite being named "the headline result" in April; the observer-net infrastructure for it exists (`engine/epiplexity.py`) but has never been pointed at a real corpus-size sweep. Several established-sounding claims (P1 first-mover advantage, the Bellman-Turing predicted wavelength) have real numbers behind them but weaker statistical support than earlier docs implied — see SPEC.md's corrected framing. The AlphaZero/NCA-zoo learned-agent thread is a **documented series of negative results** (draw-collapse, value-head underfitting, distillation erasing the Black edge) — see [docs/theory/2026-04-18-unified-agent-design.md](docs/theory/2026-04-18-unified-agent-design.md) §10-13. Don't resume pouring compute into it without first fixing the diagnosed causes (class imbalance on `v=0` targets, sparse threat labels).

### Active now (per DIRECTION.md)
0. Search-regime pivot executed 2026-07-06 — see [docs/theory/2026-07-06-search-regime-verdicts.md](docs/theory/2026-07-06-search-regime-verdicts.md) for candidate verdicts (2 new theorems, `fast_tactical` evaluator, [modal_bakeoff.py](modal_bakeoff.py) staged). Bake-off Phase 1 on Modal is the pending next step.
1. τ-fork heuristic in [competition/arena.py](competition/arena.py) — real but currently only proven to *not lose* (draws vs plain ES potential after the squared-term fix), not yet proven to *win*. The arena now supports seeded random openings (the fix for the deterministic-draw wall), so the asymmetric test runs inside the bake-off.
2. Programme D proxy — a cheap gzip-based MDL measurement across corpus sizes $N \in \{10^2, ..., 10^5\}$, to get a first log-vs-linear read on $S_T(N)$ without building the full observer-net pipeline. See DIRECTION.md's experiment queue.
3. Statistics tightening on P1 (first-mover advantage) and the Bellman-Turing wavelength prediction — both currently rest on thin samples (see SPEC.md).

### Known-resolved
- `ROADMAPv2.md` → `docs/ROADMAP.md`. The old v1 file is gone. If a comment or note still says "ROADMAPv2", that's a text reference, not a dead link — leave it or fix opportunistically.
- Diffraction spectrum — **done** (commit 1d876d3 on master).
- MirrorAgent — **done** (commit e143bcc on master).
- **Sibling-repo rename breakage** — `hexgo` → `hexo` directory rename left ~24 files pointing at a nonexistent path, silently breaking every experiment script. Fixed 2026-07-05.

## Invariants — do not violate

- `WIN_LENGTH` is asserted `== 6` deep inside the upstream engine ([../hexo/game.py:147](../hexo/game.py:147)). Sweeping it requires patching the assertion; don't do this without flagging it explicitly.
- The hex turn rule is **1-2-2** (P1 places 1 stone on opening; thereafter each turn = 2 placements). Agents written assuming standard 1-1 alternation will mis-play.
- Agents only need `name: str` and `choose_move(game) -> (q, r)`. Don't subclass or require a protocol — keep it flat.

## On tooling
- Always prefer editing existing files over creating new ones.
- Don't invoke skills that don't apply. `brainstorming` is for creative/UI design work; most theory questions here are answered by reading, writing, and running experiments, not by running the brainstorming flow.
- For short theoretical replies Leon prefers: (a) cite real repo symbols, (b) unify narratives, (c) end with falsifiable predictions or next experiments. See his saved preferences in `~/.claude/projects/.../memory/`.
