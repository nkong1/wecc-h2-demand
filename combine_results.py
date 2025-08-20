"""
This module is only called when both the industry and on-transport parts of the model are run.

For each load zone, this module combines the hydrogen demand profiles from on-road transport and industry.
It also combines 5x5km spatial distribution of on-road transport demand with that of industry demand.
"""

import pandas as pd
import geopandas as gpd
import os
import shutil
from pathlib import Path

# Define paths
outputs_path = Path(__file__).parent / 'outputs'
combined_profiles_path = outputs_path / 'combined_profile'
combined_grids_path = outputs_path / 'combined_grid'

def combine():
    print('\n===================\nCombining Results...\n==================')

    print('\nCombining demand profiles...')
    combine_profiles()

    print('\nCombining demand grids...')
    combine_demand_grids()

def combine_demand_grids():
    """
    Combines the 5x5km resolution demand grids from industry and transport into a single grid
    for each model year, saving the result to the combined_grids folder in the outputs
    """
    # Create new combined results folder
    if combined_grids_path.exists():
        shutil.rmtree(combined_grids_path)
    combined_grids_path.mkdir()

    # Input folders
    industry_profiles_path = outputs_path / 'industry' 
    transport_profiles_path = outputs_path / 'transport'

    # Combine the profiles for each year
    for industry_grid_path in industry_profiles_path.glob('*gpkg'):
        year = industry_grid_path.stem.split('_')[0] 

        industry_grid = gpd.read_file(industry_grid_path)
        transport_grid = gpd.read_file(transport_profiles_path / industry_grid_path.name)

        # Merge by geometry
        combined = industry_grid.merge(
            transport_grid[['geometry', 'total_h2_demand_kg']],
            on='geometry',
            how='outer',
            suffixes=('_industry', '_transport'))

        # Compute total demand
        combined['total_h2_demand_kg'] = combined['total_h2_demand_kg_industry'] + combined['total_h2_demand_kg_transport']

        # Save to combined grids folder
        combined_output_path = combined_grids_path / f"{year}_wecc_h2_demand_5km_combined.gpkg"
        combined.to_file(combined_output_path, driver='GPKG')

        print('\nCombined 5x5km demand grids saved. Model successfully run')

def combine_profiles():
    """
    Combines the hydrogen demand profiles from industry and transport into a single, total profile
    for each load zone, saving the result to the combined_profiles folder in the outputs.
    """

    # Create new combined results folder
    if combined_profiles_path.exists():
        shutil.rmtree(combined_profiles_path)
    combined_profiles_path.mkdir()

    # Input folders
    industry_profiles_path = outputs_path / 'industry' / 'demand_profiles'
    transport_profiles_path = outputs_path / 'transport' / 'demand_profiles'

    # Get cleaned file sets
    industry_files = {f for f in os.listdir(industry_profiles_path) if f.endswith('.csv') and '~' not in f}
    transport_files = {f for f in os.listdir(transport_profiles_path) if f.endswith('.csv') and '~' not in f}

    # Every load zone should have demand from transport, so we iterate by transport file
    for file in transport_files:
        # Initialize empty DataFrame
        combined_df = pd.DataFrame()

        # Load available datasets
        transport_df = pd.read_csv(transport_profiles_path / file) 
        industry_df = pd.read_csv(industry_profiles_path / file) if file in industry_files else None

        # If they both exist, sum their values for h2 demand
        if transport_df is not None and industry_df is not None:
            # Reset index to ensure row alignment
            transport_df = transport_df.reset_index(drop=True)
            industry_df = industry_df.reset_index(drop=True)

            combined_df = pd.DataFrame({
                'datetime': transport_df['datetime'],
                'h2_demand_kg': transport_df['total_h2_demand_kg'] + industry_df['total_h2_demand_kg']
            })
        elif transport_df is not None:
            combined_df = transport_df[['datetime', 'total_h2_demand_kg']].copy()
            combined_df = combined_df.rename(columns={'total_h2_demand_kg': 'h2_demand_kg'})
        else:
            combined_df = industry_df[['datetime', 'total_h2_demand_kg']].copy()
            combined_df = combined_df.rename(columns={'total_h2_demand_kg': 'h2_demand_kg'})

        # Add SWITCH timescale formatting
        combined_df['datetime'] = pd.to_datetime(combined_df['datetime'])
        combined_df['timepoint_id'] = range(len(combined_df))
        combined_df['timeseries'] = combined_df['datetime'].dt.year.astype(str) + '_all'

        combined_df = combined_df.rename(columns={'datetime': 'timestamp', 'total_h2_demand_kg': 'h2_demand_kg'})
        combined_df['timestamp'] = pd.to_datetime(combined_df['timestamp']).dt.strftime('%Y-%m-%d-%H')
        
        # Organize the columns
        combined_df = combined_df[['timepoint_id', 'timeseries', 'timestamp', 'h2_demand_kg']]

        # Save result
        combined_df.to_csv(combined_profiles_path / file, index=False)

    print("\nCombined profiles saved.")



