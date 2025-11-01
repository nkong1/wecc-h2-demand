import pandas as pd
from pathlib import Path

# from industry.aggregate_and_plot import get_aggregate_by_lz, get_demand_grid
# from industry.build_industry_profile import build_profile

# ======================
# File paths:
# ======================

base_path = Path(__file__).parent
aviation_fuel_path = base_path / "inputs" / "AV_bBtu_mat.csv"
jet_fuel_path = base_path / "inputs" / "JF_bBtu_mat.csv"
aeo_projections_path = (
    base_path / "inputs" / "Transportation_Energy_Use_(Case_Reference_case).csv"
)

# Constants
billion_btu_to_MWh_multiplier = 293.071070172
h2_to_efuel_efficiency = 0.47 # via the Fischer-Tropch process

# =============
# Read in AEO projections here to avoid reading it in every time a projection is needed
df = pd.read_csv(aeo_projections_path, header=4)
df["Year"] = df["Year"].astype(int)

# Build the two projection dictionaries
pct_change_jetfuel = dict(zip(df["Year"], df["pct_change_jetfuel"]))
pct_change_avgas = dict(zip(df["Year"], df["pct_change_avgas"]))
# =============


def get_fuel_use_profile(raw_data_df):

    # Transpose to get airports as rows
    av_airports_df = raw_data_df.T

    # Formatting
    av_airports_df.rename(columns=av_airports_df.iloc[0], inplace=True)
    av_airports_df = av_airports_df.iloc[1:]

    # Convert all daily columns to numeric
    time_cols = av_airports_df.columns[4:]
    for col in time_cols:
        av_airports_df[col] = pd.to_numeric(av_airports_df[col])

    # Aggregate demand by load zone
    aggregated_by_lz = av_airports_df.groupby("LOAD_AREA")[time_cols].sum()

    return aggregated_by_lz


def convert_to_h2_profile(fuel_use_profile, fuel_type, year, decarbonization_pct):
    """
    Inputs:
    - fuel_use_profile: a DataFrame of daily fuel use, from the get_fuel_use_profile function
    - fuel_type (String): either "jetfuel" or "avgas"
    - decarbonization_pct: a number between 0 and 100
    """

    h2_profile = pd.DataFrame()
    # Iterate across the load zones to stack
    for load_area, load_zone_profile in fuel_use_profile.iterrows():

        # Convert fuel consumption to MWh
        load_zone_profile *= billion_btu_to_MWh_multiplier

        # Convert to hydrogen demand
        load_zone_profile *= decarbonization_pct / 100

        # Project it into the future year
        projected_lz_profile = project_profile(load_zone_profile, fuel_type, year)
        projected_lz_profile["LOAD_AREA"] = load_area

        h2_profile = pd.concat([h2_profile, projected_lz_profile])
        h2_profile = h2_profile.sort_values(by=["LOAD_AREA", "date"])

    return h2_profile


def project_profile(h2_profile_series, fuel_type, year):
    """
    Projects a 2024 hydrogen demand daily profile into another year
    by matching weekdays (e.g., all Mondays in the target year get
    values from Mondays in 2024).
    """

    # --- 1. Reformat the 2024 profile ---
    h2_profile = h2_profile_series.reset_index()
    h2_profile.columns = ["date", "fuel_use"]
    h2_profile["date"] = pd.to_datetime(h2_profile["date"])

    # Ensure it's exactly the 2024 calendar
    h2_profile = h2_profile.sort_values("date")

    # --- 2. Build date lists ---
    dates_2024 = pd.DataFrame(
        {"date_2024": pd.date_range("2024-01-01", "2024-12-31", freq="D")}
    )
    dates_2024["weekday"] = dates_2024["date_2024"].dt.weekday  # Monday=0

    dates_proj = pd.DataFrame(
        {f"date_{year}": pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")}
    )
    dates_proj["weekday"] = dates_proj[f"date_{year}"].dt.weekday

    # --- 3. Create deterministic weekday mapping ---
    weekday_groups_2024 = {
        w: list(g["date_2024"]) for w, g in dates_2024.groupby("weekday")
    }
    counters = {w: 0 for w in range(7)}
    mapped_2024_dates = []

    for w in dates_proj["weekday"]:
        seq = weekday_groups_2024[w]
        mapped_2024_dates.append(seq[counters[w] % len(seq)])
        counters[w] += 1

    dates_proj["date_2024_mapped"] = mapped_2024_dates

    # --- 4. Merge 2050 dates with 2024 profile by mapped date ---
    dates_proj["date_2024_mapped"] = pd.to_datetime(dates_proj["date_2024_mapped"])
    daily_projected = dates_proj.merge(
        h2_profile, left_on="date_2024_mapped", right_on="date", how="left"
    )

    print(daily_projected.columns)
    # Clean up the columns
    daily_projected = daily_projected.drop(columns=["date_2024_mapped", "date", "weekday"], errors="ignore")

    daily_projected = daily_projected.rename(columns={
        "date_2050": "date",
    })

    # --- 5. Apply AEO25 multiplier ---
    if fuel_type == "jetfuel":
        growth_multiplier = pct_change_jetfuel[year]
    elif fuel_type == "avgas":
        growth_multiplier = pct_change_avgas[year]
    else:
        raise ValueError("invalid aviation fuel type")

    daily_projected["zone_demand_mwh_h2"] = daily_projected["fuel_use"] * growth_multiplier / h2_to_efuel_efficiency

    # --- 6. Output clean final dataframe ---
    daily_projected.rename(columns={f"date_{year}": "date"}, inplace=True)
    return daily_projected[["date", "zone_demand_mwh_h2"]]


def get_airports(raw_data_df):

    # Transpose to get airports as rows
    av_airports_df = raw_data_df.T

    # Formatting
    av_airports_df.rename(columns=av_airports_df.iloc[0], inplace=True)
    av_airports_df = av_airports_df.iloc[1:]


av_df = pd.read_csv(aviation_fuel_path)
final_df = convert_to_h2_profile(get_fuel_use_profile(av_df), "avgas", 2050, 100)

print(final_df)
final_df.to_csv("testing.csv", index=False)


jet_df = pd.read_csv(jet_fuel_path)
# Directly use the days and remove the mapping stuff