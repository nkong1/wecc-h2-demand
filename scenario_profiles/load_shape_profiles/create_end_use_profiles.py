"""
Generate normalized load shape profile CSVs for each sector.

Profiles:
  - Industry: hourly resolution (8760 hours), same profile for all industries
  - On-road Transport: hourly resolution (8760 hours), same for LD and HD
  - Aviation: daily resolution (365 days)

Each profile is normalized so the peak value = 1.
"""

import pandas as pd
import numpy as np
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
outputs_path = Path("outputs")
load_shapes_path = Path("scenario_profiles/load_shape_profiles") 
load_shapes_path.mkdir(parents=True, exist_ok=True)

# Sectors whose demand profiles live under outputs/<sector>/demand_profiles/
HOURLY_SECTORS = {
    "industry": {
        "profile_dir": outputs_path / "industry" / "demand_profiles",
        "demand_col": "total_h2_demand_kg",   # column to aggregate
        "output_file": "industry_load_shape.csv",
    },
    "transport": {
        "profile_dir": outputs_path / "transport" / "demand_profiles",
        "demand_col": "total_h2_demand_kg",
        "output_file": "on_road_transport_load_shape.csv",
    },
}

AVIATION_CONFIG = {
    "daily_file": outputs_path / "h2_daily_demand.csv",
    "demand_col": "zone_demand_mwh_h2",
    "day_col": "h2_daily_ts",
    "output_file": "aviation_load_shape.csv",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def aggregate_hourly_profiles(profile_dir: Path, demand_col: str) -> pd.Series:
    """
    Read every zone CSV in *profile_dir*, sum the demand column across all
    zones for each hour, and return a Series indexed 0..8759 (or however
    many hours exist).
    """
    all_frames = []
    for csv_file in sorted(profile_dir.glob("*_profile.csv")):
        df = pd.read_csv(csv_file)
        if demand_col not in df.columns:
            print(f"  [warning] '{demand_col}' not found in {csv_file.name}, skipping")
            continue
        df["datetime"] = pd.to_datetime(df["datetime"])
        all_frames.append(df[["datetime", demand_col]])

    if not all_frames:
        raise FileNotFoundError(
            f"No valid profile CSVs found in {profile_dir}"
        )

    combined = pd.concat(all_frames, axis=0)
    # Sum across all load zones for each timestamp
    hourly_total = combined.groupby("datetime")[demand_col].sum().sort_index()
    return hourly_total


def normalize(series: pd.Series) -> pd.Series:
    """Normalize so the maximum value equals 1."""
    peak = series.max()
    if peak == 0:
        print("  [warning] peak demand is 0 — returning zeros")
        return series
    return series / peak


# ---------------------------------------------------------------------------
# 1. Hourly load shapes: Industry & On-road Transport
# ---------------------------------------------------------------------------
for sector_name, cfg in HOURLY_SECTORS.items():
    print(f"\nProcessing {sector_name} …")
    profile_dir = cfg["profile_dir"]

    if not profile_dir.exists():
        print(f"  Directory not found: {profile_dir}  — skipping")
        continue

    hourly_total = aggregate_hourly_profiles(profile_dir, cfg["demand_col"])

    # Build output DataFrame
    out = pd.DataFrame({
        "datetime": hourly_total.index,
        "hour_of_year": range(1, len(hourly_total) + 1),
        "demand": hourly_total.values,
    })
    out["normalized_demand"] = normalize(out["demand"]).values

    out_path = load_shapes_path / cfg["output_file"]
    out.to_csv(out_path, index=False)
    print(f"  Saved → {out_path}  ({len(out)} rows, peak demand = {out['demand'].max():.2f})")


# ---------------------------------------------------------------------------
# 2. Daily load shape: Aviation
# ---------------------------------------------------------------------------
print("\nProcessing aviation …")
aviation_file = AVIATION_CONFIG["daily_file"]

if aviation_file.exists():
    av = pd.read_csv(aviation_file)

    day_col = AVIATION_CONFIG["day_col"]
    demand_col = AVIATION_CONFIG["demand_col"]

    # Sum across all load zones for each day-of-year
    daily_total = av.groupby(day_col, as_index=False)[demand_col].sum()
    daily_total = daily_total.sort_values(day_col).reset_index(drop=True)

    # Ensure 365 days present
    all_days = pd.DataFrame({day_col: range(1, 366)})
    daily_total = all_days.merge(daily_total, on=day_col, how="left").fillna(0)

    daily_total.rename(columns={day_col: "day_of_year", demand_col: "demand"}, inplace=True)
    daily_total["normalized_demand"] = normalize(daily_total["demand"]).values

    out_path = load_shapes_path / AVIATION_CONFIG["output_file"]
    daily_total.to_csv(out_path, index=False)
    print(f"  Saved → {out_path}  ({len(daily_total)} rows, peak demand = {daily_total['demand'].max():.2f})")
else:
    print(f"  Aviation daily file not found: {aviation_file}  — skipping")


print("\nDone.")