from __future__ import annotations

import csv
import html
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class BookPaths:
    root: Path
    markdown: Path
    html: Path
    figures: Path


@dataclass(frozen=True)
class CorpusSummary:
    opening_rows: int
    opening_wlu: dict[str, int]
    opening_classes: dict[str, int]
    opening_max_tree_nodes: int
    opening_mean_score: float
    self_play_games: int
    self_play_black_wins: int
    self_play_white_wins: int
    self_play_undecided: int
    parity_rows: list[dict[str, str]]
    atom_count: int
    atom_families: dict[str, int]
    atom_mean_gap: float


FIGURES = {
    "hex": "hex_d6_board.png",
    "progression": "length6_progression.png",
    "obligation": "obligation_hitting.png",
    "triads": "obligation_triads.png",
    "cooling": "one_cap_cooling.png",
    "opening": "opening_evidence.png",
    "strategy": "strategy_matrix.png",
    "parity": "parity_sweep.png",
    "pipeline": "atom_pipeline.png",
}


def default_paths(root: Path | None = None) -> BookPaths:
    root = (root or Path.cwd()).resolve()
    return BookPaths(
        root=root,
        markdown=root / "docs" / "connect6_theory_book.md",
        html=root / "reports" / "connect6_theory_book.html",
        figures=root / "reports" / "connect6_theory_book_figures",
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _as_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_corpus(root: Path) -> CorpusSummary:
    opening_rows = read_csv(root / "opening_tablebase_results" / "r3_depth3_corpus" / "opening_tablebase.csv")
    self_play_rows = read_csv(root / "self_play_results" / "r3_strategy_grid" / "strategy_matrix.csv")
    parity_rows = read_csv(root / "connect_k_parity_results" / "k3_to_k10" / "connect_k_parity.csv")
    atom_rows = read_csv(root / "primitive_atom_corpus_results" / "rich_run" / "primitive_atoms.csv")

    opening_wlu = Counter(row.get("wlu", "U") or "U" for row in opening_rows)
    opening_classes = Counter(row.get("final_class", "unknown") or "unknown" for row in opening_rows)
    tree_nodes = [_as_int(row.get("estimated_tree_nodes", "0")) for row in opening_rows]
    scores = [_as_float(row.get("score", "0")) for row in opening_rows]

    self_play_games = sum(_as_int(row.get("games", "0")) for row in self_play_rows)
    self_play_black_wins = sum(_as_int(row.get("black_wins", "0")) for row in self_play_rows)
    self_play_white_wins = sum(_as_int(row.get("white_wins", "0")) for row in self_play_rows)
    self_play_undecided = sum(_as_int(row.get("undecided", "0")) for row in self_play_rows)

    atom_families = Counter(row.get("family", "unknown") or "unknown" for row in atom_rows)
    gaps = [_as_float(row.get("integrality_gap", "0")) for row in atom_rows]

    return CorpusSummary(
        opening_rows=len(opening_rows),
        opening_wlu=dict(opening_wlu),
        opening_classes=dict(opening_classes),
        opening_max_tree_nodes=max(tree_nodes) if tree_nodes else 0,
        opening_mean_score=mean(scores) if scores else 0.0,
        self_play_games=self_play_games,
        self_play_black_wins=self_play_black_wins,
        self_play_white_wins=self_play_white_wins,
        self_play_undecided=self_play_undecided,
        parity_rows=parity_rows,
        atom_count=len(atom_rows),
        atom_families=dict(atom_families),
        atom_mean_gap=mean(gaps) if gaps else 0.0,
    )


def axial_to_xy(cell: tuple[int, int]) -> tuple[float, float]:
    q, r = cell
    return (q + 0.5 * r, 0.8660254037844386 * r)


def hex_ball(radius: int) -> list[tuple[int, int]]:
    cells = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            if max(abs(q), abs(r), abs(q + r)) <= radius:
                cells.append((q, r))
    return cells


def _require_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle

    return plt, Circle, FancyArrowPatch, Polygon, Rectangle


def _hex_patch(cell: tuple[int, int], size: float = 0.43, **kwargs):
    _, _, _, Polygon, _ = _require_matplotlib()
    x, y = axial_to_xy(cell)
    points = []
    for i in range(6):
        angle = 3.141592653589793 / 6 + i * 3.141592653589793 / 3
        points.append((x + size * __import__("math").cos(angle), y + size * __import__("math").sin(angle)))
    return Polygon(points, closed=True, **kwargs)


def draw_hex_d6_board(path: Path) -> None:
    plt, Circle, FancyArrowPatch, _, _ = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7, 6))
    for cell in hex_ball(3):
        face = "#ffffff"
        if cell == (0, 0):
            face = "#111111"
        ax.add_patch(_hex_patch(cell, facecolor=face, edgecolor="#bec7d5", linewidth=1.0))
    for d, color in [((1, 0), "#d1495b"), ((0, 1), "#2a9d8f"), ((1, -1), "#457b9d")]:
        for sign in (1, -1):
            end = (sign * 3.35 * d[0], sign * 3.35 * d[1])
            sx, sy = axial_to_xy((0, 0))
            ex, ey = axial_to_xy((end[0], end[1]))
            ax.add_patch(FancyArrowPatch((sx, sy), (ex, ey), arrowstyle="-|>", mutation_scale=14, linewidth=2.4, color=color))
    ax.add_patch(Circle(axial_to_xy((0, 0)), 0.18, color="#f4d35e"))
    ax.text(0, -3.55, "A2 axial ball, rooted seed, and the three unoriented Hex line foliations", ha="center", fontsize=10)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_length6_progression(path: Path) -> None:
    plt, *_ = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7, 2.8))
    line = [(-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0), (3, 0)]
    for cell in hex_ball(2):
        ax.add_patch(_hex_patch(cell, facecolor="#f9fafb", edgecolor="#d7dde8", linewidth=0.8))
    for i, cell in enumerate(line):
        ax.add_patch(_hex_patch(cell, facecolor="#202020", edgecolor="#000000", linewidth=1.2))
        x, y = axial_to_xy(cell)
        ax.text(x, y, str(i + 1), color="white", ha="center", va="center", fontsize=11, weight="bold")
    ax.text(0.45, -1.9, "A winning edge is a six-term arithmetic progression.", ha="center", fontsize=11)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_obligation_hitting(path: Path) -> None:
    plt, Circle, _, _, _ = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7, 4.2))
    positions = {
        "a": (0.0, 1.2),
        "b": (1.4, 1.2),
        "c": (0.7, 0.0),
        "d": (2.1, 0.0),
        "e": (2.8, 1.2),
    }
    edges = [("O1", ("a", "b"), "#e76f51"), ("O2", ("c", "d"), "#2a9d8f"), ("O3", ("b", "d", "e"), "#457b9d")]
    for label, members, color in edges:
        xs = [positions[m][0] for m in members]
        ys = [positions[m][1] for m in members]
        ax.plot(xs, ys, color=color, linewidth=6, alpha=0.25, solid_capstyle="round")
        ax.text(mean(xs), mean(ys) + 0.22, label, color=color, ha="center", fontsize=11, weight="bold")
    for name, (x, y) in positions.items():
        fill = "#f4d35e" if name in {"b", "c"} else "#ffffff"
        ax.add_patch(Circle((x, y), 0.16, facecolor=fill, edgecolor="#111111", linewidth=1.2))
        ax.text(x, y - 0.36, name, ha="center", va="center", fontsize=10)
    ax.text(1.4, -0.62, "Yellow cells hit every obligation: tau is the size of the smallest such hitting set.", ha="center", fontsize=10)
    ax.set_xlim(-0.4, 3.25)
    ax.set_ylim(-0.9, 1.75)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_triads(path: Path) -> None:
    plt, Circle, _, _, Rectangle = _require_matplotlib()
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.2))
    for ax, title in zip(axes, ["Independent singleton triad", "Independent pair triad"]):
        ax.set_title(title, fontsize=11)
        ax.axis("off")
        ax.set_aspect("equal")
    for i, x in enumerate([0, 1.2, 2.4]):
        axes[0].add_patch(Circle((x, 0.55), 0.18, facecolor="#f4d35e", edgecolor="#111111"))
        axes[0].text(x, 0.05, f"O{i+1}", ha="center", fontsize=10)
    for i, x in enumerate([0, 1.5, 3.0]):
        axes[1].add_patch(Rectangle((x - 0.24, 0.34), 0.48, 0.36, facecolor="#ffffff", edgecolor="#111111"))
        axes[1].add_patch(Rectangle((x - 0.24, -0.12), 0.48, 0.36, facecolor="#ffffff", edgecolor="#111111"))
        axes[1].text(x, -0.55, f"O{i+1}", ha="center", fontsize=10)
    axes[0].text(1.2, -0.52, "tau = 3: three separate one-cell bills", ha="center", fontsize=9)
    axes[1].text(1.5, -0.95, "tau = 3: three disjoint two-cell bills", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_one_cap_cooling(path: Path) -> None:
    plt, Circle, _, _, _ = _require_matplotlib()
    fig, axes = plt.subplots(2, 1, figsize=(8.5, 3.8), sharex=True)
    cases = [
        ("No cap: White can raise a full two-stone tax", set(), "best White tax: tau = 2"),
        ("One cap: Black cools the line and keeps one stone free", {-1}, "best White tax: tau = 1"),
    ]
    cells = list(range(-4, 6))
    for ax, (title, caps, note) in zip(axes, cases):
        for x in cells:
            fill = "#ffffff"
            edge = "#c7cedb"
            if x in {0, 1}:
                fill = "#ffffff"
                edge = "#111111"
            if x in caps:
                fill = "#111111"
                edge = "#111111"
            ax.add_patch(Circle((x, 0), 0.22, facecolor=fill, edgecolor=edge, linewidth=1.4))
            if x in {0, 1}:
                ax.text(x, 0, "W", ha="center", va="center", fontsize=9, weight="bold")
            if x in caps:
                ax.text(x, 0, "B", ha="center", va="center", fontsize=9, color="white", weight="bold")
        ax.plot([-4, 5], [0, 0], color="#e5e7eb", zorder=-1)
        ax.text(-4.35, 0.55, title, ha="left", fontsize=10, weight="bold")
        ax.text(5.25, 0, note, va="center", fontsize=10)
        ax.set_xlim(-4.7, 7.1)
        ax.set_ylim(-0.45, 0.85)
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_opening_evidence(path: Path) -> None:
    plt, *_ = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ["r3 exact reply scan", "r4 exact reply scan"]
    data = {
        "tau 0": [33111, 234708],
        "tau 1": [3915, 44304],
        "tau 2": [0, 5304],
        "tau > 2": [0, 0],
    }
    colors = ["#dbeafe", "#93c5fd", "#2563eb", "#111827"]
    bottoms = [0, 0]
    for (name, values), color in zip(data.items(), colors):
        ax.bar(labels, values, bottom=bottoms, label=name, color=color)
        bottoms = [a + b for a, b in zip(bottoms, values)]
    ax.set_ylabel("Black reply cases")
    ax.set_title("White's second-turn overload search after the seed")
    ax.legend(frameon=False, ncol=2)
    ax.text(0.5, -0.23, "No sampled finite opening produced White tau > 2.", transform=ax.transAxes, ha="center", fontsize=10)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_strategy_matrix(path: Path, root: Path) -> None:
    plt, *_ = _require_matplotlib()
    rows = read_csv(root / "self_play_results" / "r3_strategy_grid" / "strategy_matrix.csv")
    if not rows:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "Self-play matrix not available", ha="center", va="center")
        ax.axis("off")
        fig.savefig(path, dpi=180)
        plt.close(fig)
        return
    black = sorted({row["black_strategy"] for row in rows})
    white = sorted({row["white_strategy"] for row in rows})
    table = defaultdict(float)
    for row in rows:
        key = (row["black_strategy"], row["white_strategy"])
        table[key] = _as_float(row.get("mean_tactical_score", "0"))
    values = [[table[(b, w)] for w in white] for b in black]
    fig, ax = plt.subplots(figsize=(max(6, len(white) * 0.85), max(4, len(black) * 0.55)))
    im = ax.imshow(values, cmap="coolwarm", aspect="auto")
    ax.set_xticks(range(len(white)), white, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(black)), black, fontsize=8)
    ax.set_title("Strategy comparison: mean tactical score")
    fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_parity_sweep(path: Path, root: Path) -> None:
    plt, *_ = _require_matplotlib()
    rows = read_csv(root / "connect_k_parity_results" / "k3_to_k10" / "connect_k_parity.csv")
    if not rows:
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.text(0.5, 0.5, "Parity sweep not available", ha="center", va="center")
        ax.axis("off")
        fig.savefig(path, dpi=180)
        plt.close(fig)
        return
    ks = [_as_int(row["k"]) for row in rows]
    white_tau = [_as_float(row.get("white_max_tau", "0")) for row in rows]
    black_tau = [_as_float(row.get("black_reply_max_tau", "0")) for row in rows]
    prime = [row.get("prime", "False") == "True" for row in rows]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(ks, white_tau, marker="o", label="White opening max tau", color="#457b9d")
    ax.plot(ks, black_tau, marker="s", label="Black reply max tau", color="#d1495b")
    for k, is_prime in zip(ks, prime):
        if is_prime:
            ax.axvline(k, color="#f4d35e", alpha=0.22, linewidth=8)
    ax.set_xlabel("connect length k")
    ax.set_ylabel("observed max tau")
    ax.set_title("Odd/even and prime-length opening probes")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def draw_atom_pipeline(path: Path) -> None:
    plt, _, FancyArrowPatch, _, Rectangle = _require_matplotlib()
    fig, ax = plt.subplots(figsize=(8, 2.8))
    labels = ["position", "live lines", "obligations", "tau witness", "minor atom", "atlas"]
    xs = [0.6 + i * 1.35 for i in range(len(labels))]
    for x, label in zip(xs, labels):
        ax.add_patch(Rectangle((x - 0.43, 0.55), 0.86, 0.52, facecolor="#f8fafc", edgecolor="#334155", linewidth=1.2))
        ax.text(x, 0.81, label, ha="center", va="center", fontsize=9)
    for a, b in zip(xs[:-1], xs[1:]):
        ax.add_patch(FancyArrowPatch((a + 0.45, 0.81), (b - 0.45, 0.81), arrowstyle="-|>", mutation_scale=12, linewidth=1.2, color="#334155"))
    ax.text(4.0, 0.18, "The lab loop: missed tactic -> tau witness -> shrink -> canonical fingerprint.", ha="center", fontsize=10)
    ax.set_xlim(0, 8.3)
    ax.set_ylim(0, 1.45)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def generate_figures(paths: BookPaths) -> None:
    paths.figures.mkdir(parents=True, exist_ok=True)
    draw_hex_d6_board(paths.figures / FIGURES["hex"])
    draw_length6_progression(paths.figures / FIGURES["progression"])
    draw_obligation_hitting(paths.figures / FIGURES["obligation"])
    draw_triads(paths.figures / FIGURES["triads"])
    draw_one_cap_cooling(paths.figures / FIGURES["cooling"])
    draw_opening_evidence(paths.figures / FIGURES["opening"])
    draw_strategy_matrix(paths.figures / FIGURES["strategy"], paths.root)
    draw_parity_sweep(paths.figures / FIGURES["parity"], paths.root)
    draw_atom_pipeline(paths.figures / FIGURES["pipeline"])


