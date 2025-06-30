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

The weekly profiles, which contain values for 4-Week Avg U.S. Product Supplied of each fuel type, are taken
directly from EIA data. Values every week from 1/5/24 to 1/3/25 are used for weekly profile, spanning a total of 53 weeks.

https://www.eia.gov/dnav/pet/hist/leafhandler.ashx?n=pet&s=wgfupus2&f=4
https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?n=pet&s=wdiupus2&f=4
"""

ld_hourly_profile_path = base_path / 'input_files' / 'LD_fueling_hourly_normalized.csv'
hd_hourly_profile_path = base_path / 'input_files' / 'HD_fueling_hourly_normalized.csv'

ld_weekly_profile_path = base_path / 'input_files' / '4-Week_Avg_Gasoline_Profiles.csv'
hd_weekly_profile_path = base_path / 'input_files' / '4-Week_Avg_Diesel_Profiles.csv'


def disaggregate_annual_to_hourly(annual_total, hourly_week_profile, weekly_year_profile, year):
    """
    Disaggregates an annual total into hourly values using an hourly week profile spanning a week
    (starting Sunday) and a weekly profile spanning a year (53 values)

    Inputs:
    - annual_total: total annual value to be disaggregated
    - hourly_week_profile: numpy array of length 168, starting with Sunday 00:00
    - weekly_year_profile: numpy array of length 53, one value per week of the year
    - year: the calendar year to generate hourly data for

    Returns:
    - a DataFrame with 'datetime', 'day_of_week', and 'hourly_value' columns
    """
    # Create hourly timestamps for the year
    hours = pd.date_range(start=f'{year}-01-01 00:00', end=f'{year}-12-31 23:00', freq='h')
    df = pd.DataFrame({'datetime': hours})

    # Compute week index (week 0 = Jan 1–7, etc.)
    days_since_start = (df['datetime'] - pd.Timestamp(f'{year}-01-01')).dt.days
    df['week_index'] = np.clip(days_since_start // 7, 0, 52)

    # Compute hour of week index (Sunday 00:00 = 0, ..., Saturday 23:00 = 167)
    weekday = df['datetime'].dt.weekday  # Monday=0, Sunday=6
    sunday_start_weekday = (weekday + 1) % 7  # Sunday=0, Monday=1, ..., Saturday=6
    hour = df['datetime'].dt.hour
    df['hour_of_week'] = sunday_start_weekday * 24 + hour

    # Add day_of_week string column
    df['day_of_week'] = df['datetime'].dt.day_name()

    # Normalize profiles
    hourly_week_profile_norm = hourly_week_profile / hourly_week_profile.sum()
    weekly_year_profile_norm = weekly_year_profile / weekly_year_profile.sum()

    # Vectorized lookup
    df['hourly_shape'] = hourly_week_profile_norm[df['hour_of_week'].values]
    df['weekly_shape'] = weekly_year_profile_norm[df['week_index'].values]

    # Combine shapes and scale
    df['combined_shape'] = df['hourly_shape'] * df['weekly_shape']
    df['hourly_value'] = df['combined_shape'] * (annual_total / df['combined_shape'].sum())

    return df[['datetime', 'day_of_week', 'hourly_value']]


def build_profile(lz_summary_df):
    """
    For each load zone, disaggregates LD and HD annual hydrogen demand into hourly profiles,
    saves them to CSVs, and plots the profile for the highest demand zone. 
    """
    output_profiles_path = base_path.parent / 'outputs' / 'transport' / 'demand_profiles'
    output_profiles_path.mkdir(parents=True, exist_ok=True)

    print('\nBuilding transport demand profiles...')

    # Read all input files 
    ld_hourly_fueling_df = pd.read_csv(ld_hourly_profile_path)
    hd_hourly_fueling_df = pd.read_csv(hd_hourly_profile_path)

    ld_weekly_fueling_df = pd.read_csv(ld_weekly_profile_path, header=4)
    hd_weekly_fueling_df = pd.read_csv(hd_weekly_profile_path, header=4)

    # Extract numpy arrays 
    ld_fueling_hourly = ld_hourly_fueling_df['normalized_h2_demand'].values
    hd_fueling_hourly = hd_hourly_fueling_df['normalized_h2_demand'].values
    ld_fueling_weekly = ld_weekly_fueling_df['4-Week Avg U.S. Product Supplied of Finished Motor Gasoline Thousand Barrels per Day'].values
    hd_fueling_weekly = hd_weekly_fueling_df['4-Week Avg U.S. Product Supplied of Distillate Fuel Oil Thousand Barrels per Day'].values

    # Find load zone and year combination with highest demand
    row = lz_summary_df.loc[lz_summary_df['total_h2_demand'].idxmax()]
    highest_demand_lz = str(row['load_zone'])
    highest_demand_year = int(row['year'])

    # Get the first load_zone in the DataFrame
    previous_load_zone = lz_summary_df.iloc[0].loc['load_zone']
    
    profile_across_years = pd.DataFrame()

    # Process each load zone/year combination
    for _, lz_row in lz_summary_df.iterrows():
        load_zone = lz_row['load_zone']
        year = lz_row['year']

        # Save results when moving on to a new load zone
        if load_zone != previous_load_zone:
            output_path = output_profiles_path / f'{previous_load_zone}_profile.csv'
            profile_across_years = profile_across_years.sort_values(by='datetime').reset_index(drop=True)
            profile_across_years.to_csv(output_path, index=False)

            # Update for next iteration
            profile_across_years = pd.DataFrame()
            previous_load_zone = load_zone

        ld_h2_demand = lz_row['LD_h2_demand']
        hd_h2_demand = lz_row['HD_h2_demand']

        # Generate profiles for both LD and HD
        ld_profile = disaggregate_annual_to_hourly(ld_h2_demand, ld_fueling_hourly, ld_fueling_weekly, year)
        hd_profile = disaggregate_annual_to_hourly(hd_h2_demand, hd_fueling_hourly, hd_fueling_weekly, year)

        # Combine profiles 
        merged = pd.DataFrame({
            'datetime': ld_profile['datetime'],
            'day_of_week': ld_profile['day_of_week'],
            'ld_h2_demand': ld_profile['hourly_value'],
            'hd_h2_demand': hd_profile['hourly_value']
        })
        merged['total_h2_demand'] = merged['ld_h2_demand'] + merged['hd_h2_demand']
        merged['year'] = year

        profile_across_years = pd.concat([profile_across_years, merged], ignore_index=True)

        # Plot for highest demand zone/year combination
        if load_zone == highest_demand_lz and year == highest_demand_year:
            plot_output_path = base_path.parent / 'outputs' / 'transport' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(merged, load_zone, plot_output_path)

    # Save the profile from the last load zone
    output_path = output_profiles_path / f'{load_zone}_profile.csv'
    profile_across_years = profile_across_years.sort_values(by='datetime').reset_index(drop=True)
    profile_across_years.to_csv(output_path, index=False)

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
    print(f"\n{lz_name} profile graph saved to: {plot_output_path}")