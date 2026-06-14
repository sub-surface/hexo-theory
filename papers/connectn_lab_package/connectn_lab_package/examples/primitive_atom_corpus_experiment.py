"""Generate a focused corpus of primitive transversal atoms.

This experiment targets the publishable core:

    Connect-n tactics contain connected, minor-minimal tau > p obligation atoms.

For p=2 pair obligations, the first edge-critical connected graph atoms are K4
and C5.  The script mines concrete progression-deficit realizations of those
atoms across A2_hex, Z2_diag, and Z2_rook, then attaches incidence-Laplacian
spectral features inspired by the "emergent quantization" framing:

    finite spatial operator + symmetry + boundary/localization + dispersion test

The spectral data are exploratory descriptors, not a claim of hydrogenic law.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from connectn_lab.lattices import a2_hex, z2_diag, z2_rook
from connectn_lab.primitive_atom_search import (
    PrimitiveAtomRecord,
    mine_pair_graph_critical_atoms,
    overlap_summary,
)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, set):
        return sorted(_jsonable(v) for v in value)
    return value


def _atom_family(record: PrimitiveAtomRecord) -> str:
    if record.support_size == 4 and record.obligations == 6:
        return "K4 pair atom"
    if record.support_size == 5 and record.obligations == 5:
        return "C5 pair atom"
    return "Other primitive atom"


def _flat_record(record: PrimitiveAtomRecord) -> dict[str, Any]:
    row = asdict(record)
    spectral = row.pop("spectral_features")
    row["family"] = _atom_family(record)
    for key, value in spectral.items():
        row[key] = value
    for key in ("fingerprint", "abstract_key", "geometric_key", "edges", "witness_lines"):
        row[key] = json.dumps(_jsonable(row[key]), sort_keys=True)
    return row


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _abstract_rows(records: list[PrimitiveAtomRecord]) -> list[dict[str, Any]]:
    grouped: dict[str, list[PrimitiveAtomRecord]] = defaultdict(list)
    for record in records:
        grouped[json.dumps(_jsonable(record.abstract_key), sort_keys=True)].append(record)

    rows = []
    for key, group in grouped.items():
        lattice_counts = Counter(record.lattice for record in group)
        k_values = sorted({record.k for record in group})
        rows.append({
            "abstract_key": key,
            "family": _atom_family(group[0]),
            "abstract_realizations": len(group),
            "lattice_count": len(lattice_counts),
            "lattices": json.dumps(dict(sorted(lattice_counts.items())), sort_keys=True),
            "k_values": json.dumps(k_values),
            "min_support_size": min(record.support_size for record in group),
            "obligations": group[0].obligations,
            "tau": group[0].tau,
            "tau_star": group[0].tau_star,
            "spectral_gap": group[0].spectral_features["spectral_gap"],
            "low_mode_degeneracy": group[0].spectral_features["low_mode_degeneracy"],
        })
    return sorted(rows, key=lambda row: (row["family"], row["abstract_key"]))


def _write_overlap_csv(path: Path, grouped: dict[str, list[PrimitiveAtomRecord]]) -> None:
    rows = []
    for (left, right), metrics in overlap_summary(grouped).items():
        rows.append({"left": left, "right": right, **metrics})
    _write_csv(path, rows)


def _make_figures(out_dir: Path, records: list[PrimitiveAtomRecord], grouped: dict[str, list[PrimitiveAtomRecord]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figures = out_dir / "figures"
    figures.mkdir(parents=True, exist_ok=True)

    labels = sorted({record.lattice for record in records})
    k_values = sorted({record.k for record in records})
    counts = {(label, k): 0 for label in labels for k in k_values}
    for record in records:
        counts[(record.lattice, record.k)] += 1

    x = np.arange(len(labels))
    width = 0.8 / max(1, len(k_values))
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, k in enumerate(k_values):
        ax.bar(x + i * width - width * (len(k_values) - 1) / 2, [counts[(label, k)] for label in labels], width, label=f"k={k}")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("geometric primitive atom realizations")
    ax.set_title("Primitive pair-atom corpus by lattice and k")
    ax.legend()
    fig.tight_layout()
    fig.savefig(figures / "atom_counts_by_lattice_k.png", dpi=180)
    plt.close(fig)

    overlap = overlap_summary(grouped)
    names = sorted(grouped)
    matrix = np.zeros((len(names), len(names)))
    for i, left in enumerate(names):
        for j, right in enumerate(names):
            key = (left, right) if (left, right) in overlap else (right, left)
            matrix[i, j] = overlap[key]["jaccard"]
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(matrix, vmin=0, vmax=1, cmap="viridis")
    ax.set_xticks(np.arange(len(names)))
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(names)))
    ax.set_yticklabels(names)
    ax.set_title("Abstract atom overlap, Jaccard")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    fig.savefig(figures / "abstract_overlap_heatmap.png", dpi=180)
    plt.close(fig)

    color_by_lattice = {label: color for label, color in zip(labels, plt.cm.Set2(np.linspace(0, 1, len(labels))))}
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    for record in records:
        ax.scatter(
            record.support_size,
            record.obligations,
            s=24,
            alpha=0.65,
            color=color_by_lattice[record.lattice],
            label=record.lattice,
        )
    handles, labels_seen = ax.get_legend_handles_labels()
    by_label = dict(zip(labels_seen, handles))
    ax.legend(by_label.values(), by_label.keys(), loc="best")
    ax.set_xlabel("support size")
    ax.set_ylabel("obligation count")
    ax.set_title("Atom size: support versus obligations")
    fig.tight_layout()
    fig.savefig(figures / "support_vs_obligations.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    families = sorted({_atom_family(record) for record in records})
    for i, family in enumerate(families):
        gaps = [
            record.spectral_features["spectral_gap"]
            for record in records
            if _atom_family(record) == family and record.spectral_features["spectral_gap"] is not None
        ]
        ax.scatter([i] * len(gaps), gaps, alpha=0.55, s=24)
    ax.set_xticks(range(len(families)))
    ax.set_xticklabels(families, rotation=20, ha="right")
    ax.set_ylabel("incidence-support Laplacian gap")
    ax.set_title("Discrete spectral gaps by atom family")
    fig.tight_layout()
    fig.savefig(figures / "spectral_gap_by_family.png", dpi=180)
    plt.close(fig)

    representatives: dict[str, PrimitiveAtomRecord] = {}
    for record in sorted(records, key=lambda r: (r.lattice, r.k, r.support_size, r.obligations)):
        representatives.setdefault(_atom_family(record), record)
    fig, axes = plt.subplots(1, max(1, len(representatives)), figsize=(5 * max(1, len(representatives)), 4.5))
    if len(representatives) == 1:
        axes = [axes]
    for ax, (family, record) in zip(axes, representatives.items()):
        cells = sorted({cell for edge in record.edges for cell in edge})
        for edge in record.edges:
            if len(edge) == 2:
                (x0, y0), (x1, y1) = edge
                ax.plot([x0, x1], [y0, y1], color="#444", linewidth=1.5, alpha=0.8)
        ax.scatter([x for x, _ in cells], [y for _, y in cells], s=85, color="#1f77b4", zorder=3)
        for x0, y0 in cells:
            ax.text(x0, y0 + 0.08, f"{x0},{y0}", ha="center", va="bottom", fontsize=8)
        ax.set_aspect("equal", adjustable="box")
        ax.set_title(f"{family}\n{record.lattice}, k={record.k}, tau={record.tau}")
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(figures / "representative_atoms.png", dpi=180)
    plt.close(fig)


def _write_report(out_dir: Path, records: list[PrimitiveAtomRecord], abstract_rows: list[dict[str, Any]]) -> None:
    lattice_counts = Counter(record.lattice for record in records)
    family_counts = Counter(_atom_family(record) for record in records)
    shared = [row for row in abstract_rows if row["lattice_count"] > 1]
    lines = [
        "# Primitive Transversal Atom Corpus",
        "",
        "This run is focused on the publishable core: connected, minor-minimal obligation hypergraphs with `tau > p` that are concretely realizable as Connect-n progression deficits.",
        "",
        "## Theoretical framing",
        "",
        "The referenced dynamic-vacuum quantization paper argues that discrete modes arise from a spatial operator, symmetry, boundary/localization conditions, and a dispersion law. This experiment uses that as a restrained design analogy: each atom gets a finite incidence-support Laplacian spectrum, lattice symmetry is tracked through geometric canonical keys, the finite radius supplies the boundary, and the quadratic-dispersion column squares the lowest spatial gap as an exploratory score.",
        "",
        "The combinatorial claim remains primary: spectra are descriptors of primitive `tau > p` atoms, not substitutes for the transversal obstruction.",
        "",
        "## Corpus summary",
        "",
        f"- geometric realizations: {len(records)}",
        f"- abstract atom types: {len(abstract_rows)}",
        f"- shared abstract atom types across lattices: {len(shared)}",
        f"- lattice counts: {dict(sorted(lattice_counts.items()))}",
        f"- family counts: {dict(sorted(family_counts.items()))}",
        "",
        "## Files",
        "",
        "- `primitive_atoms.csv`: one row per geometric atom realization.",
        "- `abstract_atoms.csv`: one row per abstract coordinate-free atom type.",
        "- `overlap_by_lattice.csv`: abstract atom overlap by lattice.",
        "- `primitive_atoms.json`: complete JSON corpus.",
        "- `figures/`: count, overlap, size, spectral, and representative diagrams.",
        "",
        "## Interpretation target",
        "",
        "A clean result would be a table of primitive atoms showing which abstract transversal obstructions are universal, which are geometry-native, and which have different embedding multiplicities across `A2_hex`, `Z2_diag`, and `Z2_rook`.",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(out_dir: Path, preset: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    specs = []
    if preset == "smoke":
        specs = [(a2_hex(), 4, 2), (z2_diag(), 4, 2), (z2_rook(), 4, 2)]
    else:
        specs = [
            (a2_hex(), 4, 2),
            (z2_diag(), 4, 2),
            (z2_rook(), 4, 2),
            (a2_hex(), 5, 2),
            (z2_diag(), 5, 2),
            (z2_rook(), 5, 2),
            (a2_hex(), 6, 3),
            (z2_diag(), 6, 3),
            (z2_rook(), 6, 3),
        ]

    records: list[PrimitiveAtomRecord] = []
    grouped: dict[str, list[PrimitiveAtomRecord]] = defaultdict(list)
    manifest = {"preset": preset, "specs": []}
    for lattice, k, radius in specs:
        mined = list(mine_pair_graph_critical_atoms(lattice=lattice, k=k, radius=radius, max_support=5))
        key = f"{lattice.name}:k{k}:r{radius}"
        grouped[key].extend(mined)
        records.extend(mined)
        manifest["specs"].append({
            "lattice": lattice.name,
            "k": k,
            "p": 2,
            "radius": radius,
            "records": len(mined),
            "abstract_atoms": len({record.abstract_key for record in mined}),
        })

    flat_rows = [_flat_record(record) for record in records]
    abstract_rows = _abstract_rows(records)
    _write_csv(out_dir / "primitive_atoms.csv", flat_rows)
    _write_csv(out_dir / "abstract_atoms.csv", abstract_rows)
    _write_overlap_csv(out_dir / "overlap_by_lattice.csv", grouped)
    (out_dir / "primitive_atoms.json").write_text(json.dumps(_jsonable(records), indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    _make_figures(out_dir, records, grouped)
    _write_report(out_dir, records, abstract_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", choices=("smoke", "rich"), default="rich")
    parser.add_argument("--out", default="primitive_atom_corpus_results/rich_run")
    args = parser.parse_args()
    run(Path(args.out), preset=args.preset)


if __name__ == "__main__":
    main()
