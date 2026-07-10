#!/usr/bin/env python3
"""
Minimal CLI dashboard for the RZ-BDPN relevance-zone benchmark.

No dependencies beyond pandas/matplotlib for summaries already used by the benchmark.
Works on Windows PowerShell, cmd, macOS, and Linux.

Commands:
  help
  show
  set KEY VALUE
  save [PATH]
  start [CONFIG_PATH]
  stop
  status
  summary
  open
  exit

Examples:
  python dashboard.py
  rz> show
  rz> set positions 300
  rz> set zone_margin_ap_cells 10
  rz> start
  rz> status
  rz> stop
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

try:
    import pandas as pd
except Exception:
    pd = None

ROOT = Path(__file__).resolve().parent
BENCH = ROOT / "rz_bdpn_benchmark.py"
DEFAULT_CONFIG = ROOT / "configs" / "overnight.json"
SESSION_CONFIG = ROOT / "configs" / "_dashboard_session.json"


def parse_value(s: str):
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    low = s.lower()
    if low in ("true", "yes", "on"):
        return True
    if low in ("false", "no", "off"):
        return False
    try:
        return int(s)
    except Exception:
        pass
    try:
        return float(s)
    except Exception:
        pass
    return s


def load_config(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_config(cfg: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def out_dir(cfg: dict) -> Path:
    return Path(str(cfg.get("out", "rz_bdpn_dashboard_run")))


def show_config(cfg: dict):
    keys = [
        "out", "positions", "radius", "candidate_radius", "max_spread",
        "reference_candidate_width", "white_reply_width", "black_continuation_width",
        "candidate_pool", "candidate_reservoir", "reply_pool", "reply_reservoir",
        "zone_ap_cells", "zone_branch_moves", "zone_margin_ap_cells", "zone_margin_branch_moves",
        "zone_naive_radius", "checkpoint_every", "seed", "resume",
    ]
    print("\nactive config")
    print("-" * 72)
    for k in keys:
        if k in cfg:
            print(f"{k:30s} {cfg[k]}")
    print("-" * 72)


def summary(cfg: dict):
    if pd is None:
        print("pandas is not available; install requirements.txt first.")
        return
    d = out_dir(cfg)
    zpath = d / "data" / "zone_metrics.csv"
    if not zpath.exists():
        print(f"No zone_metrics.csv yet at {zpath}")
        return
    df = pd.read_csv(zpath)
    print(f"\npositions: {df['position_id'].nunique()} | rows: {len(df)} | out: {d}")
    table = df.groupby("zone").agg(
        pair_reduction=("pair_reduction", "mean"),
        forcing_recall=("forcing_recall", "mean"),
        terminal_recall=("terminal_recall", "mean"),
        best_retention=("best_value_retention", "mean"),
        false_mass=("false_zone_mass", "mean"),
        zone_cells=("zone_cells", "mean"),
    ).sort_values(["forcing_recall", "pair_reduction"], ascending=False)
    print(table.to_string(float_format=lambda x: f"{x:0.3f}"))


def status(proc, cfg):
    if proc is None:
        print("process: not started")
    else:
        rc = proc.poll()
        print("process:", "running" if rc is None else f"exited rc={rc}", f"pid={proc.pid}")
    d = out_dir(cfg)
    zpath = d / "data" / "zone_metrics.csv"
    if zpath.exists() and pd is not None:
        try:
            df = pd.read_csv(zpath, usecols=["position_id", "zone"])
            print(f"completed positions: {df['position_id'].nunique()} | zone rows: {len(df)}")
        except Exception as e:
            print("could not read progress:", e)
    elif zpath.exists():
        print(f"zone_metrics exists: {zpath}")
    else:
        print(f"no zone_metrics yet at {zpath}")


def start_process(cfg, config_path: Path):
    # Remove stale STOP marker if present.
    stop = out_dir(cfg) / "STOP"
    if stop.exists():
        try:
            stop.unlink()
        except Exception:
            pass
    save_config(cfg, config_path)
    cmd = [sys.executable, str(BENCH), "--config", str(config_path), "--resume"]
    print("starting:", " ".join(shlex.quote(x) for x in cmd))
    return subprocess.Popen(cmd, cwd=str(ROOT))


def stop_process(proc, cfg):
    # Soft stop: benchmark notices STOP between positions and exits cleanly.
    d = out_dir(cfg)
    d.mkdir(parents=True, exist_ok=True)
    (d / "STOP").write_text("stop requested by dashboard\n", encoding="utf-8")
    print(f"wrote soft-stop marker: {d / 'STOP'}")
    if proc is not None and proc.poll() is None:
        print("also sending terminate() to subprocess...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("terminate timed out; sending kill()")
            proc.kill()


def main():
    cfg_path = DEFAULT_CONFIG
    cfg = load_config(cfg_path)
    proc = None

    print("RZ-BDPN CLI dashboard")
    print("Type 'help' for commands. Start with 'show', then 'start'.")
    while True:
        try:
            line = input("rz> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            if proc is not None and proc.poll() is None:
                print("Run still active. Use 'stop' before exiting if you want to terminate it.")
            break
        if not line:
            continue
        parts = shlex.split(line)
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            if proc is not None and proc.poll() is None:
                print("Run still active. Use 'stop' first, or 'exit!' to leave it running.")
                continue
            break
        if cmd == "exit!":
            break
        elif cmd == "help":
            print(__doc__)
        elif cmd == "show":
            show_config(cfg)
        elif cmd == "set":
            if len(args) < 2:
                print("usage: set KEY VALUE")
                continue
            key = args[0]
            value = parse_value(" ".join(args[1:]))
            cfg[key] = value
            print(f"{key} = {value!r}")
        elif cmd == "save":
            path = Path(args[0]) if args else SESSION_CONFIG
            save_config(cfg, path)
            print(f"saved {path}")
        elif cmd == "load":
            path = Path(args[0]) if args else DEFAULT_CONFIG
            cfg = load_config(path)
            cfg_path = path
            print(f"loaded {path}")
        elif cmd == "start":
            if proc is not None and proc.poll() is None:
                print("already running; use status or stop")
                continue
            config_path = Path(args[0]) if args else SESSION_CONFIG
            proc = start_process(cfg, config_path)
        elif cmd == "stop":
            stop_process(proc, cfg)
        elif cmd == "status":
            status(proc, cfg)
        elif cmd == "summary":
            summary(cfg)
        elif cmd == "watch":
            try:
                every = float(args[0]) if args else 10.0
            except Exception:
                every = 10.0
            print("watching; press Ctrl+C to return to prompt")
            try:
                while True:
                    status(proc, cfg)
                    summary(cfg)
                    time.sleep(every)
            except KeyboardInterrupt:
                print()
        elif cmd == "open":
            d = out_dir(cfg).resolve()
            if sys.platform.startswith("win"):
                os.startfile(str(d))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(d)])
            else:
                subprocess.run(["xdg-open", str(d)])
        else:
            print("unknown command; type help")


if __name__ == "__main__":
    main()
