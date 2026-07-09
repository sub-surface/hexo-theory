# Pairing thresholds, turn-granularity, and transfinite game values in HeXO

> Status: working theory note, now in its second pass. First pass found a real
> soundness gap in the k=7 pairing proof and read three Hamkins infinite-chess
> papers. This pass **computationally stress-tests** the proposed fix
> (`experiments/run_pairing_capacity_check.py`, `results/pairing_capacity_check.json`),
> finds it fails under dense clustering (a real, verified counterexample, not a
> script bug), writes out the mate-in-$n$ decidability argument properly, and
> reframes the right reference class as infinite Go-style placement games
> rather than infinite chess. Confidence tags: 🟢 solid, 🟡 directional/partial,
> 🔴 open or contradicted.

## 0. Summary

1. **🟢 General pairing-threshold necessity bound**, unchanged from pass one:
   $k \ge 2m+1$ for $m$ win-directions, unifying the hex bound ($k\ge7$) and
   the classical square-lattice bound ($k\ge9$).
2. **🔴 The naive turn-aware fix does not work.** Pass one proposed a
   "triaged" defense (react to immediate threats; proactively pre-empt
   brink windows). I implemented it, stress-tested it computationally, and
   **it loses** — reliably, in about half of trials — once enough
   heavily-overlapping windows are packed into a small region. This is a
   genuine capacity failure (three simultaneous immediate threats from two
   attacker placements, more than the 2-stone budget can cover), verified
   directly in the game log, not an artifact of the test harness. The k=7
   sufficiency question is **more open than pass one left it**, not less.
3. **🟡 Mate-in-$n$ decidability**, now written out properly (§4) rather than
   sketched. I'm confident in this one; it's a clean, close adaptation of
   Brumleve–Hamkins–Schlicht, arguably easier for HeXO than for chess.
4. **Reframing:** HeXO is structurally much closer to Go (or a
   capture-free placement game) than to chess. This matters concretely: the
   right toolkit for SPEC.md's open NP-hardness question (§7 item 6) is
   Go's local-gadget hardness-reduction literature (Lichtenstein–Sipser,
   Robson), not chess's piece-movement-based hardness results — because
   HeXO's interactions are local/window-based like Go's liberty structure,
   not long-range like a chess queen's slide. "Infinite Go" isn't a paper
   that exists (unlike infinite chess/Hex), so this is a methodological
   redirect, not a new citation to lean on.
5. Your CGT "island / free move" question turns out to be the *same
   phenomenon* as the capacity-lemma counterexample, from the opposite side:
   the dense-cluster attack **is** a demonstration that opening many fronts
   at once can be strategically real, computationally verified for the first
   time in this repo rather than left as a hand-wavy worry.
6. Lean: deliberately not started this pass — explained in §2.4 why now is
   the wrong moment.

---

## 1. The Pairing Threshold Theorem, generalized 🟢 (unchanged)

See pass one. $k \ge 2m+1$ is necessary, proven generally; $m=3$ (hex) gives
$k\ge7$, $m=4$ (square) gives $k\ge9$, matching both existing repo numbers
from one argument. The unit-group observation (HeXO's three axes are exactly
the three $\pm$-pairs of $\mathbb{Z}[\omega]$'s six units, whereas the square
lattice's diagonals are a rule bolted onto $\mathbb{Z}[i]$'s smaller unit
group) still stands and is unaffected by anything below.

---

## 2. The turn-aware sufficiency question: a real, verified negative result 🔴

### 2.1 What was proposed

Pass one's fix: whenever a live window reaches "all 5 free cells
attacker-filled, its protecting domino completely untouched," claim the
domino before the attacker's same-turn double-placement can secure it. The
hand argument was that completing any window forces the attacker through
this "brink" state on some turn $T$, with the earliest possible completion
on turn $T+1$ — giving the defender, who moves in between, exactly enough
budget (at most 2 such brink events per attacker turn, since crossing the
threshold needs 1 dedicated placement and the attacker only has 2).

