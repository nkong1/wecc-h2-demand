"""
This code temporally disaggregates the hydrogen demand by load zone over the course of an average week, saving
the result for each load zone, and plots the profile for the load zone with the highest transport hydrogen demand.
"""

import pandas as pd
import matplotlib.pyplot as plt
import os
from pathlib import Path

base_path  = Path(__file__).parent

ld_profile_path = base_path / 'input_files' / 'LD_fueling_hourly_normalized.csv'
hd_profile_path =  base_path / 'input_files' / 'HD_fueling_hourly_normalized.csv'

def build(demand_df):
    output_profiles_path = base_path.parent / 'outputs' / 'transport' / 'demand_profiles'
    output_profiles_path.mkdir()

    print('\nBuilding transport demand profiles...')

    h2_demand_df = demand_df
    ld_fueling_df = pd.read_csv(ld_profile_path)
    hd_fueling_df = pd.read_csv(hd_profile_path)

    highest_demand_lz = h2_demand_df.loc[h2_demand_df['total_h2_demand'].idxmax(), 'load_zone']

    for _, lz_row in h2_demand_df.iterrows():
        load_zone = lz_row.iloc[0] 

        ld_h2_demand = lz_row.iloc[1]
        hd_h2_demand = lz_row.iloc[2]

        lz_ld_fueling_df = ld_fueling_df.copy()
        lz_hd_fueling_df = hd_fueling_df.copy()

        lz_ld_fueling_df['LD_h2_demand'] = lz_ld_fueling_df['normalized_h2_demand'] * ld_h2_demand / 52.1429 
        lz_hd_fueling_df['HD_h2_demand'] = lz_hd_fueling_df['normalized_h2_demand'] * hd_h2_demand / 52.1429

        merged = lz_ld_fueling_df.merge(lz_hd_fueling_df, on = 'hour', how = 'left')

        output_path = output_profiles_path / f'{load_zone}_profile.csv'
        merged[['hour', 'LD_h2_demand', 'HD_h2_demand']].to_csv(output_path, index = False)

        if load_zone == highest_demand_lz:
            plot_output_path = base_path.parent / 'outputs' / 'transport' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(merged, highest_demand_lz, plot_output_path)
    
    print(f'Profiles (csv files) saved to {output_profiles_path}')

def plot_demand_profile(profile_df, lz_name, plot_output_path):

    # Calculate total weekly demand
    total_demand = profile_df['LD_h2_demand'].sum() + profile_df['HD_h2_demand'].sum()

    # Plotting
    plt.figure(figsize=(12, 5))
    plt.plot(profile_df['hour'], profile_df['LD_h2_demand'], label='LDV H2 Demand', color='blue')
    plt.plot(profile_df['hour'], profile_df['HD_h2_demand'], label='HDV H2 Demand', color='orange')
    plt.title(f"Hourly Hydrogen Demand Profile for {lz_name}")
    plt.xlabel("Hour of the Week")
    plt.ylabel("Hydrogen Demand (kg)")
    plt.legend()
    plt.grid(True)

    # Add total demand as a label in the top-left corner
    plt.text(
        x=0.01, y=0.95,
        s=f"Total Weekly Demand: {total_demand:,.0f} kg",
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment='top',
        bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray')
    )

    # Save the plot
    plt.savefig(plot_output_path, dpi=300, bbox_inches='tight')
    print(f"{lz_name} profile graph saved to: {plot_output_path}")

