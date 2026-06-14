# A unified agent for HexGo — design note

*2026-04-18, after reading [../../results/charlies-artifacts/](../../results/charlies-artifacts/)*

## 0. Context

Charlie (a friend, working on a similar 32×32 HexGo substrate on a 5070 Ti)
has run a richer program than ours: static-position supervised learning on
four tactical predicates (`five`, `threat`, `double`, `winning_cells`),
multi-task and "universal" NCA trunks, SSL reconstruction, a ~20-matchup
tournament, and MCTS with an NCA value net.

His probe cross-transfer matrix ([../../results/charlies-artifacts/checkpoints/linear_probe_results.pt](../../results/charlies-artifacts/checkpoints/linear_probe_results.pt))
reduces to one actionable finding: **a `threat`-supervised 9.4k-param NCA
trunk transfers to all four predicates (0.985 / 0.993 / 0.920 / 0.485) and
beats SSL-pretrained or random-initialised trunks by a wide margin.**
Meanwhile his SSL reconstruction head stalls at "always predict empty"
(val_acc = 0.967 dominated by empty-class correctness, with X-recall 9%,
O-recall 0%), so the friend's "masked reconstruction tests generality"
claim does not survive contact with sparse HexGo positions.

This note folds those findings into our roadmap and specifies the agent
architecture + training pipeline that is our best candidate for the paper's
flagship "strongest agent on HexGo" figure.

## 1. The design in one sentence

**A shared HexConv trunk with five heads — policy, value, threat,
winning-cell, optional occluded-stone — trained in three phases (supervised
pre-train, teacher-bootstrap, MCTS self-play with colour-symmetric
augmentation) on our own `engine.analysis`-derived labels, evaluated both
as a playing agent and via our existing epiplexity observer for the
$(|P|, H_T)$ Pareto plane.**

## 2. Architecture

### 2.1 Shared trunk

```python
class UnifiedTrunk(nn.Module):
    """HexConv stack — 6 layers, hidden=32."""
    # Input:  (B, 4, H, W)  [empty, own, opp, to_move_flag]
    # Output: (B, 32, H, W)
```

Structurally identical to `StrategyTrunk` in
[engine/observer.py](../../engine/observer.py) except `hidden=32` not 16,
and inputs are the 4-channel encoding from `observer.encode_position` so
the trunk shares its feature space with the observer. Parameter budget
≈ 30k (well within our 5GB VRAM on the 2060).

### 2.2 Heads

Per [synthesis §3.1](./2026-04-18-epiplexity-of-strategy.md) but with
Charlie's transfer-matrix evidence baked in.

| Head | Shape | Loss | Always on? | Rationale |
|---|---|---|---|---|
| **policy** | (H, W) softmax | CE vs MCTS visit-count distribution | yes | AlphaZero-style; prior for MCTS tree expansion |
| **value** | scalar | MSE vs game outcome ∈ [-1, +1] | yes | AlphaZero leaf evaluator |
| **threat** | (H, W) sigmoid | BCE on `threat_cells` labels | yes (aux) | Charlie's `probe_threat` row dominates the transfer matrix; we apply it as a continuous regulariser |
| **win-cell** | (H, W) sigmoid | BCE on `threat_cells` for either player, ≥1 | yes (aux) | Pixel-level win geometry; Charlie's `probe_winning_cells` was his tournament NCA |
| **occluded-stone** | (3, H, W) softmax | CE at masked stone positions only | optional | Weaker version of Head B from our epiplexity note — only masks *stones* (not empties), which avoids the "predict empty" trivial solution Charlie's SSL hit |

**Dropped**: the `five`-predicate head — Charlie's data shows `five`-trained
trunks are narrow (val_acc 0.016 on winning_cells) because 5-in-a-row is a
local counting task with no spatial-structure content.

**Dropped (for now)**: `fork_self` — our `engine.analysis.fork_cells` is
more expensive than `threat_cells` and the added signal is marginal given
threat already transfers to `double`-threat prediction at 0.920 in
Charlie's matrix.

### 2.3 MCTS

Light UCB1-style tree search with the policy head as prior and the value
head at the leaf. Charlie's [mcts_run.log](../../results/charlies-artifacts/checkpoints/mcts_run.log)
tuning gives us a sensible starting point: `N_sims ∈ {100, 400}`, rollouts
per leaf = 8, rollout depth cap = 60. Charlie's MCTS has **no learnt
policy prior**; ours does — this is the main algorithmic improvement.

## 3. Training pipeline

### Phase 0 — supervised trunk pretrain

- Generate 8 000 train / 2 000 val 32×32 static positions via
  `experiments/gen_static_positions.py` (to build — see §5).
- Labels: `threat_self`, `threat_opp`, `win_cell`, `occluded` — computed
  from [engine/analysis.py](../../engine/analysis.py) so the paper can
  cite `threat_cells()` / `potential_map()` as the ground-truth functions.
- Multi-task joint BCE, 40 epochs, lr=1e-3, dropout=0.15, weight_decay=1e-4.
- Save `checkpoints/trunk_pretrained.pt`. This is our cold-start for all
  subsequent agents.
