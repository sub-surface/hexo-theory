#!/usr/bin/env python3
from pathlib import Path
import sys
import pandas as pd

path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("rz_bdpn_overnight_run/data/zone_metrics.csv")
if not path.exists():
    print(f"No file: {path}")
    raise SystemExit(1)

df = pd.read_csv(path)
print("positions:", df["position_id"].nunique(), "rows:", len(df))
print(df.groupby("zone").agg(
    pair_reduction=("pair_reduction", "mean"),
    forcing_recall=("forcing_recall", "mean"),
    terminal_recall=("terminal_recall", "mean"),
    best_retention=("best_value_retention", "mean"),
    false_mass=("false_zone_mass", "mean"),
    zone_cells=("zone_cells", "mean"),
).sort_values(["forcing_recall", "pair_reduction"], ascending=False).to_string(float_format=lambda x: f"{x:0.3f}"))
