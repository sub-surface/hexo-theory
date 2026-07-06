# Search-regime candidates A–E: verdicts

*2026-07-06. Executes the handoff brief
[2026-07-05-search-regime-handoff.md](2026-07-05-search-regime-handoff.md) §0:
math re-derived before building, weak ideas cut with reasons, two new theorems
found along the way. Confidence labels follow SPEC.md §5 (🟢 solid /
🟡 directional / 🔴 not established).*

## Verdict table

| Candidate | Verdict | Confidence | Artifact |
|---|---|---|---|
| A — transfer-matrix λ | **Built, scope-corrected**: 1-D automaton exact; "compose to get inflation λ" **cut** (category error + Hochman–Meyerovitch barrier) | 🟢 spectrum, 🔴 λ-bridge | [run_line_automaton.py](../../experiments/run_line_automaton.py), `results/line_automaton.json` |
| B — cube decomposition | **Verified and absorbed**: decomposition is real but its naive sum already ships as `cell_score`; the isolated 1-D subgame is a trivial pairing draw, so all value lives in the cross-line coupling = τ | 🟢 | folded into `fast_tactical` ([arena.py](../../competition/arena.py)) |
| C — τ tractability | **Built and validated**: zero LP integrality gap on 1,657 real instances incl. 914 genuine τ>2 forks; LP certifies 100% of forks; per-axis TU prediction confirmed | 🟢 (mined distribution) | [run_tau_lp_gap.py](../../experiments/run_tau_lp_gap.py), `results/tau_lp_gap.json` |
| D — FFT threat maps | **Built and validated** (as sliding sums, not FFT): exact match to `cell_score`/`threat_count`; buys depth-2 lookahead inside the 1 s budget | 🟢 | `make_fast_tactical` + `--selftest` in [arena.py](../../competition/arena.py) |
| E — residue covering | **Resolved both ways**: covering algebra verified; covering→pairing upgrade **impossible** (new theorem); k=7 is the sharp threshold (new construction); cheap bias bots built for the empirical remainder | 🟢 theorems, 🟡 bots | [run_pairing_bound.py](../../experiments/run_pairing_bound.py), `results/pairing_bound.json` |

---

## A — per-line transfer matrix: exact spectrum, corrected scope

The automaton is real and now exact: states = run descriptors (colour, run
length 1–5), transitions as in
[run_line_automaton.py](../../experiments/run_line_automaton.py).

**Result 🟢.** The binary draw shift ({B,W} lines with no 6-run of either
colour — maximal runs are compositions into parts 1..5, forced directly by
`WIN_LENGTH = 6`) has Perron eigenvalue equal to the **pentanacci constant**
≈ 1.965948 (largest root of $x^5 = x^4+x^3+x^2+x+1$), whose four conjugates
all lie strictly inside the unit circle — **it is a Pisot number**, exactly,
not empirically. The ternary shift (empties unconstrained) sits at ≈ 2.9945.

**Cut 🔴, with reasons.** The brief proposed reading the quasicrystal
inflation constant λ off this spectrum. Two independent obstructions:

1. *Category error.* A **transfer** matrix's Perron root is an entropy base
   (growth rate of legal words); a **substitution** matrix's Perron root is a
   tile-inflation multiplier. README.md's Central Conjecture (its §"Pisot
   property", citing Thurston–Kenyon) needs the latter. They coincide only
   for special substitutions; nothing here supplies that identification.
2. *Composition barrier.* Both proposed compositions (Kronecker product, RG
   coupling) target the entropy of the full 2-D draw shift — a 2-D shift of
   finite type. By Hochman–Meyerovitch, 2-D SFT entropies are exactly the
   right-recursively-enumerable reals; they are not functions of the 1-D
   factor spectra. No clever tensor construction can be both correct and
   closed-form in general, so this route is cut rather than tuned.