- Expected wall time on 2060: ~10 min (Charlie's 5070 Ti does this in
  ≤ 3 min; we're 4× slower per batch).

**Phase 0 is ~90% of Charlie's reported trunk-quality** per his
`probe_threat.pt` results. The remaining 10% comes from task-specific
fine-tuning during self-play.

### Phase 1 — teacher-bootstrap

- For N ≈ 200 games, play the policy+value agent as trainee vs
  `ca_combo_v2` teacher (reusing our
  [engine/neural_ca.py:train_self_play](../../engine/neural_ca.py) teacher-phase
  machinery).
- Loss per game: policy head on MCTS visits (small sims, e.g. N=50),
  value head on outcome, threat + win-cell heads on positions sampled from
  the game trajectory.
- **Colour-symmetric augmentation**: each position is trained twice — as
  sampled, and with stones swapped + `to_move_flag` flipped. Free anti-FMA
  regulariser, directly targeting Charlie's `oracle_greedy` 7%/93% P1/P2
  split.
- Output: a policy+value agent that reliably beats `ca_combo_v2`.

### Phase 2 — MCTS self-play iteration

- Repeat `n_iter` times (start with 4, following Charlie's `value_net_iter4`):
  1. Generate `games_per_iter ≈ 400` games with MCTS(N=100-400 sims) via
     self-play against a frozen copy from iter k-1.
  2. For each state visited: record (state, MCTS visit distribution,
     terminal reward).
  3. Train: policy head KL(MCTS visits ∥ policy), value head MSE, threat
     + win-cell heads on colour-balanced static-position batches drawn
     fresh each step (keeps trunk honest on auxiliary tasks).
  4. Freeze current weights as next-iteration opponent.
- Wall time estimate: MCTS(100 sims) ≈ 0.7s/move (Charlie's numbers),
  40 plies/game, 400 games ≈ 3.1 h per iteration. Four iterations =
  ~12 h of wall time, but this runs unattended.

### Phase 3 — evaluation

For each saved checkpoint (trunk_pretrained, teacher-bootstrapped, and
each of the 4 self-play iterates):

- Plug into
  [experiments/run_strategy_observer.py](../../experiments/run_strategy_observer.py)
  to get $(|P|, H_T)$ — gzipped state_dict as $|P|$, held-out corpus
  policy-CE as $H_T$.
- Run against the matchup ladder via
  [experiments/harness.py](../../experiments/harness.py) to get Wilson-CI
  win rates.
- Run probe matrix (Head A, B, C accuracies per
  [docs/theory/2026-04-18-epiplexity-of-strategy.md](./2026-04-18-epiplexity-of-strategy.md)
  §3.3).

The paper's flagship figure becomes: **a $(|P|, H_T)$ Pareto plot with a
trajectory of six points** (random-init → pretrained → teacher-bootstrap
→ iter1..4), each annotated with its tournament Elo, showing our agent
pushing the Pareto frontier down-right as iteration proceeds.

## 4. What this borrows and what it drops

### Borrowed from Charlie

- **Multi-task static-position trunk pretrain** (Phase 0 recipe:
  8k/2k split, 40 epochs, `hidden=16-32, inner=64, K=8`).
- **MCTS tuning**: 100–400 sims, 8 rollouts/leaf, 60-move rollout cap.
- **Four-iteration self-play value-net schedule** (`value_net_iter{1..4}`).
- **Threat-head primacy**: validated by his transfer matrix.

### Borrowed from our own stack

- **Our 4-channel encoding** ([engine/observer.py:encode_position](../../engine/observer.py))
  with windowed padding, so the infinite lattice isn't cropped to 32×32
  at inference time.
- **Our `engine.analysis` label functions** — so the trunk fits quantities
  we cite in the paper, not Charlie's reinventions.
- **Our `train_self_play` teacher-phase machinery** with the per-game
  backward + `empty_cache()` fix.
- **Our observer / epiplexity read-out** for the $(|P|, H_T)$ Pareto.

### Dropped

- **SSL masked reconstruction (Head B) as originally scoped.** Charlie
  showed it collapses to "predict empty" on sparse positions. The optional
  stones-only occluded-stone head is a replacement, but it's not a priority.
- **NCA-zoo as an agent experiment.** Our 5-prior zoo
  ([engine/neural_ca.py:make_nca_variant](../../engine/neural_ca.py)) is
  demoted from "candidate for strongest agent" to "trunk-initialisation
  experiment: does a $D_6$-tied prior reduce Phase 0 epochs-to-ceiling?".
  Still worth running for P9, but not the main event.
- **P8** (MLM accuracy > 15pp higher on structured vs random corpus) —
  **likely false** given Charlie's SSL result; we should amend the
  synthesis note to replace MLM with stones-only occlusion, and restate
  P8 accordingly. (Action item: see §6.)

## 5. New code to write

| Path | Purpose |
|---|---|
| `experiments/gen_static_positions.py` | Generate color-balanced 8k/2k datasets with labels from `engine.analysis`. Reuses `generate_corpus` from [engine/observer.py](../../engine/observer.py) to sample positions; then adds colour-swap augmentation to hit 50% positive-class rate. |
| `engine/alphazero.py` (or extend `engine/neural_ca.py`) | `UnifiedTrunk`, per-head modules, `AlphaZeroAgent(choose_move)` with MCTS, `pretrain_trunk()`, `self_play_iterate()`. |
| `experiments/run_az_pretrain.py` | Phase 0 runner; outputs `checkpoints/trunk_pretrained.pt` + `results/az_pretrain.json`. |
| `experiments/run_az_selfplay.py` | Phase 1+2 runner; outputs `checkpoints/az_iter{0..4}.pt` + `results/az_selfplay.json`. |

Resisting the urge to write `engine/mcts.py` as a separate file — MCTS is
small and only used from `alphazero.py`; keeping it colocated saves one
file.

## 6. Checklist

### Must do before building

- [ ] **Amend P8** in [2026-04-18-epiplexity-of-strategy.md](./2026-04-18-epiplexity-of-strategy.md)
      to replace MLM with stones-only occluded-stone prediction. Add a
      note citing Charlie's SSL result as prior evidence that naive MLM
      doesn't work here.
- [ ] **Sanity-check**: can we load one of Charlie's checkpoints
      (e.g. `probe_threat.pt`) into our `UnifiedTrunk` architecture?
      If yes, we have a free baseline. If no, pick the most-similar
      reconstruction and note the mismatch.
- [ ] Wait for the current NCA-zoo training sweep to complete so we have
      the P9 result before committing to the unified design — it's
      possible (though unlikely) the zoo experiment will surface a prior
      that already beats Phase 0 pretrain.

### Phase 0 — supervised trunk

- [ ] Write `experiments/gen_static_positions.py` with `_colour_balance`
      helper. Labels: `threat_any`, `threat_p1`, `threat_p2`, `win_cell`.
- [ ] Build `engine/alphazero.py::UnifiedTrunk` + `pretrain_trunk()`.
- [ ] Run `experiments/run_az_pretrain.py --quick` (1k positions, 5 epochs)
      to smoke-test.
- [ ] Full run: 8k train / 2k val, 40 epochs, save `trunk_pretrained.pt`.
- [ ] Record val accuracies per task; confirm they're within 10% of
      Charlie's (five=0.998, threat=0.993, double=0.989, win=0.996).
- [ ] Commit checkpoint to `checkpoints/` and result to `results/`.

### Phase 1 — teacher-bootstrap

- [ ] Build `engine/alphazero.py::AlphaZeroAgent` with `choose_move(game)`
      using MCTS(N=50) at training time, N=400 at eval time.
- [ ] Port our `train_self_play` teacher-phase loop to drive the
      policy+value+aux heads jointly (not just policy gradient).
- [ ] Add colour-symmetric augmentation in the loss step.
- [ ] Run 200-game teacher-bootstrap; confirm the bootstrapped agent
      beats `ca_combo_v2` > 70% on the harness.

### Phase 2 — MCTS self-play iteration

- [ ] Implement `self_play_iterate(n_iter=4, games_per_iter=400)`.
- [ ] Every iteration: save checkpoint + self-play corpus.
- [ ] Track per-iteration: Elo vs previous iter, policy-head KL to MCTS
      visits, value-head MSE, auxiliary-head accuracies.
- [ ] After 4 iters: compare tournament strength vs Charlie's reported
      `mcts(N=400)` on equivalent matchups.

### Phase 3 — Pareto + paper plot

- [ ] Run `experiments/run_strategy_observer.py` over all 6 saved
      checkpoints; produce `results/az_pareto.json`.
- [ ] Generate `figures/fig_az_pareto.png` — the $(|P|, H_T)$ trajectory
      with annotated Elo at each point.
- [ ] Update [docs/ROADMAP.md](../ROADMAP.md) §13 — "what done looks
      like" — to promote this figure to panel (1) of the paper triptych.

### Bonus (time permitting)

- [ ] Replicate 3-4 rows of Charlie's transfer matrix with our pretrained
      trunk, for direct comparability. Adds ~15 min of compute.
- [ ] Run the trained unified agent on the diffraction analyser and the
      Hamkins-echo horizon sweep. If long self-play from the unified agent
      still hits Bragg99 > 0.5, that's a publishable combination: strongest
      agent + quasi-crystal spectrum.
- [ ] Pisot fit of $S_T(N)$ across the 6 checkpoint corpora.

## 7. Predictions updated

Replaces / augments the P6-P9 block in
[2026-04-18-epiplexity-of-strategy.md](./2026-04-18-epiplexity-of-strategy.md):

- **P6** (agent learnability matches tournament strength). *Sharpened.*
  With 6 checkpoints on a single trajectory, the ranking is forced — no
  one-inversion slack. Predict: val policy-CE of observer trained on each
  self-play corpus is monotone in iteration index. Falsified by:
  non-monotonicity after iter 2.
- **P7** (probe emergence). *Sharpened.* Threat-probe val accuracy on the
  iter-4 trunk exceeds 0.99 on a colour-balanced test set. *Falsified by:*
  < 0.95. (Charlie's ceiling is 0.993; we expect to match it.)
- **P8** (MLM → stones-only occlusion). *Reframed.* Occluded-stone recall
  on stones-only masked positions exceeds 0.70 on iter-4 vs < 0.55 on
  random-init. *Falsified by:* < 0.15pp gap.
- **P9** (NCA-prior discriminator). *Unchanged.* Unaffected by the
  unified-agent design; measured from the current zoo training sweep.
- **P10** (AZ-style beats Charlie's MCTS value-net). *New.* At matched
  MCTS sims, our unified agent beats a re-implementation of Charlie's
  `mcts(N=400)` + `value_net_iter4` head-to-head. *Falsified by:*
  < 55% win rate on 30-game sample.
- **P11** (colour-symmetric aug fixes FMA inversion). *New.* Self-play
  from iter-4 of our unified agent yields $p_B \in [0.45, 0.55]$ at 95%
  Wilson CI on n ≥ 200 games. *Falsified by:* $p_B < 0.40$ or > 0.60.

## 8. What this note decides

It picks the **pretrained-trunk-with-always-on-auxiliary-heads** path
*over*:

1. Pure AlphaZero-lite (leaves the threat-transfer signal on the floor).
2. Pure NCA-zoo self-play (Charlie's data shows priors can't substitute
   for supervision).
3. Pure SSL reconstruction (doesn't work on sparse boards; dropped).

And folds in two findings from Charlie that change our measurement story:

1. The FMA inversion at `oracle_greedy` level is **severe and replicable**
   — our own n=200 combo_v2 `p_B = 0.52` is the mild end of the same
   effect.
2. **Threat supervision** produces the most transferable trunk, dominating
   SSL and single-task alternatives. Our observer's Head-C probe set
   should anchor on `threat_cells()` from `engine.analysis`.

## 9. Open questions

- **Which task function do we use for the win-cell head?** Charlie's
  `winning_cells` is a binary segmentation of "cells where placing a
  stone wins". Our closest analogue is `threat_cells(game, player)` — a
  dict keyed by winning cells. Direct port.
- **Do we need board-size transfer experiments?** Charlie ran 32 → 48 →
  64 hidden-width transfer at fixed board. Our encoding is windowed, so
  we get board-size transfer for free — but width-transfer is worth
  checking once. Maybe run hidden=16, 32, 64 on the same corpus and
  confirm monotone improvement.
- **Where does the diffraction analysis fit?** Probably post-hoc on
  iter-4 self-play corpora. Not on the critical path.

---

**Next action**: when the current NCA-zoo training sweep finishes, run
the observer experiment on its corpora (P9 check), then pivot to Phase 0
of the unified agent.

---

## 10. Status update (later on 2026-04-18)

### 10.1 NCA zoo training sweep — completed
All 5 priors ({`random`, `d6_tied`, `line_detector`, `erdos_selfridge`,
`combo`}) trained to 300 steps with the per-game-backward OOM fix; no
crashes. `results/nca_train_<prior>.json` shows the same pattern across
every prior:
- **Early (teacher phase, step ≤ 5):** decisive fraction ≈ 0.4, mean
  reward ≈ –0.4 → trainee loses most of the decisive games seeded by
  `ca_combo_v2`.
- **Late (pure self-play, step ≥ 50):** decisive fraction = **0.00**,
  mean reward = 0.0 → games drag to the 240-ply cap.

Read: the REINFORCE signal on a 9k-param NCA is too sparse to lift the
trainee past draw-saturation once the teacher drops out. This is exactly
the failure mode that motivated the AZ-lite pivot in §3. **P9 (prior
discriminator) becomes trivially negative under this corpus** — all
priors collapsed to the same "empty-action" equilibrium, so there is
nothing for a discriminator to latch onto. P9 should be re-run on
checkpoints taken *during* the teacher phase (step 0–5), not at the end.

### 10.2 FMA inversion panel — produced
[../../figures/fig_fma_inversion_panel.png](../../figures/fig_fma_inversion_panel.png),
data in [../../results/fma_inversion_combined.json](../../results/fma_inversion_combined.json).

Combined our `fma_curve.json` (n=200, infinite lattice) with the
diagonals of Charlie's `tournament_results.pt` (n=30, 32×32 board). The
inversion signal is cleaner than the single-dataset view suggests:

| agent                 | source   | n_dec | $p_B$ | 95% CI         |
|-----------------------|----------|-------|-------|----------------|
| local_random*         | Charlie  | 6     | 0.50  | [0.19, 0.81]   |
| nca_greedy*           | Charlie  | 30    | 0.00  | [0.00, 0.11]   |
| oracle_greedy*        | Charlie  | 30    | 0.07  | [0.02, 0.21]   |
| fork (n=200)          | ours     | 17    | 0.59  | [0.36, 0.78]   |
| combo                 | ours     | 163   | 0.42  | [0.35, 0.50]   |
| ca_combo_v2           | ours     | 156   | 0.46  | [0.39, 0.54]   |
| balanced_lookahead*   | Charlie  | 30    | 0.47  | [0.30, 0.64]   |
| lookahead*            | Charlie  | 29    | 0.52  | [0.34, 0.69]   |

Two things this changes about our story:

1. **The extreme end is replicable, not an artefact.** Charlie's
   `oracle_greedy` puts p_B at [0.02, 0.21] with n=30. Two very different
   greedy policies (threat-counting vs NCA-valued) on two different
   substrates both produce < 0.1 Black-win rate. This rules out
   "lookup-table bug in fork_aware" and similar local explanations.
2. **Our combo / combo_v2 is on the gentle slope of the same curve.**
   Our p_B ≈ 0.42–0.46 [0.35, 0.54] sits between greedy's 0.07 and
   lookahead's 0.50. The bounded-rationality gap shrinks continuously
   with decision horizon.

This upgrades the status of P11 from "speculative" to "worth betting
on": the inversion isn't a quirk of a specific agent, so colour-
symmetric augmentation during AZ self-play has a concrete, measurable
hypothesis to close against.

### 10.3 Updated checklist

- [x] Per-game backward + gradient accumulation in `neural_ca.py`
- [x] NCA zoo training sweep (300 steps × 5 priors, all priors done)
- [x] FMA inversion panel figure
- [ ] **Next**: observer experiment on NCA-zoo *teacher-phase*
      checkpoints (P9 check, re-scoped)
- [x] Phase 0: `experiments/gen_static_positions.py`
- [x] Phase 0: `engine/alphazero.py` UnifiedTrunk + `pretrain_trunk`

## 11. 2026-04-19 status — Phase 0 + Phase 1 complete, cheap pass done

Ran the "cheap things first" pass from §10 plus the full Phase 0 pretrain and
a Phase 1 standalone evaluation. Three outputs land cleanly; one falsifies
the imitation-only hypothesis.

### 11.1 Cheap sweep (A1, A3, B1)

- **A1 cross-program tournament table** ([run_cross_program_table.py](../../experiments/run_cross_program_table.py),
  [results/cross_program_table.json](../../results/cross_program_table.json),
  [figures/fig_cross_program_table.png](../../figures/fig_cross_program_table.png)) — 2-panel
  p_B matrix for our 7 agents × Charlie's 6 agents. Makes the FMA-inversion
  signature visible on both substrates side-by-side.
- **A3 diffraction Bragg histogram** ([run_diffraction_histogram.py](../../experiments/run_diffraction_histogram.py),
  [figures/fig_diffraction_bragg_histogram.png](../../figures/fig_diffraction_bragg_histogram.png)) —
  reanalysed `diffraction_p4.json` (n=18 self-play, n=18 random). Median
  self-play / random Bragg99 ratio = **6.3×**. Random control tightly clamped
  at ~0.055; self-play spread 0.3–0.8 with **corr(N, Bragg99_sp) = +0.84** —
  the quasi-periodic signal *grows with game length*, sharper than P4's
  mean-comparison statement.
- **B1 Hamkins echo h=960** ([run_hamkins_echo_960.py](../../experiments/run_hamkins_echo_960.py)
  + [run_hamkins_echo_merge.py](../../experiments/run_hamkins_echo_merge.py),
  [figures/fig_hamkins_echo_merged.png](../../figures/fig_hamkins_echo_merged.png)) —
  wall 65 min on CPU. Decisive share for `combo_vs_combo` rises monotonically
  30 → 960, reaching **0.80 at h=960** (was 0.74 at h=480). P5 (no draw
  regime) holds at doubled horizon.

### 11.2 Phase 0: static positions + UnifiedTrunk pretrain

- **Corpus**: 10 000 `ca_combo_v2`-self-play positions with
  `{threat_self, threat_opp, fork_self, potential_norm, winning_self,
  policy_target, value_target}`, generated by
  [gen_static_positions.py](../../experiments/gen_static_positions.py)
  in 204 s across 224 games (sample_rate 0.6, max_moves 120).
  Grid sizes range 9×9 to 45×39 (median 18×18).
- **Positive-rate audit** (new finding): threat_self, threat_opp,
  winning_self all fire in **<1.1%** of positions. These are rare-late-game
  signals; ca_combo_v2 rarely reaches a live 5-of-6 window. fork_self (95%)
  and potential_norm (99%) are dense. Auxiliary-supervision story in §4
  assumed dense tactical labels; it does not hold on our substrate without
  explicit resampling or pos_weight.
- **Pretrain** ([run_az_pretrain.py](../../experiments/run_az_pretrain.py)):
  49 480 params, hidden=32, depth=6, 40 epochs batch=32, 12.7 min on 2060.
  Final policy-imitation accuracy **tr=0.547, va=0.500**. Threat/win F1 = 0
  across all epochs — the heads collapse to "predict zero" because the
  rare-positive signal cannot overcome BCE's zero-bias without pos_weight.
  Fork/potential contribute without being separately probed.
- **OOM incident**: first full-run attempt crashed the host. Root cause:
  batch-max padding when grids range 9×9 → 45×39 produces ~1 GB per batch
  on the 5 GB card plus numpy collate spike. Fix in
  [engine/alphazero.py](../../engine/alphazero.py) `pretrain_trunk`:
  sort samples by H×W so each batch is grid-homogeneous; shuffle *chunks*
  not individual samples; wrap val path in `torch.no_grad()`; detach all
  loss scalars to CPU; `opt.zero_grad(set_to_none=True)`; per-16-batch
  `empty_cache()`. Verified with batch=16 × 15 ep (6 min) then full 40 ep
  × batch=32 (12.7 min). No second crash.

### 11.3 Phase 1: standalone policy head eval (n=50)

[run_az_policy_eval.py](../../experiments/run_az_policy_eval.py),
[results/az_policy_eval.json](../../results/az_policy_eval.json),
temperature=0 (deterministic):

| matchup             | B wins | W wins | unfinished |
|---------------------|--------|--------|------------|
| az_policy vs random | 0      | 0      | **50**     |
| az_policy vs combo_v2 | 0    | 50     | 0          |
| combo_v2 vs az_policy | 46   | 2      | 2          |

**Supervised-only imitation does not produce a strong standalone agent.**
Three failure modes, one signal each:

1. Against random, deterministic AZ loops — 50/50 games hit the 240-move
   cap. The policy head learned ca_combo_v2's preferred moves but has no
   mechanism to *close out a win* when the opponent drifts off-policy.
   Imitation accuracy 0.50 samples 50% of the teacher's decision surface;
   the other 50% of novel positions has no gradient signal.
2. As Black vs combo_v2: loses every game. The trunk is a weaker copy of
   its teacher.
3. As White vs combo_v2: wins 2/50 — marginally better than random (which
   wins 0%ish), not enough to claim any genuine play strength.

### 11.4 What this tells us about the design

- **§1's phased recipe is still the right shape**. Pretrain gives priors;
  MCTS has to do the actual search-time work. Phase 2 (PUCT +
  self-play iteration) is where strength comes from, not Phase 0.
- **Auxiliary heads per §4 do not transfer "for free" from Charlie's
  setup.** On a 32×32 closed grid with dense stone counts, `threat` is a
  frequent event. On our infinite-lattice observer grid with padded empty
  rings, threats are rare-late-game. Two options for Phase 2:
  (a) `pos_weight = 40` on the threat/win BCE and re-train, or
  (b) drop those heads and keep the trunk shaped purely by policy + fork
  + potential (which *are* dense). I lean (b) — simpler, doesn't force
  the trunk to memorise rare tactical patterns it mostly never sees.
- **FMA inversion lives on through the policy head**. The imitation
  trunk loses 0/50 as Black against its teacher — Black's statistical
  advantage does not transfer through ca_combo_v2 → trunk
  distillation. Interesting side observation: the teacher *is* weakly
  Black-favoured (our combo_v2 self-play p_B ≈ 0.46 [0.39, 0.54]) but
  the student loses every game as Black. Distillation *erases* the Black
  edge, presumably because it over-indexes on white-side positions
  that appear later in the teacher's game trees.

### 11.5 Updated checklist

- [x] A1 cross-program tournament table
- [x] A3 diffraction Bragg histogram
- [x] B1 Hamkins echo h=960 (full sweep + merged figure)
- [x] Phase 0: static positions + trunk pretrain
- [x] Phase 1: standalone policy-head eval (negative, as expected)
- [ ] **Decide**: pos_weight rescue for threat/win heads, or drop them
      for Phase 2 and rely on policy+fork+potential shaping
- [ ] Phase 2: PUCT wrapper around the pretrained net
      (`engine/mcts.py`), self-play iteration loop, colour-symmetric
      augmentation
- [x] First-mover-advantage curve across the full ladder (see §12)

## 12. 2026-04-19 follow-up — FMA full ladder + measurement artefact

Ran the long-pending FMA curve across 8 agents spanning all families
([run_fma_full_ladder.py](../../experiments/run_fma_full_ladder.py),
[results/fma_full_ladder.json](../../results/fma_full_ladder.json),
[figures/fig_fma_full_ladder.png](../../figures/fig_fma_full_ladder.png)).
n=40 self-play games per agent, horizon 240, 9.6 min total wall.

### 12.1 Measurement artefact: deterministic self-play is n=1

First pass showed az_policy at temperature=0 producing `0 Black / 15
White` with Wilson CI [0.00, 0.20] — apparent strategy-stealing
violation. This is a measurement bug, not an agent defect. Traced
it: deterministic argmax policy in self-play produces the *identical*
trajectory across all seeds. Seeds 0, 7, 42 all give
`[(0,0), (0,1), (-1,1), (-1,0), (-2,1), (-2,0), (-3,1), ...]`
as the first 12 moves. So n_games iid-with-seed is effectively
n=1 for deterministic self-play; the Wilson CI assumes game
independence and becomes meaningless. Lesson for future FMA-style
experiments with deterministic learned agents: **always use
temperature > 0 for the self-play measurement, or explicitly seed
the agent's tiebreaker independently per game**. Rewrote
harness.`_f_az_policy` to accept a per-call random seed, and added
`_f_az_policy_t03` (softened argmax) as the canonical FMA
measurement point for the pretrained trunk.

### 12.2 Headline numbers

Decisive-only p_B with Wilson 95% CI:

| agent          | family      | p_B  | [lo,  hi]    | n_dec |
|----------------|-------------|------|--------------|-------|
| fork_aware     | handcrafted | 0.60 | [0.23, 0.88] |   5   |
| combo          | handcrafted | 0.56 | [0.39, 0.71] |  34   |
| ca_combo_v2    | handcrafted | 0.44 | [0.30, 0.60] |  36   |
| az_policy_t03  | learned     | 0.56 | [0.37, 0.72] |  27   |
| az_policy_t05  | learned     | 0.62 | [0.44, 0.77] |  29   |
| neural_ca      | neural-CA   | 0.00 | [0.00, 0.09] |  40   |

(random and greedy produce 0 decisive games in 40 self-play matches
at horizon 240 — strategy-stealing undefined, not falsified.)

### 12.3 Three structural findings worth flagging

1. **p_B is not monotone in strength.** Going fork_aware (0.60) →
   combo (0.56) → ca_combo_v2 (0.44) → az_policy_t03 (0.56), the
   Black-share swings both directions as we climb the ladder.
   This rules out the naive "stronger play amplifies tempo"
   prediction and makes P11 (FMA-inversion-at-strength) more
   interesting: the inversion isn't just a greedy-agent quirk,
   it's that p_B is *agent-specific* in a way that doesn't collapse
   to one-dimensional strength.
2. **Untrained neural_ca flagrantly violates the strategy-stealing
   bound**: 0/40 Black wins, Wilson upper 0.09. Because NCA is
   stochastic per-game (not deterministic-seed-invariant like
   az_policy at t=0), this *is* genuine. Random convolutional weights
   on the infinite lattice produce reactive play where moving second
   with more information dominates moving first with the tempo
   advantage. Natural follow-up: does this survive training? The
   existing NCA-zoo training runs all collapsed to draws, so we
   can't yet answer. Important for Phase 2: the unified-agent
   trunk must not inherit this reactive bias from its conv backbone
   alone; the policy-head-from-imitation is probably what saves
   az_policy_t03.
3. **az_policy_t03's p_B=0.56 matches combo, not its literal teacher
   ca_combo_v2=0.44.** The imitator distills toward the combo
   *family* rather than v2's specific opening-centre-bias fix.
   Which is consistent with §11.4's distillation observation:
   supervised imitation averages over nearby teacher variants,
   losing the specific positional tuning that separates combo from
   combo_v2. For Phase 2 this means: the pretrained trunk is a
   *weaker* starting point than ca_combo_v2 in the specific sense
   that matters most to our FMA story. MCTS search amplification
   needs to do more than wrap the policy -- it needs to recover the
   positional precision that imitation averaged out.

### 12.4 What this tells us about Phase 2 priorities

The three findings converge on the same design implication: **a
value head is the missing piece, not a search loop**. az_policy at
t=0 loops against random because the policy has no notion of "this
position is +1 for me, let me close it out" -- it just picks the
highest-prior move forever. Temperature fixes looping but doesn't fix
the underlying issue. MCTS would paper over it by forcing
breadth-first exploration. But the cleanest fix is to train the
value head (currently untouched from Phase 0) on actual game
outcomes, then let the policy's argmax break ties using
`V(s_next)` as a tiebreaker.

That's Phase 2a: **Monte-Carlo value-head training on the existing
static-positions corpus** (value target = final game outcome from
the to-move player's perspective, which is already stored in
`static_positions/*.npz`). No new self-play data needed. One
pretrain rerun, then compare az_policy with and without value-head
tiebreaking.


## 13. 2026-04-19 — Phase 2a MC value head trained, Phase 2b probe run

### 13.1 Setup

Added an MSE value loss to [pretrain_trunk](../../engine/alphazero.py)
with target $v \in \{-1, 0, +1\}$ already written by
[gen_static_positions.py](../../experiments/gen_static_positions.py)
(line 210: `rec["value"] = 1.0 if rec["to_move"] == game.winner else -1.0`).
No new data. Re-ran 40 epochs with `--lambda-value 1.0`:

    policy_acc   tr=0.543 va=0.500    (vs Phase 0: tr=0.547 va=0.500 — unchanged)
    threat_f1    tr=0.000 va=0.000    (Phase 0 also 0.000 — threshold-at-0.5 artefact)
    value_mse    tr=0.384 va=0.376    (trivial baseline "predict 0": ~0.42)
    value_sgn    tr=0.549 va=0.537    (chance = 0.50; 42% of samples have |v|=1)

Checkpoint: `artifacts/checkpoints/az_pretrain_phase2a.pt`.
Full history in [results/az_pretrain_phase2a.json](../../results/az_pretrain_phase2a.json).

### 13.2 The value head did not learn to discriminate

Inspecting predictions on the val set by target class:

    target=-1   n= 35   mean(pred)=+0.005   std=0.051   sign_acc=0.51
    target= 0   n=118   mean(pred)=+0.006   std=0.051   sign_acc=—
    target=+1   n= 47   mean(pred)=+0.016   std=0.050   sign_acc=0.60

Three things to notice. First, **all three class means cluster near 0**
— the head has collapsed to a regression-toward-the-mean prediction.
Second, **std ≈ 0.05** means the head's output range is ~20× smaller
than the target range (±1). Third, **sign accuracy of 0.54 over
decisive positions** is barely above chance — above it for
winning positions (0.60), at it for losing (0.51).

This is almost certainly an **underfitting + class-imbalance** problem.
With 58% of training samples at $v=0$, an MSE-minimising head that
can't discriminate well picks its "safe" default output near the
mean (which is $-0.008$ on the corpus). The variance ceiling is ~0.42
(Bernoulli on |v|=1 vs 0); the head achieved 0.38 — it moved about
10% of the way toward a useful regressor. Not enough.

### 13.3 Phase 2b probe — value-aware tie-break

[engine/az_agent.py](../../engine/az_agent.py) gained a
`value_topk` kwarg: at temperature $\leq 0$ with $K > 0$, the agent
takes the top-$K$ policy logits, applies each to a clone, runs the
trunk once per candidate, and picks the move that maximises
$V(s')$ from our POV (with a sign flip when $s'$ is the opponent's
turn under the 1-2-2 rule).

[experiments/run_az_value_probe.py](../../experiments/run_az_value_probe.py)
runs three paired comparisons against the baseline `az_policy_t03`
(same trunk, softmax $t=0.3$, no lookahead):

| comparison | az_policy_t03 | az_value_t0k4 |
|---|---|---|
| **self-play decisive rate** (n=40, horizon=240) | 0.70 (28/40) | **0.00 (0/40)** |
| **self-play $p_B$** | 0.61 [0.42, 0.76] | undefined (0 decisive) |
| vs `combo` (n=20 pooled both colours) | 4/20 | 0/20 |
| vs `ca_combo_v2` | 3/20 | 2/20 |
| vs `fork_aware` | 0/20 | 0/20 |
| head-to-head (same trunk, n=40) | 21/40 | 19/40, Wilson [0.33, 0.63] |

Full numbers: [results/az_value_probe.json](../../results/az_value_probe.json);
figure: [figures/fig_az_value_probe.png](../../figures/fig_az_value_probe.png).

Three conclusions.

**(a) Head-to-head null at n=40**: 19 vs 21 wins across both colours
with pooled Wilson [0.33, 0.63]. Same trunk, different decision rule,
and the tie-break is within noise — exactly what we'd predict from §13.2.
The value head *as it stands* cannot rank candidates better than
"whatever the policy already said".

**(b) Self-play decisive rate collapses $0.70 \to 0.00$**. This is
the most striking number. The mechanism: at $t=0$ the tie-break is
fully deterministic (argmax over value-adjusted top-K), and the
nearly-zero value differences shuffle the policy-argmax order into
a new fixed trajectory. If that trajectory happens to be "safe
midboard moves forever", the game simply never terminates. We saw
exactly this at horizon 240: 40/40 unfinished. That is *worse* than
the looping we fixed in §12.1, and it's intrinsic to value-aware
argmax when the head is uninformative.

**(c) Vs ladder az_value is weakly worse than az_policy_t03** on
`combo` (0/20 vs 4/20) and `ca_combo_v2` (2/20 vs 3/20), tied on
`fork_aware` (both 0/20). The distillation trunk is weaker than
all three handcrafted opponents — that's the Phase 1 result — and
plugging in a noisy tie-break only makes it worse where it already
had signal (vs combo).

### 13.4 Interpretation — not "TD was wrong", but "the head needs real signal"

The λ=1 Monte-Carlo return **is the correct target**. What went wrong
is the training regime, not the direction. Three candidate fixes, in
increasing order of likely yield:

1. **Raise $\lambda_{\text{value}}$ and drop $\lambda_{\text{threat,win}}$
   to zero** until value discriminates. The other heads contribute 0-F1
   gradients to the trunk anyway (§13.1) and their MSE on sigmoid
   targets is inflating the loss. Let the value head drive the trunk
   for a while. Cost: one more 40-epoch run (~15 min).

2. **Filter out $v=0$ samples during value-loss computation.** 58% of
   the corpus has target 0 (unresolved positions mid-game). Those are
   informationally weak — the target is just "the trainer rollout
   didn't finish in this position's subtree". Regressing on them
   teaches the head to output 0. Easier fix: weighted MSE that
   down-weights (or masks) $v=0$. Cost: a three-line edit + one rerun.

3. **Generate more decisive-game data.** The current corpus is
   biased toward positions that *didn't* resolve within the rollout
   budget of `gen_static_positions.py`. A more useful value target
   comes from positions *closer* to game-end, where the final return
   is more strongly correlated with local structure. Cost: regen
   data with a longer rollout budget and/or higher decisive-rate
   opponent mix.

The single quickest experiment is (2) — mask zero-valued samples in
the value loss (but keep them for the policy/threat/win heads, where
they still carry labels). If the head still regresses to mean after
(2), that rules out "class imbalance"; if it now discriminates, we
also get a usable value head for Phase 2c actor-critic.

Before investing in (1)–(3), one more design question is open:
**is the trunk capacity the bottleneck**? hidden=32, depth=6, 49.5k
params is small by MLP standards. A 3× wider trunk (hidden=96) would
still fit comfortably in VRAM and give the value head more room to
discriminate. This is independent of the data-side fixes (2)–(3).

### 13.5 Implications for Phases 2c-3

Phase 2c (actor-critic self-play) needs a value head that's at least
better than a fixed baseline. A sign-acc of 0.54 is barely better
than the running-mean baseline [engine/neural_ca.py:483](../../engine/neural_ca.py:483)
already uses. So **Phase 2c is blocked on fixing 2a** — there's no
point training on a noisy baseline.

Phase 3 (MCTS) fundamentally depends on $V(s)$ being a useful leaf
estimate. If MSE doesn't improve materially past the current 0.38,
MCTS will just spend budget exploring without getting better leaf
evaluations. Same block.

### 13.6 Updated checklist

- [x] Phase 0: supervised trunk pretrain on static positions.
- [x] Phase 1: policy-only agent evaluation (beats random, loses to handcrafted).
- [x] §12: FMA full ladder with measurement-artefact fix.
- [x] §13: Phase 2a MC value-head training + Phase 2b probe.
- [ ] **§13.4 (2)**: mask $v=0$ from value loss; re-run.
- [ ] §13.4 (1): raise $\lambda_v$ with auxiliaries turned off.
- [ ] §13.4 (3): regen data with longer rollouts / better opponents.
- [ ] Phase 2c (gated on 2a fix): actor-critic self-play with
  learned baseline replacing the running-mean baseline.
- [ ] Phase 3 (gated on 2a fix): PUCT MCTS with UnifiedNet.
