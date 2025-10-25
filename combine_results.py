"""
This module is only called when both the industry and on-transport parts of the model are run.

For each load zone, this module combines the hydrogen demand profiles from on-road transport and industry.
It also combines 5x5km spatial distribution of on-road transport demand with that of industry demand.
"""

import pandas as pd
import geopandas as gpd
import shutil
from pathlib import Path

# Define paths
outputs_path = Path(__file__).parent / 'outputs'
combined_profiles_path = outputs_path / 'combined_profile'
combined_grids_path = outputs_path / 'combined_grid'

def combine(years, transport, industry):
    print('\n===================\nCombining Results...\n==================')

    print('\nCombining demand profiles...')
    combine_profiles(years, transport, industry)

    print('\nCombining demand grids...')
    combine_demand_grids(transport, industry)

def combine_demand_grids(transport=False, industry=False):
    """
    Combines 5x5km resolution demand grids from baseline and optionally
    transport and industry into a single grid for each model year.
    
    Parameters:
    - transport (bool): If True, merge transport grids.
    - industry (bool): If True, merge industry grids.
    """
    # Create new combined results folder
    if combined_grids_path.exists():
        shutil.rmtree(combined_grids_path)
    combined_grids_path.mkdir()

    # Input folders
    baseline_profiles_path = outputs_path / 'baseline'
    industry_profiles_path = outputs_path / 'industry'
    transport_profiles_path = outputs_path / 'transport'

    # Loop over baseline files (baseline always exists)
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

        # Compute total demand
        combined['total_h2_demand_kg'] = (
            combined['total_h2_demand_kg_baseline'] +
            combined['total_h2_demand_kg_industry'] +
            combined['total_h2_demand_kg_transport']
        )

        # Save to combined grids folder
        combined_output_path = combined_grids_path / f"{year}_wecc_h2_demand_5km_combined.gpkg"
        combined.to_file(combined_output_path, driver='GPKG')


def combine_profiles(years, transport=False, industry=False):
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

    h2_timepoint_demand_df = pd.DataFrame()

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

        # -------------------------------
        # Optional: Industry
        # -------------------------------
        if industry:
            industry_file = industry_profiles_path / f"{zone}_profile.csv"
            if industry_file.exists():
                industry_df = pd.read_csv(industry_file).reset_index(drop=True)
                combined_df['h2_demand_kg_industry'] = industry_df['total_h2_demand_kg']
            else:
                combined_df['h2_demand_kg_industry'] = 0
        else:
            combined_df['h2_demand_kg_industry'] = 0

        # -------------------------------
        # Optional: Transport
        # -------------------------------
        if transport:
            transport_file = transport_profiles_path / f"{zone}_profile.csv"
            if transport_file.exists():
                transport_df = pd.read_csv(transport_file).reset_index(drop=True)
                combined_df['h2_demand_kg_transport'] = transport_df['total_h2_demand_kg']
            else:
                combined_df['h2_demand_kg_transport'] = 0
        else:
            combined_df['h2_demand_kg_transport'] = 0

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
        combined_df['TIMEPOINT'] = range(len(combined_df))
        combined_df['LOAD_ZONE'] = zone
        #combined_df['timeseries'] = combined_df['datetime'].dt.year.astype(str) + '_all'
        #combined_df['timestamp'] = combined_df['datetime'].dt.strftime('%Y-%m-%d-%H')

        # Organize columns
        combined_df = combined_df[['LOAD_ZONE', 'TIMEPOINT', 'zone_demand_mw_h2']]

        # Save result
        # combined_df.to_csv(combined_profiles_path / f"{zone}_profile.csv", index=False)
        h2_timepoint_demand_df = pd.concat([h2_timepoint_demand_df, combined_df])
        h2_timepoint_demand_df = h2_timepoint_demand_df.sort_values(['LOAD_ZONE', 'TIMEPOINT'])

    # Save final output
    h2_timepoint_demand_df.to_csv(outputs_path / "h2_timepoint_demand.csv", index=False)
    print("\nCombined profiles saved.")