The honest bridge to λ runs through Line B's forcing atoms (the candidate
substitution *tiles*), not through this spectrum. **Falsifiable remainder:**
if optimal-play corpora inherit per-line substitution structure, pentanacci
(or a power/conjugate) should appear in diffraction peak-position ratios —
checkable against `results/diffraction_p4.json` with no new theory.
Incidentally: README.md called ~1.3247 "tribonacci"; that value is the
plastic number (fixed in README).

## B — cube-coordinate decomposition: verified, then absorbed

The algebra checks (each axis direction fixes exactly one cube coordinate;
`cube_coords` at [engine/isomorphisms.py:22](../../engine/isomorphisms.py)).
But the two open questions close in a deflationary direction:

1. **The isolated 1-D subgame is a trivial draw.** Pair positions
   $\{2i, 2i+1\}$: any 6 consecutive cells on a line contain a full pair, so
   Breaker (responding stone-for-stone, which the 1-2-2 budget permits)
   forever denies 6-in-a-row on an isolated line. Hence there is no useful
   closed-form "1-D game value" — the per-line lookup table the brief hoped
   for is degenerate.
2. **The naive per-line sum already ships.** `cell_score`
   ([competition/arena.py](../../competition/arena.py)) *is* the sum of a
   1-D window potential over the three axis families; the fork cross-term
   the brief asked about *is* the existing τ-surplus term
   (`max(0, threat_count − 1)`). Candidate B, done right, is a unification
   statement: **ES potential + fork term = cube decomposition + τ coupling.**

What survives as new value is the *implementation* (see D): because the three
families are independent 1-D window systems, the whole board evaluates in a
handful of vectorized sliding sums. No separate `cube_evaluator.py` was
created — it would duplicate `cell_score` semantics under a new name.

## C — τ is exactly LP-computable on real positions

**Theory 🟢 (new, small but sharp).**
- One-turn obligations (windows with ≥4 attacker stones, unblocked) have ≤2
  empty cells, so the obligation hypergraph is a **graph** and τ is minimum
  vertex cover; its LP relaxation is half-integral (Nemhauser–Trotter), and
  since LP ≤ IP, **LP > 2 is a sound polynomial-time certificate of τ > 2**
  (forcing) — the certificate direction is exactly the one play needs.
- Single-axis obligation families are interval hypergraphs (consecutive-ones
  property ⇒ totally unimodular constraint matrix) ⇒ **zero gap, provably**.
  Any integrality gap therefore requires an odd structure mixing ≥2 axes —
  i.e. precisely a multi-axis fork motif.

**Empirics 🟢 (for the mined distribution).** 40 games, 4 pairing types
(including random-vs-random, the only cheap source of standing forks),
mid-turn sampling; 1,657 instances across both tiers (one-turn: edges ≤2;
proto own≥3: edges ≤3, a true hypergraph):

- integrality gap = **0 on every instance** (`zero_gap_fraction = 1.0` both tiers)
- 914 genuine τ>2 instances; **LP certified 100 %** of them
- single-axis gap = 0 always (TU prediction confirmed)

**Reading.** SPEC.md §7 item 6's NP-hardness worry is real only for
adversarial constructions; bounded-radius obligation structures arising from
actual play are LP-exact. τ can be used as an *exact* evaluator term at LP
cost (or interval-greedy per axis + tiny LP across axes). Prior-art check per
the brief: `papers/hexconnect6_atom_miner_results/` computes exact τ by brute
force (`tau()` at hexconnect6_atom_miner.py:109) but contains no LP anywhere;
this result is new to the repo.

**Falsifier kept open:** an adversarially *constructed* bounded-radius
position with nonzero gap would bound the method's reach — the atom-mining
pipeline is the right tool to search for one.

## D — whole-board threat maps: exact, and they buy depth 2

Built as `make_fast_tactical` in [competition/arena.py](../../competition/arena.py).
Implementation notes that differ from the brief:

- FFT is the wrong tool at kernel length 6 — shifted adds (O(N) per axis) are
  simpler and faster. The brief's live/dead subtlety is handled exactly as it
  prescribed: separate own/opp window sums, liveness mask, then
  $4^{\text{own}}$ weighting.
