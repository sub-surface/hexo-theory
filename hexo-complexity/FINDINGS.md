# Death HeXO: first structural and empirical investigation

**Date:** 2026-07-20  
**Canonical variant:** infinite Connect-6 on the A2/Eisenstein lattice, 1-2-2
turns, simultaneous enemy-bracket death after every atomic placement.  
**Evidence:** [evidence/results/death_hexo.json](evidence/results/death_hexo.json)  
**Reference implementation:** [death_hexo.py](death_hexo.py)

## Executive verdict

Death HeXO is not a small perturbation of HeXO. It crosses three mathematical
boundaries at once:

1. **From monotone positional play to reversible reachability.** A blocker can
   be killed, a previously dead winning window can become live again, and the
   number of stones can fall after a placement.
2. **From short play to loopy play.** A legal placement may die immediately and
   return its cell to empty. There are finite cycles returning the complete
   game state to itself.
3. **From a length-6-only arithmetic to a coupled length-3/length-6
   arithmetic.** Death certificates are bichromatic 3-term arithmetic
   progressions; wins are monochromatic 6-term progressions on the same three
   Eisenstein axes.

The strongest early result is the **opening inversion theorem**: White can
always use the first two-stone turn to bracket and kill Black's unique opening
stone. Up to translation and D6, White can force the game after the first round
into the state

```text
W . W     Black to place two
```

This does not prove that White wins the infinite game. It does prove that the
usual "Black has an extra harmless stone" strategy-stealing intuition is the
wrong starting point.

The arithmetic story is equally strong. Stable fully occupied line words have
Fibonacci growth and entropy base phi. Stable words with vacancies have growth
base

```text
lambda_D = 2.831177207...,
lambda_D^3 - 2 lambda_D^2 - 2 lambda_D - 1 = 0,
```

and `lambda_D` is Pisot. These constants come exactly from the death rule's
finite-state constraint. They are entropy bases, not yet quasicrystal inflation
constants.

The first iterative follow-up now supplies an exact geometric object as well:
an open family of irrational-height colorings that are simultaneously
aperiodic, death-stable, Connect-6-free, and pure-point diffractive. Every
finite erasure can be restored without a death or win. This is genuine passive
self-repair, but not yet a strategy that withstands hostile off-pattern moves.

## Confidence ladder

| Status | Finding | Basis |
|---|---|---|
| **Proved** | simultaneous cleanup is idempotent and D6/color equivariant | direct local argument; implementation at `death_hexo.py:35-53` |
| **Proved** | White can erase Black's opening on the first reply turn | explicit two-placement strategy; regression at `tests/test_death_hexo.py:68` |
| **Proved** | at most seven stones die after one atomic placement, and seven is attainable | locality bound plus explicit star witness at `death_hexo.py:502` |
| **Proved** | the game has a four-placement state cycle | explicit null-move construction at `death_hexo.py:479-499` |
| **Proved** | stable occupied line words grow as Fibonacci/phi | four-state transfer automaton and exact recurrence |
| **Proved** | stable line words with empty cells grow with a cubic Pisot root | nine-state transfer automaton and exact recurrence |
| **Proved** | an open family of full-board, aperiodic, six-free, pure-point colorings exists | irrational-height construction and directional increment bounds |
| **Proved** | every finite erasure of one of these colorings can be repaired in arbitrary order | every intermediate board remains a subset of the stable, six-free target |
| **Proved** | wrong-color point invasions are rejected on phase measure `1-sqrt(3)/4`, while the remainder freeze | exact 38-context phase partition |
| **Exhaustive finite result** | Death Connect-3 on a line of length 5 is a forced White win; ordinary control is a draw | complete 211-state reachability graph with attractor certificate |
| **Exhaustive finite result** | the provisional `n=2k-1` White-win law fails at full `k=6`: length 11 is a draw, although the central Black opening loses | complete 367,914-state graph / 1,489,501 edges |
| **Directional** | 2-D stable-coloring entropy extrapolates to about 0.346 bits/site | exact rhombus counts only through `8 x 8`; finite-size fit |
| **Exploratory** | capture-aware local policies exhibit high turnover and state recurrence | 24 randomized games/group, wide intervals, bounded local policies |
| **Open** | infinite-board optimal outcome, complexity class, dynamic forcing algebra, diffraction class | not settled by this first suite |

## 1. Canonical rule

Let the board be a finite-support map

```text
B : Z[omega] -> {empty, Black, White}.
```

The three unoriented unit axes are

```text
u1 = (1, 0), u2 = (0, 1), u3 = (1, -1).
```

A stone of color `p` at `c` is vulnerable when, for at least one axis `u`,

```text
B(c-u) = B(c+u) = opponent(p).
```

After each atomic placement, mark every vulnerable stone on the post-placement
board and remove all marked stones simultaneously. Then test the mover's
surviving stones for a length-6 win. If the placed stone dies, the placement is
still spent. If its cell is empty again, the second placement of the same turn
may legally reuse that cell.

This is implemented by `vulnerable_stones` at `death_hexo.py:35`,
`resolve_deaths` at `death_hexo.py:47`, and the state transition
`DeathHexGame.make` at `death_hexo.py:239`.

### Why atomic simultaneous cleanup

The user-level rule leaves one serious ambiguity: cleanup after each placement
or after the complete two-placement turn. The canonical choice is **after each
placement**, because the upstream engine is atomic (`../../hexo/game.py:49`),
tests a win after each stone (`../../hexo/game.py:72`), and only then advances
the 1-2-2 phase (`../../hexo/game.py:80-87`). It also makes each displayed board
a stable board.

