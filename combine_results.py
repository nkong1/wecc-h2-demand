"""
This module is only called when both the industry and transport parts of the model are run.

For each load zone, this module combines the hydrogen demand results from industry and transport 
into a single csv file showing total hourly demand over each model year. 
"""

from transport.plot_demand import plot_lz_demand
import pandas as pd
import os
import shutil
from pathlib import Path

# Define paths
outputs_path = Path(__file__).parent / 'outputs'
combined_outputs_path = outputs_path / 'combined_profiles'


def combine():
    """
    Combines the hydrogen demand profiles from industry and transport into a single, total profile
    for each load zone, saving the result to the combined_profiles folder in the outputs.
    """

    print('\n===================\nCombining Results...\n==================')

    # Create new combined results folder
    if combined_outputs_path.exists():
        shutil.rmtree(combined_outputs_path)
    combined_outputs_path.mkdir()

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

        # If both exist, sum them
        if transport_df is not None and industry_df is not None:
            combined_df['datetime'] = transport_df['datetime']
            combined_df['h2_demand'] = transport_df['total_h2_demand'] + industry_df['total_h2_demand']
        elif transport_df is not None:
            combined_df = transport_df[['datetime', 'total_h2_demand']]
        else:
            combined_df = industry_df[['datetime', 'total_h2_demand']]

        # Save result
        combined_df.to_csv(combined_outputs_path / file, index=False)

    print("\nCombined profiles saved. Model successfully run.\n")