- **Correctness gate passed:** `python competition/arena.py --selftest`
  verifies the vectorized maps equal `cell_score` and `threat_count` on every
  candidate cell of 20 random boards (exact, not approximate).
- Cost: ~70–95 ms/move at 80 stones (vs 29 ms for `fork_aware`, 9 ms for the
  shipped heuristic) — comfortably inside the 1 s arena budget, spent on a
  1-placement opponent-reply lookahead over the top-12 static candidates.
  This is the "next real gain is shallow search" rung of DIRECTION.md's
  ladder, made affordable.

## E — residue covering: two theorems close the construction question

**Covering algebra 🟢 (verified, one vacuity found).** With
$p=7$, $\omega \mapsto 2$: axis steps reduce to 1, 2, 6 mod 7, all nonzero,
so every 6-window on every axis covers 6 distinct residues and excludes
exactly one (start − step, varying with position). Consequently **any two
distinct residue classes** form a density-2/7 sublattice meeting every
possible 6-window on all three axes simultaneously. (The brief's "cyclic gaps
≤ 6" side-condition is vacuous — true of every distinct pair.)

**Theorem 1 (impossibility) 🟢.** *No pairing strategy — periodic or not —
exists for 6-in-a-row on the hex lattice.* A pair $\{x, x+ju\}$ lies inside
exactly $6-j \le 5$ windows, all on axis $u$ (windows are collinear, so
off-axis pairs cover nothing). Window density is 3 per cell (18 windows
through each cell / 6 cells per window); pair density is at most 1/2 per
cell. Supply $5 \times \tfrac12 = 2.5$ window-covers per cell < demand 3, so
by averaging over large balls a positive density of windows contains no full
pair. This is the hex-lattice analogue of the classical 4-direction counting
bound on $\mathbb{Z}^2$ (which forces $k \ge 9$ there — the Hales–Jewett
pairing threshold).

**Theorem 2 (sharpness) 🟢.** For $k=7$ the counting is exactly tight
(supply $= 3 =$ demand), and the zero-slack object exists: an **explicit
period-6 perfect matching** of $\mathbb{Z}[\omega]$ into axis-parallel
dominoes, one domino per line per period, found by exact-cover search and
verified directly against every 7-window on the periodic lift
(`results/pairing_bound.json`, figure
`fig_pairing_bound_k7_tiling.png`). Hence **7-in-a-row on the hex lattice is
a pairing draw, and HeXO's $k=6$ sits exactly one below the sharp pairing
threshold** — the structural analogue of $k=8$ on $\mathbb{Z}^2$ (drawn, but
only by Zetters-style non-pairing arguments).

**Consequences.**
- If HeXO is a draw, the proof *cannot* be a pairing strategy; it must be
  Zetters-style local-defence or Hamkins-style global. This sharply narrows
  the proof-search space for the paper's CGT section and quantifies exactly
  *why* `MirrorAgent`'s point-reflection ([engine/agents.py](../../engine/agents.py))
  is the right *kind* of object (a strategy, not a pairing).
- Candidate E's open question ("can the covering become a pairing?") is
  answered **no**, with the failure located precisely: covering needs density
  2/7; pairing needs effective supply ≥ 3 covers/cell, and geometry caps it
  at 2.5.

**Empirical remainder 🟡.** The covering set may still earn its keep as a
bias. Two bots ship in the arena roster: `residue_static` (win/block checks +
covering-set placement only — the brief's cheapest falsifier: it has **never
lost to random**, passing it, and drew `fast_tactical` as a pure defender in
the quick screen) and `residue_bias` (fork-aware + ε tie-break toward the
covering set). Whether the bias helps at equal compute is a bake-off
question, not a theory question.

## Bake-off status

Local quick screen (`results/arena_screen_quick.json`) reconfirmed the
2026-06-15 draw wall: deterministic strong-vs-strong pairs replay one
canonical draw. Two arena fixes landed in response: the budget-overrun
forfeit now actually fires (the old check only penalized *illegal* moves),
and `play_game`/`round_robin` support seeded random openings with paired
colour-swapped games.

**Second finding 🟡 (n=48, flag it as such): the draw wall is not just
determinism.** With 6-stone random openings, all 48 strong-vs-strong games
(`results/arena_screen_openings.json`) still drew at the 400-move cutoff —
competent 2-stone-per-turn defence holds from any shallow perturbation. This
is consistent with the opening-optimality atlas (SPEC §5 Line B:
"overwhelmingly drawn under bounded local strategies") and quantifies how
hard decisive statistics are to buy at this level: decisive share between
top bots measured 0/48 at 6 random opening placements, 1/12 at 12, 3/12 at
16 (all decisive games won by the first player — small-n but pointing the
same way as the P1-edge thread). The bake-off therefore defaults to
16-placement openings, and win-rate-vs-weaker (margin + speed) is the
primary discriminator between top bots, not strong-vs-strong score.

[modal_bakeoff.py](../../modal_bakeoff.py) (adjacent to `modal_app.py`,
reusing its image patterns and its pool-once CI discipline) runs the Phase-1
round-robin on Modal; smoke test ≈ $0.01, full screen (21 pairings × 50
games) ≈ $0.10–0.45 by local timing — well inside the $30 budget alongside
DIRECTION.md's corpus plan. Everything in the bake-off is seed-reproducible
(unlike the rust corpus backend). One scoped-out limitation, per the handoff
§3: `hexgo-rs` exposes whole-game self-play only (no per-move API), so
pure-rollout MCTS cannot join this round-robin head-to-head without a small
PyO3 binding; `hexgo.parallel_eisenstein_games` remains the indirect
MCTS-vs-greedy anchor until then.

## Phase-1 results (2026-07-06, Modal, 1,050 games, ~$0.15)

`results/modal_bakeoff_screen.json`: full 7-bot round-robin, 25 openings × 2
colours per pairing, 16-placement random openings, 1 s budget, 171 s wall.

**Champion: `heuristic_d1.1` — the plain ES potential bot wins the Pareto
comparison outright.** It is simultaneously the cheapest evaluator (9 ms/move)
and the strongest against attackers (conceded 1/50 to `greedy_offence` vs
`fork_aware`'s 7/50, CI [0.00,0.10] vs [0.07,0.26]) and the fastest to convert
wins (28.6 mean stones-to-win vs `residue_static`). Strong-vs-strong stayed
draws (549/550; the single decisive game: `heuristic` beat `fast_tactical`).

**Prediction 3 (depth-2 dominance) — FALSIFIED as implemented 🟢.**
`fast_tactical` is *weaker*, not stronger: it conceded 16/50 to greedy
(CI [0.21,0.46], colour-balanced 9B/7W, so not a first-mover artifact) and took
3× longer to convert wins (89.8 vs 28.6 stones). Diagnosis: the
score-difference lookahead (`my_score − 0.8 × opp_best_reply`) induces
passivity — sharp winning lines *raise* the opponent's best-reply score, so
the bot systematically avoids them. The exact evaluator (candidate D) is
validated and keeps its value; the *search policy on top of it* needs true
minimax semantics over the 2-placement turn, not a static score difference.
Demoted pending that fix, not cut.

**Prediction 4 (residue bias) — NULL, maximally 🟢.** `residue_bias` produced
*byte-identical outcomes* to `fork_aware_d1.2` on every opening seed — the
ε tie-break never changed a single game result. Candidate E's empirical
remainder is cut.

**Bonus echo of Theorem 1:** `residue_static` lost 1/50 to `random` (playing
White, 107 stones) — pure covering-set defence is demonstrably not loss-proof,
exactly as the impossibility theorem predicts (covering guarantees *where*,
never *when*).

**Also notable 🟡:** the τ-fork term itself appears to carry a small
*defensive cost* against a pure attacker (7/50 vs 1/50 conceded; CIs barely
separate). Before any garden port, this needs a targeted look at which greedy
lines punish the fork bonus.

Four analytic figures summarize Phase-1 (`experiments/run_bakeoff_analysis.py`):
`fig_bakeoff_pareto.png` (cost vs strength — the whole roster clusters at
0.42–0.50 win-share within a 5–28 ms/move band, confirming the 1 s budget
binds nobody), `fig_bakeoff_matrix.png` (head-to-head decisive shares),
`fig_bakeoff_conversion.png` (stones-to-win vs weak opponents — the margin
metric), `fig_bakeoff_lengths.png` (decisive games end early or never).
One GIF per pairing (shortest decisive game, else first draw) is in
`figures/replays/`, replayed deterministically from the Modal seeds
(`experiments/render_pairing_gifs.py`; every replay reproduced the Modal
winner exactly — a cross-platform determinism check).

## Phase-2 results (2026-07-06, Modal, 1,120 games, ~$0.3): search wins

`results/modal_bakeoff_phase2.json`: 8 bots (champion + a defence-weight
ladder d∈{1.0,1.1,1.3,1.6,2.0} + two `fast_minimax` + `greedy_offence`),
20 openings × 2 colours, 16-placement openings, 1 s budget, 390 s wall.

**New champion: `fast_minimax_d1.1` — true turn-minimax over the exact
vectorized evaluator beats the shipped heuristic head-to-head 🟡 (strong,
consistent, small-n).** This *reverses* Phase-1's "search doesn't help": the
Phase-1 failure was the passive score-difference policy, not search. The fix
(`make_fast_minimax`): max over my placements, min over the opponent's two,
alpha-beta over the top-k static candidates, exact win/block at every node,
ES *position* differential at the leaves — the champion's own value, one full
turn-exchange deeper, at ~200 ms/move (well inside budget).

- vs `heuristic_d1.1`: **4–1 decisive** (fast_minimax favoured)
- vs the entire ladder (d1.0/d1.3/d1.6/d2.0): won the decisive games
  4–1, 2–1, 4–1, 5–0 — a clean sweep of six independent heuristic opponents,
  never a losing record against any
- leaderboard (pooled decisive wins): `fast_minimax_d1.1` **60**,
  `fast_minimax_d1.4` 52, then every static heuristic 36–44, `greedy` 29
- `fast_minimax_d1.1` > `fast_minimax_d1.4` (7–4): low defence weight is
  better once real search backs it up

Confidence 🟡 not 🟢: per-pairing decisive counts are small (the game is
deeply drawish — ~35/40 games draw), so each individual Wilson CI is wide.
But the *pattern* is not one lucky pairing — fast_minimax beats all six
distinct heuristics and both minimax bots top the board. A 🟢 upgrade needs
~5× more openings (cheap: ~$1.5 on Modal).

**Defence-weight ladder — no better static weight, mild over-defence penalty
🟢.** d1.0 through d1.6 draw each other (1–1 with ~38 draws every pairing);
d2.0 is strictly worst (loses the single decisive game to every lower weight,
last on the leaderboard). So the garden's d1.1 was already well-chosen; the
untuned knob had no hidden gain, and pushing defence too high slightly hurts.

**Greedy note:** the heuristics actually convert marginally *more* greedy
games than fast_minimax (36–38 vs 34 of 40) — greedy games end fast and every
competent bot handles them — but fast_minimax's edge shows exactly where it
should, against *strong* opposition. That is the profile you want in a
champion: it doesn't pad its record against weak play, it wins the hard games.

**Garden-port recommendation:** `fast_minimax_d1.1` is the new port candidate,
but it is ~20× the shipped heuristic's per-move cost (~200 ms vs 9 ms). For
the browser that is still fine at a 1 s budget, but the TS port needs the
vectorized evaluator (or an equivalent incremental one) — a bigger port than
the line-for-line heuristic. Recommended sequence: confirm the edge at 🟢
sample size first (~$1.5), then port.

## Programme D: S_T(N) measured for the first time (2026-07-06)

The repo's headline unmeasured claim (README Central Conjecture / ROADMAP
Programme D / SPEC P3): is the self-play corpus description length `S_T(N)`
**sub-linear** in corpus size? `engine/epiplexity.py` existed but had never
been pointed at a sweep. Run now, cheaply, via the gzip/lzma proxy
(`experiments/run_mdl_scaling.py`): D6-canonical move encoding (so lattice
symmetry is *not* counted as structure), lzma over log-spaced prefixes of an
8,000-game `ca_combo_v2` self-play corpus generated on Modal
(`modal_app.py::corpus_moves`, ~$1, 16.8 games/s).

**Result 🟡 (first read, clean signal): `S_T(N) ~ N^0.929` — sub-linear —
and cleanly separated from a random-play null at `N^1.009` (linear).** The
marginal description cost per game *falls* 78 → 57 bytes for the agent as the
corpus grows, but stays flat at ~118 bytes for random play. That separation
is the whole point: a bigger lzma dictionary finds more matches in *any* file,
so sub-linearity alone proves nothing — but random games (independent draws)
sit exactly at β=1 while strong-agent games sit clearly below it. The
sub-linearity is real shared structure in strong play, not a compressor
artifact. `results/mdl_scaling.json`, `figures/fig_mdl_scaling.png`; the null
is reproducible via `run_mdl_scaling.py --gen-control 3000`.

**What this does and does not establish.** It supports P3's *sub-linearity
premise* — strong-play corpora have finite shared structure that random play
lacks — which is the necessary first link in the chain
`sub-linear S_T ⇒ finite substitution ⇒ Pisot`. It does **not** establish the
Pisot inflation constant: β≈0.93 is a compression exponent, not a substitution
eigenvalue, and (per §A) that identification needs the forcing-atom tiles, not
a gzip curve. Nor is it the roadmap's observer-net epiplexity S_T — it's the
cheap proxy that roadmap explicitly asked for as a first honest read. To reach
🟢 P3: repeat across agents (combo, the new fast_minimax) and push N toward
10^5 (the corpus_moves path scales there for ~$13), and check whether β keeps
falling or plateaus.

**Bonus (queue item 2, P1):** the same 8,000-game corpus is a large-sample P1
measurement. `ca_combo_v2` self-play: Black wins **0.479 [0.467, 0.492]** of
5,973 decisive games — CI *excludes* 0.5 toward a slight **second**-mover edge,
overturning the thin-sample first-mover story (raw rate agrees: B 35.8% /
W 38.9% / 25% unfinished). See SPEC P1.

## New falsifiable predictions

1. **Pentanacci in diffraction**: peak-position ratios of
   `results/diffraction_p4.json` should show powers/conjugates of 1.9659 *if*
   per-line substitution structure survives into 2-D optimal play. Absence
   falsifies the per-line route to the Pisot conjecture (not the conjecture
   itself).
2. **LP-exact τ**: any mined or constructed bounded-radius obligation
   hypergraph with nonzero integrality gap falsifies "τ is cheaply exact in
   practice". The atom miner is the search tool.
3. **Search dominance — RESOLVED (Phase-2).** `fast_tactical` (naive
   score-difference) *lost*, but `fast_minimax` (true turn-minimax over the
   same evaluator) beats every static heuristic. So the "how much of HeXO is
   capturable by bounded τ-reasoning" curve has its next rung: static
   ES+τ ≈ each other, one turn-exchange of correct minimax is a real step up.
   Open: does a second turn-exchange (deeper minimax) add another step, or
   does the drawishness flatten the curve immediately after depth 1?
4. **Residue bias — RESOLVED (Phase-1), null.** Cut.
5. **Programme D / P3**: does `S_T(N)` for `ca_combo_v2` self-play grow
   sub-linearly? `experiments/run_mdl_scaling.py` + the Modal corpus settle
   the log-vs-linear read the repo has never run. β<1 (lzma) supports finite
   substitution structure; β≈1 refuses the Pisot conjecture any MDL support.
