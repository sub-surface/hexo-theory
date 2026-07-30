# A forcing-fragment proof solver: τ-search, the √3 certificate, and where hexanacci actually lives

Status: built 2026-07-19, revised 2026-07-20 after an external review found a
real completeness bug and two overclaims (see **Changelog** below) — treat
this as a **one-sided forcing certifier with a proven defender-side
certificate**, not a finished proof system. Code:
[competition/proof_solver.py](../../competition/proof_solver.py) (solver),
[experiments/run_proof_solver.py](../../experiments/run_proof_solver.py) (verification battery + stats),
`evidence/results/proof_solver.json`, `evidence/figures/fig_proof_solver_cull.png`.
Theorem 3 is proved in full here (self-contained) and is the one claim in
this note with a completeness proof independent of the implementation;
everything else tagged 🟢 passed its machine check but should be read as
"search evidence, mechanically verified on the cases tried" rather than a
closed theorem. 🔶 marks genuinely open steps.

## Changelog (2026-07-20, external review)

An external review of the 2026-07-19 version found three real problems,
fixed here — this section records what changed and why, so the reasoning
trail is auditable rather than silently rewritten:

1. **Candidate-generator incompleteness (real bug, not a labeling issue).**
   `_forcing_pairs` only ever paired a cell from $P$ (empties of live
   own-≥3 windows) with *another* cell from $P$, or the two empties of a
   single own-2 window. It never considered a pair where ONE stone alone
   already pushes $\tau \ge 2$ (a multi-axis fork) and the SECOND stone is
   spent on something else entirely — most importantly, neutralising a
   defender's own pre-existing win-now threat elsewhere on the board. The
   reviewer's constructed counterexample (a 3-axis fork at one cell, exact
   $\tau=3$ from that cell alone, plus a single-cell-blockable defender
   threat 99 cells away) reproduced exactly as described: `refuted_fragment`
   pre-fix, when a forced win genuinely exists. Fixed by extending
   `_forcing_pairs` to generate (self-sufficient cell, defender-threat-empty)
   pairs; the counterexample is now `fork_plus_remote_block_regression` in
   the battery (🟢 passes) — see the revised Lemma 2.
2. **The locality/composition argument (§2) did not follow.** Once a
   forcing pair can include an arbitrary "spare" stone, the original
   distance-based Lemma 3 (claiming every stone stays within $5t$ of the
   initial support) is false — a spare can go wherever a remote defender
   threat is. Rather than patch the distance bound (the reviewer suggested
   $\sim 10t+5$; investigating this further surfaced something worse, item
   2b below), the argument is replaced with a **zone-containment-by-
   construction** claim, which is mechanically true given a precondition
   the code now enforces. See the revised §2.
2b. **A genuine soundness gap found while fixing (2), not by the
   reviewer.** Verifying the corrected composition claim surfaced a real
   unsoundness: if `solve()` is called with a `zone` that does *not* fully
   contain the input `stones`, a defender stone sitting outside the zone
   can have a real, board-true win-now threat that the zone-restricted
   search never checks — producing a `proven` verdict that is actually
   false against the real board. Reproduced directly: a fork position with
   defender material placed outside a too-small zone came back `proven`
   via a pair that, checked against the unrestricted board, left the
   defender free to win outright on the next turn. `solve()` now raises
   `ValueError` if any input stone lies outside `zone` — see §2.
3. **Two overclaims in prose, now corrected in place:**
   - The `double_open3_depth2` battery case was described as reaching
     exact $\tau=4$. The solver's actual chosen pair (which set-iteration
     order picks is not fixed by the code) has exact $\tau=3$; a
     *different*, hand-picked pair does reach $\tau=4$. Both are valid
     forced wins ($\tau>2$ either way) but the note claimed a specific
     number that wasn't what was tested. The battery now computes the
     exact value of whatever pair the solver actually returns
     (`ps.exact_tau`) instead of asserting a remembered one.
   - §4 said hexanacci "is the growth rate of the state space the forcing
     search walks, and the culling is its operational face." This
     conflated two unrelated things: hexanacci is a fact about the
     one-colour line language; the measured cull comes from τ-filtering
     over a threat-driven candidate generator that has nothing to do with
     the automaton. Also, the "naive" baseline in the cull stat is
     `arena.candidates` (cells adjacent to existing stones), not literally
     every legal cell on the infinite board, so the ~2.9–5.9× reduction
     numbers below are relative to that baseline, not an absolute
     state-space bound. Both corrected in §4.

   Also revised: the 3-SAT section (§5) now flags explicitly that a
   re-arming wire alone does not establish NP-hardness (variable/clause
   semantics, isolation, both reduction directions, and a polynomial
   encoding all remain open), and that failing to find a wire motif at
   bounded radius would show only that *this specific fragment* is bounded,
   not that every forcing sequence in the real game terminates in
   $O(\text{material})$ turns. The battery no longer just string-compares
   `res.status` to an expected label — cases with a specific structural
   claim (exact τ, a unique defender reply) now assert on the solver's
   internals, computed fresh each run.

