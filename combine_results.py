"""
This module is only called when both the industry and on-transport parts of the model are run.

For each load zone, this module combines the hydrogen demand profiles from on-road transport and industry.
It also combines 5x5km spatial distribution of on-road transport demand with that of industry demand.
"""

import pandas as pd
import geopandas as gpd
from pathlib import Path

# Define paths
outputs_path = Path(__file__).parent / 'outputs'
combined_profiles_path = outputs_path / 'combined_profile'

# Define the industries
industries = ["Iron_and_Steel", "Aluminum", "Cement", "Chemicals", "Refineries", "Glass"]

def combine(years, transport, industry, aviation):
    print('\n===================\nCombining Results...\n==================')

    print('\nCombining demand profiles...')
    combine_profiles(years, transport, industry, aviation)

    print('\nCombining demand grids...')
    combine_demand_grids(transport, industry, aviation)

def combine_demand_grids(transport=False, industry=False, aviation=False):
    """
    Combines 5x5km resolution demand grids from baseline and optionally
    transport, industry, and aviation into a single grid for each model year.
    
    Parameters:
    - transport (bool): If True, merge transport grid.
    - industry (bool): If True, merge industry grid.
    - aviation (bool): If True, merge aviation grid.
    """

    # Input folders
    baseline_profiles_path = outputs_path / 'baseline'
    industry_profiles_path = outputs_path / 'industry'
    transport_profiles_path = outputs_path / 'transport'
    aviation_profiles_path = outputs_path / 'aviation'

    # Loop over baseline files (this always exists)
    for baseline_grid_path in baseline_profiles_path.glob('*gpkg'):
        year = baseline_grid_path.stem.split('_')[0]

        # Read baseline grid
        combined = gpd.read_file(baseline_grid_path)
        combined.rename(columns={'total_h2_demand_kg': 'total_h2_demand_kg_baseline'}, inplace=True)

        # Merge industry if exists
        if industry:
            industry_grid = gpd.read_file(industry_profiles_path / baseline_grid_path.name)
            combined = combined.merge(
                industry_grid[['geometry', 'total_h2_demand_kg']],
                on='geometry',
                how='left'
            )
            combined.rename(columns={'total_h2_demand_kg': 'total_h2_demand_kg_industry'}, inplace=True)
        else:
            combined['total_h2_demand_kg_industry'] = 0

        # Merge transport if exists
        if transport:
            transport_grid = gpd.read_file(transport_profiles_path / baseline_grid_path.name)
            combined = combined.merge(
                transport_grid[['geometry', 'total_h2_demand_kg']],
                on='geometry',
                how='left'
            )
            combined.rename(columns={'total_h2_demand_kg': 'total_h2_demand_kg_transport'}, inplace=True)
        else:
            combined['total_h2_demand_kg_transport'] = 0

        # Merge aviation if exists
        if aviation:
            aviation_grid = gpd.read_file(aviation_profiles_path / baseline_grid_path.name)
            combined = combined.merge(
                aviation_grid[['geometry', 'total_h2_demand_kg']],
                on='geometry',
                how='left'
            )
            combined.rename(columns={'total_h2_demand_kg': 'total_h2_demand_kg_aviation'}, inplace=True)
        else:
            combined['total_h2_demand_kg_aviation'] = 0

        # Compute total demand
        combined['total_h2_demand_kg'] = (
            combined['total_h2_demand_kg_baseline'] +
            combined['total_h2_demand_kg_industry'] +
            combined['total_h2_demand_kg_transport'] + 
            combined['total_h2_demand_kg_aviation']
        )

        # Save to combined grids folder
        combined_output_path = outputs_path / f"{year}_wecc_h2_demand_grid_combined.gpkg"
        combined.to_file(combined_output_path, driver='GPKG')