### 2.2 What the stress test found, and how the model had to be fixed twice

I built `experiments/run_pairing_capacity_check.py` against the actual k=7
matching (reusing `find_k7_pairing()` from `run_pairing_bound.py`, verified
against the same period-6 torus). Two real bugs surfaced before the model was
trustworthy, both worth recording because they're exactly the kind of thing
armchair reasoning misses:

- **First bug (harness):** a scripted attacker plan blindly executed
  precomputed moves without checking the board, once placing a stone on a
  cell the defender had already claimed — impossible in a real game (no
  captures). Fixed by making the attacker fully adaptive, re-checking the
  live board state every turn (`run_multifront`).
- **Second bug (model, not harness) — a real gap in the *strategy*, not the
  code:** two windows that overlap heavily (e.g. offset by 1 or 2 along the
  same axis) can have one window's free cells incidentally fill the *other*
  window's domino cell, as an ordinary side effect of unrelated progress. The
  original "domino completely untouched" brink check can't see this — it
  requires *zero* prior contact — so a window contaminated this way was
  never flagged, and the simulated defender did nothing while it quietly
  approached completion. Fixed by adding a **first-priority tier**: block
  any live window that has reached an ordinary 6-of-7 immediate threat,
  *regardless of how it reached that state*. This is not exotic — it's just
  "block the obvious one-move win," something any competent defense already
  does — but the original brink-only formulation had a blind spot for it.

With both fixes in place, every hand-picked adversarial case from pass one
(sequential single-window grab, two disjoint fronts, two fronts sharing an
axis, two fronts sharing a domino) resolves cleanly: **the defender wins all
of them**, and a moderate random multi-front test (30 trials, 40 fronts each
scattered across a 400-cell span, 200 turns) never lost either.

### 2.3 Then a genuine failure, at higher density

I then specifically tried to construct the scenario most likely to break the
"at most 2 new obligations per attacker turn" accounting: pack many windows
(60) into a *small* region (radius 12, ~470 cells) so their free cells and
dominoes overlap heavily, rather than scattering them across open space.
Result, at full scale (30 trials): **the attacker won 15 of 30 trials**, and
in several of those, the log shows an explicit, unrecoverable **tier-1
overrun** — three separate windows simultaneously reaching an immediate
(6-of-7) threat from just two attacker placements in one turn, more than the
2-stone budget can block. One example, verified directly in the game log
(`results/pairing_capacity_check.json`, `dense_cluster` trial 4, turn 57):
placements at $(2,-2)$ and $(3,-3)$ simultaneously pushed three different
windows to immediate-threat status; the defender's two claims
($(2,-3)$, $(-2,2)$) covered two of the three; the third window — axis
$(1,-1)$, cells $(-1,1)$ through $(5,-5)$ — completed on the following turn.

This is not a harness artifact (I checked: `check_attacker_win` only counts
genuine 7-of-7 windows, the tier-1 detector only counts windows with exactly
one true empty cell remaining, and the log shows the exact cells and the
exact overrun count). **The proposed triaged defense is unsound against a
sufficiently dense multi-front attack.** The mechanism is exactly what a
single cell lying on three axes at once makes possible: one placement can
simultaneously be "the last free cell" for several different windows on
different axes through it, and enough of these can coincide to produce more
simultaneous immediate threats than any O(1)-per-turn reactive rule can
clear.

### 2.4 What this changes, and what it doesn't

- The **necessity** bound (§1, Theorem A) is completely unaffected — it's a
  pure counting argument, independent of any specific defense.
- The **static covering property** (every 7-window contains a domino) is
  still true and still verified.
- What's now genuinely unresolved is whether *any* turn-aware defense closes
  the gap, or whether HeXO's real 2-stones-per-turn rule pushes the true
  pairing threshold for the hex lattice **above** 7. Both are live
  possibilities. A natural next move — not yet tried — is asking whether a
  *sparser* matching (redundant coverage, more than one domino per window,
  trading off against the necessity bound from §1) can survive dense
  clustering where the tight, zero-slack $k=7$ matching cannot; that would
  mean the real turn-aware threshold is some $k^* > 7$, still finite, still
  provable, just not the number currently in SPEC.md.
