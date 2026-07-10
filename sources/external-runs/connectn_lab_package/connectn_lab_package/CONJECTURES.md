# Conjectures and theorem-shaped targets

## Conjecture 1: Transversal threshold universality

For any lattice connect-n game with defender budget `p`, local forcing is mediated by obligation families satisfying:

```text
tau(O) > p
```

The exact atoms vary by lattice and direction set, but the threshold principle is invariant.

## Conjecture 2: Seeded asymmetry

The `q=1, p=2` opening does not merely balance first-player material. It creates a rooted symmetry-breaking charge that changes the distribution, generation depth, and embeddability of primitive forcing atoms.

Experiment:

```text
Compare q=0, q=1, q=2 for fixed L,D,k,p.
Measure first tau>p depth, atom diversity, and support size.
```

## Conjecture 3: Lattice-dependent atom embeddability

Some forcing atoms are abstractly identical as hypergraphs but differ sharply in their minimal embeddings on A2 versus Z2.

Experiment:

```text
Mine atoms on A2 and Z2.
Canonicalise by abstract incidence and by lattice embedding.
Compare minimal support and generation depth.
```

## Conjecture 4: Integrality-gap atoms

The most strategically subtle atoms are those with:

```text
tau(O) > p
but
tau*(O) <= p
```

These atoms evade smooth density/flow heuristics and require integer hitting-set reasoning.

## Conjecture 5: Relevance as atom preservation

A relevance zone is strategically valid iff it preserves the minor-minimal `tau > p` atom witnesses of the local position up to the required search depth.

In benchmark form:

```text
maximise pair reduction
subject to tau-threshold retention and atom recall
```

## Conjecture 6: Direction-count effect

For fixed `k,p,q`, increasing the number of progression foliations increases atom diversity faster than it increases minimal atom support.

This predicts that `Z2_diag` and `A2_hex` differ not only geometrically but combinatorially: four square-grid foliations may generate more crossing atom types, while A2 may generate cheaper sixfold rail/bridge motifs.

## Conjecture 7: Atom algebra

Primitive atoms compose by gluing obligation supports. Some compositions are additive in tau, while others collapse because new overlaps lower the transversal number.

The algebraic question:

```text
Given atoms A and B, when is tau(A ∪ B) = tau(A) + tau(B)?
```

This is the Conway/BCG route to a calculus of local play.