def combine_profiles(years, transport=False, industry=False, aviation=False):
    """
    Combines the hydrogen demand profiles from baseline (always) and optionally
    transport and industry into a single, total profile for each load zone.
    
    Parameters:
    - years: list of model years (e.g., [2025, 2030])
    - transport: bool, include transport profiles if True
    - industry: bool, include industry profiles if True
    
    Saves the combined profiles to combined_profiles_path.
    """
    # Load all load zones
    load_zones_gdf = gpd.read_file('industry/inputs/load_zones/load_zones.shp')
    load_zones = load_zones_gdf['LOAD_AREA'].tolist()

    # Create new combined results folder
    """if combined_profiles_path.exists():
        shutil.rmtree(combined_profiles_path)
    combined_profiles_path.mkdir()"""

    # Input folders
    baseline_profiles_path = outputs_path / 'baseline' / 'demand_profiles'
    industry_profiles_path = outputs_path / 'industry' / 'demand_profiles'
    transport_profiles_path = outputs_path / 'transport' / 'demand_profiles'

    h2_timepoint_demand = []
    detailed_breakdown = []

    # Loop over each load zone
    for zone in load_zones:
        combined_df = pd.DataFrame()

        # -------------------------------
        # Baseline profile (always included)
        # -------------------------------
        baseline_file = baseline_profiles_path / f"{zone}_profile.csv"
        if baseline_file.exists():
            baseline_df = pd.read_csv(baseline_file).reset_index(drop=True)
            combined_df['h2_demand_kg_baseline'] = baseline_df['total_h2_demand_kg']
            combined_df['datetime'] = pd.to_datetime(baseline_df['datetime'])
        else:
            # If baseline profile missing, create hourly timestamps for all model years
            datetime_list = []
            for year in years:
                # 8760 hours per year (ignore leap years for simplicity)
                datetime_list.extend(pd.date_range(start=f'{year}-01-01', periods=8760, freq='h'))
            combined_df['datetime'] = pd.to_datetime(datetime_list)
            combined_df['h2_demand_kg_baseline'] = 0

        detailed_breakdown_df = combined_df.copy()

        # -------------------------------
        # Optional: Industry
        # -------------------------------
        if industry:
            industry_file = industry_profiles_path / f"{zone}_profile.csv"

            if industry_file.exists():
                industry_df = pd.read_csv(industry_file).reset_index(drop=True)

                for ind in industries:
                    detailed_breakdown_df[f'h2_demand_kg_{ind}'] = industry_df[ind]

                combined_df['h2_demand_kg_industry'] = industry_df['total_h2_demand_kg']
        else:
            combined_df['h2_demand_kg_industry'] = 0

            for ind in industries:
                detailed_breakdown_df[f'h2_demand_kg_{ind}'] = 0

        # -------------------------------
        # Optional: Transport
        # -------------------------------
        if transport:
            transport_file = transport_profiles_path / f"{zone}_profile.csv"

            if transport_file.exists():
                transport_df = pd.read_csv(transport_file).reset_index(drop=True)
                combined_df['h2_demand_kg_transport'] = transport_df['total_h2_demand_kg']

                detailed_breakdown_df['h2_demand_kg_Light_Duty_Transport'] = transport_df['ld_h2_demand']
                detailed_breakdown_df['h2_demand_kg_Heavy_Duty_Transport'] = transport_df['hd_h2_demand']
        else:
            combined_df['h2_demand_kg_transport'] = 0
            combined_df['h2_demand_kg_ld_transport'] = 0
            combined_df['h2_demand_kg_hd_transport'] = 0

            detailed_breakdown_df['h2_demand_kg_Light_Duty_Transport'] = 0
            detailed_breakdown_df['h2_demand_kg_Heavy_Duty_Transport']  = 0

        # -------------------------------
        # Compute total demand in MW
        # -------------------------------
        combined_df['zone_demand_mw_h2'] = (
            combined_df['h2_demand_kg_baseline'] +
            combined_df['h2_demand_kg_industry'] +
            combined_df['h2_demand_kg_transport']
        ) * 33.39 / 1000

        # -------------------------------
        # SWITCH formatting
        # -------------------------------
        combined_df['TIMEPOINT'] = range(1, len(combined_df)+1)
        combined_df['LOAD_ZONE'] = zone
        combined_df['timeseries'] = combined_df['datetime'].dt.year.astype(str) + '_all'
        combined_df['timestamp'] = combined_df['datetime'].dt.strftime('%Y-%m-%d-%H')

        # combined_df.to_csv(combined_profiles_path / f"{zone}_profile.csv", index=False)
        h2_timepoint_demand.append(combined_df)

        detailed_breakdown_df['LOAD_ZONE'] = zone
        detailed_breakdown_df['TIMEPOINT'] = combined_df['TIMEPOINT']
        detailed_breakdown_df['datetime'] = combined_df['datetime'] 

        detailed_breakdown.append(detailed_breakdown_df)

    h2_timepoint_demand_df = pd.concat(h2_timepoint_demand, axis=0)
    h2_timepoint_demand_df = h2_timepoint_demand_df.sort_values(['LOAD_ZONE', 'TIMEPOINT'])

    detailed_breakdown_df = pd.concat(detailed_breakdown, axis=0)
    detailed_breakdown_df = detailed_breakdown_df.sort_values(['LOAD_ZONE', 'TIMEPOINT'])
    # detailed_breakdown_df.to_csv('detailed_breakdown.csv', index=False)

    save_daily_profile(detailed_breakdown_df, aviation=aviation)

    # Organize columns
    h2_timepoint_demand_df = h2_timepoint_demand_df[['LOAD_ZONE', 'TIMEPOINT', 'zone_demand_mw_h2']]

    # Save final output
    h2_timepoint_demand_df.to_csv(outputs_path / "h2_timepoint_demand.csv", index=False)
    print("\nCombined profiles saved.")


