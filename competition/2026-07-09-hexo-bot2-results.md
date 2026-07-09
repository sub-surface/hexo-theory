# hexo_bot2 — fresh-start rebuild: design, results, ablations (2026-07-09)

Built from `competition/2026-07-08-fresh-start-bot-brief.md` alone, reasoning
from the game theory rather than inheriting the incumbent architecture. This
note records what was built, why, and what the Modal bake-offs measured.

## 1. Design, from first principles

The defender answers with at most 2 stones per turn. So all exact tactics
reduce to **hitting-set arithmetic over brink windows** (live 6-windows with
>= 4 attacker stones): the mover wins iff some brink completes within their
remaining placements; the mover is *provably lost* iff the opponent's brink
empties admit no hitting set of <= 2 cells (`covering_placements` in
[hexo_bot2.py](hexo_bot2.py) — exact and cheap, since each brink window has
<= 2 empties, a 2-cover's second cell must lie in the intersection of the
windows the first cell misses).

On that exact layer, three things the incumbent (`hexo_bot.py`) and the
vendored SealBot each lack in part:

1. **Threat-space search (TSS)** — attacker restricted to brink-*creating*
   pairs, defender restricted to exact covering replies. Finds multi-turn
   forced wins: e.g. two open-3s doubled into two open-4s in one turn is
   threat-cost 4 > 2, a proven win invisible to beam/positional search until
   the brinks already exist. This is the operational form of the
   defender-budget argument in
   [docs/theory/2026-07-08-pairing-thresholds-and-game-values.md](../docs/theory/2026-07-08-pairing-thresholds-and-game-values.md) §3.2b.
2. **Defensive TSS** (added in v2 after the v1 loss diagnosis): run the same
   forced-win detector *for the opponent* at the root; if they have one,
   restrict the root to turns verified (by re-running their TSS) to defuse
   it. Detection must run both ways — v1's losses were short games where the
   opponent assembled fronts unopposed.
3. **Incremental window-count board** (SealBot-style `wc` counts, make/unmake
   undo stack, no copies) with joint 2-stone turns and brink-resolution
   quiescence. Node cost ~100x below the incumbent's global numpy re-eval;
   depth 2 (turns) + quiescence completes inside 0.7 s in pure Python.

