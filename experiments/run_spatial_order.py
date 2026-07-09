"""
Spatial order in play corpora: patch entropy (E2) + residue extinctions (E3).

E2 -- patch complexity, the lattice-correct gateway to the Pisot/quasicrystal
conjecture (Meyer-ness is near-automatic for lattice subsets; the contentful
dichotomy is patch-counting): pooled distinct-patch counts and patch Shannon
entropy over hex balls of radius r in {1,2,3}, color-normalized to the center
stone, at a MATCHED stone count N* across three corpora:
    strong  = results/hexo_bot2_selfplay.json      (2026-07-09, all decisive)
    weak    = results/modal_moves_python_8000.json (ca_combo_v2 self-play)
    random  = results/mdl_random_control_3000.json (random legal play)
Quasicrystalline order predicts strong-play patch entropy well below the
random baseline and (the sharper claim) below weak play at equal N.

E3 -- residue extinction. Two exact selection rules on win-windows:
  mod 3 (ramified prime, class c3 = (q - r) mod 3): every 6-window on every
    axis hits each class exactly twice (all three axis steps are +/-1 mod 3).
  mod 7 (split prime, the repo's arena._residue = (q + 2r) mod 7): every
    6-window misses exactly one of the 7 classes (axis steps 1, 2, -1 are
    invertible mod 7).
If threat-dense strong play balances class occupancy, the diffraction
amplitude at the class-dual wavevector is suppressed. The exact per-board
statistic is I_m = |sum_stones e^{2 pi i c/m}|^2 / N -- the structure factor
at the residue-dual point; E[I_m] = 1 for uniformly random classes, so
I_m << 1 in strong play = extinction, tested vs the random control
(Mann-Whitney, normal approximation).

Output: results/spatial_order.json,
        figures/fig_spatial_order_patches.png
        figures/fig_spatial_order_extinction.png
        figures/fig_spatial_order_diffraction.png
"""
from __future__ import annotations

import json
import math
import random
from collections import Counter
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
CORPORA = {
    "strong": ROOT / "results" / "hexo_bot2_selfplay.json",
    "weak": ROOT / "results" / "modal_moves_python_8000.json",
    "random": ROOT / "results" / "mdl_random_control_3000.json",
}
OUT = ROOT / "results" / "spatial_order.json"
C = {"strong": "#2a78d6", "weak": "#eda100", "random": "#e34948"}
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e1e0d9"
MAX_GAMES = 400
SEED = 0


