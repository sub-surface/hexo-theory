"""Ambitious embedding-layer figures for Hex Connect-6 template atlases."""

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


PALETTE = atlas.PALETTE


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def as_int(row: Dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(float(row.get(key, default)))
    except (TypeError, ValueError):
        return default


def as_float(row: Dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def quotient_ladder_rows(summary: Dict) -> List[Dict[str, float]]:
    stages = [
        ("D6 templates", int(summary.get("canonical_rows", 0))),
        ("embedding signatures", int(summary.get("conway_embedding_signature_count", 0))),
        ("incidence signatures", int(summary.get("abstract_incidence_signature_count", 0))),
        ("integer fingerprints", int(summary.get("fingerprint_count", 0))),
        ("motif families", int(summary.get("family_count", 0))),
    ]
    out: List[Dict[str, float]] = []
    previous = 0
    for name, count in stages:
        compression = previous / count if previous and count else 1.0
        out.append(
            {
                "name": name,
                "count": count,
                "compression_from_previous": round(compression, 6),
            }
        )
        previous = count
    return out


def manifold_distribution(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    counts: Counter = Counter()
    for row in rows:
        counts[row.get("manifold_label") or "unknown"] += 1
    return dict(counts)


def family_atom_load_matrix(rows: Sequence[Dict[str, str]]) -> Tuple[List[str], List[int], List[List[int]]]:
    family_loads: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        family = row.get("family") or "unknown"
        load = as_int(row, "contained_abstract_atom_count")
        family_loads[family][load] += 1
    families = sorted(family_loads, key=lambda family: sum(family_loads[family].values()), reverse=True)
    loads = sorted({load for counter in family_loads.values() for load in counter})
    matrix = [[family_loads[family].get(load, 0) for load in loads] for family in families]
    return families, loads, matrix


def find_annular_templates(rows: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    return [row for row in rows if row.get("manifold_label") == "annulus"]


def load_atlas_tables(run_path: Path) -> Dict[str, object]:
    atlas_dir = run_path / "atlas"
    return {
        "summary": read_json(atlas_dir / "atlas_summary.json"),
        "templates": read_csv(atlas_dir / "template_signal_reservoir.csv"),
        "containment": read_csv(atlas_dir / "abstract_containment.csv"),
        "poset": read_csv(atlas_dir / "subtemplate_poset.csv"),
        "abstract_atoms": read_csv(atlas_dir / "abstract_atomic_representatives.csv"),
        "embedding_summary": read_csv(atlas_dir / "embedding_layer_summary.csv"),
    }


def save_figure(fig, out_dir: Path, stem: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.png", dpi=300, bbox_inches="tight")


def figure_style() -> None:
    atlas.apply_nature_style()


def make_quotient_telescope(summary: Dict, out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figure_style()
    rows = quotient_ladder_rows(summary)
    names = [row["name"] for row in rows]
    counts = [row["count"] for row in rows]
    colors = [PALETTE["blue_main"], PALETTE["teal"], PALETTE["violet"], PALETTE["gold"], PALETTE["red_strong"]]

    fig, ax = plt.subplots(figsize=(7.0, 3.2))
    x = np.arange(len(rows))
    ax.bar(x, counts, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=18, ha="right")
    ax.set_ylabel("objects, log scale")
    ax.set_title("Quotient telescope: geometry to algebra")
    for i, row in enumerate(rows):
        ax.text(i, counts[i] * 1.08, str(counts[i]), ha="center", va="bottom", fontsize=7)
        if i > 0:
            ax.annotate(
                f"{row['compression_from_previous']:.2g}x",
                xy=(i - 0.5, max(counts[i - 1], counts[i]) * 0.85),
                ha="center",
                va="center",
                fontsize=7,
                color=PALETTE["neutral_dark"],
            )
    ax.text(
        0.01,
        0.95,
        "D6 is the embedding quotient; incidence minors are the tactical quotient.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color=PALETTE["neutral_dark"],
    )
    save_figure(fig, out_dir, "quotient_telescope")
    plt.close(fig)


def make_embedding_phase_portrait(rows: Sequence[Dict[str, str]], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_style()
    color_for = {
        "disk": PALETTE["blue_main"],
        "disconnected": PALETTE["gold"],
        "annulus": PALETTE["red_strong"],
        "punctured": PALETTE["violet"],
        "unknown": PALETTE["neutral_mid"],
    }
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    for label in sorted(manifold_distribution(rows)):
        subset = [row for row in rows if (row.get("manifold_label") or "unknown") == label]
        if not subset:
            continue
        x = [as_int(row, "a2_convex_deficit") for row in subset]
        y = [as_int(row, "boundary_edge_count") for row in subset]
        sizes = [18 + 6 * as_int(row, "tau") for row in subset]
        ax.scatter(
            x,
            y,
            s=sizes,
            c=color_for.get(label, PALETTE["neutral_mid"]),
            alpha=0.68,
            edgecolor="white",
            linewidth=0.35,
            label=f"{label} ({len(subset)})",
        )
    annuli = find_annular_templates(rows)
    for row in annuli:
        ax.annotate(
            row.get("template_id", "annulus"),
            xy=(as_int(row, "a2_convex_deficit"), as_int(row, "boundary_edge_count")),
            xytext=(6, 7),
            textcoords="offset points",
            fontsize=7,
            color=PALETTE["red_strong"],
            arrowprops={"arrowstyle": "-", "lw": 0.6, "color": PALETTE["red_strong"]},
        )
    ax.set_xlabel("A2 convex deficit")
    ax.set_ylabel("hex boundary edge count")
    ax.set_title("Embedding phase portrait")
    ax.legend(loc="upper left", fontsize=7)
    save_figure(fig, out_dir, "embedding_phase_portrait")
    plt.close(fig)


def make_atom_genealogy(
    containment_rows: Sequence[Dict[str, str]],
    poset_rows: Sequence[Dict[str, str]],
    out_dir: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    figure_style()
    families, loads, matrix = family_atom_load_matrix(containment_rows)
    fig = plt.figure(figsize=(7.2, 4.7))
    grid = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0], wspace=0.34)

    ax = fig.add_subplot(grid[0, 0])
    if matrix:
        arr = np.array(matrix, dtype=float)
        image = ax.imshow(arr, aspect="auto", cmap="YlGnBu")
        ax.set_yticks(range(len(families)))
        ax.set_yticklabels(families)
        ax.set_xticks(range(len(loads)))
        ax.set_xticklabels(loads)
        fig.colorbar(image, ax=ax, fraction=0.046, pad=0.03, label="templates")
    ax.set_xlabel("contained abstract atoms")
    ax.set_title("Recursive atom load")

    ax = fig.add_subplot(grid[0, 1])
    atom_counts = Counter(row["atom_template_id"] for row in poset_rows)
    top = atom_counts.most_common(12)
    if top:
        labels = [item[0] for item in top]
        values = [item[1] for item in top]
        ax.barh(range(len(top)), values, color=PALETTE["violet"], edgecolor="black", linewidth=0.4)
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
    ax.set_xlabel("containers")
    ax.set_title("Abstract minor genealogy")
    save_figure(fig, out_dir, "atom_minor_genealogy")
    plt.close(fig)


def axial_to_xy(cell: Tuple[int, int]) -> Tuple[float, float]:
    q, r = cell
    return (math.sqrt(3) * (q + r / 2), 1.5 * r)


def hex_polygon(cell: Tuple[int, int], radius: float = 0.46) -> List[Tuple[float, float]]:
    cx, cy = axial_to_xy(cell)
    points = []
    for i in range(6):
        angle = math.radians(60 * i + 30)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def cell_role_map(row: Dict[str, str]) -> Dict[Tuple[int, int], str]:
    roles = atlas.row_cell_roles(row)
    return {cell: atlas.role_color(role_set) for cell, role_set in roles.items()}


def make_annulus_spotlight(rows: Sequence[Dict[str, str]], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    figure_style()
    annuli = find_annular_templates(rows)
    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    if annuli:
        row = annuli[0]
        role_map = cell_role_map(row)
        cells = set(role_map)
        hull = atlas.a2_convex_hull_cells(cells)
        for cell in sorted(hull):
            poly = Polygon(
                hex_polygon(cell),
                closed=True,
                facecolor="#F4F4F4",
                edgecolor="#DFDFDF",
                linewidth=0.45,
            )
            ax.add_patch(poly)
        colors = {
            "A": PALETTE["neutral_black"],
            "D": PALETTE["red_strong"],
            "M": PALETTE["gold"],
            "O": PALETTE["blue_secondary"],
            "AO": PALETTE["teal"],
            "MO": PALETTE["violet"],
            "AM": PALETTE["neutral_dark"],
            "AMO": PALETTE["green_3"],
        }
        for cell, role in sorted(role_map.items()):
            poly = Polygon(
                hex_polygon(cell),
                closed=True,
                facecolor=colors.get(role, PALETTE["neutral_mid"]),
                edgecolor="black",
                linewidth=0.55,
            )
            ax.add_patch(poly)
        xs, ys = zip(*(axial_to_xy(cell) for cell in hull))
        ax.set_xlim(min(xs) - 1.0, max(xs) + 1.0)
        ax.set_ylim(min(ys) - 1.0, max(ys) + 1.0)
        title = (
            f"Annulus spotlight: {row.get('template_id')} | "
            f"tau={row.get('tau')} | deficit={row.get('a2_convex_deficit')}"
        )
        ax.set_title(title)
        ax.text(
            0.02,
            0.02,
            "black attacker, gold move, blue obligation, pale cells are convex hull voids",
            transform=ax.transAxes,
            ha="left",
            va="bottom",
            fontsize=7,
            color=PALETTE["neutral_dark"],
        )
    else:
        ax.text(0.5, 0.5, "No annular templates in this run", ha="center", va="center")
    ax.set_aspect("equal")
    ax.axis("off")
    save_figure(fig, out_dir, "annulus_spotlight")
    plt.close(fig)


def make_embedding_summary_panel(embedding_rows: Sequence[Dict[str, str]], out_dir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_style()
    rows = sorted(embedding_rows, key=lambda row: as_int(row, "templates"), reverse=True)[:24]
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    x = [as_float(row, "mean_convex_deficit") for row in rows]
    y = [as_float(row, "mean_boundary_edges") for row in rows]
    sizes = [28 + 18 * math.sqrt(max(1, as_int(row, "templates"))) for row in rows]
    colors = [as_float(row, "mean_a2_diameter") for row in rows]
    scatter = ax.scatter(x, y, s=sizes, c=colors, cmap="magma", alpha=0.78, edgecolor="white", linewidth=0.35)
    for row, x0, y0 in zip(rows[:8], x[:8], y[:8]):
        ax.text(x0 + 0.35, y0 + 0.35, str(as_int(row, "templates")), fontsize=6, color=PALETTE["neutral_dark"])
    fig.colorbar(scatter, ax=ax, fraction=0.04, pad=0.03, label="mean A2 diameter")
    ax.set_xlabel("mean convex deficit")
    ax.set_ylabel("mean boundary edges")
    ax.set_title("Embedding signature constellations")
    save_figure(fig, out_dir, "embedding_signature_constellations")
    plt.close(fig)


def generate_figures(run_path: Path, out_dir: Optional[Path] = None) -> Dict[str, str]:
    tables = load_atlas_tables(run_path)
    target = out_dir or run_path / "atlas" / "bold_figures"
    make_quotient_telescope(tables["summary"], target)
    make_embedding_phase_portrait(tables["templates"], target)
    make_atom_genealogy(tables["containment"], tables["poset"], target)
    make_annulus_spotlight(tables["templates"], target)
    make_embedding_summary_panel(tables["embedding_summary"], target)
    return {
        "out_dir": str(target),
        "figures": "quotient_telescope, embedding_phase_portrait, atom_minor_genealogy, annulus_spotlight, embedding_signature_constellations",
    }


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Path to a miner run with atlas outputs")
    parser.add_argument("--out", default="", help="Output folder; defaults to RUN/atlas/bold_figures")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    result = generate_figures(Path(args.run), Path(args.out) if args.out else None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
