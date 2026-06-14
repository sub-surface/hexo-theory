# Hex Connect-6 Primitive Template Miner

This folder contains a self-contained empirical miner for primitive forcing
templates on the infinite axial hex grid.

The core claim tested by the script is:

```text
A local template is forcing when tau(O(P,m)) > 2,
```

where `O(P,m)` is the urgent obligation hypergraph induced by a candidate
two-stone Connect-6 move and `tau` is its exact transversal number.

## Main Command

```bash
python hexconnect6_template_miner.py \
  --out template_mining_run \
  --radius 6 \
  --samples 50000 \
  --generators random,rail,opening,selfplay \
  --max-stones 22 \
  --pressure exact,proto \
  --minimize \
  --critical-core \
  --canonicalize
```

By default the miner ranks frontier candidate pairs and caps each position with
`--max-candidate-pairs 512`. Use `--max-candidate-pairs 0` for exhaustive
candidate-pair enumeration inside `--candidate-radius`.

Use `--max-positive-events-per-source N` for source-balanced mining. Use
`--critical-core` to replace the induced obligation family by a
transversal-critical subfamily that preserves pressure; this is useful for
testing whether the finite catalogue appears at the forcing-core level.

## Outputs

Each run writes full data under `data/`, figures under `figures/`, and headline
artefacts at the run root:

```text
primitive_templates.csv
template_examples.json
template_frequency_rank.png
tau_vs_obligations.png
template_shape_spectrum.png
top_templates_diagram.pdf
template_diagrams/
```

The full data products are:

```text
positions.csv
candidate_moves.csv
positive_pressure_events.csv
raw_templates.csv
minimal_templates.csv
canonical_templates.csv
primitive_templates.csv
template_frequencies.csv
template_examples.json
```

## Verification Runs

The current smoke run is in `smoke_run/`. A smaller final verification run is in
`quick_verify_run/`.

Unit tests:

```bash
python -m pytest tests -q
```

## Atlas Analysis

After a mining run, build the paper-facing atlas:

```bash
python hexconnect6_template_atlas.py --run template_mining_run
```

This writes:

```text
atlas/template_signal_reservoir.csv
atlas/family_source_matrix.csv
atlas/pair_shape_spectrum.csv
atlas/atomic_representatives.csv
atlas/atomic_containment.csv
atlas/abstract_atomic_representatives.csv
atlas/abstract_containment.csv
atlas/subtemplate_poset.csv
atlas/d6_orbit_quotients.csv
atlas/embedding_layer_summary.csv
atlas/atlas_summary.json
atlas/conjectures.md
atlas/primitive_template_atlas.svg
atlas/primitive_template_atlas.pdf
atlas/primitive_template_atlas.png
```

The atlas borrows the signal/reservoir framing from the supplied generality
paper: recurring cross-source templates are treated as tactical signal-channel
candidates, while high-tau one-off proto templates are treated as reservoir
candidates until deeper search or recurrence validates them.

The atlas also adds a second quotient layer beyond geometric D6
canonicalisation:

```text
coordinate template
  -> D6 canonical template
  -> colored obligation-incidence hypergraph
  -> abstract incidence-minor atoms / subtemplate poset
```

This layer deliberately forgets absolute hex coordinates while preserving
attacker/defender/move/obligation colors and obligation-edge incidence. It
outputs exact component-wise colored-hypergraph signatures where the components
are small enough to canonicalise directly, D6 orbit-stabilizer/Burnside
diagnostics, and affine A2/Coxeter support signatures for the underlying hex
lattice.

The embedding layer treats each template as a finite hex-cell patch and records
Conway-style integer invariants: A2 convex hull area/deficit, connected
components, holes, Euler characteristic, boundary slope partition, parallel-line
arrangement, and a `conway_embedding_signature` for quotienting spatially
different embeddings of the same kind of tactical surface.

Useful atlas flags:

```bash
python hexconnect6_template_atlas.py \
  --run template_mining_run \
  --max-abstract-atoms 32 \
  --abstract-containment-mode minor
```

## Bold Embedding Figures

After running the atlas, generate the experimental figure suite:

```bash
python hexconnect6_embedding_figures.py --run template_mining_run
```

This writes SVG/PDF/PNG versions under `atlas/bold_figures/`:

```text
quotient_telescope
embedding_phase_portrait
atom_minor_genealogy
annulus_spotlight
embedding_signature_constellations
```

These figures are intentionally more conjectural than the main atlas plate:
they treat D6 templates, A2 embeddings, colored incidence signatures, integer
fingerprints, and motif families as successive quotients of the same tactical
object.

## Holographic Boundary Experiment

To test whether boundary data is a useful descriptive space, run:

```bash
python hexconnect6_holographic_experiments.py --run template_mining_run
```

This writes `atlas/holographic/` with:

```text
holographic_templates.csv
signature_group_metrics.csv
signature_prediction_metrics.csv
holographic_purity_matrix.svg/pdf/png
holographic_compression_accuracy.svg/pdf/png
noether_charge_heatmap.svg/pdf/png
holographic_report.md
```

The experiment compares naive bulk size, coarse/exact A2 Noether line charges,
coarse/exact boundary flux, combined holographic boundary states, abstract
incidence signatures, integer fingerprints, and motif families. The intended
question is whether lower-dimensional boundary data predicts the forcing
physics, or whether the missing information is genuinely bulk incidence
structure.
