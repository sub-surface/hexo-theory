# Seeded Connect-n as biased progression-hypergraph games

## 1. The general object

A connect-style game can be represented as:

```text
Connect(L, D, k, p, q, seed)
```

where `L` is a lattice, `D` is a set of permitted line directions, `k` is the target length, `p` is the normal move budget, and `q` is the first-player opening budget.

The game board is not the most natural state variable. The natural state variable is the live progression hypergraph:

```text
H = { L(x,d) : x in lattice, d in D }
```

where:

```text
L(x,d) = {x, x+d, ..., x+(k-1)d}
```

Each `L(x,d)` is a winning hyperedge.

For square-grid play with diagonals:

```text
L = Z^2
D = {(1,0), (0,1), (1,1), (1,-1)}
```

For A2 / hex axial play:

```text
L = A2
D = {(1,0), (0,1), (1,-1)}
```

## 2. Obligations and transversal thresholds

Given attacker stones `A` and defender stones `D`, a live progression is one containing no defender stones. If it is close enough that the attacker can complete it next turn, it imposes an obligation on the defender.

For defender budget `p`, the obligation family is a hypergraph:

```text
O = { E_L : L is urgent }
```

where `E_L` is the set of empty cells in the urgent line. The defender can stop all immediate completions iff there is a hitting set of size at most `p`:

```text
tau(O) <= p
```

Therefore the local forcing phase transition is:

```text
tau(O) > p
```

For Connect6, `p = 2`, so the familiar threshold is `tau(O) > 2`.

## 3. Conway: atoms of play

The Conway-style object is not the whole board. It is the local game fragment that behaves differently under attacker/defender continuation.

A primitive forcing atom can be defined experimentally as a small or minor-minimal obligation family with:

```text
tau(O) > p
```

but no removable obligation that preserves `tau > p`.

These atoms should be classified independently of their lattice embedding where possible. The same abstract incidence structure may have different A2 and Z2 realisations.

## 4. Noether: rooted symmetry breaking

The `1-2-2` rule is not merely a material balance trick. A singleton first move breaks translation symmetry.

For A2:

```text
A2 ⋊ D6  ->  D6
```

For Z2 with diagonal directions:

```text
Z2 ⋊ D4  ->  D4
```

White may restore approximate material balance with a two-stone reply, but cannot unroot the board. This motivates experiments comparing:

```text
q=0  no seed
q=1  central singleton seed
q=2  balanced pair seed
```

The question is whether `q=1` creates forcing atoms earlier, in greater variety, or with lower support size.

## 5. Tao and Erdos: progression extremal questions

The arithmetic-combinatorial reading is:

```text
winning lines = k-term arithmetic progressions in a lattice
forcing events = structured progression families with high transversal number
```

Natural extremal questions:

```text
minimum stones needed to realise tau(O) > p
maximum local density avoiding tau(O) > p
number of live progressions forced by n stones in a radius-r ball
```

The shift from A2 to Z2 is not cosmetic. It changes direction count, symmetry group, and embeddability of abstract forcing atoms.

## 6. Lovasz: fractional transversals

Exact `tau` is integer and combinatorial. Its fractional relaxation `tau*` gives a density-like approximation.

Especially interesting atoms satisfy:

```text
tau(O) > p
but
tau*(O) <= p
```

These are integrality-gap atoms: their force is invisible to fractional pressure fields and appears only in discrete hitting-set structure.

## 7. Shannon and Minsky: compression and societies of representations

A useful state representation should compress board geometry into tactical invariants:

```text
board -> line counts -> obligations -> fingerprints -> tau / atom class
```

Different components may need different representations:

```text
line-count agent
obligation-hypergraph agent
root-symmetry agent
pair-curvature agent
exact-tau critic
embedding classifier
```

The package is intentionally modular so these representations can be compared rather than collapsed into one heuristic.

## 8. Turing, Ulam, deLanda: dynamics and phases

The same family can be viewed as a discrete morphogenetic field:

```text
attacker debt = activator
white closure / screening = inhibitor
branching debt = instability
terminal line = crystallised stripe
```

Varying `L, D, k, p, q` should produce phase diagrams:

```text
cold diffuse field
screenable pressure
branching debt
non-coverable atom
terminal circuit
```

The hypergraph/tau layer is the discrete correction that keeps this dynamical metaphor honest.