Simultaneity is not cosmetic. On the one-dimensional word `B W B W`, the two
interior stones are both vulnerable. Simultaneous cleanup deletes both. A
left-to-right sequential cleanup deletes the first and thereby saves the
second. Among all `3^10 = 59,049` ternary length-10 words, 7,184 (12.2%) have
an order-sensitive outcome under sequential deletion. An unspecified capture
order would therefore define a materially different game.

Turn-end simultaneous cleanup is retained as an explicit sensitivity mode, not
silently conflated with the canonical game.

## 2. Local death algebra

### Theorem 1: cleanup is idempotent

Let `D(B)` delete every vulnerable stone in `B` simultaneously. Then

```text
D(D(B)) = D(B).
```

**Proof.** Cleanup only deletes stones. A surviving stone was not flanked by two
enemy stones in `B`. Deletion cannot create either missing enemy flank, so it
cannot make the survivor vulnerable in `D(B)`. There is no second death wave.

This is not the same as saying mutual death is impossible. Stones can be marked
using one another before the simultaneous deletion, as in `B W B W`.
Exhaustive checks over every ternary line through length 10 found zero
idempotence violations; the unit regression checks every word through length 7
at `tests/test_death_hexo.py:41`.

### Theorem 2: the rule preserves the lattice symmetries

The death predicate depends only on opposite unit-neighbour pairs and color
inequality. It is equivariant under all 12 elements of D6, translations, and
global color exchange. The 1-2-2 opening rule breaks player/tempo symmetry, but
the local rewrite does not. The D6 regression is part of the test suite.

### Theorem 3: seven is the sharp one-placement death bound

Assume the pre-placement board is stable. Adding a stone at `c` can newly affect
only:

- `c` itself, which may be bracketed on any of three axes; and
- the six neighbours of `c`, for which the new stone may supply one enemy
  flank.

No more distant stone sees a changed adjacent pair. Hence at most seven stones
can die. The bound is attained: put six enemy stones around an empty centre and
six friendly radial supports at distance two, then play the centre. All six
enemies die and the new centre stone is killed by the enemy ring. Net material
change is `-6`.

The witness is `annihilation_bomb_position` at `death_hexo.py:502`, tested at
`tests/test_death_hexo.py:90`, and rendered in
[fig_death_hexo_mechanics.png](evidence/figures/fig_death_hexo_mechanics.png).

### Exact radius-2 capture spectrum

The experiment exhausts all `3^12 = 531,441` assignments of the six neighbours
and six radial supports around an empty centre, then plays Black at the centre.
Under the uniform local-context measure:

| Quantity | Exact-enumeration result |
|---|---:|
| at least one enemy captured | 0.50673 |
| centre self-dies | 0.29767 |
| mean enemy captures | 2/3 |
| mean total deaths | 0.96433 |
| maximum enemy captures | 6 |
| maximum total deaths | 7 |

The enemy-capture count is binomial under this artificial uniform measure:
each radial direction captures exactly when its neighbour is White and its
distance-two support is Black, probability `1/9`. Thus
`C ~ Binomial(6, 1/9)`. This is a geometry baseline, not a model of strategic
positions. The exhaustive code is `radial_capture_spectrum` at
`experiments/run_death_hexo.py:177`.

## 3. The opening is inverted

### Theorem 4: White erases Black's opening

Suppose Black opens at `c`. Choose any unit axis `u`. White places at `c-u` and
then `c+u`. After the second placement, Black's stone at `c` lies in the pattern

```text
White - Black - White
```

and dies. Neither White stone has two adjacent Black enemies, so both survive.
The turn ends with Black to move and the board exactly `{c-u: White, c+u:
White}`.

This proof works under both atomic and turn-end simultaneous cleanup. It has
three immediate consequences:

1. Black's opening stone is not permanent strategic capital; it is a forced
   capture target.
2. Up to translation and D6, White can collapse the entire opening tree to one
   canonical state.
3. Any strategy-stealing proof for ordinary HeXO that treats an extra own stone
   as harmless needs a new monotonicity lemma. It cannot simply be quoted.

The theorem does **not** imply a White win. Black receives the next full
two-placement turn, and material advantage is not an order relation in this
loopy game.

## 4. This is a loopy game, not a short game

Put White stones at `(-1,0)` and `(1,0)`, leaving `(0,0)` empty. Put Black stones
at `(9,0)` and `(11,0)`, leaving `(10,0)` empty. Let Black be at the start of a
normal two-placement turn.

1. Black plays `(0,0)` twice. Each stone is immediately bracketed by White and
   dies; the two placements are spent.
2. White plays `(10,0)` twice. Each stone is immediately bracketed by Black and
   dies.

The board, player to move, placement phase, and opening-status bit are now
exactly as they were four placements earlier. This is verified by
`execute_null_cycle` at `death_hexo.py:491` and
`tests/test_death_hexo.py:101`.

The correct Conway/Siegel conclusion is precise:

- Death HeXO is not globally a **short** game, so ordinary recursive surreal
  values do not apply to every position.
- Finite regions are finite **loopy reachability games**. Their primary solution
  object is a win/draw/loss attractor, not a number.
- Stoppers, sides, idempotents, and loopy thermography may become useful only
  after identifying a quotient that respects this reachability objective.

