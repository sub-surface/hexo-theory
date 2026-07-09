# Hexanacci vs. pentanacci, and an MDL-derived loss function for move choice

Status: speculative synthesis, each claim tagged with a concrete falsifier and a
pointer to the code that would run it. Written after reviewing the freshly-run
(uncommitted) `results/epiplexity_corpus.json` / `figures/fig_epiplexity_corpus.png`
— the first Markov-observer (not gzip-proxy) epiplexity measurement, produced by
`experiments/run_epiplexity_corpus.py`.

## 0. What the new run actually shows

`run_epiplexity_corpus.py` fits an order-3 Markov back-off observer (not just
gzip) to the existing `ca_combo_v2` 8,000-game Modal corpus
(`results/modal_moves_python_8000.json`) and the random-play null
(`results/mdl_random_control_3000.json`), at 10 log-spaced prefixes each. Headline
(`results/epiplexity_corpus.json:headline`):

- Agent `H_T`: **9.30 → 6.68 bits/token** as N: 133 → 8,000 (falls monotonically).
- Random `H_T`: **7.91 → 7.91 bits/token**, flat within noise (7.89–8.06 across all
  N — no downward trend).
- Final gap: **1.229 bits/token**, agent more compressible.

This is a materially stronger P3 signal than the gzip-only proxy in
`run_mdl_scaling.py` (which only measured raw compressed length, not a
proper held-out cross-entropy): a learned finite-order Markov model gets
*better* at predicting the agent's moves as it sees more games, and gets *no
better* at predicting random moves — exactly the "learnable structure exists
and grows with N" signature P3 needs, from an independent measurement tool.
Worth promoting into SPEC.md §5 P3 (currently 🟡) once committed — this doesn't
move it to 🟢 by itself (still one agent, still order-3 only) but it's a second,
methodologically different data point agreeing with the gzip one.

Two follow-ups this immediately suggests, cheap:
1. Run the same sweep with `max_order` 1,2,4,5 — if `H_T` keeps dropping as order
   rises without bound, that's evidence *against* a finite substitution system
   (contradicts P3's Pisot framing); if it saturates by order 4-5, that's a
   concrete finite memory-depth for the "local generator" line B is looking for.
2. Run it on `fast_minimax_d1.1` self-play once that corpus exists (bake-off
   Phase 2 champion, `competition/arena.py:376` `make_fast_minimax`) — if the
   stronger player is *more* compressible than `ca_combo_v2`, that's a dose-response
   curve (strength ↔ compressibility) instead of a single strong/random contrast.

## 1. Hexanacci vs. pentanacci — a precise, checkable discrepancy

`results/line_automaton.json` reports the Perron eigenvalue of the "no run of 6
same-symbol" line-shift automaton as **1.965948…**, and correctly identifies
this as the **pentanacci** constant (order-5 k-bonacci: `x^5 = x^4+x^3+x^2+x+1`),
not tribonacci as README.md's loose language suggested (the file's own
`note_on_readme` field already flags this).