- **On Lean, given this:** this is exactly why formalizing anything now would
  have been premature — I'd have been asked to prove a claim that turned out
  to be false. Lean becomes the right tool once there's a specific, believed
  -true, cleanly-stated claim (e.g. "no periodic matching survives the
  dense-cluster attack below $k^*$" or a fixed, working defense) worth
  pinning down permanently. Until then, more Python stress-testing is higher
  value per hour than formalization scaffolding.
- **Recommend downgrading SPEC.md's "Pairing threshold theorem" further** —
  pass one suggested 🟢→🟡; this pass's finding is closer to 🔴 on the
  sufficiency half specifically (necessity stays 🟢). The correct framing for
  SPEC.md is now: *"no pairing strategy exists below k=7 (proven); whether
  one exists at k=7 under HeXO's true turn rule is open, and a natural
  candidate fix has been computationally falsified."*

### 2.5 The connection to your CGT "island" question

This result is a direct, computational answer to the "is opening a new front
ever strategically real" question from the CGT `+₂`-sum thread
(`docs/theory/2026-07-08-two-move-sum-execution-paused.md`) and to your
worry about free moves making islands strong: **yes, provably, in this
specific adversarial sense** — a multi-front attack that no single-front
analysis would predict is dangerous, defeats a defense that handles every
single-front and moderately-scattered case cleanly. This doesn't resolve the
general CGT question ("when does `solve(A ∪ B)` exceed `max(solve(A),
solve(B))`") but it's a concrete, verified instance of the same underlying
phenomenon, found by exactly the kind of adversarial multi-front construction
the paused thread was trying to characterize abstractly. Worth citing there
when that thread resumes.

---

## 3. Locality, transfinite game values, and the right reference class 🔴/🟡

### 3.1 Go, not chess, is the closer relative

You're right that this needs correcting. Chess's transfinite-value machinery
(§3 of pass one) is genuinely the right tool for *game-value* questions
(ordinal ranks, mate-in-$n$ decidability) because that machinery is about the
temporal/recursive structure of *any* open game and doesn't actually depend
on piece movement — Hamkins' method transfers cleanly (§4 below). But for
**what kind of object HeXO's positions are** — how threats propagate, what a
"gadget" looks like, what the right complexity-theoretic reference class is
— Go is the much closer relative, and chess is actively the wrong intuition
pump:

- Both HeXO and Go are **placement games**: nothing moves once played (Go
  removes captured groups; HeXO doesn't even do that — positions only grow).
  Chess's entire transfinite-value mechanism, recall, depends on the
  interaction of unbounded-distance moves with *bounded-speed* pieces — HeXO
  has neither moving nor bounded-speed pieces, so that specific machinery
  (beyond the game-value formalism itself) doesn't describe HeXO's dynamics.
- Interactions in both HeXO and Go are **local**: a Go stone matters through
  adjacency and its group's liberties; a HeXO stone matters through the
  $\le18$ windows through it (`engine/analysis.py`'s `_all_windows`). A chess
  queen's single move can matter across the entire board instantly — nothing
  in HeXO or Go does that.
- **Complexity theory already reflects this split.** Chess-family hardness
  results (Fraenkel–Lichtenstein: generalized chess is EXPTIME-complete) are
  proved by relaying signals across the board using long-range piece
  movement — a technique with no HeXO analogue. Go-family hardness results
  (Lichtenstein–Sipser 1980: generalized Go is PSPACE-hard; Robson 1983:
  with superko, EXPTIME-complete) are proved with **local gadgets** — small,
  fixed board patterns wired together to encode AND/OR/NOT gates or QBF
  clauses, using only local capture/life-and-death interactions. That's
  exactly the shape of construction SPEC.md's open item 6 already gestures
  at ("variable gadgets as forced ladders, clause gadgets as shared threat
  cells") and exactly what the existing $\tau$-atom library (rail/bridge
  motifs, `papers/hexconnect6_atom_miner_results/`) is already positioned to
  supply. **This is the concrete payoff of the reframing**: it points the
  NP/PSPACE-hardness question at the right existing literature and the right
  existing repo machinery, where the chess framing pointed at neither.

One real caveat, worth flagging rather than glossing over: Go's gadget
constructions frequently use **capture** (a life-and-death fight resolving a
local sub-position one way or the other, sometimes repeatedly, to simulate a
variable's value being read/tested). HeXO has no capture — every cell, once
set, is permanent. This could make gadget design *easier* (no need to guard
against ko or repetition) or *harder* (no way to let a local sub-position's
status be tested without permanently committing it) — I don't know which
yet, and "infinite Go" isn't a paper I can point at for a ready answer, since
as far as I can find, no one has published on it the way Hamkins has for
chess and Hex specifically. This is a genuinely open methodological question
for whoever picks up SPEC.md item 6 next, not something I'm resolving here.

### 3.2 The locality lemma and the multi-front question, restated

The gestation-time lemma from pass one — a single far-away stone can't force
anything, because $\tau>2$ needs a hard-floor number of stones no matter
where they're placed — still holds; it was never about pairing dominoes
specifically, and §2's finding doesn't touch it. What §2 *does* sharpen is
the "successive fronts" half of the open question from pass one: I said then
that whether an attacker can sustain unbounded delay via serial front-opening
was open. The dense-cluster result shows something adjacent but different —
not unbounded *delay*, but a genuine *capacity* failure of one specific
defense under *simultaneous*, tightly-packed fronts. Whether this bears on
the transfinite-value question (does HeXO have positions of ordinal value
$\ge\omega$) is still open, and now slightly more concerning than pass one's
optimistic read: if a natural pairing-flavored defense can be defeated by
packing threats densely enough, it's less obvious that *no* mechanism in
HeXO can manufacture escalating, opponent-controlled delay, even without
bounded-speed pieces. I don't have a resolution here — flagging the
connection honestly rather than either overclaiming safety (pass one) or
overclaiming danger.

### 3.2b Resolving the new-front question with a budget argument (2026-07-08, part 2)

§3.2 left "can an attacker sustain unbounded delay by serially opening new
fronts" open. It has a cleaner answer than I gave it, arrived at while
building `_forced_result` (`competition/arena.py`, ported to
`hexo/hexgo-rs/src/search.rs`'s `forced_result`) — the exact, non-heuristic
tactical solver that decides whether a position is forced win/loss within
the mover's remaining placements this turn.

**Minimal stone counts, derived from `_forced_result`'s own definitions.**
A *brink* window needs `WIN_LENGTH-2 = 4` of a player's stones, live,
$\le 2$ empty cells (completable within one full 1-2-2 turn). Two brink
windows on different axes can share at most one cell (two lines in
different directions meet the lattice at one point), so the cheapest
2-window fork is $1 + 3 + 3 = 7$ stones (one shared corner, three more per
arm) — but this is beatable by a defender with a full turn (`remaining=2`
in `forced_result`'s signature): play one cell in each window's empty pair,
2 cells for 2 windows, exactly the defender's budget. To force
*unconditional* loss against a full defensive turn you need **three
pairwise-uncoverable brink windows** (pigeonhole: 2 cells can't hit 3
disjoint sets) — the `_forced_result` `LOSS` branch's `remaining >= 2` case
literally checks this. Minimum stones for three genuinely disjoint brink
windows (no shared corners) is $3 \times 4 = 12$; sharing corners can only
lower this, not raise it, so 12 is a loose upper bound on the true minimum,
not a tight one — worth pinning down exactly if this thread gets picked up
again, but not load-bearing for what follows.

**The budget argument.** The defender places exactly 2 stones/turn,
always. A single "warm" front (some live window already at 3-4 of its 6
cells) costs the defender roughly 1 cell/turn to keep contained once it's
live (this is Tier-2 of the 2026-07-08-part-1 triaged defense in
`experiments/run_pairing_capacity_check.py`). Two simultaneous warm fronts
exactly exhaust the budget (1+1=2). **A third simultaneous, comparably
-mature front is therefore the precise point where a single-defender
budget provably breaks** — consistent with, and a mechanistic explanation
for, §2's dense-cluster failure. This directly resolves the original
mate-in-$\omega$-flavored speculation: opening fronts serially is *not* a
free, unbounded escalation. Each fresh front needs its own gestation ($\sim
4$ of the attacker's own turns to reach even the weakest 7-stone
2-fork stage, from the count above), and during that gestation the
defender — running the identical `forced_result` detector — has equal
tempo to resolve or neutralize earlier fronts before the new one matures.
An attacker only wins the delay game by keeping **two or more fronts
perpetually, simultaneously live**, which is a strictly harder combinatorial
commitment than "place one stone arbitrarily far away and repeat" — the
original speculation's implicit free-lunch framing doesn't survive contact
with the budget count.

**But the empirical data says this is a smooth degradation, not a cliff,
and that matters for how to use it.** `results/pairing_capacity_phase_diagram.json`
(k=7, cluster_radius=12) shows attacker win rate climbing gradually with
front density — 2.5% at n_fronts=10, 7.5% at 20, 12.5% at 30, 30% at 40,
47.5% at 60, 67.5% at 80 — not a step function at "3 fronts." That's
expected: those trials scatter many fronts at *random, uncorrelated*
maturity, so what actually matters is the *expected number simultaneously
mature at any given time*, not a hard count. The clean "3 pairwise
-uncoverable brink windows now" criterion above is a **proven sufficient**
condition for forced loss (and is exactly what `forced_result` checks
NOW-cast, at zero risk of false positives). A *pre-emptive* "should I
invest a move opening a new front before anything is fully mature"
judgment is a different, inherently probabilistic question the theorem
doesn't answer — the phase-diagram curve is the right kind of evidence to
calibrate that judgment, not a proof to derive it from. Section 8 below
specifies this as an explicit, ablatable heuristic (front-count/race
signal), not a theorem, to avoid this repo's now-familiar mistake of
shipping an "obviously good" untested feature (see
`competition/2026-07-08-optimal-play-and-bot-design.md` §3 on the
`fork_bonus` ablation).

### 3.3 The computable-strategy point, unchanged

Still holds, still worth restating precisely: any bounded *or* unbounded
self-play corpus built from this repo's bots only ever bounds the
**computable-strategy** game value, per Evans–Hamkins' explicit example of a
chess position that's a win under computable play and a draw without that
restriction. Nothing in §2 changes this; if anything, discovering that a
plausible-looking computable defense fails under adversarial pressure is a
small extra data point for taking that caveat seriously.

---

## 4. Mate-in-$n$ is decidable in HeXO 🟡 (written out properly this time)

### 4.1 The target claim

For any finite HeXO position $p$ and $n \in \mathbb{N}$: whether the player
to move can force a win in at most $n$ further own-moves is decidable,
uniformly in $p$ and $n$, with a computable optimal strategy — the direct
analogue of Brumleve–Hamkins–Schlicht's (BHS) Main Theorem 1 for infinite
chess.

### 4.2 The reduction

BHS's method: fix a finite piece-type list $A$; since chess never introduces
new pieces (captures only remove), the reduct $\mathfrak{Ch}_A$ (positions
built from at most $|A|$ pieces) is representable as tuples of fixed-length
strings — one triple of strings per piece (alive/captured bit, signed-binary
$x$, signed-binary $y$) — with every relevant relation (attack, legal move,
check) shown to be *regular* (recognizable by a read-only multi-tape Turing
machine), because sliding-piece movement only needs addition and comparison,
which read-only automata can check. Automatic structures have decidable
first-order theories (Khoussainov–Nerode), and mate-in-$n$ is a bounded
($\Sigma_{2n}\vee\Pi_{2n}$) first-order formula in this structure, so it's
decidable, uniformly, with an extractable strategy.

**HeXO's version, concretely.** Fix $M = |p| + 2n$ — an *exact* bound, not
merely an upper one, since `../hexo/game.py:53`'s refusal to place on an
occupied cell (confirmed directly, no capture relation exists anywhere in
the file) means a mate-in-$n$ query from $p$ can only ever involve the
stones already in $p$ plus at most $2n$ new ones, and none can ever be
removed. Represent a position in the reduct $\mathfrak{Hx}_M$ as $M$ ordered
"slots," each a triple $\langle j, x, y\rangle$: $j \in \{0,1,2\}$
(unplaced / attacker-color / defender-color — simpler than chess's binary
alive/captured bit, since there's no capture state to track at all), and
$(x,y)$ the signed-binary cell coordinates (default value if unplaced,
exactly as BHS handle captured pieces' dummy coordinates). This gives every
position in $\mathfrak{Hx}_M$ a representation as a fixed number ($3M$) of
finite strings, the same shape BHS use.

The relations needed are, if anything, simpler than chess's:

- **Occupied$(p,x,y)$**: does some placed slot in $p$ sit at $(x,y)$? A
  bounded ($M$-way) disjunction of equality checks on signed-binary strings
  — regular.
- **OneMove$(p,q)$**: $q$ differs from $p$ by setting exactly one previously
  unplaced slot to a specific $(x,y)$ not already Occupied in $p$, with the
  correct color for whichever player's placement this is (tracked by an
  auxiliary bounded counter for "how many of the current turn's placements
  are done," itself just a 2-valued bit given the 1-2-2 rule) — regular, and
  structurally simpler than chess's `OneMove_i` because there is no
  piece-type-dependent case split (no bishops/rooks/knights each needing
  their own attack-relation proof) — every HeXO move relation is the same
  one rule.
- **WinningLine$(p,\text{axis},\text{start})$**: cells
  $\text{start}, \text{start}+u,\dots,\text{start}+5u$ (for $u$ one of the
  three fixed unit steps) are all Occupied by the *same* color — a bounded
  conjunction of Occupied checks plus equality of the color bit across all
  six, again regular; if anything a cleaner base case than chess's
  checkmate condition, which needs the recursive attack/pin apparatus just
  to define "in check" before mate can even be stated.
- **WhiteWins$_n(p)$ / BlackWins$_n(p)$**: defined by the identical recursion
  BHS use (base case $n=0$: someone has already completed a line; inductive
  step: exists-a-move-to-a-value-$\le n$ position, for-all-opponent-replies
  it's-still-value-$\le n$), giving the same $\Sigma_{2n}\vee\Pi_{2n}$
  complexity.

Since $\mathfrak{Hx}_M$'s domain and every relation used are regular, it's an
automatic structure, its first-order theory is decidable, and mate-in-$n$ is
expressible in it — so mate-in-$n$ is decidable, uniformly, with a
computable optimal strategy extracted the same way BHS do (search increasing
$n$ for the smallest mate-in-$n$ value, then follow the value-reducing
strategy).

### 4.3 What this does and doesn't buy

This is a genuine, if unglamorous, theorem — clean scope, no hand-waving,
directly citable. It is emphatically **not** a way to settle whether HeXO
has a forced win at all (unbounded $n$) — BHS are explicit that this remains
open even for chess, not known to be arithmetic or hyperarithmetic, and §3
above gives good reason to keep taking that seriously here too. It also
isn't a *practical* algorithm — automatic-structure decidability procedures
are not competitive with the alpha-beta search this repo's opening tablebase
already uses (`papers/.../opening_tablebase_results`); the value of this
theorem is that it *explains and guarantees* what that tablebase search is
already doing informally (searching a well-defined, decidable predicate),
not that it replaces it.

---

## 5. Player asymmetry — unchanged 🟢

Still holds exactly as pass one described: pairing strategies are
turn-order-agnostic by construction, so the single-stone opening doesn't
touch them; §2's failure mode has nothing to do with P1/P2 asymmetry either
(the dense-cluster attacker isn't exploiting tempo, it's exploiting
geometric density). The standing methodological rule from pass one — check
every *non*-pairing strategy against both roles separately — still applies
and is untouched by this pass's findings.

---

## 6. Physics analogies — unchanged 🟡

See pass one §6 for the full treatment (crystallographic selection rules as
the real Noether-adjacent structure; RG spectral gap as a sharper Pisot
check; Yang–Mills as an honest metaphor, not a bridge; Dirichlet density of
primes $\equiv 1 \pmod 3$ as the one place actual prime distribution matters
here). Nothing in this pass changes any of it.

---

## 7. Revised shape of the paper

The pairing-threshold story is now genuinely two papers' worth of honesty
apart from where pass one left it — which is fine, and worth saying plainly
rather than papering over:

1. **What's fully done, right now, no further work needed:** Theorem A
   (§1, general necessity bound, $k\ge2m+1$), the unit-group observation, and
   mate-in-$n$ decidability (§4). These three are clean, complete, and don't
   depend on anything unresolved.
2. **What's now the paper's real open problem, correctly stated:** does
   *any* computable turn-aware strategy pair the hex lattice at $k=7$, or is
   the true turn-aware threshold $k^*>7$? Section 2 gives a genuine, verified
   negative result (one natural candidate fails) plus a concrete next
   experiment (does a redundant, non-tight matching survive the same
   dense-cluster attack?). This is a *better* paper problem than pass one's
   framing, not a worse one — it's now backed by an actual counterexample
   instead of an unresolved hand-argument, and finding $k^*$ (whatever it
   is) would be a real, citable result either way.
3. Locality/transfinite values (§3) stays open, now correctly anchored to
   Go-style placement-game intuition rather than chess-style
   movement-game intuition, with the NP-hardness connection (§3.1) as a
   concrete, actionable redirect for SPEC.md item 6.
4. The self-play-evidence caveat (§3.3) stays as its own short methodological
   section, unaffected by this pass.

---

## 8. Falsifiers and concrete next steps

1. **Does a redundant (non-tight) matching survive the dense-cluster attack?**
   The zero-slack $k=7$ matching has no spare protection anywhere, which is
   plausibly *why* it's vulnerable to simultaneous multi-window pressure. A
   matching with, say, 2 protecting dominoes per window (trading against a
   higher $k$, per §1's formula with a redundancy factor) might survive where
   the tight one doesn't. Cheapest next experiment: extend
   `run_pairing_capacity_check.py` to build and test such a matching at, say,
   $k=9$ or $k=13$, and re-run the same dense-cluster stress test.
2. **What's the actual worst-case density** — is there a clean formula for
   "how many mutually-overlapping windows can be packed into a radius-$R$
   ball," and does it predict the observed failure threshold (radius 12,
   ~60 fronts)? This would turn the empirical counterexample into a real
   theorem about *why* the tight matching fails, not just *that* it does.
3. **Mate-in-$n$**, write the formal reduction all the way out (§4 is a
   solid sketch; turning it into an actual paper section is mostly
   transcription at this point, not new mathematics).
4. **Go-gadget feasibility check** (§3.1): can a HeXO $\tau>2$ obligation
   family (already mined in `papers/hexconnect6_atom_miner_results/`) encode
   a NOT gate without capture — i.e., is there a local motif whose forced
   response flips a binary "read" elsewhere without ever needing a stone to
   be removed? A single worked gadget would be the concrete first step
   toward SPEC.md item 6, and would resolve the "does capture-free placement
   support gate gadgets" uncertainty flagged in §3.1.
5. Lean: revisit once (1) or (2) produces a stable, believed-true statement.

Recommend downgrading `SPEC.md`'s pairing-threshold entry per §2.4.
