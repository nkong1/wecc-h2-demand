import pandas as pd
from pathlib import Path

from industry.aggregate_and_plot import get_demand_grid

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
h2_to_saf_efficiency = 0.47  # via the Fischer-Tropch process
fuel_cell_efficiency = 0.60
jet_engine_efficiency = 0.30

# =============
# Read in AEO projections here to avoid reading it in every time a projection is needed
df = pd.read_csv(aeo_projections_path, header=4)
df["Year"] = df["Year"].astype(int)

# Build the two projection dictionaries
pct_change_jetfuel = dict(zip(df["Year"], df["pct_change_jetfuel"]))
pct_change_avgas = dict(zip(df["Year"], df["pct_change_avgas"]))
# =============


def get_fuel_use_profile_by_airport(raw_data_df):
    """
    Takes in the input data for fuel use by airport and day in 2024 and 
    converts it into a friendlier format for processing
    """

    # Transpose to get airports as rows
    av_airports_df = raw_data_df.T

    # Formatting
    av_airports_df.rename(columns=av_airports_df.iloc[0], inplace=True)
    av_airports_df = av_airports_df.iloc[1:]

    # Convert all daily columns to numeric
    time_cols = av_airports_df.columns[4:]
    for col in time_cols:
        av_airports_df[col] = pd.to_numeric(av_airports_df[col])

    return av_airports_df


def project_fuel_use_profile(fuel_use_profile, fuel_type, year):
    """
    Inputs:
    - fuel_use_profile: a DataFrame of daily fuel use by airport, from get_fuel_use_profile_by_airport
    - fuel_type (String): either "jetfuel" or "avgas"
    - year: the model year

    Returns:
    - projected profile: a Dataframe with fuel use projected into the model year using AEO25 data
    """

    projected_profile = pd.DataFrame()
    # Iterate across the load zones to stack
    for airport, airport_profile in fuel_use_profile.iterrows():

        # Project it into the future year
        projected_airport_profile = project_h2_series(
            airport_profile.iloc[4:], fuel_type, year
        )
        projected_airport_profile["LOAD_AREA"] = airport_profile.loc["LOAD_AREA"]
        projected_airport_profile["AIRPORT"] = airport
        projected_airport_profile["Longitude"] = airport_profile.loc["LONGITUDE"]
        projected_airport_profile["Latitude"] = airport_profile.loc["LATITUDE"]
                
        projected_profile = pd.concat([projected_profile, projected_airport_profile])
        projected_profile = projected_profile.sort_values(
            by=["AIRPORT", "LOAD_AREA", "date"]
        )

    return projected_profile


def project_h2_series(h2_profile_series, fuel_type, year):
    """
    Projects daily fuel demand profile (as a series) from 2024 into the model year. Returns a series.
    """
    # Reformat the 2024 profile
    h2_profile = h2_profile_series.reset_index()
    h2_profile.columns = ["date", "fuel_use"]

    # Apply AEO25 multiplier
    if fuel_type == "jetfuel":
        growth_multiplier = pct_change_jetfuel[year]
    elif fuel_type == "avgas":
        growth_multiplier = pct_change_avgas[year]
    else:
        raise ValueError("invalid aviation fuel type")

    h2_profile["fuel_use_bBtu"] = h2_profile["fuel_use"] * growth_multiplier

    # Output clean final dataframe ---
    h2_profile = h2_profile.sort_values("date")
    h2_profile["date"] = range(1, 366, 1)
    return h2_profile[["date", "fuel_use_bBtu"]]


def convert_to_h2_profile(daily_fuel_demand_df, decarb_pct, fuel_cell_pct, saf_pct):
    """
     Inputs:
    - daily_fuel_demand_df: a DataFrame of daily fuel demand by airport in the model year
    - decarb_pct: a number between 0 and 100
    - fuel_cell_pct: the percentage of aviation fuel decarbonization that occurs via h2 fuel cells (0 to 100)
    - saf_pct: the percentage of aviation fuel decarbonization that occurs via e-kerosene (0 to 100).
        Note: fuel_cell_pct + saf_pct must equal 100.

    Returns:
    - a DataFrame
    """
    fuel_demand_df = daily_fuel_demand_df.copy()

    fuel_demand_df["fuel_cell_h2_mwh"] = (
        fuel_demand_df["fuel_use_bBtu"]
        * (decarb_pct / 100)
        * (fuel_cell_pct / 100)
        * (jet_engine_efficiency / fuel_cell_efficiency)
        * billion_btu_to_MWh_multiplier
    )

    fuel_demand_df["saf_h2_mwh"] = (
        fuel_demand_df["fuel_use_bBtu"]
        * (decarb_pct / 100)
        * (saf_pct / 100)
        / h2_to_saf_efficiency
        * billion_btu_to_MWh_multiplier
    )

    fuel_demand_df["demand_mwh_h2"] = (
        fuel_demand_df["fuel_cell_h2_mwh"] + fuel_demand_df["saf_h2_mwh"]
    )
    fuel_demand_df.to_csv('ratio.csv', index=False)
    return fuel_demand_df[["AIRPORT", "Latitude", "Longitude", "LOAD_AREA", "date", "demand_mwh_h2"]].copy()