The supplied PDF is Aaron Siegel's *Combinatorial Game Theory* front/end matter,
not the chapter text. Its table of contents nevertheless points exactly to
Chapter VI (loopy games), Chapter VII (temperature), and Chapter VIII
(transfinite games): [local PDF](gsm146-endmatter.pdf). The corresponding
[AMS book page](https://bookstore.ams.org/view?ProductCode=GSM%2F146) confirms
the scope, and Siegel's Berkeley dissertation is explicitly titled
[Loopy Games and Computation](https://math.berkeley.edu/publications/loopy-games-and-computation).

### Descriptive complexity does not jump merely because loops exist

A win still has a finite certificate: six surviving stones in a line after
some placement. Therefore "Black eventually wins" and "White eventually wins"
remain open (`Sigma^0_1`) payoff sets. The set of infinite plays in which nobody
wins is closed (`Pi^0_1`). Nontermination changes recursive game values and
search, but it does not by itself raise the Borel rank of the winning event.

This corrects a tempting but invalid inference: loopy is not synonymous with a
higher payoff-set complexity.

## 5. Exact one-dimensional games

The finite-line solver at `experiments/run_death_hexo.py:364` constructs the
entire reachable state graph, including the current player, placement phase,
and opening-status bit. It initializes terminal Black/White wins, iterates the
two reachability attractors to a least fixed point, and labels the unresolved
complement draw. There is no depth cutoff. Every decisive result includes the
value of every root move and a replayable principal variation.

### Root outcomes

All ordinary controls swept through length 9 are draws. Death-rule outcomes are:

| Connect target | Drawn lengths | Forced White-win lengths |
|---:|---|---|
| 3 | 3-4 | 5-9 |
| 4 | 4-6 | 7-9 |
| 5 | 5-8 | 9-10 |
| 6 | 6-11 | none in the completed sweep |

For Death Connect-3 on length 5, the graph has 211 states and 400 edges. All
five Black openings have value White-win. One longest-resistance line is:

```text
.....   Black: 2
..B..   White: 1,3       -> .W.W.  (Black centre dies)
.W.W.   Black: 0,2       -> B..W.  (mutual death at 1 and 2)
B..W.   White: 1,2       -> BWWW.  White wins
```

This is a concrete finite counterexample to any blanket claim that the first
player cannot lose in the death variant.

### A useful failed conjecture

The first grid suggested:

> provisional law: Death Connect-`k` on a line becomes a White win at length
> `2k-1`.

It held for `k=3,4,5`, including the length-10 Connect-5 extension. The targeted
full-rule check falsified it: length-11 Connect-6 has 367,914 reachable states
and 1,489,501 edges, and the root is a draw. Only the exact central Black
opening has White-win value; all ten off-centre openings draw.

That exception is more informative than a clean sequence would have been. It
says the full target length interacts with the one-stone opening charge and
boundary geometry, rather than following a target-independent sandwich law.

The phase diagram is
[fig_death_hexo_exact_phase.png](evidence/figures/fig_death_hexo_exact_phase.png).

## 6. Stable configurations form finite-type shifts

Every post-cleanup board is stable: no occupied adjacent triple on any axis has
color word `BWB` or `WBW`.

### Fully occupied one-axis words: the golden ratio

Let `a_n` be the number of binary words of length `n` avoiding `BWB` and `WBW`.
The counts are

```text
n:   1   2   3   4   5   6   7   8   9   10
a_n: 2   4   6  10  16  26  42  68  110  178
```

The four-state automaton on the last two colors gives

```text
a_n = a_(n-1) + a_(n-2),  n >= 3.
```

Hence the topological entropy is `log(phi)` and the exponential growth base is
the golden ratio. Equivalently, stable full rows have no singleton internal
color run.

### Words with vacancies: a new cubic Pisot constant

Let `b_n` count words over `{empty, B, W}` avoiding the same two fully occupied
forbidden triples. The counts begin

```text
3, 9, 25, 71, 201, 569, 1611, 4561, 12913, 36559.
```

The nine-state last-two-symbol automaton gives

```text
b_n = 2 b_(n-1) + 2 b_(n-2) + b_(n-3),  n >= 4
```

with characteristic polynomial

```text
x^3 - 2x^2 - 2x - 1.
```

Its real root is `lambda_D = 2.831177207...`. The other two roots are complex
with modulus about `0.594`, so `lambda_D` is a Pisot number. The cubic has no
rational root and is irreducible over the integers, making this the genuine
minimal polynomial.

This is the cleanest new connection to the parent project's Pisot programme:
the rule itself supplies exact Pisot entropy bases. The interpretive boundary
matters: a one-dimensional transfer-matrix Perron root is not automatically a
two-dimensional substitution inflation constant.

### Three-axis coupling

The transfer-matrix calculation at `experiments/run_death_hexo.py:243` counts
fully occupied stable colorings of `n x n` axial rhombi:

| n | sites | stable colorings | bits/site |
|---:|---:|---:|---:|
| 3 | 9 | 80 | 0.7024 |
| 4 | 16 | 998 | 0.6227 |
| 5 | 25 | 17,676 | 0.5644 |
| 6 | 36 | 505,798 | 0.5263 |
| 7 | 49 | 23,451,600 | 0.4997 |
| 8 | 64 | 1,749,952,542 | 0.4798 |

A small-strip fit

```text
h(n) = h_inf + a/n + b/n^2, n=4..8
```

gives `h_inf ~= 0.3464 bits/site`, or per-site growth base `~1.2714`. The fit
residual is tiny on these five points, but the extrapolation is directional,
not a rigorous entropy estimate. Larger-width transfer matrices or tensor
network bounds are required.

The full comparison is
[fig_death_hexo_stable_entropy.png](evidence/figures/fig_death_hexo_stable_entropy.png).

## 7. Why the old transversal algebra is no longer sufficient

Ordinary HeXO can be represented as a monotone 6-uniform winning hypergraph.
The parent repo's `live_lines` machinery (`../engine/analysis.py:47`) and
obligation transversal `tau` ask which empty cells complete or hit surviving
windows. That is powerful because stones are permanent.

Death HeXO breaks every static assumption:

- A defender may answer a threat by **killing an existing attacker stone**, not
  by occupying an empty completion cell.
- An attacker may kill a defender blocker, **resurrecting** a window previously
  absent from the live hypergraph.
- A nominal two-cell winning completion may fail because one new stone dies
  after the first atomic placement.
- A legal two-placement action may use the **same coordinate twice** if the
  first stone suicides.

The right local objects should be:

1. `rho_B(c)`: capture resilience of stone `c`, the minimum number of opponent
   placements needed to kill it from board `B` (`1`, `2`, or infinity in the
   simplest isolated geometry).
2. `A_p(B)`: ordered one- or two-placement actions that leave a surviving
   winning line after every intervening cleanup.
3. `K_p(B, a)`: stones killed by action `a`, including whether the placed stone
   suicides.
4. A **dynamic obligation hypergraph on actions**, not cells. Defender replies
   hit attacking action families either by occupying cells or changing their
   survival conditions through capture.

The old pressure `max(0, tau(O)-2)` can remain a feature, but it is no longer a
state-complete forcing criterion. A plausible replacement is a pair

```text
(tau_safe, capture_leverage)
```

where `tau_safe` is computed only over death-safe joint actions and
`capture_leverage` measures how cheaply either player can delete the stones
supporting those obligations.

## 8. Conway, thermography, and the two-move sum

The parent project correctly observed that 1-2-2 play is not an ordinary
disjunctive sum: a turn can spend both placements in one component or split
them across two (`../engine/two_move_sum.py:34`). Death adds two new failures of
ordinary decomposition:

1. **null placements** can spend a move without changing the board;
2. **capture coupling** can delete a stone supporting several nominal
   components at once.

The scalar heat map in `../engine/cgt.py:85` measures line urgency, but an
annihilation bomb can be strategically hot with no near-complete line. A Death
HeXO thermograph likely needs at least three coordinates:

```text
line urgency, capture volatility, recurrence/escape rank.
```

An exact disjunctive or `+_2` decomposition is justified only when two finite
zones share no winning window, no capture adjacency, and no legal action whose
two placements couple them. That separation lemma should be proved before
assigning Conway-style component values.

## 9. Shannon's switching-game lens

Shannon's switching game and Lehman's solution are the right contrast, not a
ready-made solution. In the classical graph game, Short permanently reinforces
an edge and Cut permanently deletes an edge. Lehman's criterion is matroidal
and monotone; see [Lehman 1964](https://epubs.siam.org/doi/10.1137/0112059).

Death HeXO is a **signed reversible switching game on a hypergraph**:

- playing a stone strengthens one's own length-6 hyperedges;
- the same placement can delete opponent vertices;
- deletion can reopen a previously cut hyperedge;
- ownership is not permanent.

Therefore Lehman's two-edge-disjoint-spanning-tree criterion cannot transfer
unchanged. The productive research question is whether a restricted quotient
of the dynamic live-window incidence graph admits a matroid, delta-matroid, or
greedoid structure. The local symmetric-difference flavour makes delta-matroids
especially worth testing, but there is no evidence yet.

## 10. Computational and descriptive complexity

### Finite boards

For a fixed `N`-cell board, the state graph has at most a constant phase factor
times `3^N` board colorings. Given that graph explicitly, win/draw/loss is a
standard reachability-attractor computation, polynomial in vertices plus
edges. Given only the board succinctly, this is still exponential-size search.

The exact one-dimensional solver demonstrates the correct algorithmic shape.
The generalized finite-board complexity class is open. Capture gadgets and
cycles make the comparison to Go more appropriate than to monotone
Maker-Breaker play. Lichtenstein and Sipser's primary result establishes that
generalized Go is PSPACE-hard via local planar gadgets
([IBM summary](https://research.ibm.com/publications/go-is-polynomial-space-hard),
[Berkeley report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1978/28922.html)).
Death HeXO now has the capture mechanism the parent repo previously lacked, but
no reduction has been built.

### Infinite board and bounded mate

Every mate-in-`n` query still involves finitely many placement events even
though stones may be deleted and cells reused. The parent repo's permanent-slot
argument cannot be copied literally, but it can be repaired by representing
bounded placement events plus live/dead status. The local death relation is a
finite Boolean combination of coordinate-equality and unit-offset checks, so a
bounded-horizon automatic-structure route remains plausible.

Unbounded optimal outcome is harder because null cycles defeat any argument
from steadily increasing material. The game remains an open reachability game,
but "who can force a win rather than merely non-loss?" is unresolved.

### Repetition conventions matter

The canonical game has no superko. Adding a rule that forbids repeated board
states would remove the explicit null cycle but make legality history-dependent.
Those should be treated as two separate games:

- **Death HeXO:** repetition allowed, loopy;
- **Superko Death HeXO:** repeated state illegal, terminating on finite boards
  but with larger history state.

## 11. Exploratory 2-D self-play

The simulation harness at `death_hexo.py:405` uses seeded adjacent-frontier
policies. This is a finite experimental move generator, not a mathematical
restriction on the infinite game. Each group has 24 games, eight randomized
opening placements, and a 140-placement cap. The full suite ran 312 games with
eight workers in 973 seconds.

| Matchup | Ordinary decisive | Death decisive | Death turnover | Death live-stone yield | Death state-revisit games |
|---|---:|---:|---:|---:|---:|
| hunter-hunter | 0.375 | 0.708 | 0.778 | 0.222 | 0.292 |
| hybrid-hybrid | 0.708 | 0.917 | 0.592 | 0.408 | 0.083 |
| hybrid-line | 1.000 | 0.750 | 0.743 | 0.257 | 0.250 |
| line-hybrid | 0.917 | 0.833 | 0.684 | 0.316 | 0.167 |
| line-line | 1.000 | 0.875 | 0.629 | 0.371 | 0.125 |
| random-random | 0.792 | 0.833 | 0.270 | 0.730 | 0.000 |

Wilson intervals are stored in the JSON. With `n=24`, they are wide: for
example hybrid-hybrid Death decisiveness is `0.917 [0.742, 0.977]`, while its
ordinary control is `0.708 [0.508, 0.851]`.

Three readings survive the uncertainty:

1. **Turnover is a first-order state variable.** Tactical policies delete
   roughly 59-78 stones per 100 placements. Random play deletes only 27.
2. **Capture does not uniformly increase decisiveness.** It raises decisiveness
   in hunter-hunter and hybrid-hybrid, but lowers it in several line-policy
   matchups. "More violence means fewer draws" is false as a universal rule.
3. **Recurrence is strategic, not merely combinatorial.** Uniform random play
   produced no exact state revisit in this sample, while capture-seeking
   hunter play revisited a state in 29% of games. Policies can discover and
   exploit the null-move substrate.

The state key includes board, player, placement phase, and opening status, but
not an agent's random-number-generator state. A revisit is therefore a board
dynamics event, not proof that the future policy will loop forever.

The canonical placement-cleanup hybrid self-play was `14 Black / 8 White / 2
cutoffs`, turnover `0.592`. Turn-end cleanup was `17 / 7 / 0`, turnover `0.473`.
The sample is too small for an optimal-play claim, but timing changes quantitative
dynamics enough that the rule convention must remain explicit.

See [fig_death_hexo_empirical.png](evidence/figures/fig_death_hexo_empirical.png)
and [fig_death_hexo_samples.png](evidence/figures/fig_death_hexo_samples.png).

## 12. Connection to the parent Pisot/epiplexity programme

Death HeXO supplies a more disciplined bridge than "captures may make new
patterns":

```text
local death SFT -> exact algebraic entropy bases -> three-axis stable shift
-> reachable strategic corpus -> MDL/diffraction measurements.
```

The first two arrows are now real. The latter two remain open.

Predictions:

1. A death-aware corpus should have lower live-stone density but higher temporal
   event entropy than ordinary HeXO because many placements are later erased.
2. Encoding only final boards will understate epiplexity. The correct token
   stream is `(placement, death-set)`; two histories can reach the same board.
3. Stable-board diffraction and event-stream diffraction may diverge: the
   former sees the SFT-selected survivors, the latter sees annihilation waves.
4. If the 2-D stable shift has a finite substitution sector, its inflation
   constant need not equal either `phi` or `lambda_D`; those are null-model
   entropy bases to test against.

The parent repository's warning remains decisive: a transfer-matrix entropy
root is not an inflation constant. The new constants are exact and relevant,
but they do not by themselves prove quasicrystalline optimal play.

## 13. Exact result: an aperiodic sanctuary exists

The first follow-up to the dream finding produces something stronger than a
numerical hint: an explicit open family of aperiodic, death-stable,
Connect-6-free colorings of the entire lattice.

For real parameters `alpha`, `beta`, and phase `theta`, color `(q,r)` by

```text
chi(q,r) = 1 + (floor(alpha q + beta r + theta) mod 2).
```

The experiment uses

```text
alpha = sqrt(2)/3       = 0.4714045208...
beta  = sqrt(3)/8       = 0.2165063509...
alpha - beta            = 0.2548981698...
theta = 1/7.
```

The construction is `height_owner` in
[experiments/run_aperiodic_repair.py](experiments/run_aperiodic_repair.py),
with evidence in
[aperiodic_repair.json](evidence/results/aperiodic_repair.json) and the summary
figure [fig_aperiodic_repair.png](evidence/figures/fig_aperiodic_repair.png).

### Theorem 5: the irrational-height sanctuary

Let the directional phase increments be

```text
delta_1 = alpha,  delta_2 = beta,  delta_3 = alpha - beta.
```

If

```text
1/5 < |delta_i| < 1/2       for i = 1,2,3,
```

and `1, alpha, beta` are rationally independent, then `chi` has all of the
following properties.

1. **Death stability.** No stone is bracketed by two enemies.
2. **Six-freeness.** Neither color has six consecutive stones on a lattice
   axis.
3. **Strong aperiodicity.** There is no nonzero lattice translation preserving
   the coloring.
4. **Pure-point spectrum.** With weights `+1/-1`, the coloring has Bragg
   diffraction supported at odd multiples of `(alpha/2,beta/2)` modulo the
   reciprocal lattice.
5. **Linear language complexity.** Every directional word has at most `2n`
   length-`n` factors and hence zero entropy density. The chosen slopes attain
   `2n` in every finite check through `n=32`.

**Stability proof.** Along an axis, the heights of a cell and its two neighbours
are `x-delta`, `x`, and `x+delta`. Because `2|delta| < 1`, that interval cannot
cross an integer boundary on both sides of its centre. At most one neighbour
can therefore have the opposite parity of `floor(x)`. The forbidden `x-o-x`
pattern cannot occur.

**Six-free proof.** Six consecutive cells span height `5|delta| > 1`. At least
one integer boundary is crossed, and each crossing flips the parity. Because a
single step is less than `1/2`, the six samples cannot all have the same color.

**Aperiodicity proof.** A period `(u,v)` would shift every phase by
`Delta=alpha u+beta v`. Density of the phase orbit implies that the square-wave
coding can be invariant only if `Delta` is an even integer. Rational
independence of `1,alpha,beta` forces `u=v=0`. For the chosen radicals this also
follows directly from the linear independence of `1,sqrt(2),sqrt(3)` over the
rationals.

**Diffraction proof sketch.** The color weight is the period-two square wave
`g(x)=(-1)^floor(x)`. Its only nonzero Fourier coefficients occur at odd `m`,
with squared amplitudes `4/(pi^2 m^2)`. Pulling this observable back along the
Kronecker action `(q,r) -> theta+alpha q+beta r mod 2` gives a pure-point
spectrum. This is the same almost-periodic mechanism connecting compact
rotations and Bragg diffraction in the mathematical diffraction literature.

For a length-`n` directional word, its value changes only at the `2n`
translated partition boundaries on the phase circle, proving the linear upper
bound. Aperiodicity supplies the complementary `n+1` lower bound by
Morse-Hedlund; the observed exact `2n` law is recorded separately from the
proved bound.

The inequalities define an **open sanctuary chamber**, not an isolated lucky
example. There are uncountably many irrational slopes in it. The figure maps
the larger stability chamber and the darker six-free subregions.

### Exact erasure repair

There is also a clean self-repair theorem, although its strategic scope must be
stated carefully.

Let `T` be any stable, six-free target coloring and let `S` be obtained by
deleting an arbitrary set of stones from `T`. Every subset of `T` remains
stable and six-free: deletion cannot create an enemy flank or a monochromatic
run. Consequently, the deleted stones can be reinserted in **any order** and
every intermediate configuration remains safe.

For the sanctuary this was checked on a radius-12 patch of 469 cells, with 24
random trials at each deletion size through 128. All 192 repairs returned
exactly to the target with zero deaths and zero wins. The computation is an
audit; the subset argument is the proof.

The 1-2-2 schedule is compatible with a legal cooperative growth path: on each
placement the current player selects any still-empty target cell of its own
color. Both colors occur infinitely often. The recorded 120-placement prefix
has 120 surviving stones, no capture, and no winner. Thus a dense aperiodic
draw trajectory exists, rather than merely a static coloring in configuration
space.

This is **oracle repair**, not yet autonomous or adversarial repair. The target
color is supplied by the global phase formula. We have not proved that a player
can infer it from a bounded neighbourhood, or maintain it while an opponent
deliberately places off-pattern stones. Winfree's definition of self-healing
tile assembly makes the missing requirement precise: boundary information must
force correct regrowth after arbitrary damage. Death HeXO still needs its
analogue of local matching rules.

### Exact hostile-invasion threshold

The simplest adversarial perturbation can also be classified completely.
Delete the target stone at a site and replace it with the wrong color, while
leaving the sanctuary otherwise intact. The invader dies precisely when the
central phase is farther than the smallest directional step `beta` from an
integer boundary. Therefore the phase measure of automatically rejected
invasions is

```text
1 - 2 beta = 1 - sqrt(3)/4 = 0.5669872981...
```

There are exactly 38 radius-2 phase contexts. Their exhaustive classification
is:

| Invader | Collateral target deaths | Safe target refills | Phase contexts | Phase measure |
|---|---:|---:|---:|---:|
| dies | 2 | 3 | 8 | 0.153567 |
| dies | 3 | 4 | 16 | 0.393827 |
| dies | 4 | 5 | 2 | 0.019593 |
| survives | 0 | impossible | 8 | 0.114382 |
| survives | 1 | impossible | 4 | 0.318631 |

Whenever the invader dies, the remaining configuration is a subset of the
target and exact erasure repair applies. Whenever it survives, simply refilling
target-colored holes cannot remove it: even the complete target neighbourhood
does not bracket that wrong stone. The sanctuary is thus **56.7% locally
self-policing and 43.3% frozen-defect prone** under the uniform phase measure.

This is the first exact obstruction to the dream strategy. A genuinely
self-healing construction needs redundant local phase information or a second
layer of motifs that actively routes surviving defects toward annihilation.

### Almost periods and phason scale

A translation `(u,v)` changes phase by `alpha u+beta v`. Its mismatch density
from a genuine period is exactly its distance to the nearest even integer.
This produces a Diophantine hierarchy of approximate periods:

- `(7,-6)` has phase drift only `0.00079354` beyond `2`; it agrees exactly on
  the checked radius-24 window.
- `(11,13)` has phase drift only `0.000032291` beyond `8`, predicting about
  three mismatches per 100,000 sites under that translation.

This is the desired combination: no exact period, yet translations with
arbitrarily sparse defect walls. It suggests a concrete strategic object to
search for—not a fixed board, but a phase field whose local captures act like
phason flips between nearby almost-periodic representatives.

### What actual capture play is repairing

The six stored canonical death-game replays contain 355 placements and 195
stone deaths. Symmetry-normalized radius-2 motifs were reused on 46.8% of
placements. Of 126 death events, exactly 63 returned to their pre-event local
motif within 12 placements, with median lag 3.

But individual stones were rarely restored: only 9 of 195 death tokens (4.6%)
were later reoccupied by the same color, while 85 (43.6%) were converted to the
opponent, with median reoccupation lag 1. This points toward **geometric repair
without material repair**. Local pattern classes recur while ownership flows
through them. That is much closer to a phason-flip picture than to rebuilding
the identical stones.

These replay statistics are exploratory: one stored game per matchup, shallow
policies, and canonicalization quotients by D6 and color exchange. Their role is
to select the next invariant, not to establish optimal behavior.

As a direct null test, the sanctuary family was fitted to each final live board
over 12 orientations, 128 phases, and global color exchange, then compared with
32 color shuffles on the same occupied coordinates. Five of six boards scored
at or below their shuffle mean. Hybrid self-play was the lone positive case
(`+0.099`, `z=1.74`) but had only 12 live stones. There is therefore **no current
evidence that shallow play spontaneously selects this particular sanctuary**.
That negative result matters: the construction is a target family to challenge
with a phase-aware strategy, not a pattern inferred after the fact.

The two animations make the distinction visible:

- [capture-driven recurrent play](evidence/figures/gif_death_hexo_capture_loop.gif)
- [legal aperiodic sanctuary growth](evidence/figures/gif_death_hexo_aperiodic_growth.gif)

## 14. Research programme, ordered by information gain

### A. Solve the canonical post-opening state

Start from White's forced opening inversion state `W . W`, Black to place two.
This removes irrelevant first-move symmetry and asks the true opening question.

- Build an exact finite-zone tablebase for increasing hex radii and smaller
  targets `k=3,4,5,6`.
- Record win/draw/loss, attractor rank, and whether Black's best first turn
  captures one White flank or expands elsewhere.
- Falsifier: if outcomes oscillate with boundary shape/radius, no finite-zone
  opening verdict should be extrapolated to the infinite board.

### B. Dynamic obligation solver

Replace static empty-cell threats with ordered, death-resolved action pairs.

- Enumerate all one-turn winning actions `A_p(B)`.
- Mine minimal defender reply families allowing both occupancy and capture.
- Compare `tau`, `tau_safe`, and capture resilience against exact search labels.
- Success gate: a bounded local certificate with zero false positives on every
  exact `k<=5` position and on a held-out full-game tactical suite.

### C. Loopy thermography

- Compute strongly connected components of finite-zone state graphs.
- Distinguish pure null cycles, cycles with unilateral exits, and stoppers.
- Define an escape rank and test whether it predicts strategic choices beyond
  line temperature and capture count.
- Falsifier: if SCC/escape features add no held-out move prediction, the
  Conway-loopy layer is descriptive rather than mechanistic.

### D. Sanctuary-to-strategy programme

- Extend exact rhombus/strip counts to width 12+ with sparse transfer matrices.
- Produce rigorous upper/lower entropy bounds, not only finite-size fits.
- Classify periodic ground states and locate the irrational-height sanctuary
  inside the full three-axis SFT.
- Test whether the fully occupied three-axis SFT is mixing, has multiple
  entropy-maximizing phases, or reduces to stripe/domain-wall families.
- Search for a bounded-radius decoder of sanctuary phase and color. A decoder
  would upgrade oracle repair toward autonomous matching-rule repair.
- Define a phason defect charge from local phase inconsistency and test whether
  death moves transport, annihilate, or multiply that charge.
- Build a minimax `sanctuary` agent whose score is local phase coherence minus
  live opponent six-window potential. The success criterion is robustness to
  deliberately off-pattern adversarial moves, not visual similarity.

### E. Capture-aware search ladder

The 2026 Nature study on novel games finds that a small number of shallow,
goal-directed simulations explains much human first-play reasoning
([Collins et al. 2026](https://www.nature.com/articles/s41586-026-10722-1)).
That is a timely methodological baseline here.

- Build flat Monte Carlo, depth-2 full-turn minimax, and MCTS agents over the
  exact death transition.
- Ablate line score, immediate captures, suicide/null moves, resilience, and
  repetition avoidance.
- Use paired openings and at least hundreds of games per comparison.
- Do not train a neural policy until the tactical labels cease being sparse.

### F. Complexity gadgets

Capture makes local signal restoration possible, addressing the parent
project's main obstacle to Go-style reductions.

- Search automatically for reusable wire, NOT, fan-out, and latch gadgets in
  bounded zones.
- Require isolation under all legal off-script moves.
- Decide separately the bounded-horizon problem, finite-board outcome problem,
  and superko variant.
- A radius-limited failure to find gadgets is evidence only, never a hardness
  refutation.

### G. Epiplexity and diffraction

- Serialize full event histories, including simultaneous death sets.
- Compare gzip/observer MDL scaling for ordinary versus Death HeXO under matched
  agents and openings.
- Compute diffraction on survivors, all placements, and death events separately.
- Pre-register the null: exact 1-D Pisot roots need not generate 2-D Bragg peaks.

## 15. Falsifiable conjectures

1. **Opening inversion advantage.** From the canonical `W . W` state, White's
   material lead improves White's exact finite-zone outcome relative to an
   equal-material control. Falsifier: no outcome/rank improvement over radii
   3-6 and targets 3-5.
2. **Dynamic forcing sufficiency.** `(tau_safe, resilience)` predicts exact
   one-turn and two-turn force labels without false positives. Falsifier: a
   held-out counterexample with the same pair but different outcome.
3. **Recurrence specialization.** Capture-seeking agents revisit exact states
   more often than line-only or random agents at matched strength. Falsifier:
   no difference in a 1,000-game paired-opening run.
4. **Entropy suppression.** Three-axis full stable colorings have topological
   entropy strictly below `log2(phi)`. Current finite strips support this;
   rigorous strip bounds must certify it.
5. **Pisot nontriviality.** Strategic survivor corpora show spectral/MDL
   structure not explained by the one-axis `phi` and `lambda_D` null models.
   Falsifier: matched SFT samples reproduce every claimed peak/compression gain.
6. **Timing robustness.** Opening inversion and qualitative high-turnover
   dynamics persist under atomic and turn-end cleanup. Falsifier: a large
   paired run reverses the outcome ordering or eliminates recurrence in one
   semantics.
7. **Local phase repair.** Strong capture play preserves or restores a
   bounded-radius sanctuary phase class after damage. Falsifier: phase error
   spreads ballistically or motif-return frequency falls with stronger search.
8. **Diophantine recurrence.** Strategic spatial recurrence concentrates near
   low-residual sanctuary translations such as `(7,-6)` and `(11,13)`.
   Falsifier: recurrence vectors have no relationship to the predicted
   almost-period hierarchy under matched null models.

## 16. Reproducibility and limitations

Run:

```powershell
python -m pytest tests -q
python experiments/run_death_hexo.py --quick
python experiments/run_death_hexo.py --workers 8
python experiments/run_aperiodic_repair.py
```

The verified test status is 18 passed. The full JSON records configuration,
seed, wall time, git snapshot, exact graphs, root certificates, local spectra,
simulation summaries, and representative games. The lightweight follow-up
replays stored games, verifies the sanctuary geometry, and generates one PNG
plus two GIFs in about 30 seconds on the local machine.

Limitations:

- The full 2-D policies are shallow and adjacent-frontier bounded; they are not
  claims about perfect play.
- Randomized openings deliberately measure midgame dynamics and do not test the
  exact opening inversion theorem.
- Each empirical matchup has only 24 games.
- The `8 x 8` stable-coloring fit is a small-strip extrapolation.
- Only atomic cleanup has the full exact solver battery; turn-end cleanup is a
  sensitivity comparison.
- The sanctuary theorem establishes a pure-point aperiodic sector, not that
  optimal play selects that sector.
- Oracle erasure repair is not an adversarial self-repair strategy.
- The infinite-board outcome and hardness class remain open.

## Sources

- Aaron N. Siegel, *Combinatorial Game Theory*, AMS GSM 146 (2013):
  [local front/end matter](gsm146-endmatter.pdf),
  [AMS record](https://bookstore.ams.org/view?ProductCode=GSM%2F146).
- Aaron N. Siegel, *Loopy Games and Computation* (PhD thesis, 2005):
  [Berkeley record](https://math.berkeley.edu/publications/loopy-games-and-computation).
- Alfred Lehman, "A Solution of the Shannon Switching Game" (1964):
  [DOI](https://epubs.siam.org/doi/10.1137/0112059).
- I-Chen Wu, Dei-Yen Huang, Hsiu-Chen Chang, "Connect6" (2005):
  [journal record](https://journals.sagepub.com/doi/10.3233/ICG-2005-28405).
- David Lichtenstein and Michael Sipser, "GO Is Polynomial-Space Hard" (1980):
  [primary summary](https://research.ibm.com/publications/go-is-polynomial-space-hard),
  [archived technical report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/1978/28922.html).
- Katherine M. Collins et al., "People use fast and flat simulation to reason
  about new games" (2026):
  [Nature](https://www.nature.com/articles/s41586-026-10722-1).
- Daniel Lenz et al., "Pure Point Diffraction and Almost Periodicity" (2024):
  [journal record](https://onlinelibrary.wiley.com/doi/10.1002/ijch.202300158).
- Erik Winfree, "Self-Healing Tile Sets":
  [author-hosted paper](https://www.dna.caltech.edu/Papers/self_healing_paper.pdf).
- Berlekamp, Conway, Guy, *Winning Ways for Your Mathematical Plays*; Conway,
  *On Numbers and Games*; Gale and Stewart, "Infinite Games with Perfect
  Information". These supply the short/loopy, temperature, and open-game
  background; no claim above depends on an inaccessible quotation.

---

The best concise description of the new object is:

> Death HeXO is a D6-equivariant, two-action, loopy reachability game on a
> reversible signed winning hypergraph, whose local stable states form a
> finite-type shift containing an open family of aperiodic, pure-point,
> erasure-repairable sanctuaries.

The geometric object now exists exactly. The next real question is whether a
player can force, decode, or locally repair its phase against opposition.