def player_at(i: int) -> int:
    if i == 0:
        return 1
    return 2 if ((i - 1) // 2) % 2 == 0 else 1


def boards_at(path: Path, n_stones: int, max_games: int) -> list[dict]:
    games = json.loads(path.read_text())["games"]
    out = []
    for g in games:
        if len(out) >= max_games:
            break
        if len(g["moves"]) < n_stones:
            continue
        b = {}
        ok = True
        for i, (q, r) in enumerate(g["moves"][:n_stones]):
            if (q, r) in b:
                ok = False
                break
            b[(q, r)] = player_at(i)
        if ok:
            out.append(b)
    return out


def hex_ball(radius: int) -> list[tuple[int, int]]:
    offs = []
    for dq in range(-radius, radius + 1):
        for dr in range(-radius, radius + 1):
            if (abs(dq) + abs(dr) + abs(dq + dr)) // 2 <= radius:
                offs.append((dq, dr))
    offs.sort()
    return offs


def patch_stats(boards: list[dict], radius: int, n_samples: int,
                rng: random.Random) -> dict:
    """Sample n_samples stone-centered patches (color-normalized: center
    stone's color -> 1), return distinct count and Shannon entropy."""
    offs = hex_ball(radius)
    all_patches = []
    for bi, b in enumerate(boards):
        for cell in b:
            all_patches.append((bi, cell))
    picks = rng.sample(all_patches, min(n_samples, len(all_patches)))
    counts: Counter = Counter()
    for bi, (q, r) in picks:
        b = boards[bi]
        me = b[(q, r)]
        patch = tuple(
            0 if (q + dq, r + dr) not in b
            else (1 if b[(q + dq, r + dr)] == me else 2)
            for dq, dr in offs)
        counts[patch] += 1
    n = sum(counts.values())
    ent = -sum((c / n) * math.log2(c / n) for c in counts.values())
    return {"radius": radius, "n_samples": n, "distinct": len(counts),
            "entropy_bits": ent,
            "max_entropy_bits": math.log2(min(n, 3 ** (len(offs) - 1)))}


def residue_stats(boards: list[dict]) -> dict:
    i3, i7 = [], []
    for b in boards:
        n = len(b)
        f3 = sum(complex(math.cos(2 * math.pi * ((q - r) % 3) / 3),
                         math.sin(2 * math.pi * ((q - r) % 3) / 3))
                 for q, r in b)
        f7 = sum(complex(math.cos(2 * math.pi * ((q + 2 * r) % 7) / 7),
                         math.sin(2 * math.pi * ((q + 2 * r) % 7) / 7))
                 for q, r in b)
        i3.append(abs(f3) ** 2 / n)
        i7.append(abs(f7) ** 2 / n)
    return {"I3": i3, "I7": i7}


def mann_whitney(a: list[float], b: list[float]) -> float:
    """One-sided p-value (a < b), normal approximation."""
    na, nb = len(a), len(b)
    ranks = {}
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    i = 0
    rsum_a = 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        rank = (i + j + 1) / 2
        for k in range(i, j):
            if allv[k][1] == 0:
                rsum_a += rank
        i = j
    u = rsum_a - na * (na + 1) / 2
    mu = na * nb / 2
    sigma = math.sqrt(na * nb * (na + nb + 1) / 12)
    z = (u - mu) / sigma
    return 0.5 * math.erfc(-z / math.sqrt(2)) if z < 0 else \
        1 - 0.5 * math.erfc(z / math.sqrt(2))


def diffraction_panel(boards: list[dict], m: int = 66) -> np.ndarray:
    acc = np.zeros((m, m))
    for b in boards:
        qs = [q for q, _ in b]
        rs = [r for _, r in b]
        q0, r0 = min(qs), min(rs)
        grid = np.zeros((m, m))
        for (q, r) in b:
            y, x = (r - r0) % m, (q - q0) % m
            grid[y, x] = 1.0
        grid -= grid.mean()
        acc += np.abs(np.fft.fft2(grid)) ** 2
    return np.fft.fftshift(acc / len(boards))


def main() -> None:
    rng = random.Random(SEED)
    # matched stone count: 30th percentile of strong-game lengths, capped 40
    strong_lens = [len(g["moves"]) for g in
                   json.loads(CORPORA["strong"].read_text())["games"]]
    n_star = min(40, sorted(strong_lens)[int(0.3 * len(strong_lens))])
    boards = {name: boards_at(p, n_star, MAX_GAMES)
              for name, p in CORPORA.items()}
    counts = {k: len(v) for k, v in boards.items()}
    print(f"[boards] N*={n_star} stones; usable games: {counts}")

    # E2: patch entropy, equal sample counts across corpora
    n_patch = min(len(v) for v in boards.values()) * n_star
    patch = {name: [patch_stats(bs, r, n_patch, rng) for r in (1, 2, 3)]
             for name, bs in boards.items()}

    # E3: residue extinction
    res = {name: residue_stats(bs) for name, bs in boards.items()}
    e3 = {}
    for m in ("I3", "I7"):
        e3[m] = {
            "mean": {n: float(np.mean(res[n][m])) for n in boards},
            "median": {n: float(np.median(res[n][m])) for n in boards},
            "p_strong_lt_random": mann_whitney(res["strong"][m], res["random"][m]),
            "p_strong_lt_weak": mann_whitney(res["strong"][m], res["weak"][m]),
            "p_weak_lt_random": mann_whitney(res["weak"][m], res["random"][m]),
        }

    # ---- figures ----
    fig, ax = plt.subplots(figsize=(5.4, 4.2), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    for name in ("strong", "weak", "random"):
        rs = [p["radius"] for p in patch[name]]
        es = [p["entropy_bits"] for p in patch[name]]
        ax.plot(rs, es, color=C[name], lw=2, marker="o", ms=5, label=name)
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("patch radius r (hex ball)", color=MUTED)
    ax.set_ylabel("patch entropy (bits)", color=MUTED)
    ax.set_title(f"Local pattern entropy at matched N={n_star} stones",
                 color=INK)
    ax.grid(color=GRID, lw=0.6)
    ax.tick_params(colors=MUTED)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.legend(frameon=False, labelcolor=INK)
    fig.tight_layout()
    f1 = ROOT / "figures" / "fig_spatial_order_patches.png"
    fig.savefig(f1, dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.8), facecolor="#fcfcfb")
    for ax, m, title in zip(axes, ("I3", "I7"),
                            ("mod-3 (ramified λ)", "mod-7 (split π)")):
        ax.set_facecolor("#fcfcfb")
        names = ["strong", "weak", "random"]
        data = [res[n][m] for n in names]
        bp = ax.boxplot(data, tick_labels=names, showfliers=False,
                        patch_artist=True, medianprops={"color": INK})
        for box, n in zip(bp["boxes"], names):
            box.set_facecolor(C[n])
            box.set_alpha(0.55)
        ax.axhline(1.0, color=MUTED, lw=1, ls="--")
        ax.text(0.52, 1.02, "random baseline E[I]=1", color=MUTED,
                fontsize=7, transform=ax.get_yaxis_transform())
        ax.set_title(f"structure factor at {title} dual", color=INK,
                     fontsize=10)
        ax.set_ylabel("I = |F(k)|²/N", color=MUTED)
        ax.grid(color=GRID, lw=0.6, axis="y")
        ax.tick_params(colors=MUTED)
        for s in ax.spines.values():
            s.set_color(GRID)
    fig.suptitle("Residue-class extinction test", color=INK)
    fig.tight_layout()
    f2 = ROOT / "figures" / "fig_spatial_order_extinction.png"
    fig.savefig(f2, dpi=150)
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), facecolor="#fcfcfb")
    for ax, name in zip(axes, ("strong", "weak", "random")):
        spec = diffraction_panel(boards[name])
        ax.imshow(np.log10(spec + 1e-9), cmap=matplotlib.colors.
                  LinearSegmentedColormap.from_list(
                      "seq", ["#fcfcfb", "#86b6ef", "#1c5cab", "#0d366b"]))
        # mod-3 dual wavevector (q-r)/3 -> bins (+/-22, -/+22) after shift
        for dy, dx in ((22, -22), (-22, 22)):
            ax.plot(33 + dx, 33 + dy, marker="o", ms=10, mfc="none",
                    mec="#e34948", mew=1.5)
        ax.set_title(name, color=INK, fontsize=10)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle("Mean diffraction power (log), mod-3 dual points circled",
                 color=INK)
    fig.tight_layout()
    f3 = ROOT / "figures" / "fig_spatial_order_diffraction.png"
    fig.savefig(f3, dpi=150)
    plt.close(fig)

    out = {"n_star": n_star, "usable_games": counts,
           "patch_complexity": patch, "extinction": e3, "seed": SEED}
    OUT.write_text(json.dumps(out, indent=2))
    print(json.dumps({"patch_entropy_bits": {
        n: {p['radius']: round(p['entropy_bits'], 3) for p in patch[n]}
        for n in patch}, "extinction": e3}, indent=2))
    print(f"[saved] {OUT}, {f1.name}, {f2.name}, {f3.name}")


if __name__ == "__main__":
    main()
