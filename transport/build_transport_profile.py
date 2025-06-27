"""
This code temporally disaggregates hydrogen demand by load zone over the course of a year using weekly and monthly profiles.
It saves a CSV profile for each load zone and plots the profile for the zone with the highest total transport hydrogen demand.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

base_path = Path(__file__).parent

"""
The light-duty fueling profile, which has hourly values over the course of a week, is taken from a gas station fueling 
profile used in the NREL's H2A model and found in one of their reports. (Figures 2-3, 2-4, and 2-5)

https://www1.eere.energy.gov/hydrogenandfuelcells/pdfs/nexant_h2a.pdf

The same profile is currently being used for heavy-duty transport.

The seasonal profiles, which contain values for monthly US demand of gasoline and diesel, are derived
from EIA data. 2023 values for weekly US demand of gasoline and diesel are averaged across all weeks that
begin in each month to obtain the monthly profile values.

https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=pet&s=wgfupus2&f=4
https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=PET&s=WDIUPUS2&f=4
"""

ld_weekly_profile_path = base_path / 'input_files' / 'LD_fueling_hourly_normalized.csv'
hd_weekly_profile_path = base_path / 'input_files' / 'HD_fueling_hourly_normalized.csv'
seasonal_profile_path = base_path / 'input_files' / 'monthly_profiles.xlsx'


def disaggregate_annual_to_hourly(annual_total, weekly_profile, monthly_profile, year):
    """
    Disaggregates an annual total into hourly values based on a weekly and monthly profile.
    
    Inputs:
    - annual_total: a value for an annual sum that will be disaggregated into hourly values
    - weekly_profile: a numpy array with hourly values for normalized demand (length 168)
    - monthly_profile: an numpy array with monthly values for demand (length 12)
    - year: the model year 
    
    Returns:
    - A DataFrame with 'datetime' and 'hourly_value' columns, showing the annual total disaggreagated
    into hourly values based on the given weekly and monthly profiles
    """
    # Create a data frame with all of the hours in the model year
    hours = pd.date_range(start=f'{year}-01-01 00:00', end=f'{year}-12-31 23:00', freq='h')
    df = pd.DataFrame({'datetime': hours})
    
    # Extract time components efficiently
    df['month'] = df['datetime'].dt.month
    df['weekday'] = df['datetime'].dt.weekday 
    df['hour'] = df['datetime'].dt.hour
    df['day_of_week'] = df['datetime'].dt.day_name()  

    # Normalize the monthly profile (the hourly one over a week is already normalized)
    monthly_profile_norm = monthly_profile / monthly_profile.sum()
    
    weekly_indices = df['weekday'] * 24 + df['hour']
    df['weekly_shape'] = weekly_profile[weekly_indices]
    df['monthly_shape'] = monthly_profile_norm[df['month'] - 1]
    
    # Disaggregate the annual total
    df['combined_shape'] = df['weekly_shape'] * df['monthly_shape']
    df['hourly_value'] = df['combined_shape'] * (annual_total / df['combined_shape'].sum())
    
    # Return a DataFrame with the final result
    return df[['datetime', 'day_of_week', 'hourly_value']]


def build_profile(lz_summary_df, year):
    """
    For each load zone, disaggregates LD and HD annual hydrogen demand into hourly profiles,
    saves them to CSVs, and plots the profile for the highest demand zone. 
    """
    output_profiles_path = base_path.parent / 'outputs' / 'transport' / 'demand_profiles'
    output_profiles_path.mkdir(parents=True, exist_ok=True)

    print('\nBuilding transport demand profiles...')

    # Read all input files once at the beginning
    ld_fueling_df = pd.read_csv(ld_weekly_profile_path)
    hd_fueling_df = pd.read_csv(hd_weekly_profile_path)
    monthly_fueling_df = pd.read_excel(seasonal_profile_path, header=1)
    
    # Extract numpy arrays once
    ld_fueling_hourly = ld_fueling_df['normalized_h2_demand'].values
    hd_fueling_hourly = hd_fueling_df['normalized_h2_demand'].values
    ld_fueling_monthly = monthly_fueling_df['Gasoline'].values
    hd_fueling_monthly = monthly_fueling_df['Diesel'].values

    # Find load zone with highest demand
    highest_demand_lz = lz_summary_df.loc[lz_summary_df['total_h2_demand'].idxmax(), 'load_zone']

    # Process each load zone
    for _, lz_row in lz_summary_df.iterrows():
        load_zone = lz_row['load_zone']
        ld_h2_demand = lz_row['LD_h2_demand']
        hd_h2_demand = lz_row['HD_h2_demand']

        # Generate profiles for both LD and HD
        ld_profile = disaggregate_annual_to_hourly(ld_h2_demand, ld_fueling_hourly, ld_fueling_monthly, year)
        hd_profile = disaggregate_annual_to_hourly(hd_h2_demand, hd_fueling_hourly, hd_fueling_monthly, year)

        # Combine profiles efficiently
        merged = pd.DataFrame({
            'datetime': ld_profile['datetime'],
            'day_of_week': ld_profile['day_of_week'],
            'ld_h2_demand': ld_profile['hourly_value'],
            'hd_h2_demand': hd_profile['hourly_value']
        })
        merged['total_h2_demand'] = merged['ld_h2_demand'] + merged['hd_h2_demand']

        # Save profile
        output_path = output_profiles_path / f'{load_zone}_profile.csv'
        merged.to_csv(output_path, index=False)

        # Plot for highest demand zone
        if load_zone == highest_demand_lz:
            plot_output_path = base_path.parent / 'outputs' / 'transport' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(merged, load_zone, plot_output_path)

    print(f'\nProfiles saved to: {output_profiles_path}')


def plot_demand_profile(profile_df, lz_name, plot_output_path):
    """
    Plots hourly hydrogen demand for a given load zone over the model year and saves the figure.
    """
    # Calculate total demand more efficiently
    total_demand = profile_df[['ld_h2_demand', 'hd_h2_demand']].sum().sum()

    fig, ax = plt.subplots(figsize=(12, 5))
    
    # Plot both series
    ax.plot(profile_df['datetime'], profile_df['ld_h2_demand'], 
            label='LDV H2 Demand', color='blue', linewidth=0.8)
    ax.plot(profile_df['datetime'], profile_df['hd_h2_demand'], 
            label='HDV H2 Demand', color='orange', linewidth=0.8)
    
    # Set labels and formatting
    ax.set_title(f"Hourly Hydrogen Demand Profile for {lz_name} ({profile_df['datetime'].dt.year.iloc[0]})")
    ax.set_xlabel("Date")
    ax.set_ylabel("Hydrogen Demand (kg/hour)")
    ax.legend()
    ax.grid(True)

    # Add total demand text box
    ax.text(0.99, 0.01, f"Total Annual Demand: {total_demand:,.0f} kg",
            transform=ax.transAxes, fontsize=12,
            verticalalignment='bottom', horizontalalignment='right',
            bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray'))

    plt.tight_layout()
    plt.savefig(plot_output_path, dpi=300)
    plt.close(fig)  # Close figure to free memory
    print(f"{lz_name} profile graph saved to: {plot_output_path}")