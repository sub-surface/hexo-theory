"""Holographic/Noether-style descriptors for Hex Connect-6 templates.

The experiment asks whether local forcing data can be represented in a lower
dimensional descriptive space: boundary flux plus affine-A2 line charges.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


HERE = Path(__file__).resolve().parent
ATLAS_PATH = HERE / "hexconnect6_template_atlas.py"
spec = importlib.util.spec_from_file_location("hexconnect6_template_atlas", ATLAS_PATH)
atlas = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(atlas)


Cell = Tuple[int, int]
PALETTE = atlas.PALETTE


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def as_int(row: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def parse_cells_json(value: str) -> List[Cell]:
    return [tuple(cell) for cell in json.loads(value)] if value else []


def transform_row_geometry(
    row: Dict[str, str],
    rot: int = 0,
    reflect: bool = False,
    delta: Cell = (0, 0),
) -> Dict[str, str]:
    def transform(cell: Iterable[int]) -> List[int]:
        q, r = atlas.add_cell(atlas.transform_cell(tuple(cell), rot=rot, reflect=reflect), delta)
        return [q, r]

    out = dict(row)
    for field in ("attacker_stones", "defender_stones", "move_stones"):
        out[field] = json.dumps([transform(cell) for cell in parse_cells_json(row.get(field, ""))])
    edges = []
    for edge in atlas.parse_edges(row.get("obligation_edges", "")):
        edges.append([transform(cell) for cell in edge])
    out["obligation_edges"] = json.dumps(edges)
    return out


def role_map(row: Dict[str, str]) -> Dict[Cell, str]:
    return {
        cell: atlas.role_color(roles)
        for cell, roles in atlas.row_cell_roles(row).items()
    }


def _counter_tuple(counter: Counter) -> Tuple[Tuple[str, int], ...]:
    return tuple(sorted((str(key), int(value)) for key, value in counter.items() if value))


def noether_line_charge_signature(row: Dict[str, str]) -> str:
    """A translation/D6-invariant affine-A2 line-charge profile.

    Translation symmetry removes absolute line coordinates. D6 symmetry
    permutes and reverses the three A2 axis profiles, so each profile is
    normalised against reversal and the axes are sorted as an unordered triple.
    """
    cells = role_map(row)
    if not cells:
        return "()"
    profiles = []
    for axis in range(3):
        by_line: Dict[int, Counter] = defaultdict(Counter)
        for cell, color in cells.items():
            by_line[atlas.a2_coordinates(cell)[axis]][color] += 1
        coords = sorted(by_line)
        shifted = [coord - coords[0] for coord in coords]
        dense = []
        lookup = dict(zip(coords, shifted))
        for coord in range(coords[0], coords[-1] + 1):
            dense.append((lookup.get(coord, coord - coords[0]), _counter_tuple(by_line.get(coord, Counter()))))
        profile = tuple(dense)
        reversed_profile = tuple((i, counts) for i, (_, counts) in enumerate(reversed(dense)))
        profiles.append(min(profile, reversed_profile))
    return repr(tuple(sorted(profiles, key=repr)))


def coarse_noether_spectrum_signature(row: Dict[str, str]) -> str:
    cells = role_map(row)
    if not cells:
        return "()"
    axis_spectra = []
    for axis in range(3):
        by_line: Dict[int, Counter] = defaultdict(Counter)
        for cell, color in cells.items():
            by_line[atlas.a2_coordinates(cell)[axis]][color] += 1
        line_masses = tuple(sorted(sum(counter.values()) for counter in by_line.values()))
        obligation_masses = tuple(sorted(sum(v for color, v in counter.items() if "O" in color) for counter in by_line.values()))
        axis_spectra.append((line_masses, obligation_masses))
    return repr(tuple(sorted(axis_spectra, key=repr)))


def _flux_payload_for_role_map(cells: Dict[Cell, str]) -> Tuple[Tuple[Tuple[str, int], ...], ...]:
    counters = [Counter() for _ in atlas.HEX_DIRECTIONS]
    occupied = set(cells)
    direction_index = {direction: i for i, direction in enumerate(atlas.HEX_DIRECTIONS)}
    for cell, color in cells.items():
        for direction in atlas.HEX_DIRECTIONS:
            if atlas.add_cell(cell, direction) not in occupied:
                counters[direction_index[direction]][color] += 1
    return tuple(_counter_tuple(counter) for counter in counters)


def boundary_flux_signature(row: Dict[str, str]) -> str:
    cells = role_map(row)
    if not cells:
        return "()"
    payloads = []
    for reflect in (False, True):
        for rot in range(6):
            transformed = {
                atlas.transform_cell(cell, rot=rot, reflect=reflect): color
                for cell, color in cells.items()
            }
            payloads.append(_flux_payload_for_role_map(transformed))
    return repr(min(payloads, key=repr))


def coarse_boundary_flux_signature(row: Dict[str, str]) -> str:
    cells = role_map(row)
    if not cells:
        return "()"
    exposed_by_role = Counter()
    exposed_by_direction = []
    occupied = set(cells)
    for direction in atlas.HEX_DIRECTIONS:
        direction_count = 0
        for cell, color in cells.items():
            if atlas.add_cell(cell, direction) not in occupied:
                exposed_by_role[color] += 1
                direction_count += 1
        exposed_by_direction.append(direction_count)
    return repr(
        (
            tuple(sorted(exposed_by_direction)),
            _counter_tuple(exposed_by_role),
        )
    )


def holographic_boundary_signature(row: Dict[str, str]) -> str:
    support = row.get("a2_support_signature") or atlas.a2_support_signature(row)
    chi = row.get("hex_euler_characteristic")
    holes = row.get("hex_holes")
    return (
        f"line={noether_line_charge_signature(row)}|"
        f"flux={boundary_flux_signature(row)}|"
        f"support={support}|chi={chi}|holes={holes}"
    )


def coarse_holographic_signature(row: Dict[str, str]) -> str:
    support = row.get("a2_support_signature") or atlas.a2_support_signature(row)
    topology = (
        row.get("manifold_label", ""),
        row.get("hex_euler_characteristic", ""),
        row.get("hex_holes", ""),
    )
    return repr(
        (
            coarse_noether_spectrum_signature(row),
            coarse_boundary_flux_signature(row),
            support,
            topology,
        )
    )


def size_signature(row: Dict[str, str]) -> str:
    return repr(
        (
            as_int(row, "num_obligations"),
            as_int(row, "num_obligation_vertices"),
            as_int(row, "num_attacker_stones"),
            as_int(row, "num_defender_stones"),
            row.get("edge_size_histogram", ""),
        )
    )


def noether_signature(row: Dict[str, str]) -> str:
    return f"line={noether_line_charge_signature(row)}|support={row.get('a2_support_signature') or atlas.a2_support_signature(row)}"


def flux_signature(row: Dict[str, str]) -> str:
    return f"flux={boundary_flux_signature(row)}|boundary={row.get('boundary_slope_partition', '')}"


def add_descriptors(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for row in rows:
        enriched = dict(row)
        enriched["size_signature"] = size_signature(row)
        enriched["noether_line_signature"] = noether_signature(row)
        enriched["coarse_noether_signature"] = coarse_noether_spectrum_signature(row)
        enriched["boundary_flux_signature"] = flux_signature(row)
        enriched["coarse_boundary_flux_signature"] = coarse_boundary_flux_signature(row)
        enriched["holographic_boundary_signature"] = holographic_boundary_signature(row)
        enriched["coarse_holographic_signature"] = coarse_holographic_signature(row)
        enriched["abstract_signature"] = row.get("abstract_incidence_signature", "")
        enriched["atom_presence"] = "1" if as_int(row, "contained_abstract_atom_count") > 0 else "0"
        out.append(enriched)
    return out


def majority_purity(values: Iterable[str]) -> float:
    counts = Counter(values)
    total = sum(counts.values())
    return max(counts.values()) / total if total else 0.0


def signature_group_metrics(
    rows: Sequence[Dict[str, str]],
    signature_field: str,
    target_fields: Sequence[str],
) -> Dict[str, float]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get(signature_field, "")].append(row)
    metrics: Dict[str, float] = {
        "signature": signature_field,
        "rows": len(rows),
        "groups": len(groups),
        "compression_ratio": round(len(rows) / len(groups), 6) if groups else 0.0,
        "mean_group_size": round(len(rows) / len(groups), 6) if groups else 0.0,
        "max_group_size": max((len(group) for group in groups.values()), default=0),
    }
    for target in target_fields:
        weighted = 0.0
        for group in groups.values():
            weighted += len(group) * majority_purity(str(row.get(target, "")) for row in group)
        metrics[f"{target}_purity"] = round(weighted / len(rows), 6) if rows else 0.0
    return metrics


def signature_prediction_metrics(
    rows: Sequence[Dict[str, str]],
    signature_field: str,
    target_field: str,
) -> Dict[str, float]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row.get(signature_field, "")].append(row)

    global_majority = Counter(str(row.get(target_field, "")) for row in rows).most_common(1)
    fallback = global_majority[0][0] if global_majority else ""
    correct = 0
    covered = 0
    for i, row in enumerate(rows):
        signature = row.get(signature_field, "")
        peers = [peer for peer in groups[signature] if peer is not row]
        if peers:
            prediction = Counter(str(peer.get(target_field, "")) for peer in peers).most_common(1)[0][0]
            covered += 1
        else:
            prediction = fallback
        if prediction == str(row.get(target_field, "")):
            correct += 1
    return {
        "signature": signature_field,
        "target": target_field,
        "accuracy": round(correct / len(rows), 6) if rows else 0.0,
        "covered_fraction": round(covered / len(rows), 6) if rows else 0.0,
    }


def all_experiment_metrics(rows: Sequence[Dict[str, str]]) -> Tuple[List[Dict], List[Dict]]:
    signature_fields = [
        "size_signature",
        "coarse_noether_signature",
        "noether_line_signature",
        "coarse_boundary_flux_signature",
        "boundary_flux_signature",
        "coarse_holographic_signature",
        "holographic_boundary_signature",
        "abstract_signature",
        "integer_fingerprint",
        "family",
    ]
    target_fields = ["tau", "pressure", "family", "manifold_label", "atom_presence"]
    group_rows = [signature_group_metrics(rows, field, target_fields) for field in signature_fields]
    prediction_rows = [
        signature_prediction_metrics(rows, field, target)
        for field in signature_fields
        for target in ("tau", "pressure", "family", "atom_presence")
    ]
    return group_rows, prediction_rows


def figure_style() -> None:
    atlas.apply_nature_style()


def make_purity_figure(metrics: Sequence[Dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figure_style()
    labels = [str(row["signature"]).replace("_signature", "").replace("_", "\n") for row in metrics]
    purity_fields = ["tau_purity", "pressure_purity", "family_purity", "atom_presence_purity"]
    arr = np.array([[float(row[field]) for field in purity_fields] for row in metrics])

    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    im = ax.imshow(arr.T, aspect="auto", cmap="viridis", vmin=0.0, vmax=1.0)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=0, ha="center")
    ax.set_yticks(range(len(purity_fields)))
    ax.set_yticklabels([field.replace("_purity", "") for field in purity_fields])
    for y in range(arr.shape[1]):
        for x in range(arr.shape[0]):
            ax.text(x, y, f"{arr[x, y]:.2f}", ha="center", va="center", fontsize=7, color="white" if arr[x, y] < 0.65 else "black")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="within-signature purity")
    ax.set_title("Holographic reconstruction: what boundary data determines")
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(out_dir / f"holographic_purity_matrix.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def make_compression_accuracy_figure(metrics: Sequence[Dict], prediction_rows: Sequence[Dict], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_style()
    tau_acc = {
        row["signature"]: float(row["accuracy"])
        for row in prediction_rows
        if row["target"] == "tau"
    }
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for row in metrics:
        signature = row["signature"]
        ax.scatter(
            float(row["compression_ratio"]),
            tau_acc.get(signature, 0.0),
            s=50 + 6 * float(row["max_group_size"]),
            color=PALETTE["blue_main"] if "holographic" in signature else PALETTE["neutral_mid"],
            alpha=0.78,
            edgecolor="white",
            linewidth=0.4,
        )
        ax.text(
            float(row["compression_ratio"]) + 0.05,
            tau_acc.get(signature, 0.0),
            str(signature).replace("_signature", "").replace("_", " "),
            fontsize=7,
            va="center",
        )
    ax.set_xscale("log")
    ax.set_xlabel("compression ratio")
    ax.set_ylabel("leave-one-out tau accuracy")
    ax.set_title("Compression vs predictive power")
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(out_dir / f"holographic_compression_accuracy.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def make_noether_charge_figure(rows: Sequence[Dict[str, str]], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figure_style()
    families = sorted({row.get("family", "unknown") or "unknown" for row in rows})
    measures = ["a2_convex_deficit", "boundary_edge_count", "a2_coxeter_diameter", "hex_components", "hex_holes"]
    arr = np.zeros((len(families), len(measures)))
    for i, family in enumerate(families):
        subset = [row for row in rows if (row.get("family", "unknown") or "unknown") == family]
        for j, measure in enumerate(measures):
            arr[i, j] = sum(as_int(row, measure) for row in subset) / len(subset)

    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    im = ax.imshow(arr, aspect="auto", cmap="magma")
    ax.set_yticks(range(len(families)))
    ax.set_yticklabels(families)
    ax.set_xticks(range(len(measures)))
    ax.set_xticklabels([m.replace("a2_", "A2 ").replace("_", "\n") for m in measures], rotation=0)
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02, label="family mean")
    ax.set_title("Noether-style spatial charges by motif family")
    out_dir.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "pdf", "png"):
        fig.savefig(out_dir / f"noether_charge_heatmap.{ext}", dpi=300 if ext == "png" else None, bbox_inches="tight")
    plt.close(fig)


def make_report(
    out_path: Path,
    group_metrics: Sequence[Dict],
    prediction_metrics: Sequence[Dict],
    rows: Sequence[Dict[str, str]],
) -> None:
    best_tau = max(
        (row for row in prediction_metrics if row["target"] == "tau"),
        key=lambda row: row["accuracy"],
        default={},
    )
    exact_holographic = next((row for row in group_metrics if row["signature"] == "holographic_boundary_signature"), {})
    coarse_holographic = next((row for row in group_metrics if row["signature"] == "coarse_holographic_signature"), {})
    coarse_noether = next((row for row in group_metrics if row["signature"] == "coarse_noether_signature"), {})
    coarse_flux = next((row for row in group_metrics if row["signature"] == "coarse_boundary_flux_signature"), {})
    abstract = next((row for row in group_metrics if row["signature"] == "abstract_signature"), {})
    tau_predictions = {
        row["signature"]: row
        for row in prediction_metrics
        if row["target"] == "tau"
    }
    text = f"""# Holographic Boundary Experiment

