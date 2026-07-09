# Status & direction — end of 2026-07-09 session

One-stop handoff for tomorrow. Everything below is on disk and reproducible;
**nothing is committed to git yet** (deliberate — commit is Leon's call).

## What exists as of tonight

### The bot (deliverable-ready)

**[competition/hexo_bot2.py](../competition/hexo_bot2.py)** — fresh-start
rebuild, single pure-Python stdlib file, same `choose_move` interface as the
incumbent. Architecture: incremental window-count board with integer
per-cell move deltas (exact make/unmake), exact hitting-set tactics at every
node (`covering_placements`), joint-pair depth-2+ alpha-beta with
brink-resolution quiescence, STRICTLY SOUND threat-space search (defender
must spend both stones; any 1-cell cover refutes a line). Validated on
Modal (`results/bakeoff_hexo_bot2_v{1,2,3}.json`):

- vs vendored SealBot **23-1** (Wilson CI [0.80, 0.99])
- vs incumbent hexo_bot.py **20-4** ([0.64, 0.93])
- vs fast_tactical **10-0** (14 draws)

Full design/ablation history (incl. the v2 lesson: bounded-optimism TSS was
2-22 AGAINST its own ablation — unsound search is worse than none):
[competition/2026-07-09-hexo-bot2-results.md](../competition/2026-07-09-hexo-bot2-results.md).
Eval-weight mining = honest negative (`results/eval_mining.json`): mined
linear window weights UNDERPERFORM the hand prior; signal lives at brink
level. Remaining bot options (not started): 50-opening confirmation run,
transposition table, partial depth-3.

### The theory sweep (five experiments, all run)

Full write-up: [docs/theory/2026-07-09-empirical-theory-sweep.md](theory/2026-07-09-empirical-theory-sweep.md).
Headlines:

1. **Additive temperature law (exact)** — for disjoint collinear fragments
   under (2:2), draw-draw unions win iff h(A)+h(B) ≥ 3; verified with ZERO
   exceptions on 40,785 exact solves (`results/two_move_sum_full.json`).
   Solver: [experiments/run_two_move_sum.py](../experiments/run_two_move_sum.py).
2. **Split-prime extinction** — strong play suppresses the structure factor
   at the F₇-dual (p=2.4e-4 vs random), with NO mod-3 suppression
   (modulus-specificity = internal control). `results/spatial_order.json`.
3. **Defense dichotomy** — exact-hitting-set reactive defense shuts out the
   entire scripted multi-front attacker suite at k=6 (0% losses to 120
   dense fronts, ablation shows tier-1 exactness is the load-bearing part,
   NOT the F₇ structure) — then hexo_bot2 beats the same defense **24-0,
   zero draws**. Cheap-reactive defenses are dead against adaptive attack;
   the 2026-07-08 "capacity failure" falsified a weak tier-1, not
   turn-aware defense per se. `results/residue_defense_sweep.json`,
   `results/bakeoff_residue_blocker.json`.
4. **n_crit(R) ~ R^0.6–0.9** — sub-linear defender-collapse scaling,
   excluding constant-density and pure-count mechanisms.
   `results/pairing_scaling.json`.
5. **Patch entropy non-monotone in strength** — weak 7.87 < strong 8.76 <
   random 9.04 bits (r=1, matched N=27). "Stronger ⇒ more ordered" is
   false at patch level; wrinkle for the epiplexity narrative.

Supporting: `results/hexo_bot2_selfplay.json` (400-game strong corpus, all
decisive, colour parity 204-196 — no P1 edge visible at 12-stone random
openings). Figures: `fig_two_move_sum_matrix`, `fig_spatial_order_*` (3),
`fig_pairing_scaling_*` (2), `fig_residue_defense` — all in figures/.

### Fresh tonight (run, needs interpretation folded in tomorrow)

**(p:q) bias sweep** ([experiments/run_bias_temperature.py](../experiments/run_bias_temperature.py),
`results/bias_temperature.json`): the naive "ambient temperature = q"
generalization is PARTIALLY refuted, informatively:
- (2:2): law replicates exactly (0 errors).
- (1:1): 0 non-additive pairs, 712 law-false-positives — but h was defined
  with p=2's brink notion (≤2 empties). At p=1 heat must be **p-relative**
  (brink = ≤p empties). Not yet a law failure; rerun with h₁ required.
- (2:1): 350 false NEGATIVES — with q < p, cold components win by
  multi-turn escalation (+1 net pressure/turn) that one-turn heat cannot
  see. Consistent with Beck's biased-game theory: unbalanced games
  escalate unboundedly.

Working refined conjecture: **additivity of one-turn heat is a phenomenon
of BALANCED (p:p) games, with heat defined p-relatively.**

## Tomorrow's queue (priority order)

1. **E6b** — fix `cover_cost_after` to p-relative brinks (threshold k−p,
   covers of size ≤ q), rerun (1:1). Prediction: law holds at (1:1) with
   threshold h₁(A)+h₁(B) ≥ 2. Confirms/kills the balanced-game conjecture.
   (~30 min.)
2. **E10** — additivity failure boundary: bent/interleaved two-axis
   fragments (disjoint cells, crossing windows). The onset of
   super-additivity is the mechanism hexo_bot2 used to beat the blocker —
   connects the theorem to the bot result. Solver already takes arbitrary
   cell sets; needs a 2-D fragment generator. (~day.)
3. **E9** — Beck-null for n_crit(R): random-maturation scheduling model
   (no geometry); does it reproduce α ≈ 0.6–0.9? (hours)
4. **E7** — win-depth mass formula (solver returns depth, ~10 lines) →
   Hamkins value-ω construction from win-in-n fragment families {C_n}
   where the DEFENDER's move selects n. Goal: "HeXO admits positions of
   game value ≥ ω" as a companion to Hamkins–Leonessi.
5. **E8** — cross-lattice extinction. Preregistered prediction: clean
   extinction ⟺ k+1 is a split-prime norm in the lattice ring. ℤ[i]:
   k=4 → mod-5 extinction predicted; k=6 → NO clean modulus (7 inert in
   ℤ[i]) — WIN_LENGTH=6 on ℤ[ω] is the arithmetically distinguished case.
   Needs a ℤ² engine/corpus variant (the only real build in the queue).
6. **E11** — polyhex achievement heat tables (Bode–Harborth bridge),
   opportunistic.
7. **Paper skeleton** — the pieces now assemble: (i) exact additive
   temperature theory for balanced biased connect-k fragments (+ hand
   proof attempt for collinear case), (ii) arithmetic fingerprint of
   strong play (F₇ extinction), (iii) the adaptive-attacker dichotomy
   bounding all cheap defenses, (iv) collapse scaling. Literature anchors:
   Hales–Jewett/Zetters/Allis (k* thresholds), Beck/Erdős–Selfridge
   (biased potentials — our law is the exact local sharpening), Berlekamp
   (thermographs — the (p:q) sweep IS one), Lehman/Shannon (why exact
   local algebra is the best obtainable), Reisch (PSPACE), Hamkins
   (transfinite values), Bode–Harborth (achievement games).

## Housekeeping / open decisions for Leon

- **Nothing committed.** Modified: competition/{arena.py? no — external_bots.py,
  hexo_bot2.py NEW, 2026-07-09-hexo-bot2-results.md NEW}, modal_bakeoff.py,
  modal_theory_sweep.py, modal_selfplay.py NEW, experiments/run_{eval_mining,
  pairing_scaling,two_move_sum,spatial_order,residue_defense,bias_temperature}.py
  NEW, docs/theory/2026-07-09-empirical-theory-sweep.md NEW, this file, plus
  results/ and figures/ outputs.
- **SPEC.md updates recommended but NOT made** (deliberately, pending
  Leon's read): (a) "no cheap draw" entry should cite the dichotomy
  (result 3 above) — it is now stronger AND more precisely scoped;
  (b) the 2026-07-08 dense-cluster counterexample needs the reframe
  (it falsified single-cell tier-1, not turn-aware defense).
- **Deliverable handoff**: hexo_bot2.py is ready to hand to the opposing
  team as-is; a 50-opening confirmation run (~$0.5 Modal) would tighten
  the CI first.
- Modal spend today: roughly $3-5 total across ~10 runs.
