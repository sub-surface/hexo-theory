"""Ultraminimal Hex Connect6 corpus viewer.

Run:
    python examples/game_viewer.py --corpus opening_tablebase_results/r3_corpus/opening_tablebase.json

Keys:
    Left/Right  step backward/forward
    Home/End    first/last frame
    Space       play/pause
    +/-         speed up/down
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from pathlib import Path
from tkinter import Button, Canvas, Entry, IntVar, Label, OptionMenu, Scale, Text, Tk, HORIZONTAL, StringVar, END
from tkinter import ttk

from PIL import Image, ImageDraw, ImageTk


Cell = tuple[int, int]
_DIRECTIONS: tuple[Cell, ...] = ((1, 0), (0, 1), (1, -1))


def _cell(raw) -> Cell:
    return int(raw[0]), int(raw[1])


def flatten_corpus_games(corpus: dict) -> list[dict]:
    if "games" in corpus:
        return corpus["games"]
    if "openings" in corpus:
        games = []
        for row in corpus["openings"]:
            moves = [{"color": "black", "stones": [[0, 0]]}]
            moves.append({"color": "white", "stones": row.get("white_pair", [])})
            if row.get("best_black_reply"):
                moves.append({"color": "black", "stones": row["best_black_reply"]})
            for step in row.get("principal_variation", []):
                color = "black" if step.get("player") == "black" else "white"
                move = step.get("move", [])
                if move:
                    moves.append({"color": color, "stones": move})
            games.append({"game_id": row.get("opening_id", f"game_{len(games)}"), "moves": moves, "class": row.get("final_class", "")})
        return games
    if "rollouts" in corpus:
        games = []
        for i, row in enumerate(corpus["rollouts"]):
            moves = [{"color": "black", "stones": [[0, 0]]}]
            moves.append({"color": "white", "stones": row.get("white_pair", [])})
            if row.get("black_reply"):
                moves.append({"color": "black", "stones": row["black_reply"]})
            games.append({"game_id": row.get("opening_id", f"rollout_{i}"), "moves": moves, "class": row.get("winner", "")})
        return games
    return []


def frames_from_game(game: dict) -> list[dict]:
    black: set[Cell] = set()
    white: set[Cell] = set()
    frames = [{"black": set(), "white": set(), "last": set(), "label": f"{game.get('game_id', 'game')} start"}]
    for i, move in enumerate(game.get("moves", []), 1):
        stones = {_cell(stone) for stone in move.get("stones", [])}
        if move.get("color") == "black":
            black |= stones
        else:
            white |= stones
        frames.append({
            "black": set(black),
            "white": set(white),
            "last": set(stones),
            "label": f"{game.get('game_id', 'game')} ply {i}: {move.get('color')}",
        })
    return frames


def find_winning_line(stones: set[Cell], k: int = 6) -> tuple[Cell, ...] | None:
    for q, r in sorted(stones):
        for dq, dr in _DIRECTIONS:
            line = tuple((q + i * dq, r + i * dr) for i in range(k))
            if all(cell in stones for cell in line):
                return line
    return None


def _has_win(stones: set[Cell], k: int = 6) -> bool:
    return find_winning_line(stones, k=k) is not None


def classify_game_wlu(game: dict) -> str:
    black: set[Cell] = set()
    white: set[Cell] = set()
    for move in game.get("moves", []):
        stones = {_cell(stone) for stone in move.get("stones", [])}
        if move.get("color") == "black":
            black |= stones
            if _has_win(black):
                return "B"
        else:
            white |= stones
            if _has_win(white):
                return "W"
    result = str(game.get("result", "")).lower()
    cls = str(game.get("class", "")).lower()
    if result == "black" or cls == "black_forced_line":
        return "B"
    if result == "white" or cls == "white_counter_line":
        return "W"
    return "U"


def sort_games_by_wlu(games: list[dict]) -> list[dict]:
    order = {"B": 0, "W": 1, "U": 2}
    return sorted(games, key=lambda game: (order[classify_game_wlu(game)], game.get("game_id", "")))


def filter_games_by_wlu(games: list[dict], status: str) -> list[dict]:
    return list(games) if status == "All" else [game for game in games if classify_game_wlu(game) == status]


def _bounds(frame: dict) -> tuple[int, int, int, int]:
    cells = frame["black"] | frame["white"] | {(0, 0)}
    qs = [q for q, _ in cells]
    rs = [r for _, r in cells]
    return min(qs), max(qs), min(rs), max(rs)


def _xy(cell: Cell, size: int, bounds: tuple[int, int, int, int]) -> tuple[float, float]:
    q, r = cell
    min_q, max_q, min_r, max_r = bounds
    span_q = max(1, max_q - min_q + 1)
    span_r = max(1, max_r - min_r + 1)
    scale = min(size / (span_q + 3), size / (span_r + 3))
    x = size / 2 + ((q - (min_q + max_q) / 2) + 0.5 * (r - (min_r + max_r) / 2)) * scale
    y = size / 2 + (0.8660254038 * (r - (min_r + max_r) / 2)) * scale
    return x, y


def render_frame_image(frame: dict, size: int = 500) -> Image.Image:
    image = Image.new("RGB", (size, size), "white")
    draw = ImageDraw.Draw(image)
    bounds = _bounds(frame)
    cells = sorted(frame["black"] | frame["white"] | {(0, 0)})
    radius = max(4, size // 75)
    black_win = find_winning_line(frame["black"])
    white_win = find_winning_line(frame["white"])
    win_line = black_win or white_win
    if win_line:
        points = [_xy(cell, size, bounds) for cell in win_line]
        draw.line(points, fill="#f2c94c", width=max(3, size // 120))
    for cell in cells:
        x, y = _xy(cell, size, bounds)
        color = "#222222" if cell in frame["black"] else "#d62728" if cell in frame["white"] else "#cccccc"
        outline = "#f2c94c" if cell in frame.get("last", set()) else "#555555"
        width = 3 if cell in frame.get("last", set()) else 1
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color, outline=outline, width=width)
    draw.text((8, 8), frame.get("label", ""), fill="#111111")
    return image


def save_gif(frames: list[dict], path: Path, size: int = 500, duration_ms: int = 140) -> None:
    images = [render_frame_image(frame, size=size) for frame in frames]
    if not images:
        return
    images[0].save(path, save_all=True, append_images=images[1:], duration=duration_ms, loop=0)


def load_games(path: Path) -> list[dict]:
    return flatten_corpus_games(json.loads(path.read_text(encoding="utf-8")))


def build_corpus_command(radius: int, depth: int, candidate_cells: int, limit: int | None, out_dir: str) -> list[str]:
    script = Path(__file__).with_name("opening_tablebase_corpus.py")
    command = [
        sys.executable,
        str(script),
        "--radius",
        str(radius),
        "--depth",
        str(depth),
        "--candidate-cells",
        str(candidate_cells),
        "--out",
        out_dir,
    ]
    if limit is not None:
        command.extend(["--limit", str(limit)])
    return command


def run_viewer(path: Path) -> None:
    all_games = sort_games_by_wlu(load_games(path))
    if not all_games:
        raise SystemExit(f"No games found in {path}")

    root = Tk()
    root.title("Hex6 Viewer")
    root.geometry("560x650")
    root.resizable(False, False)
    project_root = Path(__file__).resolve().parents[1]
    current_path = {"path": path}

    tabs = ttk.Notebook(root)
    tabs.pack(fill="both", expand=True)
    view_tab = ttk.Frame(tabs)
    run_tab = ttk.Frame(tabs)
    tabs.add(view_tab, text="Viewer")
    tabs.add(run_tab, text="Runs")

    status = StringVar(value="All")
    games = filter_games_by_wlu(all_games, status.get())
    option_labels = [f"{classify_game_wlu(game)} {game['game_id']}" for game in games]
    games_by_label = dict(zip(option_labels, games))
    selected = StringVar(value=option_labels[0])
    speed = IntVar(value=140)
    state = {"game": games[0], "frames": frames_from_game(games[0]), "index": 0, "playing": False, "photo": None}

    canvas = Canvas(view_tab, width=500, height=500, bg="white", highlightthickness=0)
    canvas.pack()
    label = Label(view_tab, text="")
    label.pack()

    def paint() -> None:
        frame = state["frames"][state["index"]]
        image = render_frame_image(frame, size=500)
        state["photo"] = ImageTk.PhotoImage(image)
        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=state["photo"])
        label.config(text=f"{classify_game_wlu(state['game'])}  {state['index']}/{len(state['frames']) - 1}  {frame.get('label', '')}")

    def choose(option_label: str) -> None:
        if option_label not in games_by_label:
            return
        game = games_by_label[option_label]
        state.update({"game": game, "frames": frames_from_game(game), "index": 0, "playing": False})
        paint()

    def rebuild_menu(*_args) -> None:
        nonlocal games, option_labels, games_by_label, menu
        games = filter_games_by_wlu(all_games, status.get())
        option_labels = [f"{classify_game_wlu(game)} {game['game_id']}" for game in games]
        games_by_label = dict(zip(option_labels, games))
        menu.destroy()
        if not option_labels:
            selected.set("(none)")
            menu = OptionMenu(view_tab, selected, "(none)")
            menu.place(x=10, y=522, width=150)
            label.config(text=f"no {status.get()} games")
            return
        selected.set(option_labels[0])
        menu = OptionMenu(view_tab, selected, *option_labels, command=choose)
        menu.place(x=10, y=522, width=150)
        choose(option_labels[0])

    def step(delta: int) -> None:
        state["index"] = max(0, min(len(state["frames"]) - 1, state["index"] + delta))
        paint()

    def jump(index: int) -> None:
        state["index"] = max(0, min(len(state["frames"]) - 1, index))
        paint()

    def tick() -> None:
        if not state["playing"]:
            return
        if state["index"] >= len(state["frames"]) - 1:
            state["playing"] = False
            return
        step(1)
        root.after(speed.get(), tick)

    def play_pause() -> None:
        state["playing"] = not state["playing"]
        if state["playing"]:
            tick()

    def export() -> None:
        out = current_path["path"].with_name(f"{state['game']['game_id']}.gif")
        save_gif(state["frames"], out, size=500, duration_ms=speed.get())
        label.config(text=f"exported {out.name}")

    def export_png() -> None:
        out = current_path["path"].with_name(f"{state['game']['game_id']}_{state['index']:02d}.png")
        render_frame_image(state["frames"][state["index"]], size=500).save(out)
        label.config(text=f"exported {out.name}")

    def load_corpus_file(corpus_path: Path) -> None:
        nonlocal all_games
        loaded = sort_games_by_wlu(load_games(corpus_path))
        if not loaded:
            raise ValueError(f"No games found in {corpus_path}")
        all_games = loaded
        current_path["path"] = corpus_path
        rebuild_menu()
        label.config(text=f"loaded {len(all_games)} games from {corpus_path.name}")

    controls = Canvas(view_tab, width=520, height=64, highlightthickness=0)
    controls.pack()
    menu = OptionMenu(view_tab, selected, *option_labels, command=choose)
    menu.place(x=10, y=522, width=150)
    status.trace_add("write", rebuild_menu)
    OptionMenu(view_tab, status, "All", "B", "W", "U").place(x=165, y=522, width=70)
    Scale(view_tab, from_=40, to=600, orient=HORIZONTAL, variable=speed, label="ms").place(x=240, y=512, width=120)
    Button(view_tab, text="Play", command=play_pause).place(x=365, y=530, width=50)
    Button(view_tab, text="GIF", command=export).place(x=420, y=530, width=45)
    Button(view_tab, text="PNG", command=export_png).place(x=470, y=530, width=50)

    run_radius = IntVar(value=3)
    run_depth = IntVar(value=3)
    run_candidates = IntVar(value=10)
    run_limit = StringVar(value="")
    run_out = StringVar(value="opening_tablebase_results/r3_from_viewer")
    run_state = {"running": False}

    def append_log(text: str) -> None:
        run_log.insert(END, text)
        run_log.see(END)

    def parse_limit() -> int | None:
        raw = run_limit.get().strip()
        return None if not raw else max(1, int(raw))

    def corpus_json_path() -> Path:
        return project_root / run_out.get().strip() / "opening_tablebase.json"

    def set_run_enabled(enabled: bool) -> None:
        run_state["running"] = not enabled
        run_button.config(state="normal" if enabled else "disabled")

    def run_corpus() -> None:
        if run_state["running"]:
            return
        try:
            radius = max(3, int(run_radius.get()))
            depth = max(1, int(run_depth.get()))
            candidates = max(2, int(run_candidates.get()))
            limit = parse_limit()
            out_dir = run_out.get().strip()
            if not out_dir:
                raise ValueError("output directory is required")
        except ValueError as exc:
            append_log(f"input error: {exc}\n")
            return

        command = build_corpus_command(radius, depth, candidates, limit, out_dir)
        append_log("$ " + " ".join(command) + "\n")
        append_log("running Torch-ranked alpha-beta corpus build...\n")
        set_run_enabled(False)

        def worker() -> None:
            try:
                completed = subprocess.run(command, cwd=project_root, capture_output=True, text=True)
            except OSError as exc:
                root.after(0, lambda: append_log(f"launch failed: {exc}\n"))
                root.after(0, lambda: set_run_enabled(True))
                return

            def finish() -> None:
                if completed.stdout:
                    append_log(completed.stdout)
                if completed.stderr:
                    append_log(completed.stderr)
                if completed.returncode == 0:
                    out_json = corpus_json_path()
                    append_log(f"done: {out_json}\n")
                    try:
                        load_corpus_file(out_json)
                        tabs.select(view_tab)
                    except (OSError, ValueError, json.JSONDecodeError) as exc:
                        append_log(f"load failed: {exc}\n")
                else:
                    append_log(f"failed with exit code {completed.returncode}\n")
                set_run_enabled(True)

            root.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def load_run_output() -> None:
        try:
            load_corpus_file(corpus_json_path())
            tabs.select(view_tab)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            append_log(f"load failed: {exc}\n")

    Label(run_tab, text="Radius").place(x=20, y=24, width=80, anchor="w")
    Entry(run_tab, textvariable=run_radius).place(x=120, y=14, width=60)
    Label(run_tab, text="Depth").place(x=20, y=58, width=80, anchor="w")
    Entry(run_tab, textvariable=run_depth).place(x=120, y=48, width=60)
    Label(run_tab, text="Candidates").place(x=20, y=92, width=90, anchor="w")
    Entry(run_tab, textvariable=run_candidates).place(x=120, y=82, width=60)
    Label(run_tab, text="Limit").place(x=210, y=24, width=70, anchor="w")
    Entry(run_tab, textvariable=run_limit).place(x=280, y=14, width=70)
    Label(run_tab, text="Output").place(x=210, y=58, width=70, anchor="w")
    Entry(run_tab, textvariable=run_out).place(x=280, y=48, width=245)
    Label(run_tab, text="Torch-ranked radius-n opening tablebase corpus").place(x=20, y=130, width=380, anchor="w")
    run_button = Button(run_tab, text="Run Corpus", command=run_corpus)
    run_button.place(x=20, y=160, width=110)
    Button(run_tab, text="Load Output", command=load_run_output).place(x=140, y=160, width=110)
    run_log = Text(run_tab, width=66, height=22)
    run_log.place(x=20, y=205, width=510, height=360)
    append_log("ready: radius >= 3, depth/candidate pruning is handled by the corpus builder\n")

    root.bind("<Left>", lambda _event: step(-1))
    root.bind("<Right>", lambda _event: step(1))
    root.bind("<Home>", lambda _event: jump(0))
    root.bind("<End>", lambda _event: jump(len(state["frames"]) - 1))
    root.bind("<space>", lambda _event: play_pause())
    root.bind("+", lambda _event: speed.set(max(40, speed.get() - 20)))
    root.bind("-", lambda _event: speed.set(min(600, speed.get() + 20)))
    paint()
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    args = parser.parse_args()
    run_viewer(Path(args.corpus))


if __name__ == "__main__":
    main()