## Mathematical Setup

The finite local template is treated as a bulk object embedded in the affine A2
hex lattice. Translation symmetry removes absolute position. D6 symmetry
quotients rotations and reflections. The Noether-style charges are line-charge
profiles along the three A2 coordinate foliations. The holographic boundary
data is the exposed colored flux around the occupied patch plus these line
charges and coarse topology.

This is not a theorem yet; it is an empirical test of whether boundary data
nearly determines the forcing physics.

## Headline Results

- Templates analysed: {len(rows)}
- Exact holographic groups: {exact_holographic.get('groups', '')}
- Exact holographic compression: {exact_holographic.get('compression_ratio', '')}
- Coarse holographic groups: {coarse_holographic.get('groups', '')}
- Coarse holographic compression: {coarse_holographic.get('compression_ratio', '')}
- Coarse Noether compression: {coarse_noether.get('compression_ratio', '')}
- Coarse boundary-flux compression: {coarse_flux.get('compression_ratio', '')}
- Abstract-incidence groups: {abstract.get('groups', '')}
- Abstract-incidence tau purity: {abstract.get('tau_purity', '')}
- Best leave-one-out tau predictor: {best_tau.get('signature', '')} at accuracy {best_tau.get('accuracy', '')}
- Coarse Noether leave-one-out tau accuracy: {tau_predictions.get('coarse_noether_signature', {}).get('accuracy', '')}
- Coarse boundary-flux leave-one-out tau accuracy: {tau_predictions.get('coarse_boundary_flux_signature', {}).get('accuracy', '')}
- Coarse holographic leave-one-out tau accuracy: {tau_predictions.get('coarse_holographic_signature', {}).get('accuracy', '')}