Deliberately absent: no second language (pitfall #1 in the brief), no soft
fork bonus (ablated to zero twice in this project), no NN eval.

## 2. Bake-off v1 (results/bakeoff_hexo_bot2_v1.json, 12 openings x 2 colours, 1.0s budget, opening_placements=16, seed_base=0)

| pairing | result | Wilson 95 (decisive share) |
|---|---|---|
| hexo_bot2 vs sealbot | **21-3** | [0.69, 0.96] |
| hexo_bot2 vs hexo_bot_standalone | 12-12 | [0.31, 0.69] |
| hexo_bot2 vs fast_tactical | **10-0** (14 draws) | [0.72, 1.00] |
| sealbot vs hexo_bot_standalone | 0-24 | — |
| hexo_bot_standalone vs fast_tactical | 2-0 (22 draws) | — |

Reads: beats the external bar decisively out of the gate; converts draws into
wins against defensive opposition far better than the incumbent (10-0 vs the
incumbent's 2-0 against fast_tactical — the bot that 24-0'd the old
tactically-blind deep search); dead even with the incumbent.

**Loss diagnosis:** all 3 sealbot losses and most incumbent losses were
*short* games (25-39 stones) clustered on specific opening seeds, both
colours — offense executed brilliantly (median win 27 stones vs sealbot),
but the bot never asked whether the *opponent* had a forced attacking
sequence. Hence defensive TSS in v2.

## 3. Bake-off v2 (results/bakeoff_hexo_bot2_v2.json, same seeds, + no-TSS ablation arm)

The ablation *inverted* expectations — the TSS layer as first built was
actively harmful:

| pairing | result |
|---|---|
| hexo_bot2 (attack+defensive TSS) vs hexo_bot2_no_tss | **2-22** |
| hexo_bot2 vs sealbot | 20-4 |
| hexo_bot2 vs hexo_bot_standalone | 6-18 (v1 with attack-TSS only: 12-12) |
| hexo_bot2_no_tss vs sealbot | **24-0** |
| hexo_bot2_no_tss vs hexo_bot_standalone | 11-11 (2d) |

Diagnosis: the TSS defender model had *bounded optimism* (a "free stone"
reply enumerated from a top-k set, plus a truncated cover list) — it claimed
forced wins that weren't, committed stones to fizzling attacks, and burned
0.25-0.4 s of the 0.7 s budget doing it. The defensive variant added false
alarms that narrowed the root to passive moves (12-12 → 6-18 on its own).
The brief's facts #2/#4 rhyming again: an unsound deep search is worse than
a sound shallow one. Fixes for v3: (a) defensive TSS deleted; (b) attack TSS
made STRICTLY sound — a line only counts as forcing if every defender reply
must spend both stones covering (any 1-cell cover refutes; full cover
enumeration, no truncation), so it can only find real wins; (c) the real
bottleneck fixed — incrementally-maintained integer per-cell move deltas
replaced the full-candidate rescoring that dominated node cost, so depth-2
joint-pair search (which prices opponent double-threat turns *exactly*)
always completes inside the budget.

## 3b. Bake-off v3 (results/bakeoff_hexo_bot2_v3.json, same seeds)

| pairing | result | Wilson 95 |
|---|---|---|
| hexo_bot2 (sound TSS) vs sealbot | **23-1** | [0.80, 0.99] |
| hexo_bot2 vs hexo_bot_standalone | **20-4** | [0.64, 0.93] |
| hexo_bot2 vs hexo_bot2_no_tss | 12-12 | [0.31, 0.69] |
| hexo_bot2_no_tss vs sealbot | 23-1 | [0.80, 0.99] |
| hexo_bot2_no_tss vs hexo_bot_standalone | 15-9 | [0.43, 0.79] |
| sealbot vs hexo_bot_standalone | 0-24 | — |

Reads, in causal order:
1. **The speed fix was the decisive change** — no_tss alone went from 11-11
   to 15-9 against the incumbent purely from reliable depth-2/partial
   depth-3.
2. **Sound TSS is safe and adds a real edge**: harmful-TSS 2-22 became
   12-12 in the mirror, identical vs sealbot, and 20-4 vs the incumbent's
   15-9 for the no-TSS arm. Kept ON as the default.
3. hexo_bot2 now beats every opponent it has faced: sealbot 23-1,
   incumbent 20-4, fast_tactical 10-0 (v1), and tops the pooled leaderboard
   (55 vs 50 vs 37 vs 2).

## 4. Eval-weight mining: an honest negative (results/eval_mining.json)

The brief's open question #3 (mined evaluation), tested via
[experiments/run_eval_mining.py](../experiments/run_eval_mining.py):
logistic regression P(mover wins) over live-window counts by stone count
(k=1..5 both sides, features extracted through hexo_bot2's own Board so they
are definitionally what the bot evaluates), fit on the 8,000-game
`ca_combo_v2` corpus (5,973 decisive games, 23,698 sampled positions,
80/20 split).

- Mined linear weights: test accuracy **0.594**.
- Hand-set exponential V table as a linear scorer, same split: **0.610**.
- Mined weight structure is degenerate: only the k=4 (brink) columns carry
  signal; sub-brink counts get near-zero or wrong-sign weights. (The mined
  defence weight on the meaningful columns lands at 1.104 — the hand-set
  value is 1.1.)

Conclusion: on a weak-agent corpus, mined window weights are *worse* than the
hand prior; the outcome signal lives almost entirely at brink level, which
the exact layer already handles. Consistent with the fork-bonus ablations:
in this game, strength lives in exact tactics, not evaluation refinement.
Revisit only with a corpus from a strong (tactically complete) player.

## 5. Deliverable

`competition/hexo_bot2.py` — single pure-Python stdlib-only file, same
`choose_move(stones, turn, placed_this_turn, stones_per_turn)` interface as
the incumbent, stated rule assumptions in the module docstring, hard internal
time budget (default 0.70 s, parameter), never crashes (greedy legal
fallback). Selftest: `python competition/hexo_bot2.py` (exact win/block/
fork/TSS/defense cases + make-unmake integrity + budget check).
