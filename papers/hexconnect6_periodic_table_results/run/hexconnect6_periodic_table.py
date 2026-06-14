#!/usr/bin/env python3
"""
hexconnect6_periodic_table.py

Build a "periodic table of forcing atoms" from the Hex Connect-6 primitive atom miner.

Input:
  - a results zip or extracted folder containing data/primitive_atoms.csv
  - optional data/positive_pressure_events.csv

Output:
  - data/forcing_elements.csv
  - data/element_embeddings.csv
  - data/periodic_grid.csv
  - data/holographic_twins.csv
  - data/family_transition_candidates.csv
  - data/metrics.json
  - figures/periodic_table_of_forcing_atoms.png
  - figures/periodic_table_by_family.png
  - figures/element_frequency_rank.png
  - figures/bulk_boundary_compression.png
  - figures/element_embedding_multiplicity.png
  - figures/family_tau_pressure_map.png
  - figures/top_element_cards.png
  - figures/element_embedding_multiplicity_by_tau.png

Element definition:
  One "element" is one abstract bulk integer incidence fingerprint.
  Its "isotopes" / "embeddings" are distinct A2/D6 embedded primitive atoms
  with the same bulk fingerprint.

This deliberately separates:
  - bulk incidence algebra: integer_fingerprint
  - geometry: pair_shape, boundary flux, noether line charge
  - observed abundance: frequency
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import shutil
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



def axial_to_xy(c):
    q, r = c
    return (math.sqrt(3.0) * (q + r / 2.0), 1.5 * r)


def extract_if_zip(input_path: Path, work: Path) -> Path:
    if input_path.is_file() and input_path.suffix == ".zip":
        out = work / "extracted"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(out)
        return out
    return input_path


def find_file(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if not matches:
        raise FileNotFoundError(f"Could not find {name} under {root}")
    # Prefer data directory.
    matches.sort(key=lambda p: (0 if p.parent.name == "data" else 1, len(str(p))))
    return matches[0]


def parse_fingerprint(fp: str):
    """Return robust parsed data from incidence_integer_fingerprint string.

    Expected shape:
      (num_edges, num_vertices, edge_sizes, degrees, intersections, tau, min_transversals)
    """
    try:
        val = ast.literal_eval(fp)
        return {
            "fp_edges": int(val[0]),
            "fp_vertices": int(val[1]),
            "fp_edge_sizes": tuple(val[2]),
            "fp_degrees": tuple(val[3]),
            "fp_intersections": tuple(val[4]),
            "fp_tau": int(val[5]),
            "fp_min_transversals": int(val[6]),
        }
    except Exception:
        return {
            "fp_edges": np.nan,
            "fp_vertices": np.nan,
            "fp_edge_sizes": (),
            "fp_degrees": (),
            "fp_intersections": (),
            "fp_tau": np.nan,
            "fp_min_transversals": np.nan,
        }


def mode(series, default=""):
    if len(series) == 0:
        return default
    m = series.mode()
    if len(m):
        return m.iloc[0]
    return series.iloc[0]


def safe_int(x, default=0):
    try:
        if pd.isna(x):
            return default
        return int(x)
    except Exception:
        return default


def classify_element(row):
    tau = int(row["tau"])
    target = row["target_mode"]
    edge_hist = str(row["edge_size_hist_mode"])
    shape = str(row["pair_shape_mode"])
    axis = safe_int(row["axis_support_mean"])
    if target == "proto":
        stage = "Proto"
    elif row.get("terminal_count_sum", 0) > 0:
        stage = "Terminal"
    else:
        stage = "Exact"
    if "1:" in edge_hist:
        core = "Singleton Fork"
    elif axis >= 3:
        core = "Tri-axis Web"
    elif "(-1, 0)" in shape or "(-2, 0)" in shape or "(-3, 0)" in shape:
        core = "Rail Web"
    else:
        core = "Bridge Web"
    return f"{stage} {core}"


def build_elements(atoms: pd.DataFrame):
    # Ensure needed columns exist.
    for col in ["frequency", "source_count", "terminal_count"]:
        if col not in atoms.columns:
            atoms[col] = 1 if col == "frequency" else 0

    rows = []
    embeddings = []
    for i, (fp, g) in enumerate(atoms.groupby("integer_fingerprint", dropna=False)):
        parsed = parse_fingerprint(str(fp))
        tau_values = sorted(g["tau"].dropna().astype(int).unique().tolist())
        pressure_values = sorted(g["pressure"].dropna().astype(int).unique().tolist())
        tau = tau_values[0] if tau_values else parsed.get("fp_tau", 0)
        pressure = pressure_values[0] if pressure_values else max(0, tau - 2)
        target_mode = mode(g["target"], "")
        family_mode = mode(g["family"], "")
        pair_shape_mode = mode(g["pair_shape"], "")
        edge_size_hist_mode = mode(g["edge_size_hist"], "")
        frequency_sum = int(g["frequency"].sum())
        embedding_count = int(g["canonical_template"].nunique())
        boundary_count = int(g["coarse_boundary_flux_signature"].nunique()) if "coarse_boundary_flux_signature" in g else 0
        noether_count = int(g["coarse_noether_signature"].nunique()) if "coarse_noether_signature" in g else 0
        shape_count = int(g["pair_shape"].nunique())
        source_count = int(g["source"].nunique()) if "source" in g else 0
        atom_ids = ",".join(map(str, g["atom_id"].head(30).tolist())) if "atom_id" in g else ""
        row = {
            "integer_fingerprint": fp,
            "element_index_raw": i,
            "tau": int(tau),
            "pressure": int(pressure),
            "target_mode": target_mode,
            "family_mode": family_mode,
            "pair_shape_mode": pair_shape_mode,
            "edge_size_hist_mode": edge_size_hist_mode,
            "frequency": frequency_sum,
            "embedding_count": embedding_count,
            "boundary_count": boundary_count,
            "noether_count": noether_count,
            "shape_count": shape_count,
            "source_count": source_count,
            "atom_ids": atom_ids,
            "attacker_stones_min": int(g["attacker_stones"].min()) if "attacker_stones" in g else 0,
            "attacker_stones_mean": float(g["attacker_stones"].mean()) if "attacker_stones" in g else 0,
            "defender_stones_min": int(g["defender_stones"].min()) if "defender_stones" in g else 0,
            "defender_stones_mean": float(g["defender_stones"].mean()) if "defender_stones" in g else 0,
            "total_stones_min": int(g["total_stones"].min()) if "total_stones" in g else 0,
            "total_stones_mean": float(g["total_stones"].mean()) if "total_stones" in g else 0,
            "num_edges_mean": float(g["num_edges"].mean()) if "num_edges" in g else parsed.get("fp_edges", 0),
            "num_vertices_mean": float(g["num_vertices"].mean()) if "num_vertices" in g else parsed.get("fp_vertices", 0),
            "axis_support_mean": float(g["axis_support"].mean()) if "axis_support" in g else 0,
            "min_transversals_mode": int(mode(g["min_transversals"], parsed.get("fp_min_transversals", 0))) if "min_transversals" in g else parsed.get("fp_min_transversals", 0),
            "terminal_count_sum": int(g["terminal_count"].sum()) if "terminal_count" in g else 0,
            **parsed,
        }
        rows.append(row)
        for _, a in g.iterrows():
            embeddings.append({
                "integer_fingerprint": fp,
                "atom_id": a.get("atom_id", ""),
                "tau": int(a["tau"]),
                "pressure": int(a["pressure"]),
                "target": a.get("target", ""),
                "family": a.get("family", ""),
                "pair_shape": a.get("pair_shape", ""),
                "frequency": int(a.get("frequency", 1)),
                "canonical_template": a.get("canonical_template", ""),
                "coarse_boundary_flux_signature": a.get("coarse_boundary_flux_signature", ""),
                "coarse_noether_signature": a.get("coarse_noether_signature", ""),
                "board_json": a.get("board_json", ""),
                "move_json": a.get("move_json", ""),
                "edges_json": a.get("edges_json", ""),
            })

    elements = pd.DataFrame(rows)
    if elements.empty:
        return elements, pd.DataFrame(embeddings)

    elements["family_periodic"] = elements.apply(classify_element, axis=1)
    # Stable order: target/stage, tau, edges, vertices, then abundance.
    elements = elements.sort_values(
        ["tau", "target_mode", "fp_edges", "fp_vertices", "frequency", "embedding_count"],
        ascending=[True, True, True, True, False, False],
    ).reset_index(drop=True)
    elements["element_number"] = np.arange(1, len(elements) + 1)
    elements["symbol"] = elements.apply(lambda r: f'{str(r["target_mode"])[:1].upper()}{int(r["tau"])}-{int(r["element_number"]):02d}', axis=1)
    return elements, pd.DataFrame(embeddings)


def build_periodic_grid(elements: pd.DataFrame):
    # Place by tau rows and edge/vertex complexity columns.
    df = elements.copy()
    # "period" = tau, "group" = coarsened complexity by edges and vertices.
    df["period_tau"] = df["tau"]
    # Use edge/vertex pair as group, then rank within to avoid collisions.
    complexity_keys = sorted(df[["fp_edges", "fp_vertices"]].drop_duplicates().itertuples(index=False, name=None))
    group_index = {k: i + 1 for i, k in enumerate(complexity_keys)}
    df["complexity_group"] = [group_index[(r.fp_edges, r.fp_vertices)] for r in df.itertuples()]
    df["slot_rank"] = df.groupby(["period_tau", "complexity_group"]).cumcount()
    # If collisions, offset slightly in y/columns with slot_rank. For csv keep both.
    df["grid_x"] = df["complexity_group"] + 0.18 * df["slot_rank"]
    df["grid_y"] = df["period_tau"]
    return df


def find_holographic_twins(elements: pd.DataFrame, embeddings: pd.DataFrame):
    rows = []
    for _, e in elements.iterrows():
        if e["embedding_count"] > 1 or e["boundary_count"] > 1 or e["noether_count"] > 1:
            g = embeddings[embeddings["integer_fingerprint"] == e["integer_fingerprint"]]
            rows.append({
                "element_number": int(e["element_number"]),
                "symbol": e["symbol"],
                "tau": int(e["tau"]),
                "pressure": int(e["pressure"]),
                "embedding_count": int(e["embedding_count"]),
                "boundary_count": int(e["boundary_count"]),
                "noether_count": int(e["noether_count"]),
                "pair_shapes": ",".join(sorted(g["pair_shape"].dropna().astype(str).unique())),
                "families": ",".join(sorted(g["family"].dropna().astype(str).unique())),
                "atom_ids": ",".join(g["atom_id"].head(20).astype(str).tolist()),
                "integer_fingerprint": e["integer_fingerprint"],
            })
    return pd.DataFrame(rows).sort_values(["embedding_count", "boundary_count", "tau"], ascending=False) if rows else pd.DataFrame()


def family_transition_candidates(elements: pd.DataFrame):
    # Not true dynamics; a chemical-style adjacency: same/similar bulk shape with increasing tau or target shift.
    rows = []
    for _, a in elements.iterrows():
        for _, b in elements.iterrows():
            if a["element_number"] == b["element_number"]:
                continue
            close_edges = abs(a["fp_edges"] - b["fp_edges"]) <= 1
            close_vertices = abs(a["fp_vertices"] - b["fp_vertices"]) <= 2
            shape_match = a["pair_shape_mode"] == b["pair_shape_mode"]
            family_match = a["family_periodic"].split()[-1] == b["family_periodic"].split()[-1]
            tau_step = b["tau"] - a["tau"]
            if close_edges and close_vertices and (shape_match or family_match) and 0 <= tau_step <= 2:
                score = (2 if shape_match else 0) + (1 if family_match else 0) + (1 if tau_step > 0 else 0) + min(a["frequency"], b["frequency"]) / max(1, elements["frequency"].max())
                rows.append({
                    "from_element": int(a["element_number"]),
                    "to_element": int(b["element_number"]),
                    "from_symbol": a["symbol"],
                    "to_symbol": b["symbol"],
                    "from_tau": int(a["tau"]),
                    "to_tau": int(b["tau"]),
                    "from_family": a["family_periodic"],
                    "to_family": b["family_periodic"],
                    "pair_shape_match": bool(shape_match),
                    "transition_score": float(score),
                })
    return pd.DataFrame(rows).sort_values("transition_score", ascending=False).head(250) if rows else pd.DataFrame()


def plot_periodic_table(grid: pd.DataFrame, path: Path):
    if grid.empty:
        return
    families = sorted(grid["family_periodic"].unique())
    fam_idx = {f: i for i, f in enumerate(families)}
    plt.figure(figsize=(15, 8.5))
    ax = plt.gca()
    max_freq = max(1, grid["frequency"].max())
    for _, r in grid.iterrows():
        x = r["grid_x"]
        y = r["grid_y"]
        size = 0.82
        rect = plt.Rectangle((x - size/2, y - size/2), size, size,
                             fill=True, alpha=0.78, linewidth=1.2,
                             edgecolor="black")
        rect.set_facecolor(plt.cm.tab20(fam_idx[r["family_periodic"]] % 20))
        ax.add_patch(rect)
        ax.text(x, y + 0.18, r["symbol"], ha="center", va="center", fontsize=8, weight="bold")
        ax.text(x, y - 0.03, f'τ={int(r["tau"])}  f={int(r["frequency"])}', ha="center", va="center", fontsize=6)
        ax.text(x, y - 0.22, f'e={int(r["fp_edges"])} v={int(r["fp_vertices"])}', ha="center", va="center", fontsize=6)
    ax.set_xlim(grid["grid_x"].min() - 1, grid["grid_x"].max() + 1)
    ax.set_ylim(grid["grid_y"].min() - 1, grid["grid_y"].max() + 1)
    ax.invert_yaxis()
    ax.set_xlabel("bulk complexity group: (# hyperedges, # vertices)")
    ax.set_ylabel("period: transversal number τ")
    ax.set_title("Periodic table of Hex Connect-6 forcing atoms\nElement = abstract integer incidence fingerprint; isotopes = A2/D6 embeddings")
    # legend outside
    handles = [plt.Line2D([0], [0], marker='s', color='w', label=f,
                          markerfacecolor=plt.cm.tab20(fam_idx[f] % 20), markersize=10)
               for f in families[:20]]
    ax.legend(handles=handles, bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8)
    plt.tight_layout()
    plt.savefig(path, dpi=220)
    plt.close()


def plot_periodic_by_family(elements: pd.DataFrame, path: Path):
    piv = elements.pivot_table(index="tau", columns="family_periodic", values="frequency", aggfunc="sum", fill_value=0)
    plt.figure(figsize=(12, 6))
    plt.imshow(piv.values, aspect="auto", origin="lower")
    plt.xticks(np.arange(len(piv.columns)), piv.columns, rotation=45, ha="right")
    plt.yticks(np.arange(len(piv.index)), piv.index)
    plt.xlabel("family")
    plt.ylabel("tau")
    plt.title("Forcing-atom abundance by family and transversal period")
    plt.colorbar(label="frequency")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def plot_rank(elements: pd.DataFrame, path: Path):
    freq = elements["frequency"].sort_values(ascending=False).to_numpy()
    emb = elements.sort_values("frequency", ascending=False)["embedding_count"].to_numpy()
    plt.figure(figsize=(8, 5))
    plt.plot(np.arange(1, len(freq) + 1), freq, marker="o", label="frequency")
    plt.plot(np.arange(1, len(emb) + 1), emb, marker="o", label="embedding multiplicity")
    plt.xlabel("element rank")
    plt.ylabel("count")
    plt.title("Element rank curve: abundance and embedding multiplicity")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def plot_compression(elements: pd.DataFrame, atoms: pd.DataFrame, path: Path):
    labels = ["embedded atoms", "bulk elements", "families", "pair shapes"]
    vals = [
        len(atoms),
        len(elements),
        elements["family_periodic"].nunique(),
        atoms["pair_shape"].nunique() if "pair_shape" in atoms else 0,
    ]
    plt.figure(figsize=(7, 5))
    plt.bar(labels, vals)
    plt.ylabel("count")
    plt.title("Bulk/boundary compression hierarchy")
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def plot_embedding_multiplicity(elements: pd.DataFrame, path: Path):
    plt.figure(figsize=(8, 5))
    plt.scatter(elements["tau"], elements["embedding_count"], s=25 + 10 * np.log1p(elements["frequency"]))
    plt.xlabel("tau")
    plt.ylabel("A2/D6 embedding multiplicity")
    plt.title("Holographic multiplicity by transversal period")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()

    plt.figure(figsize=(8, 5))
    plt.scatter(elements["fp_edges"], elements["embedding_count"], s=25 + 10 * elements["tau"])
    plt.xlabel("# obligation hyperedges")
    plt.ylabel("embedding multiplicity")
    plt.title("Embedding multiplicity by bulk edge count")
    plt.tight_layout()
    plt.savefig(path.with_name("element_embedding_multiplicity_by_edges.png"), dpi=200)
    plt.close()


def plot_family_tau_pressure(elements: pd.DataFrame, path: Path):
    plt.figure(figsize=(8, 5.5))
    fams = sorted(elements["family_periodic"].unique())
    idx = {f: i for i, f in enumerate(fams)}
    plt.scatter(elements["tau"], elements["frequency"], c=[idx[f] for f in elements["family_periodic"]], s=40 + 15 * elements["embedding_count"])
    plt.xlabel("tau")
    plt.ylabel("frequency")
    plt.title("Forcing element frequency by tau and family")
    plt.colorbar(label="family index")
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()


def parse_cells_json(s):
    try:
        return json.loads(s)
    except Exception:
        return []


def plot_element_cards(elements: pd.DataFrame, embeddings: pd.DataFrame, path: Path, n=16):
    top = elements.sort_values(["frequency", "embedding_count", "tau"], ascending=False).head(n)
    cols = 4
    rows = math.ceil(len(top) / cols)
    plt.figure(figsize=(cols * 3.7, rows * 3.4))
    for i, (_, e) in enumerate(top.iterrows(), start=1):
        ax = plt.subplot(rows, cols, i)
        emb = embeddings[embeddings["integer_fingerprint"] == e["integer_fingerprint"]].sort_values("frequency", ascending=False).head(1)
        if not emb.empty:
            emb = emb.iloc[0]
            board = parse_cells_json(emb.get("board_json", "[]"))
            move = parse_cells_json(emb.get("move_json", "[]"))
            edges = parse_cells_json(emb.get("edges_json", "[]"))
            ob = sorted({tuple(c) for edge in edges for c in edge})
            for q, r, v in board:
                x, y = axial_to_xy((q, r))
                marker = "o" if v == 1 else "s"
                ax.scatter([x], [y], marker=marker, s=70)
            for c in move:
                x, y = axial_to_xy(tuple(c))
                ax.scatter([x], [y], marker="*", s=150)
            for c in ob:
                x, y = axial_to_xy(tuple(c))
                ax.scatter([x], [y], marker="x", s=80)
        ax.set_aspect("equal", adjustable="box")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(f'{e["symbol"]}  τ={int(e["tau"])}  emb={int(e["embedding_count"])}\n{e["family_periodic"]}', fontsize=9)
    plt.suptitle("Top forcing elements: sample embeddings\ncircle=A, square=D, star=move, x=obligation")
    plt.tight_layout()
    plt.savefig(path, dpi=220)
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Atom miner results zip or extracted folder")
    parser.add_argument("--out", default="hexconnect6_periodic_table_out")
    args = parser.parse_args()

    out = Path(args.out)
    fig = out / "figures"
    data = out / "data"
    work = out / "_work"
    for p in [fig, data, work]:
        p.mkdir(parents=True, exist_ok=True)

    root = extract_if_zip(Path(args.input), work)
    atoms_path = find_file(root, "primitive_atoms.csv")
    atoms = pd.read_csv(atoms_path)

    events = None
    try:
        events = pd.read_csv(find_file(root, "positive_pressure_events.csv"))
    except Exception:
        pass

    elements, embeddings = build_elements(atoms)
    grid = build_periodic_grid(elements)
    twins = find_holographic_twins(elements, embeddings)
    transitions = family_transition_candidates(elements)

    elements.to_csv(data / "forcing_elements.csv", index=False)
    embeddings.to_csv(data / "element_embeddings.csv", index=False)
    grid.to_csv(data / "periodic_grid.csv", index=False)
    twins.to_csv(data / "holographic_twins.csv", index=False)
    transitions.to_csv(data / "family_transition_candidates.csv", index=False)
    atoms.to_csv(data / "source_primitive_atoms.csv", index=False)
    if events is not None:
        events.to_csv(data / "source_positive_pressure_events.csv", index=False)

    plot_periodic_table(grid, fig / "periodic_table_of_forcing_atoms.png")
    plot_periodic_by_family(elements, fig / "periodic_table_by_family.png")
    plot_rank(elements, fig / "element_frequency_rank.png")
    plot_compression(elements, atoms, fig / "bulk_boundary_compression.png")
    plot_embedding_multiplicity(elements, fig / "element_embedding_multiplicity.png")
    plot_family_tau_pressure(elements, fig / "family_tau_pressure_map.png")
    plot_element_cards(elements, embeddings, fig / "top_element_cards.png")

    # Periodic table as a compact markdown/html for human browsing.
    top_cols = [
        "element_number", "symbol", "tau", "pressure", "frequency", "embedding_count",
        "family_periodic", "pair_shape_mode", "fp_edges", "fp_vertices", "min_transversals_mode"
    ]
    md = "# Periodic Table of Hex Connect-6 Forcing Atoms\n\n"
    md += "Element = abstract integer incidence fingerprint. Embeddings = distinct A2/D6 primitive atoms with the same bulk incidence algebra.\n\n"
    md += elements[top_cols].to_markdown(index=False)
    (out / "periodic_table.md").write_text(md)

    metrics = {
        "source_atoms": int(len(atoms)),
        "forcing_elements": int(len(elements)),
        "families": int(elements["family_periodic"].nunique()),
        "pair_shapes": int(atoms["pair_shape"].nunique()) if "pair_shape" in atoms else None,
        "compression_embedded_to_bulk": float(len(atoms) / max(1, len(elements))),
        "max_tau": int(elements["tau"].max()) if len(elements) else 0,
        "max_pressure": int(elements["pressure"].max()) if len(elements) else 0,
        "max_embedding_multiplicity": int(elements["embedding_count"].max()) if len(elements) else 0,
        "holographic_twin_elements": int(len(twins)),
        "top_elements": elements.sort_values(["frequency", "embedding_count"], ascending=False).head(12)[top_cols].to_dict(orient="records"),
        "top_holographic_twins": twins.head(12).to_dict(orient="records") if len(twins) else [],
        "family_counts": elements.groupby("family_periodic")["frequency"].sum().sort_values(ascending=False).to_dict(),
        "interpretation": (
            "The periodic table treats the bulk integer incidence fingerprint as the element. "
            "Different embedded primitive atoms with the same fingerprint are geometric isotopes/holographic twins. "
            "This separates tactical forcing invariants from A2/D6 boundary realisations."
        ),
    }
    with open(data / "metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    readme = """# Periodic Table of Hex Connect-6 Forcing Atoms

This package converts primitive embedded atoms into a periodic table of abstract
bulk forcing elements.

Core idea:
- Element = integer incidence fingerprint of the obligation hypergraph.
- Isotopes / embeddings = A2/D6 primitive atoms sharing that bulk fingerprint.
- Period = transversal number tau.
- Group = bulk complexity (# obligation hyperedges, # obligation vertices).
- Colour/family = proto/exact/terminal + rail/web/fork class.

Key files:
- periodic_table.md
- data/forcing_elements.csv
- data/element_embeddings.csv
- data/periodic_grid.csv
- data/holographic_twins.csv
- figures/periodic_table_of_forcing_atoms.png
- figures/top_element_cards.png
"""
    (out / "README.md").write_text(readme)

    zip_path = out.with_suffix(".zip")
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in out.rglob("*"):
            if "_work" in p.parts:
                continue
            z.write(p, p.relative_to(out.parent))
        z.write(Path(__file__), Path(out.name) / "hexconnect6_periodic_table.py")

    print(json.dumps(metrics, indent=2))
    print(f"wrote {zip_path}")


if __name__ == "__main__":
    main()