def get_airport_demand_grid(h2_profile_by_airport):

    h2_demand_by_airport = (
        h2_profile_by_airport
        .groupby('AIRPORT', as_index=False)
        .agg({
            'demand_mwh_h2': 'sum',
            'Latitude': 'first',
            'Longitude': 'first'
        })
    )

    h2_demand_by_airport['total_h2_demand_kg'] = h2_demand_by_airport['demand_mwh_h2'] / 33.39 * 1000

    h2_demand_by_airport.to_csv('h2_demand_by_airport.csv', index=False)

    return get_demand_grid(h2_demand_by_airport)



def model_aviation_demand(model_years, decarb_pcts, fuel_cell_pcts, saf_pcts):

    print("\n===================\nAVIATION H2 DEMAND\n==================\n")

    iteration = 0

    av_df = pd.read_csv(aviation_fuel_path)
    jet_df = pd.read_csv(jet_fuel_path)
    
    combined_daily_profile = pd.DataFrame()

    for model_year in model_years:
        print(f'Processing year {model_year}\n')

        # Get the input parameters for the model year
        decarb_pct = decarb_pcts[iteration]
        fuel_cell_pct = fuel_cell_pcts[iteration]
        saf_pct = saf_pcts[iteration]

        av_gas_profile_by_airport = project_fuel_use_profile(
            get_fuel_use_profile_by_airport(av_df), "avgas", model_year
        )
        jet_fuel_profile_by_airport = project_fuel_use_profile(
            get_fuel_use_profile_by_airport(jet_df), "jetfuel", model_year
        )

        # av_gas_profile.to_csv("av_gas_profile.csv", index=False)
        # jet_fuel_profile.to_csv("jet_fuel_profile.csv", index=False)

        # Add aviation and jet fuel profiles
        combined_fuel_profile_by_airport = av_gas_profile_by_airport.merge(
            jet_fuel_profile_by_airport,
            on=["AIRPORT", "Latitude", "Longitude", "LOAD_AREA", "date"],
            suffixes=("_av", "_jet"),
        )
        combined_fuel_profile_by_airport["fuel_use_bBtu"] = (
            combined_fuel_profile_by_airport["fuel_use_bBtu_av"]
            + combined_fuel_profile_by_airport["fuel_use_bBtu_jet"]
        )

        combined_fuel_profile_by_airport.to_csv("combined_fuel_profile.csv", index=False)

        daily_h2_profile_by_airport = convert_to_h2_profile(
            combined_fuel_profile_by_airport, decarb_pct, fuel_cell_pct, saf_pct
        )

        h2_profile_by_load_zone = (
            daily_h2_profile_by_airport[["date", "LOAD_AREA", "demand_mwh_h2"]]
            .groupby(["LOAD_AREA", "date"], as_index=False).sum()
            .rename({'demand_mwh_h2': 'zone_demand_mwh_h2'})
        )
        
        combined_daily_profile = pd.concat([combined_daily_profile, h2_profile_by_load_zone])

        # Get the 5x5 km resolution of hydrogen demand
        wecc_demand_grid = get_airport_demand_grid(daily_h2_profile_by_airport)
        wecc_demand_grid.to_file(base_path.parent / 'outputs' / 'aviation' / 
            f'{model_year}_wecc_h2_demand_5km_resolution.gpkg', driver='GPKG')
        
        iteration += 1

    # Save combined the daily profile
    combined_daily_profile = combined_daily_profile.rename({'date': 'TIMEPOINT'})
    combined_daily_profile.to_csv(base_path.parent / 'outputs' / "h2_daily_profile.csv", index=False)