def md_figure(filename: str, caption: str) -> str:
    return f"![{caption}](../reports/connect6_theory_book_figures/{filename})\n\n*{caption}*"


def build_markdown(summary: CorpusSummary) -> str:
    opening_wlu = ", ".join(f"{k}: {v}" for k, v in sorted(summary.opening_wlu.items())) or "not available"
    opening_classes = ", ".join(f"{k}: {v}" for k, v in sorted(summary.opening_classes.items())) or "not available"
    atom_families = ", ".join(f"{k}: {v}" for k, v in sorted(summary.atom_families.items())[:6]) or "not available"
    parity_lines = []
    for row in summary.parity_rows[:8]:
        parity_lines.append(
            f"| {row.get('k')} | {row.get('parity')} | {row.get('prime')} | {row.get('tempo_owner')} | "
            f"{row.get('white_max_tau')} | {row.get('black_reply_max_tau')} |"
        )
    parity_table = "\n".join(parity_lines) if parity_lines else "| n/a | n/a | n/a | n/a | n/a | n/a |"

    return f"""# The Little Book of Seeded Connect6

## A playful laboratory monograph on rooted Hex, obligations, atoms, and budget symmetry

This is a working theory book for the Connect6 lab. It is written as a playbook rather than a finished paper: positions get names, diagrams carry the burden, and conjectures are allowed to stand where the proofs are still being hunted.

The main claim is simple enough to fit on a slate:

```text
Seeded Hex Connect6 is a rooted progression-hypergraph game.
The visible stones are only the surface.
The tactical state is the live obligation hypergraph.
The opening question is whether Black's one-stone seed defect leaks through the later two-stone budget symmetry.
```

Our current answer is:

```text
The defect survives as a quiet resource leak, not as an immediate shallow win.
```

## 1. The Board That Is Not The Board

Normal Hex Connect6 is played on the A2 hex lattice. In axial coordinates the board cells are pairs `(q, r)`, and the three line directions are `(1, 0)`, `(0, 1)`, and `(1, -1)`. A player wins by occupying six consecutive cells on one of those lines.

{md_figure(FIGURES["hex"], "The rooted A2 board: the seed destroys translation symmetry but leaves a D6 stabiliser.")}

The first move is the unusual move: Black places one stone. After that both players place two stones per turn. The game therefore begins with a defect, then immediately puts both players on equal budget. That is the source of the central tension.

{md_figure(FIGURES["progression"], "A length-6 progression is a winning hyperedge.")}

The right object is not the board graph. It is the hypergraph of winning progressions:

```text
H = {{x, x+d, x+2d, x+3d, x+4d, x+5d}}
```

where `d` ranges over the three Hex directions.

## 2. Obligations

For a live line `L`, write:

```text
b_L = number of Black stones on L
w_L = number of White stones on L
e_L = empty cells of L
```

If `w_L = 0` and `0 < |e_L| <= 2`, then `e_L` is an urgent Black obligation: White must hit it immediately or Black can complete the line next turn.

So the position produces a family of missing-cell sets:

```text
O = {{missing cells of each urgent line}}
```

White's local survival question is not "how many threats are there?" It is:

```text
What is tau(O), the smallest number of cells that hits every obligation?
```

For Connect6 the defender has budget `p = 2`, so the local forcing threshold is:

```text
tau(O) > 2
```

{md_figure(FIGURES["obligation"], "Obligations form a small hitting problem; tactics live in the transversal, not the threat count.")}

## 3. Threats Are Not Numbers

The first trap in this game is counting threats as if they were coins. Three threats may be harmless if one stone blocks all of them. Two threats may be decisive if they are badly separated and the defender is short of tempo.

Two small positions deserve names:

{md_figure(FIGURES["triads"], "Two primitive bills: singleton and pair triads both force tau = 3 against a two-stone defender.")}

The moral:

```text
raw threat count != tactical force
transversal structure = tactical force
```

A forcing atom is a minor-minimal obligation family with `tau(O) > p`. The word "minor" matters: if a smaller subfamily already forces, the larger object is decoration. The atom is the part that actually bites.

## 4. The Seed Defect

The 1-2-2 rule is usually introduced as a balancing patch. The hypergraph view makes it stranger. Black's first stone breaks translation symmetry forever:

```text
A2 semidirect D6  ->  D6
```

White can restore material count, but White cannot unroot the game.

This gives the defect-vs-budget question:

```text
Does White's two-stone budget wash out the seed,
or can Black keep converting the seed into rooted obligation debt?
```

The opening probes suggest a middle answer. The seed does not produce a quick certified win. But the equal budget does not create exact symmetry either.

## 5. The Toll Gate: One-Cap Cooling

The smallest useful cartoon is one-dimensional. Suppose White has an adjacent pair on a length-6 line. If Black ignores it, White can spend two stones to raise a full two-stone tax. If Black places one adjacent cap, White's best line tax drops to one.

{md_figure(FIGURES["cooling"], "One-cap cooling: Black spends one stone to reduce White's next line tax from tau = 2 to tau = 1.")}

This is the current best name for the phenomenon:

```text
one-cap cooling
```

It explains why the defect survives quietly. Black can often spend one stone to cool White's even-budget local threat while investing the other stone into rooted debt. That is not a proof of a win. It is a resource leak.

### Puzzle 1

White has stones at `0` and `1` on a length-6 line. Black may place one cap at `-1` or `2`. What is White's strongest two-stone continuation after each cap? What changes if Black places no cap?

Answer in the lab notes: no cap permits a full `tau = 2` tax; one cap cools the line to `tau = 1`; two caps kill that line but spend Black's whole move.

## 6. Opening Evidence

The finite searches were not proofs of the infinite game. They were microscopes aimed at the seed-budget interaction.

The exact reply scans found:

```text
radius 3: tau 0 = 33111, tau 1 = 3915, tau 2 = 0, tau > 2 = 0
radius 4: tau 0 = 234708, tau 1 = 44304, tau 2 = 5304, tau > 2 = 0
```

{md_figure(FIGURES["opening"], "White's early overload search: the scans found taxes, not overloads.")}

The radius-3 tablebase corpus contains `{summary.opening_rows}` canonical openings. W/L/U counts: `{opening_wlu}`. Final classes: `{opening_classes}`. The largest estimated naive tree in that corpus was `{summary.opening_max_tree_nodes}` leaves before pruning.

The important reading is not "Black is proven winning." It is:

```text
White does not appear to get an immediate tau > 2 symmetry-restoring overload.
Black's problem is therefore quiet debt building, not shallow tactical conversion.
```

## 7. Atoms Of Play

The atom programme asks a Conway-style question:

```text
What are the indivisible local games?
```

For this lab, an atom is a minor-minimal obligation family where `tau(O) > p`. It has an abstract form and a geometric realisation.

{md_figure(FIGURES["pipeline"], "The atom-mining loop turns zone failures into canonical forcing witnesses.")}

The current rich atom corpus has `{summary.atom_count}` geometric rows. The most common named families include: `{atom_families}`. The mean observed integrality gap is `{summary.atom_mean_gap:.3f}`.

Especially interesting are atoms where:

```text
tau(O) > p but tau*(O) <= p
```

Those are discrete tactical effects invisible to smooth density heuristics.

## 8. Strategy Families

The self-play runner is not a perfect-play oracle. It is a way to compare temperaments. Some strategies try to maximise bulk pressure. Some minimise the opponent's obligations. Some screen first. Some chase atom load.

{md_figure(FIGURES["strategy"], "Strategy families compared by mean tactical score in the radius-3 self-play grid.")}

The current radius-3 strategy grid ran `{summary.self_play_games}` games: Black wins `{summary.self_play_black_wins}`, White wins `{summary.self_play_white_wins}`, undecided `{summary.self_play_undecided}`.

This supports the earlier observation that optimal-looking Black and White play may be structurally different. Black wants rooted debt and branching. White wants cooling, screening, and budget denial.

## 9. Odd, Even, Prime

Changing the connect length `k` changes the rhythm. The naive slogan is:

```text
even k gives White more natural budget symmetry
odd k leaves Black closer to the tempo edge
```

The data is still small, but it is already useful as a diagnostic.

{md_figure(FIGURES["parity"], "Connect-k sweep: prime and odd/even lengths as rhythm probes, not final theorems.")}

| k | parity | prime | tempo owner | White max tau | Black reply max tau |
|---|---|---|---|---|---|
{parity_table}

Connect-3 is almost too hot: it behaves like an immediate tactical fire. Connect-4 begins to look like a game. Connect-6 is in the interesting middle, where the seed matters but does not simply explode.

## 10. The Unproved Kingdom

The current lab result can be stated cautiously:

```text
Defect-vs-budget symmetry is leaky.
The seed survives as a resource asymmetry.
Finite opening probes find no immediate White tau > 2 overload.
One-cap cooling explains how Black can spend one stone defensively and keep one stone for rooted debt.
```

What is not proved:

- Black has not been certified to win infinite Hex Connect6.
- The finite radius tablebases are not complete infinite-board certificates.
- Boundary effects can exaggerate one-sided caps.
- The spectral and atom pictures are strong organising hypotheses, not replacement proofs.

The next theorem target is a resource ledger:

```text
required Black cooling stones
versus
free Black debt-building stones
versus
White's ability to split independent obligations
```

### Conjecture A: One-Cap Cooling Lemma

In the length-6 line abstraction, one adjacent Black cap reduces a White adjacent-pair continuation from a full-budget `tau = 2` tax to a `tau = 1` partial tax.

### Conjecture B: Defect Leakage

In infinite Hex Connect6, the rooted seed allows Black to repeatedly cool local even-budget threats with one stone while using the other stone to accumulate rooted obligation debt, unless White can force independent obligations faster than Black can cool them.

### Conjecture C: Atom-Preserving Relevance

A relevance zone is strategically valid only when it preserves the minor-minimal `tau > p` atoms reachable at the searched depth.

### Puzzle 2

Find the smallest A2 position where White's best reply is not to block the largest apparent Black threat, but to block a lower-count obligation that prevents a future atom. That is the sort of position a threat counter misses and an obligation atlas should catch.

## Coda

This book is deliberately unfinished. Its job is to make the game easier to think with. The next edition should add:

- certified outside-slack proof trees,
- a table of named atoms,
- boundary-shadow diagrams,
- spectral mode cartoons,
- and a small gallery of opening positions classified by the resource ledger.

The rule of thumb for the lab remains:

```text
Do not count threats.
Count the cheapest way to hit them.
Then ask who paid the bill.
```
"""


