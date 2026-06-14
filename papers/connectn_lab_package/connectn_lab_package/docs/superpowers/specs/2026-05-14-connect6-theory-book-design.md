# Connect6 Theory Book Design

Date: 2026-05-14

## Goal

Build a compact illustrated theory book for the current Connect6 lab. The book should explain the seeded Hex Connect6 programme at a high mathematical level while remaining playful enough to invite further experimentation.

The main outputs are:

- `docs/connect6_theory_book.md` as the canonical editable source.
- `reports/connect6_theory_book.html` as the readable local book.
- `reports/connect6_theory_book_figures/` as generated diagram assets.

## Tone

The book should take inspiration from the spirit of *Winning Ways for Your Mathematical Plays*: named positions, small diagrams, tactical morals, puzzles, informal conjectures, and a willingness to treat local games as living mathematical objects. It should not imitate the text; it should use the same broad mode of mathematical playfulness while staying grounded in our empirical Connect6 corpus.

The style should alternate between:

- clear definitions,
- tactical cartoons,
- named lemmas and conjectures,
- "try this position" puzzles,
- empirical tables,
- short postgrad-level commentary.

## Core Thesis

The central story is:

```text
Seeded Connect6 is not just a stone game.
It is a rooted progression-hypergraph game.
Its tactical phase changes are governed by obligation transversals.
The key opening question is whether the one-stone seed defect leaks through the later two-stone budget symmetry.
```

The strongest current answer is:

```text
The defect survives as a quiet resource leak, not as an immediate shallow proof of a Black win.
```

## Chapters

1. **The Board That Is Not The Board**
   Introduce Hex Connect6, axial coordinates, D6 directions, and winning progressions.

2. **Obligations**
   Define live progressions, missing sets, urgent obligations, hitting number, and the `tau(O) > p` threshold.

3. **Threats Are Not Numbers**
   Show why raw threat counts fail; use singleton triads, pair triads, and overlapping obligations.

4. **The Seed Defect**
   Explain 1-2-2 symmetry breaking, rooted D6 stabiliser, and the resource question.

5. **One-Cap Cooling**
   Present the line abstraction where one Black cap cools a White adjacent pair from a full-budget tax to a partial tax.

6. **Opening Evidence**
   Summarise the radius-3 and radius-4 empirical probes, including the absence of White `tau > 2` overloads.

7. **Atoms Of Play**
   Define primitive forcing atoms and show how relevance zones should preserve minor-minimal witnesses.

8. **Strategy Beasts**
   Compare self-play strategy families and explain why Black and White appear to prefer distinct styles.

9. **Odd, Even, Prime**
   Use the `k`-sweep corpus to discuss even/odd and prime connect lengths as probes of budget rhythm.

10. **The Unproved Kingdom**
    State what remains conjectural and list the next proof/search targets.

## Figures

The generated figure set should include:

- Hex axial board and D6 direction rays.
- A length-6 winning progression.
- Obligation hypergraph with hitting cells.
- Independent obligation triads.
- One-cap cooling line diagram.
- Opening radius summary from current empirical results.
- Self-play strategy matrix if available.
- Atom extraction pipeline.

## Implementation

Add a small build script that:

1. Creates the figure directory.
2. Generates diagrams with matplotlib.
3. Reads selected existing CSV results when present.
4. Writes Markdown.
5. Converts the Markdown to a standalone HTML file with simple CSS.

The builder must degrade gracefully if optional result CSVs are missing.

## Verification

Run the builder and verify:

- Markdown file exists and is non-empty.
- HTML file exists and references generated figures.
- Generated figures exist and are readable PNG files.
- Existing tests still pass, or at minimum the builder compiles and runs.

## Scope Boundaries

This book is a living lab artifact, not a final monograph. It should be compact enough to revise often. Formal literature comparison and detailed citations are intentionally deferred until after this defect-vs-budget symmetry writeup exists.