What survived unchanged: the obligation-graph/vertex-cover exactness (§1),
the AND-node complete-reply-enumeration argument, and Theorem 3 (the √3
certificate, §3) — independently re-derived by the reviewer and confirmed
internally coherent.

This is the opening move on **DIRECTION.md queue item 4** (formalise the 3-SAT
reduction, SPEC.md §7 item 6 — the Discord AND-gate/wire sketch). The thesis:
that reduction cannot be formalised by drawing pictures; it needs a mechanical
verifier for statements of the form *"from position P, the attacker forces X
within t turns inside zone Z"*, plus a composition lemma letting verified
gadgets be glued. A first version of both now exists — the verifier is sound
on `proven` results and on Theorem 3's certificate, honest about uncertainty
(`unknown`) when its own search was truncated, and openly incomplete
elsewhere (§1's revised Lemma 2); the composition lemma is now proved from
an enforced isolation precondition rather than a false distance bound (§2).
Read §5 before assuming this gets close to an actual hardness proof — it
doesn't yet, on several distinct fronts.

## 1. The fragment

Fix attacker $A$, defender $D$ on $\mathbb{Z}[\omega]$, both with the 2-stone
turn budget (the 1-2-2 opening asymmetry is irrelevant to gadget analysis and
ignored throughout). A **window** is a 6-term arithmetic progression with
common difference a unit axis vector — the AP structure of the game is used
below only through two numbers: length 6 and the per-turn budget 2.

- A window is **live** for $A$ if it contains no $D$ stone; its **deficit**
  $d(w) = 6 - |w \cap A|$.
- A **one-turn obligation** is a live window with $d \le 2$; its hyperedge is
  its empty-cell set, size ≤ 2. This is exactly
  `obligation_edges(min_own=4)` at [experiments/run_tau_lp_gap.py:44](../../experiments/run_tau_lp_gap.py),
  the object behind `threat_count` at [competition/arena.py:172](../../competition/arena.py)
  and DIRECTION.md's master variable τ.
- $A$ **wins next turn iff** the obligation family $O$ has transversal number
  $\tau(O) > 2$. Because edges have ≤ 2 cells, $O$ is a *graph*, τ is minimum
  vertex cover, and both τ and the full set of size-2 hitting sets are exact
  by brute enumeration — no LP needed inside the search (the LP story, with
  its measured zero integrality gap, is SPEC.md Line B: "τ is LP-exact on
  real positions" 🟢).

**The forcing fragment (VCO — victory by continuous obligations).** A play
line is *fully forcing* if after every $A$ pair, $\tau(O) \ge 2$: the
defender's entire budget is pinned onto a hitting pair, or $\tau > 2$ and the
game ends. The solver ([competition/proof_solver.py](../../competition/proof_solver.py))
searches exactly this fragment as an AND/OR tree:

- **OR node** ($A$'s turn): win-now if any live $d\le2$ window; else generate
  candidate pairs and keep those with $\tau \ge 2$ after placement.
- **AND node** ($D$'s turn, $\tau = 2$): the reply set is *completely*
  enumerable — τ = 2 means no single cell covers, so **both** defender stones
  must hit, hence both lie in the union of edge cells; `hitting_sets_le2`
  lists every such pair. Any non-hitting reply loses immediately, and replies
  that win outright for $D$ (own $d\le2$ window, or a blocking stone that
  completes a defender 6) are checked first at every AND node.

**Soundness contract (four statuses, revised 2026-07-20).** `proven` is a
forced win in the *strong* game restricted to the zone (defender
counterplay is checked, replies are complete) — unaffected by candidate-list
truncation, since a cap only removes candidates, never fabricates a win.
`unknown` means the search found no win but truncated its candidate list
(`max_pairs`) somewhere in the tree, so the negative result is not
trustworthy. `refuted_fragment` refutes the fully-forcing fragment with an
*uncapped* candidate generator that is not proven complete in general (§1's
revised Lemma 2). `refuted_cert` (Theorem 3) refutes *every* attacker
strategy in the zone at *any* depth — the one status with a completeness
proof independent of the candidate generator. All four require, when a
`zone` is given, that the input position lies entirely inside it (`solve()`
raises otherwise) — §2 explains why this precondition is load-bearing, not
a formality.

Two exactness micro-lemmas make the search cheap:

**Lemma 1 (fresh-obligation locality).** At an OR node that is not win-now,
no obligation predates the pair (it would be a live $d \le 2$ window =
win-now). Hence every post-pair obligation contains a just-placed stone, and
the obligation rescan is 36 windows, not the board.

**Lemma 2 (candidate generation, revised 2026-07-20 — not a completeness
proof).** A pair is forcing only if each created obligation contains a
placed stone (Lemma 1). An obligation window has ≥ 4 attacker stones, the
pair supplies ≤ 2, so it had ≥ 2 before the pair. This licenses two
disjoint cases, both generated by `_forcing_pairs`:

- **Jointly-necessary pairs**: both new stones needed together — either
  both are empties of some own-≥3 window (set $P$), or both are the two
  empties of one own-2 window.
- **Self-sufficient + spare pairs**: ONE new stone $c_1 \in P$ already
  pushes $\tau(O) \ge 2$ by itself (checked directly:
  `hitting_sets_le2(obligations_through(\cdot, [c_1]))`). Since attacker
  stones only ever *add* to attacker's own live-window counts, the second
  stone cannot lower $\tau$ below what $c_1$ alone achieves — so it is free,
  and should be spent on whatever the position needs: a defender's
  pre-existing win-now threat (`_defender_threat_empties`), if one exists,
  or a zone-local spare cell if not.

**This is NOT a completeness proof for case 2 in general.** If the
defender has $\ge 2$ *disjoint* win-now windows requiring $\ge 2$ stones to
jointly neutralise, no single spare resolves them, and the generator
abstains — correctly, in the sense that it does not fabricate a candidate,
but this may mean either "no forcing pair exists here" (a true `refuted_
fragment`, e.g. because the position really is lost to a stronger defender
counter-threat — confirmed by hand-construction: a defender pattern needing
exactly 2 blocking stones genuinely cannot be neutralised while also
extending a fork with one pair) or "the generator's single-spare heuristic
undercounts a harder case the real game would still let the attacker win by
some other pair." Distinguishing these is open; the generator is a strong,
now bug-fixed superset of the obvious candidates, not a proven-exhaustive
enumeration of every forcing pair.

## 2. Locality and composition (revised 2026-07-20)

The original version bounded how far a forcing line's stones can wander by
an a priori distance argument (Lemma 2's own-count reasoning). That bound is
false once a forcing pair can include a self-sufficient stone plus an
arbitrary spare (§1's revised Lemma 2, case 2): a spare stone can go
wherever the position actually needs it, with no distance bound derivable
from the fragment's *definition* alone. Composition is rescued differently
— not by bounding an unrestricted search, but by making zone-containment a
property the solver *enforces mechanically*, and proving composition from
that instead.

**Zone-containment (by code construction, not a distance bound).** Every
cell `solve()` ever places — attacker candidates ($P$, defender-threat
blockers, spare fallback in `_forcing_pairs`) and defender's hitting replies
(vertices of `obligations_through`'s zone-filtered edges) — is drawn from
`live_windows(..., zone)`, which discards any window not *entirely* inside
`zone`. So if `zone` is given, no stone placed during the search can ever
land outside it. This is checkable by inspection of every candidate-cell
source in `_forcing_pairs` and `_solve_or`, and confirmed directly: running
`solve()` on a zone-restricted position and collecting every cell mentioned
in the returned line, all lie inside the zone (100% on the cases tried).

**The precondition this needs, and the bug it exposed (Changelog item 2b).**
Zone-containment of *placed* stones is not enough on its own — it is only a
*sound* restriction of the real (unrestricted) game when every stone
*already on the board* is also inside the zone. If the input position has
material outside the zone, that material's windows are invisible to
`_window_state` (it requires all 6 cells of a window in-zone), so a real
defender win-now threat sitting partly outside the zone is never checked by
`_defender_can_win_now` — and the search can return `proven` for a pair
that, on the real board, loses outright to the unaddressed threat. This was
found by direct construction while verifying the claim above: a fork
position with defender material placed outside a too-small zone was
reported `proven`; checking the same pair against the unrestricted board
showed `_defender_can_win_now` was true — the defender simply wins next
turn instead of responding to the fork. `solve()` now raises `ValueError`
if any input stone lies outside `zone`, closing this.

**Corollary (gadget composition, corrected form).** Let $Z_1, Z_2$ be zones
sharing no 6-window (sufficient: pairwise hex-distance ≥ 6). If
`solve(pos_1, zone=Z_1)` and `solve(pos_2, zone=Z_2)` each return `proven`,
with $\text{pos}_1 \subseteq Z_1$ and $\text{pos}_2 \subseteq Z_2$ (the
precondition above, satisfied automatically when each gadget is verified in
*isolation* — no material from the other gadget present at all), then
placing both on the same board preserves each gadget's forcing property:
no window spans both zones, so neither gadget's obligations, candidate
cells, or defender replies can reference the other's material — the two
forcing games are literally disjoint objects on disjoint vertex sets, and
$\tau$ is additive by elementary vertex-cover additivity over disjoint
graphs. This is weaker than the original claim in one respect worth being
honest about: it says verified-in-isolation gadgets compose, not that an
arbitrary forcing line in the wild stays local — the latter is false (§1).
It is the composition property the 3-SAT programme actually needs (each
gadget is a fixed, checkable local construction), just derived from
enforced isolation rather than a distance theorem.

The AND-gate seed is still machine-verified 🟢, with a corrected number:
battery case `double_open3_depth2` — two open-3s separated by 8, one
attacker pair pushes the obligation graph's exact $\tau$ above 2 (the
solver's actual chosen pair reaches exact $\tau=3$; a different, hand-picked
symmetric pair reaches exact $\tau=4$ — both computed fresh each run via
`ps.exact_tau`, not asserted from memory, per Changelog item 3), `proven` at
depth 2 either way. The rigorous content of the hand-waved "AND gate" is
unchanged: *simultaneity of two sub-threshold obligation families is itself
the gate*.

## 3. Theorem 3: the zone-local √3 certificate

This is the defender-side object. By verdicts Theorem 1 (no pairing strategy
exists at $k=6$ — `results/pairing_bound.json`), any refutation of attacker
play must be a *strategy*, not a pairing. Here is one, with a potential-
function certificate, in the biased Erdős–Selfridge style (cf. Beck's biased
criterion, *Remarks on positional games*, 1982 — cited as lineage; nothing
below depends on the citation, the proof is self-contained).

Fix a finite zone $Z$ and let $F$ = all windows entirely inside $Z$. Let
$\lambda = \sqrt{3}$ and

$$\Phi \;=\; \sum_{w \in F \text{ live for } A} \lambda^{-d(w)}.$$

Note $\Phi$ counts *all-empty* windows too ($d = 6$, weight $3^{-3} = 1/27$).

**Theorem 3.** In the (2:2) Maker–Breaker game on $F$ (attacker = Maker):
(a) if $\Phi < \lambda^{-2} = 1/3$ at a defender-to-move instant, the greedy
potential defender prevents any attacker 6 inside $Z$ forever; (b) if
$\Phi < 1/9$ at an attacker-to-move instant, likewise. Consequently the real
(strong) game admits no attacker win inside $Z$ from that position, at any
depth.

*Proof.* Cell potential $\varphi(x) = \sum_{w \ni x \text{ live}}
\lambda^{-d(w)}$. Defender strategy: claim $y_1 = \arg\max \varphi$ (all live
windows through $y_1$ die: $\Phi$ drops by exactly $\varphi(y_1)$),
recompute, claim $y_2 = \arg\max \varphi'$.

*Round non-increase.* After $y_1, y_2$, every unclaimed cell has current
potential $\le \varphi'(y_2)$ (removals only decrease $\varphi$), and
$\varphi(y_1) \ge \varphi'(y_2)$. Attacker's first stone multiplies the
weight of each live window through it by $\lambda$, gaining
$(\lambda - 1)\varphi''(x_1) \le (\lambda-1)\varphi'(y_2)$; it inflates any
remaining cell potential by at most a factor $\lambda$, so the second stone
gains $\le (\lambda-1)\lambda\,\varphi'(y_2)$. Total attacker gain
$\le (\lambda^2 - 1)\varphi'(y_2) = 2\varphi'(y_2) \le \varphi(y_1) +
\varphi'(y_2)$ = defender's removal. So $\Phi$ is non-increasing over each
defender-then-attacker round. **This is where the stone budget enters: the
inequality is exactly $\lambda^2 \le 1 + q$ with $q = 2$ — the base
$\sqrt{3}$ is the (2:2) rule, arithmetised.**

*No completion.* Completing a window requires a live $d \le 2$ window at an
attacker-to-move instant, which alone contributes $\ge \lambda^{-2} = 1/3$ to
$\Phi$. Under (a), $\Phi < 1/3$ holds at every defender instant by
non-increase, and attacker instants inherit it (defender moves only decrease
$\Phi$). Under (b), the attacker's un-answered pair gains at most
$(\lambda^2-1)\max_x \varphi(x) \le 2\Phi$, so $\Phi' \le 3\Phi < 1/3$ at the
next defender instant, and no $d\le2$ window existed at the start
($\Phi < 1/9 < 1/3$); reduce to (a). $\;\blacksquare$

Three structural remarks, each load-bearing:

1. **Consistency with pinning.** Any obligation weighs ≥ 1/3, so the
   certificate *never* fires while the defender is pinned — it fires only on
   exhausted zones. It is the formal "this wire is dead" detector.
2. **Zone-locality is forced, and that is informative.** Globally
   $\Phi = \infty$ (infinitely many empty windows at 1/27 each): the attacker
   can always rebuild potential in virgin space, so no global potential bound
   exists — the potential-side echo of verdicts Theorem 1's "no pairing at
   k=6". Local refutation + locality lemma is the *only* shape a fragment
   refutation can take, and it is exactly the shape gadget verification needs.
3. **Empirics 🟢.** `cert_selftest` in proof_solver.json (full run): 76 root
   fires on 400 defender-dense random zones, 0 false prunes against depth-3
   no-certificate fragment search. (The smoke test checks the fragment only;
   the theorem covers all strategies — the proof above is the authority, the
   test is a sanity harness for the implementation.)

## 4. Where hexanacci actually lives — closing the 2026-07-08 question

The 07-08 note ([2026-07-08-hexanacci-and-mdl-policy-prior.md](2026-07-08-hexanacci-and-mdl-policy-prior.md) §1)
asked: the measured line-shift constant is *pentanacci* (1.965948), so where
would order 6 legitimately appear? Answer: **it depends on how many colours
the constraint sees, and the two answers are the two research lines.**

| object | language | recurrence | Perron root | Pisot? | which line |
|---|---|---|---|---|---|
| corpus capacity (both players constrained) | 2 symbols, no 6-run of *either* | order k−1 = 5 | pentanacci ≈ 1.965948 | ✓ (max conj. 0.871) | **A** — measurement (`line_automaton.json`) |
| attacker-live capacity (one player constrained) | {A, not-A}, avoid $A^6$ | $f(n) = \sum_{i=1}^{6} f(n-i)$, order 6 | **hexanacci ≈ 1.983583** | ✓ (max conj. 0.906) | **B** — mechanism: the solver's per-line automaton |

Sanity check of the k vs k−1 split at k=2: avoiding runs of one symbol
("no 11") gives Fibonacci/φ (2-bonacci); avoiding runs of both symbols gives
the alternating strings, growth 1 (1-bonacci). Same dichotomy, six levels up.

The solver's per-line state is precisely the one-colour automaton: run-length
0–5 of attacker stones with the 6-state absorbing win; window deadness is the
automaton leaving its live band. So the hexanacci constant is not corpus
numerology — it is a fact about the growth of *that specific language*
(sequences a single line can hold before a window dies). Per-line live
fraction decays as $(\psi_6/2)^n$ — 0.808 at n = 30, `one_colour_live_fraction`.

**Correction (2026-07-20): this is NOT the mechanism behind the measured
search cull, and the two should not be conflated** (the 2026-07-19 version
said the culling was hexanacci's "operational face" — wrong; caught on
review). The solver never builds or walks the per-line automaton; the
actual cull comes entirely from `_forcing_pairs`'s τ-filtering over a
threat-driven candidate generator, an unrelated mechanism. What the cull
actually measures, honestly stated: on the full depth-3 mined sweep (111
positions × 2 attackers, 1,293 OR-node visits total across the resulting
search trees), the naive baseline of `arena.candidates` pairs
(cells *adjacent to an existing stone* — the repo's own move-generator
baseline, already far smaller than "every legal cell on the infinite
board," so the ratio below is relative to that baseline, not an absolute
state-space bound) averages 172.4 pairs/OR-node; `_forcing_pairs` narrows
this to 17.7 generated, of which 5.0 are actually forcing ($\tau\ge2$) —
**2.9% of the adjacency baseline**. The ratio tightens with search depth on
the same generator: 5.9% at depth 2 (quick run) → 2.9% at depth 3 (§6
prediction 3, first two data points now in) — consistent with locality
(threats saturate as the position develops) but not yet attributed to any
specific closed-form growth rate; hexanacci is not that rate.

So the original hunch — "hexanacci relates to the game rules and the stone
ratio" — still lands, just narrower than originally framed: it is a real
Pisot constant of a real automaton the game's win-length induces, sitting
alongside (not causing) the empirically-measured search cull, which has an
independent, threat-structural explanation. Three places the k=6/budget-2
arithmetic shows up rigorously:

1. $\psi_6$ = capacity of the attacker-live line language (WIN_LENGTH = 6,
   the rules' k);
2. $\lambda = \sqrt{3} = \sqrt{1+q}$ = the certificate base (the 2-stone
   budget, the rules' p:q);
3. the obligation tiers $d \le 2$ (one-turn) and $d \le 4$ (pair-reachable)
   = deficit arithmetic modulo the budget — the AP structure of windows
   quotiented by the placement rule.

The 07-08 doc's third object — the 3-axis *coupled* transfer matrix — remains
open and is still the right candidate for the substitution inflation constant
(SPEC.md §7 Q4); nothing here computes it.

## 5. The 3-SAT programme: what exists, what's still missing (revised 2026-07-20)

What the Discord sketch needs, in solver-checkable units — with an honest
accounting of how much of a full NP-hardness reduction this actually is
(not much yet; the review was right to flag the previous version as moving
too fast here):

- **Wire (partial 🟡)**: a τ = 2 chain whose hitting pair is *unique* at
  every step (defender reply forced ⇒ the play line is a path, not a tree).
  Battery case `single_open3_rail` 🟢 verifies the atomic step: at least one
  candidate forcing pair pins the defender to a unique reply (checked
  directly, not assumed — see the revised battery), and the fragment then
  genuinely exhausts (`refuted_fragment`, zero candidate-list truncation).
  **The open construction problem 🔶 is the re-arming wire**: a periodic
  τ = 2 motif that regains own-≥3 material as it advances, so the chain can
  extend indefinitely rather than dying after one step. The natural tier for
  it is proto-obligations (own ≥ 3, edge ≤ 3 — the atom miner's rail/bridge
  motifs, SPEC.md Line B provenance table). **Nothing here searches for one
  yet** — this is a construction problem, not a result.
- **Variable (specified, unverified as a gadget) 🔶**: a position whose
  obligation family has **exactly two** hitting pairs — the defender's
  forced choice *is* the truth assignment. `hitting_sets_le2` enumerates
  hitters, so "does this position have exactly two hitting pairs" is a
  one-call check; no actual variable gadget (a construction whose two
  replies provably correspond to consistent downstream states) has been
  built or checked.
- **Clause / AND (seed verified, not a general construction) 🟡**:
  τ-additivity over separated, isolation-verified gadgets (Corollary, §2).
  Verified seed only: `double_open3_depth2` shows two sub-threshold inputs
  can jointly push exact τ above 2 — a proof of concept for "simultaneity is
  the gate," not a parametrised clause construction with a checked encoding
  into 3-CNF.
- **Complexity frame — deliberately narrower than "NP-hard" 🔶.** For the
  unique-reply fragment, IF a re-arming wire exists, the winning line is a
  single path of bounded length per gadget, and "attacker forces a win
  within t turns by unique-reply forcing over a fixed gadget graph" would be
  in NP. This is far short of an actual hardness proof: still needed are
  (a) the re-arming wire's existence, (b) a variable gadget verified to
  encode a genuine binary choice with consistent downstream propagation,
  (c) an isolation argument for whole gadget *graphs* (not just pairs of
  gadgets) at the composition corollary's separation bound, (d) a
  polynomial-time encoding of an arbitrary 3-CNF formula into a HeXO
  position under that scheme, and (e) both reduction directions (formula
  satisfiable $\iff$ attacker forces a win). None of (a)–(e) exist yet.
  Symmetrically, failing to find a re-arming wire at some bounded search
  radius (§6 falsifier 1) would show only that *this specific unique-reply
  fragment* has no re-arming construction at that radius — it would **not**
  show "every forcing sequence in HeXO terminates in O(material) turns"
  (the 2026-07-19 version overstated this negative implication too; a
  broader forcing mechanism not captured by the unique-reply fragment could
  still exist). This section should be read as *what a hardness proof would
  need*, not as one in progress with only the last piece missing.

## 6. Falsifiable predictions / next experiments

1. **Re-arming wire existence (one keystone the reduction needs, not the
   only one — see §5) 🔶.** Extend the solver's move generator with the
   proto tier (own ≥ 3 ⇒ edge ≤ 3 hitting sets, defender still pinned when
   τ = 2) and run bounded gadget search over small seeds in radius-R zones
   on Modal. *Falsifier, precisely scoped:* if no re-arming τ = 2 motif
   exists for R up to ~15, that refutes *this specific unique-reply-fragment
   construction* of a wire — it does not show HeXO forcing is bounded-fuse
   in general (a different forcing mechanism outside the fragment could
   still re-arm; the fragment is a sufficient search space for the solver,
   not proven necessary for the game). Either outcome narrows the design
   space and is worth having.
2. **Certificate gap.** Over fragment-`proven` roots, min Φ should be ≥ 1/3
   (they cash obligations); over `refuted_fragment` roots Φ should spread
   down toward 1/9. Collectible from proof_solver.json with one added field.
   *Falsifier:* proven roots with Φ near 1/9 would mean the fragment exploits
   structure the potential can't see — worth knowing either way.
3. **Cull scaling.** forcing/naive branching ratio should *fall* with stone
   count and depth (locality: threats saturate), measured against the
   `arena.candidates` adjacency baseline (§4 — not an absolute state-space
   bound). Two data points in on the post-fix generator: 5.9% (depth 2,
   quick run) → 2.9% (depth 3, full run). Remaining: regress ratio vs
   n_stones on a larger corpus (the whole full sweep is ~9 s local, so scale
   is free) and check whether the `unknown` fraction (candidate-list caps;
   5.8% of negative verdicts on the current full run) grows or shrinks as
   `max_pairs` is raised — a shrinking `unknown` fraction as the cap rises
   would independently corroborate that the generator's own completeness
   (Lemma 2 case 2's caveat) isn't the thing driving refutations.
4. **The coupled 3-axis Perron root** (07-08 falsifier 1) — unchanged, still
   open, now sharper: the one-colour/two-colour split is settled, so any new
   constant from the coupled automaton is attributable to axis coupling alone.
5. **Win-mechanism breakdown, tracked going forward.** `proven` conflates
   very different strength claims — a pre-existing win-now, a single pair
   reaching τ>2, and a genuine multi-turn forcing chain are not the same
   result. Now tracked per run (`proven_mechanism` in proof_solver.json):
   full depth-3 sweep, 153 proven = 115 immediate win-now (already won
   before the solver did anything) + 18 single-pair τ>2 + 20 genuine
   multi-turn chains. The multi-turn count is new since the completeness
   fix (0 before it, since the missing self-sufficient+spare candidates
   were exactly what several deeper AND-node continuations needed) — a
   useful regression indicator: if this count collapses to near 0 again
   after a future change, treat it as a completeness-regression signal.

## Repro

```
python experiments/run_proof_solver.py --quick    # ~1 s, all sections, depth 2
python experiments/run_proof_solver.py            # full depth-3 sweep, ~9 s
```

Battery (6/6 🟢, including the fork-plus-remote-block regression), cert
self-test (0 false prunes 🟢), constants, cull stats, win-mechanism
breakdown: `evidence/results/proof_solver.json`. Roots-vs-unit-circle and
cull scatter: `evidence/figures/fig_proof_solver_cull.png`.