def markdown_to_html(markdown: str, title: str = "The Little Book of Seeded Connect6") -> str:
    lines = markdown.splitlines()
    body: list[str] = []
    in_code = False
    in_list = False
    in_table = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    def close_table() -> None:
        nonlocal in_table
        if in_table:
            body.append("</tbody></table>")
            in_table = False

    for line in lines:
        if line.startswith("```"):
            close_list()
            close_table()
            if in_code:
                body.append("</code></pre>")
                in_code = False
            else:
                body.append("<pre><code>")
                in_code = True
            continue
        if in_code:
            body.append(html.escape(line))
            continue
        if not line.strip():
            close_list()
            close_table()
            continue
        if line.startswith("|") and line.endswith("|"):
            cells = [html.escape(part.strip()) for part in line.strip("|").split("|")]
            if all(set(cell) <= {"-"} for cell in cells):
                continue
            if not in_table:
                body.append("<table><tbody>")
                in_table = True
            tag = "th" if not any("<tr>" in item for item in body[-1:]) else "td"
            body.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
            continue
        close_table()
        if line.startswith("# "):
            close_list()
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            close_list()
            body.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline_markdown(line[2:])}</li>")
        elif line.startswith("!["):
            close_list()
            alt, src = line[2:].split("](", 1)
            src = src.rstrip(")")
            if src.startswith("../reports/"):
                src = src[len("../reports/") :]
            body.append(f'<figure><img src="{html.escape(src)}" alt="{html.escape(alt)}"></figure>')
        elif line.startswith("*") and line.endswith("*") and len(line) > 2:
            close_list()
            body.append(f"<figcaption>{inline_markdown(line[1:-1])}</figcaption>")
        else:
            close_list()
            body.append(f"<p>{inline_markdown(line)}</p>")
    close_list()
    close_table()
    css = """
    :root { color-scheme: light; }
    body {
      margin: 0;
      background: #f5f3ee;
      color: #1f2933;
      font-family: Georgia, 'Times New Roman', serif;
      line-height: 1.62;
    }
    main {
      width: min(860px, calc(100% - 36px));
      margin: 0 auto;
      background: #fffdf8;
      min-height: 100vh;
      padding: 42px 48px 72px;
      box-shadow: 0 0 0 1px #e5dece, 0 22px 55px rgba(15, 23, 42, 0.12);
    }
    h1, h2, h3 { font-family: 'Trebuchet MS', Arial, sans-serif; line-height: 1.12; }
    h1 { font-size: clamp(2.1rem, 5vw, 4.4rem); margin: 0 0 0.6rem; }
    h2 { margin-top: 2.4rem; padding-top: 0.7rem; border-top: 2px solid #242424; font-size: 1.65rem; }
    h3 { margin-top: 1.7rem; font-size: 1.15rem; color: #334155; }
    p, li { font-size: 1.02rem; }
    pre {
      background: #18202f;
      color: #f8fafc;
      padding: 16px 18px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 0.92rem;
    }
    code { font-family: Consolas, 'Liberation Mono', monospace; }
    figure { margin: 1.2rem 0 0.2rem; }
    img {
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      background: white;
    }
    figcaption {
      color: #52616f;
      font-size: 0.94rem;
      text-align: center;
      margin: 0.35rem 0 1.3rem;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1rem 0;
      font-size: 0.92rem;
    }
    th, td { border: 1px solid #d8d2c5; padding: 7px 9px; text-align: left; }
    th { background: #efe8d8; }
    """
    return "<!doctype html>\n" + f"""<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{css}</style>
</head>
<body>
<main>
{chr(10).join(body)}
</main>
</body>
</html>
"""


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    out = []
    i = 0
    in_code = False
    while i < len(escaped):
        if escaped[i] == "`":
            out.append("</code>" if in_code else "<code>")
            in_code = not in_code
        else:
            out.append(escaped[i])
        i += 1
    if in_code:
        out.append("</code>")
    return "".join(out)


def write_book(paths: BookPaths | None = None) -> BookPaths:
    paths = paths or default_paths()
    paths.markdown.parent.mkdir(parents=True, exist_ok=True)
    paths.html.parent.mkdir(parents=True, exist_ok=True)
    generate_figures(paths)
    summary = summarize_corpus(paths.root)
    markdown = build_markdown(summary)
    paths.markdown.write_text(markdown, encoding="utf-8")
    paths.html.write_text(markdown_to_html(markdown), encoding="utf-8")
    return paths


def main() -> None:
    paths = write_book(default_paths())
    print(f"Wrote {paths.markdown}")
    print(f"Wrote {paths.html}")
    print(f"Wrote figures to {paths.figures}")


if __name__ == "__main__":
    main()