def save_daily_profile(profile_df, aviation=False):
    """
    Aggregates hourly hydrogen demand profiles to daily resolution and optionally
    combines with aviation daily demand. Saves a CSV with one row per day (365 rows).
    
    Parameters:
    - profile_df: pd.DataFrame with columns['LOAD_ZONE', 'datetime', and 'h2_demand_kg_{sector} for every sector
    - aviation: bool, whether to include aviation daily profile (from h2_daily_demand.csv)
    """
    print('Saving combined daily profile across all load zones...')

    # Ensure datetime column is datetime type
    profile_df['datetime'] = pd.to_datetime(profile_df['datetime'])

    # Convert datetime to day-of-year integer (1–365)
    profile_df['day_of_year'] = profile_df['datetime'].dt.dayofyear

    # Identify all H2 demand columns
    h2_cols = [col for col in profile_df.columns if col.startswith('h2_demand_kg_')]

    # Convert kg to MWh
    kg_to_mwh = 33.39 / 1000
    for col in h2_cols:
        sector = col.replace('h2_demand_kg_', '')
        profile_df[f'demand_mwh_{sector}'] = profile_df[col] * kg_to_mwh

    # Aggregate hourly to daily across all load zones
    agg_cols = [f'demand_mwh_{col.replace("h2_demand_kg_", "")}' for col in h2_cols]
    daily_profile = profile_df.groupby('day_of_year', as_index=False)[agg_cols].sum()

    # Merge aviation daily demand (1–365)
    if aviation:
        aviation_daily_path = outputs_path / 'h2_daily_demand.csv'
        if aviation_daily_path.exists():
            aviation_daily = pd.read_csv(aviation_daily_path)  # columns: LOAD_AREA,date,demand_mwh_h2,timeseries
            aviation_daily = aviation_daily.groupby('date', as_index=False)['demand_mwh_h2'].sum()
            aviation_daily.rename(columns={'date':'day_of_year', 'demand_mwh_h2':'demand_mwh_aviation'}, inplace=True)
            daily_profile = daily_profile.merge(
                aviation_daily[['day_of_year', 'demand_mwh_aviation']],
                on='day_of_year', how='left'
            ).fillna(0)
        else:
            daily_profile['demand_mwh_aviation'] = 0
    else:
        daily_profile['demand_mwh_aviation'] = 0

    # Compute total daily demand
    total_cols = [col for col in daily_profile.columns if col.startswith('demand_mwh_')]
    daily_profile['demand_mwh_total'] = daily_profile[total_cols].sum(axis=1)

    # Fill missing days (1–365)
    all_days = pd.DataFrame({'day_of_year': range(1, 366)})
    daily_profile = all_days.merge(daily_profile, on='day_of_year', how='left').fillna(0)

    # Save final output
    output_csv_path = outputs_path / 'h2_daily_profile_detailed.csv'
    daily_profile.to_csv(output_csv_path, index=False)
    print(f'Combined daily profile saved as {output_csv_path}')
