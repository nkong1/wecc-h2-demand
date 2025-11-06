import pandas as pd
from pathlib import Path
import shutil

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

logs_path = base_path / 'logs'
if logs_path.exists():
    shutil.rmtree(logs_path)
logs_path.mkdir()

# Constants
billion_btu_to_MWh_multiplier = 293.071070172

# Assumptions for final energy shares for aircraft fuel consumption
final_energy_shares_ref = {
    "electricity": 0.09,
    "direct_H2": 0.34,
    "ekerosene": 0.57
}

final_energy_shares_no_saf = {
    "electricity": 0.09,
    "direct_H2": 0.91,
    "ekerosene": 0
}

# Aircraft efficiency relative to jet fuel (lower = more efficient)
efficiencies = {
    "electricity": 0.148 / 0.409, 
    "H2": 0.285 / 0.409,        
    "ekerosene": 1.0                
}

# Conversion efficiency of producing e-kerosene from H2
h2_to_kerosene_conversion_efficiency = 0.47  # via the Fischer-Tropch process


"""
fuel_cell_efficiency = 0.60
electric_plane_efficiency = (87.2 - 40.5) / 2
jet_engine_efficiency = (38.6 - 15.6) / 2"""

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

def convert_to_h2_profile(daily_fuel_demand_df, decarb_pct, fuel_cell_only=False):
    """
    Inputs:
    - daily_fuel_demand_df: DataFrame of daily jet fuel demand by airport in bBtu
    - decarb_pct: percentage of demand to decarbonize (0-100)

    Returns:
    - DataFrame with total H2 demand (fuel cell + e-kerosene) in MWh
    """

    df = daily_fuel_demand_df.copy()

    # Step 1 Jet fuel demand to replace
    df["jet_fuel_to_replace_bBtu"] = df["fuel_use_bBtu"] * (decarb_pct / 100)

    # Get the shares of final energy demand by fuel
    if not fuel_cell_only:
        final_energy_shares = final_energy_shares_ref
    else: 
        final_energy_shares = final_energy_shares_no_saf

    # Step 2: Compute total final energy required (weighted by efficiency)
    total_final_energy_factor = sum(
        final_energy_shares[f] * efficiencies["H2" if f == "direct_H2" else f]
        for f in final_energy_shares
    )

    # Total final energy demand (all fuels combined)
    df["total_final_energy_bBtu"] = df["jet_fuel_to_replace_bBtu"] * total_final_energy_factor

    # Step 3. Project total final energy demand (all fuels combined)
    df["total_final_energy_bBtu"] = df["jet_fuel_to_replace_bBtu"] * total_final_energy_factor

    # Step 4. Disaggregate by fuel, based on shares and efficiencies
    for fuel, share in final_energy_shares.items():
        eff_key = "H2" if fuel == "direct_H2" else fuel
        df[f"{fuel}_final_bBtu"] = df["total_final_energy_bBtu"] * share

    # Step 5. Hydrogen energy calculations
    # Direct H2 (fuel cells)
    df["fuel_cell_h2_bBtu"] = df["direct_H2_final_bBtu"]

    # H2 for e-kerosene production
    df["saf_h2_bBtu"] = (df["ekerosene_final_bBtu"] / h2_to_kerosene_conversion_efficiency)

    # Step 6. Convert both to MWh
    df["fuel_cell_h2_mwh"] = df["fuel_cell_h2_bBtu"] * billion_btu_to_MWh_multiplier
    df["saf_h2_mwh"] = df["saf_h2_bBtu"] * billion_btu_to_MWh_multiplier

    # Step 7. Total H2 demand
    df["demand_mwh_h2"] = df["fuel_cell_h2_mwh"] + df["saf_h2_mwh"]

    return df.copy()



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

    return get_demand_grid(h2_demand_by_airport)



def model_aviation_demand(model_years, decarb_pcts, fuel_cell_only=False):

    print("\n===================\nAVIATION H2 DEMAND\n==================\n")

    iteration = 0

    av_df = pd.read_csv(aviation_fuel_path)
    jet_df = pd.read_csv(jet_fuel_path)
    
    combined_daily_profile = pd.DataFrame()

    for model_year in model_years:
        print(f'Processing year {model_year}\n')

        # Get the input parameters for the model year
        decarb_pct = decarb_pcts[iteration]

        av_gas_profile_by_airport = project_fuel_use_profile(
            get_fuel_use_profile_by_airport(av_df), "avgas", model_year
        )
        jet_fuel_profile_by_airport = project_fuel_use_profile(
            get_fuel_use_profile_by_airport(jet_df), "jetfuel", model_year
        )


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

        daily_h2_profile_by_airport = convert_to_h2_profile(combined_fuel_profile_by_airport, decarb_pct, fuel_cell_only)

        daily_h2_profile_by_airport.to_csv(logs_path / 'daily_h2_profile_by_airport.csv', index=False)

        h2_profile_by_load_zone = (
            daily_h2_profile_by_airport[["date", "LOAD_AREA", "demand_mwh_h2"]]
            .groupby(["LOAD_AREA", "date"], as_index=False).sum()
            .rename({'demand_mwh_h2': 'zone_demand_mwh_h2'})
        )

        h2_profile_by_load_zone['timeseries'] = f'{model_year}_all'
        
        combined_daily_profile = pd.concat([combined_daily_profile, h2_profile_by_load_zone])

        # Get the 5x5 km resolution of hydrogen demand
        wecc_demand_grid = get_airport_demand_grid(daily_h2_profile_by_airport)
        wecc_demand_grid.to_file(base_path.parent / 'outputs' / 'aviation' / 
            f'{model_year}_wecc_h2_demand_5km_resolution.gpkg', driver='GPKG')
        
        iteration += 1

    # Save combined the daily profile
    combined_daily_profile = combined_daily_profile.rename({'date': 'TIMEPOINT'})
    combined_daily_profile.to_csv(base_path.parent / 'outputs' / "h2_daily_demand.csv", index=False)

