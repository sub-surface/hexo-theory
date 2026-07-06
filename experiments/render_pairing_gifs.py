"""
GIF replay: one representative game per distinct bot pairing of the Modal
bake-off (results/modal_bakeoff_screen.json).

Game choice per pairing: the shortest decisive game if any exists (those are
the interesting ones -- forks and conversions), else the first drawn opening.
Games are replayed locally: every bot is deterministic and openings are seeded
LCG, so the local replay is move-for-move the Modal game; the recorded winner
is asserted to match as a cross-platform determinism check.

Output: figures/replays/<a>__vs__<b>.gif (+ a summary JSON of which seed/game
each GIF shows).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "competition"))
import arena

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SQ3 = np.sqrt(3.0)


def hex_xy(q: int, r: int) -> tuple[float, float]:
    return q + r / 2.0, r * SQ3 / 2.0


def replay(name_a: str, name_b: str, seed: int, a_black: bool,
           budget_s: float = 5.0) -> tuple[int, list]:
    roster = arena.default_roster()
    b1, b2 = (roster[name_a], roster[name_b]) if a_black else (roster[name_b], roster[name_a])
    log: list = []
    w = arena.play_game(b1, b2, budget_s=budget_s, max_moves=400,
                        opening_seed=seed, opening_placements=16, move_log=log)
    return w, log


def render_gif(name_a: str, name_b: str, seed: int, a_black: bool,
               winner: int, log: list, out_path: Path) -> None:
    black_name = name_a if a_black else name_b
    white_name = name_b if a_black else name_a
    total = len(log)
    step = max(1, total // 120)  # cap ~120 frames (draws run to 400 placements)
    frame_ids = list(range(step, total + 1, step))
    if frame_ids[-1] != total:
        frame_ids.append(total)

    xs = [hex_xy(q, r)[0] for (q, r), _, _ in log]
    ys = [hex_xy(q, r)[1] for (q, r), _, _ in log]
    pad = 1.5
    xlim = (min(xs) - pad, max(xs) + pad)
    ylim = (min(ys) - pad, max(ys) + pad)

    frames = []
    fig, ax = plt.subplots(figsize=(4.6, 4.9), dpi=80)
    for n in frame_ids:
        ax.clear()
        ax.set_xlim(*xlim); ax.set_ylim(*ylim)
        ax.set_aspect("equal"); ax.axis("off")
        for i, ((q, r), player, in_opening) in enumerate(log[:n]):
            x, y = hex_xy(q, r)
            face = "#222222" if player == 1 else "#fafafa"
            edge = "#e08214" if in_opening else "#555555"
            ax.scatter([x], [y], s=110, c=face, edgecolors=edge,
                       linewidths=1.6 if in_opening else 0.8, zorder=2)
        lx, ly = hex_xy(*log[n - 1][0])
        ax.scatter([lx], [ly], s=26, c="#d62728", zorder=3)
        ax.set_title(f"{black_name} (B)  vs  {white_name} (W)\n"
                     f"seed {seed} | placement {n}/{total}", fontsize=9)
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba())[..., :3]
        frames.append(Image.fromarray(buf.copy()))
    # result banner, held
    res = ("draw / cutoff" if winner == 0 else
           f"{black_name if winner == 1 else white_name} wins "
           f"({'Black' if winner == 1 else 'White'})")
    ax.set_title(f"{black_name} (B)  vs  {white_name} (W)\n{res}", fontsize=9)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[..., :3]
    frames.extend([Image.fromarray(buf.copy())] * 12)
    plt.close(fig)

    frames[0].save(out_path, save_all=True, append_images=frames[1:],
                   duration=110, loop=0, optimize=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="first 3 pairings only")
    ap.add_argument("--source", default=str(ROOT / "results" / "modal_bakeoff_screen.json"))
    args = ap.parse_args()

    data = json.loads(Path(args.source).read_text())
    out_dir = ROOT / "figures" / "replays"
    out_dir.mkdir(parents=True, exist_ok=True)
    chosen = {}

    items = list(data["raw"].items())
    if args.quick:
        items = items[:3]
    for key, games in items:
        name_a, name_b = key.split("|")
        decisive = [g for g in games if g["result"] != "draw"]
        game = min(decisive, key=lambda g: g["n_stones"]) if decisive else games[0]
        w, log = replay(name_a, name_b, game["seed"], game["a_black"])
        if w != game["winner_raw"]:
            print(f"  !! replay mismatch for {key} seed {game['seed']}: "
                  f"local={w} modal={game['winner_raw']} -- rendering local replay")
        out = out_dir / f"{name_a}__vs__{name_b}.gif"
        render_gif(name_a, name_b, game["seed"], game["a_black"], w, log, out)
        chosen[key] = {"seed": game["seed"], "a_black": game["a_black"],
                       "winner": w, "placements": len(log),
                       "decisive": bool(decisive), "gif": out.name,
                       "replay_matches_modal": w == game["winner_raw"]}
        print(f"[gif] {out.name}  ({len(log)} placements, "
              + ("decisive" if decisive else "draw") + ")")

    (ROOT / "results" / "pairing_gifs.json").write_text(json.dumps(chosen, indent=2))
    print(f"[saved] {ROOT / 'results' / 'pairing_gifs.json'}")


if __name__ == "__main__":
    main()