## Interpretation

The exact boundary state is almost a coordinate label, so it is not a useful
compression. The coarse boundary states are more interesting: they are weaker
than the abstract-incidence and integer-fingerprint quotients, but still carry
nontrivial predictive information. On this run, the tactical pressure is best
described by an algebraic bulk invariant, while the embedding boundary supplies
a partial "field theory" over motif family and topology.

## Group Metrics

```json
{json.dumps(list(group_metrics), indent=2)}
```

## Prediction Metrics

```json
{json.dumps(list(prediction_metrics), indent=2)}
```
"""
    out_path.write_text(text, encoding="utf-8")


def run_experiment(run_path: Path, out_dir: Optional[Path] = None) -> Dict:
    atlas_dir = run_path / "atlas"
    target = out_dir or atlas_dir / "holographic"
    templates = read_csv(atlas_dir / "template_signal_reservoir.csv")
    containment = read_csv(atlas_dir / "abstract_containment.csv")
    containment_by_id = {row["template_id"]: row for row in containment}
    rows = []
    for row in templates:
        merged = dict(row)
        merged.update(containment_by_id.get(row.get("template_id", ""), {}))
        rows.append(merged)
    enriched = add_descriptors(rows)
    group_metrics, prediction_metrics = all_experiment_metrics(enriched)

    write_csv(target / "holographic_templates.csv", enriched, list(enriched[0].keys()) if enriched else ["template_id"])
    write_csv(target / "signature_group_metrics.csv", group_metrics, list(group_metrics[0].keys()) if group_metrics else ["signature"])
    write_csv(target / "signature_prediction_metrics.csv", prediction_metrics, list(prediction_metrics[0].keys()) if prediction_metrics else ["signature", "target"])
    make_purity_figure(group_metrics, target)
    make_compression_accuracy_figure(group_metrics, prediction_metrics, target)
    make_noether_charge_figure(enriched, target)
    make_report(target / "holographic_report.md", group_metrics, prediction_metrics, enriched)

    summary = {
        "run": str(run_path),
        "rows": len(enriched),
        "out_dir": str(target),
        "group_metrics": group_metrics,
        "prediction_metrics": prediction_metrics,
    }
    (target / "holographic_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out", default="")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    summary = run_experiment(Path(args.run), Path(args.out) if args.out else None)
    compact = {
        "run": summary["run"],
        "rows": summary["rows"],
        "out_dir": summary["out_dir"],
        "group_metrics": summary["group_metrics"],
    }
    print(json.dumps(compact, indent=2))


if __name__ == "__main__":
    main()