But WIN_LENGTH is 6 (`game.py:147`, per CLAUDE.md's invariant). Why does the
forbidden-pattern automaton have order **5**, not **6**? Because the standard
combinatorics of "avoid a run of length k" languages is order **k−1**: the
transfer-matrix states track "currently in a run of 1, 2, 3, 4, or 5 identical
symbols" (state 6 would be the forbidden/absorbing state, so it's never a live
state) — hence pentanacci (order 5) is exactly right for k=6, and this is not a
coincidence or an error, it's `k−1`-bonacci by construction. Good — the repo's
own module docstring already scoped this correctly ("Perron eigenvalue = entropy
base of the line shift, NOT a substitution inflation constant").

The **hexanacci** constant (order-6, `x^6=x^5+…+1 ≈ 1.983583`, computed directly:
`np.roots([1,-1,-1,-1,-1,-1,-1])` → largest real root 1.9835828434243288) is a
different, *not yet computed*, quantity. Where would order-6 actually show up
correctly, rather than by miscounting the single-axis automaton?

**Candidate: the *simultaneous 3-axis* automaton**, not the single-axis one.
Every stone in HeXO sits on **three** unit-step lines at once (q, r, q−r axes —
`SPEC.md:29-32`). The single-axis line-shift in `line_automaton.json` only
forbids a run along *one* axis at a time; it doesn't encode that a move commits
a cell to all three axes' local windows simultaneously. A transfer matrix built
over the *joint* state (run-length-so-far on axis 1, axis 2, axis 3) is a
genuinely different, higher-dimensional automaton, and its Perron eigenvalue is
a **new, uncomputed number** — not obviously pentanacci, not obviously
hexanacci, but a candidate that for the first time actually reflects the game's
three-fold structure instead of one 1-D slice of it. This is the concrete way
to attack SPEC.md §7 open question 4 ("which Pisot number") with a sharper tool
than either the loose README guess or the single-axis pentanacci result.

Falsifiable prediction: build the 3-axis coupled transfer matrix (state space:
cross-product of per-axis run-length mod 6, pruned to reachable joint states on
the actual hex lattice adjacency) and compute its Perron root. If it equals
pentanacci, the axes are effectively independent at the local level (no new
information from coupling) — a clean negative result. If it's a new Pisot
number distinct from both pentanacci and hexanacci, that's the first genuine
candidate for the substitution inflation constant grounded in the *actual*
3-axis rule rather than a 1-D proxy — feeds SPEC.md §7 Q2 (does it match the
diffraction-measured λ?) and Q4 directly.

## 2. Toward one loss function: fusing τ (mechanism) and H_T (measurement)

DIRECTION.md's current framing keeps line A (epiplexity, global measurement) and
line B (τ-forcing, local mechanism) as separate research threads that happen to
share substrate (`DIRECTION.md:150-166`, `SPEC.md:93-117`). The user's ask —
"a function that minimises a value to produce optimal play" — is exactly the
prompt to fuse them into one scoring functional instead of two parallel
programmes, since HeXO's engine already treats both as scalars per move:

- τ-pressure: `max(0, τ_LP(O) − 2)` — proven LP-exact on real positions, zero
  integrality gap on 1,657 mined instances (`experiments/run_tau_lp_gap.py`,
  `results/tau_lp_gap.json`, SPEC.md:187). This is *already* a per-move loss
  term: `fast_minimax` in `competition/arena.py:376` implicitly maximizes a
  cheap correlate of it.
- H_T: the Markov observer's per-token surprisal, now computed properly
  (§0 above) via `engine/epiplexity.py:351` `measure_corpus`. Cheap to evaluate
  per-move too — it's just `-log P_markov(move | context)`.

**Proposed unified move-scoring functional** (a genuine synthesis, not in the
repo yet):

```
score(move) = τ_LP(O(s ∪ move))              # forcing pressure, maximize
            − β · H_T(move | Markov-k(corpus))  # predictability under the
                                                  # bounded observer, minimize
```

Interpretation: a move is good if it (a) manufactures real forcing (τ > 2,
line B's mechanism) and (b) is a move the opponent's model of "how this player
plays" would *not* predict — i.e. it exploits the gap between the opponent's
bounded model and the truth. This is literally an epiplexity-flavored
minimax: your opponent's practical strength is bounded by *their* time-bounded
observer of you, per Finzi's `H_T` framing (`engine/epiplexity.py:1-27`); a move
that's τ-forcing *and* high-surprisal-to-a-generic-Markov-k-model is doubly
valuable, and the two terms are not redundant (τ is a property of the board;
H_T is a property of the move sequence's statistics).

This reframes "optimal play" search as **MDL-regularized minimax** rather than
plain minimax: at each ply, prefer forcing moves the opponent's cheap internal
model would be worst at anticipating. It also gives a *third* falsifiable
prediction distinct from anything in SPEC.md: **moves in the winning lines of
decisive games should have systematically higher single-move surprisal
(-log P_markov) than moves in drawn games**, if forcing correlates with
unpredictability. That's checkable right now against the existing
`modal_moves_python_8000.json` corpus (decisive vs. drawn subsets) with no new
data collection — just a new stat over data already on disk.

## 3. The concrete, cheap next experiment this all points to

Given the NCA/AlphaZero-lite thread is parked on a *diagnosed but unfixed* data
bug (SPEC.md §6, class imbalance on v=0 / sparse threat labels — don't touch
that), and `fast_minimax_d1.1` is the current champion but is plain minimax with
no move-ordering prior (`competition/arena.py:376-`), the Markov-k observer
built for epiplexity is a **free, already-built move-ordering prior** that
sidesteps the entire blocked NN thread:

`experiments/run_epiplexity_guided_search.py` (not yet written): wrap
`fast_minimax`'s candidate-move loop with a move-ordering key of
`P_markov(move | context)` from a Markov-3 model fit on the existing 8,000-game
corpus — cheap (a dict lookup, no torch, no training loop, reuses
`engine/epiplexity.py`'s already-fit back-off tables) — and see whether better
move ordering lets a fixed 1-second budget reach greater effective depth /
beat plain `fast_minimax_d1.1` in the arena. This is compression-as-policy-prior
instead of neural-network-as-policy-prior: same AlphaZero-shaped idea
(policy net narrows the search), but built entirely from the MDL machinery
already proven to work in §0, with zero exposure to the diagnosed NCA training
bugs.

## Falsifiers, collected

1. 3-axis transfer matrix Perron root ≠ pentanacci ⇒ new Pisot candidate;
   = pentanacci ⇒ axes locally independent (negative but informative).
2. Markov `H_T` vs. order (1,2,4,5 sweep): saturates ⇒ finite local memory
   depth found; monotonically drops ⇒ evidence against a finite substitution
   system, a real threat to the Pisot conjecture worth flagging in SPEC.md.
3. Decisive vs. drawn games: single-move surprisal higher in decisive-game
   winning lines ⇒ supports the τ/H_T fusion in §2; no difference ⇒ the two
   quantities are orthogonal, not fusable as one score.
4. Markov-prior-ordered `fast_minimax` beats plain `fast_minimax_d1.1` in the
   arena ⇒ compression-derived policy priors are a viable, NN-free upgrade path;
   no edge ⇒ move ordering wasn't the bottleneck at 1 s budget (informative
   negative, rules out one cheap lever before considering deeper search).
