"""
This module uses data from the EPRI Load Shape Library to temporally disaggregate annual hydrogen demand 
into an hourly profile over the course of multiple model years. Although the profile is taken from a offpeak 
week in the WSCC/CNV region, it is also representative of weeks in peak weeks and of other regions in the WSCC, as
the profiles across WSCC regions and peak/offpeak weeks are nearly identical when for average weekends and weekdays. 
The End Use Shape for Industrial Process Heating is used.

https://loadshape.epri.com/enduse
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from transport.build_transport_profile import disaggregate_annual_to_hourly

# File paths
base_path  = Path(__file__).parent
profile_path = base_path / 'inputs' / 'EPRI_Profile_WSCC_CNV_Offpeak.xlsx'

def build_profile(lz_summary_df):
    """
    Disaggregates the annual total for industrial hydrogen demand in each load zone into an hourly profile
    spanning a year. Saves the output profiles and plots the profile for the load zone with the highest
    annual demand.

    Parameters:
    - lz_summary_df: a pandas DataFrame containing the industry hydrogen demand of each load zone in each model year.
        Has columns 'load_zone', 'total_h2_demand', 'year'. Load zones are sorted alphabetically and by descending year.
    
    Returns: None
    """

    print('\nBuilding industry demand profiles...')

    # Create output profiles directory
    output_profiles_path = base_path.parent / 'outputs' / 'industry' / 'demand_profiles'
    output_profiles_path.mkdir()

    # Load hourly profiles for weekday and weekend
    demand_profile_df = pd.read_excel(profile_path)
    weekday_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekday']]
    weekend_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekend']]

    # Create an array containing the hourly fuel demand profile from industry over the course of a week (starting Sunday)
    weekly_profile = generate_one_week_normalized_profile(weekday_profile, weekend_profile)
    weekly_profile_array = weekly_profile['demand'].values

    # Find load zone and year combination with highest demand (for plotting purposes)
    row = lz_summary_df.loc[lz_summary_df['total_h2_demand'].idxmax()]
    highest_demand_lz = str(row['load_zone'])
    highest_demand_year = int(row['year'])

    # Get the first load_zone in the DataFrame
    previous_load_zone = lz_summary_df.iloc[0].loc['load_zone']
    
    # Create a DataFrame which will contain the all the yearly profiles for one load zone, stacked on top of each other
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

        h2_demand = lz_row['total_h2_demand']

        # Generate the profile for one year
        one_year_profile = disaggregate_annual_to_hourly(h2_demand, weekly_profile_array, np.full(12, 1), year)
        one_year_profile = one_year_profile.rename(columns={'hourly_value': 'total_h2_demand'})

        # Join to make a combined DataFrame with the profiles across all years within a load zone
        profile_across_years = pd.concat([profile_across_years, one_year_profile], ignore_index=True)

        # Plot for highest demand zone/year combination
        if load_zone == highest_demand_lz and year == highest_demand_year:
            plot_output_path = base_path.parent / 'outputs' / 'industry' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(one_year_profile, load_zone, plot_output_path)

    # Save the profile for the last load zone
    output_path = output_profiles_path / f'{load_zone}_profile.csv'
    profile_across_years.to_csv(output_path, index=False)
    profile_across_years = profile_across_years.sort_values(by='datetime').reset_index(drop=True)

    print(f'\nProfiles saved to {output_profiles_path}')


def generate_one_week_normalized_profile(weekday_profile, weekend_profile):
    """
    Generates a normalized one-week (168-hour) energy profile using the second column of each
    input DataFrame (assumed to contain 24 hourly values for weekdays and weekends).

    Parameters:
    - weekday_profile: DataFrame with 24 rows, where the second column is hourly demand
    - weekend_profile: Same format as above

    Returns:
    - DataFrame with columns: 'hour' (0 to 167) and 'Energy' (normalized to sum to 1). Hour
        0 begins Sunday at midnight. Hour 167 is Saturday at 11 pm.
    """
    hours = []
    energy_values = []

    weekday_energy = weekday_profile.iloc[:, 1]
    weekend_energy = weekend_profile.iloc[:, 1]

    for h in range(7 * 24):  # 168 hours
        day = h // 24  # 0 = Sunday, ..., 6 = Saturday
        hour_of_day = h % 24

        if day in [0, 6]:  # Sunday or Saturday
            energy = weekend_energy.iloc[hour_of_day]
        else:
            energy = weekday_energy.iloc[hour_of_day]

        hours.append(h)
        energy_values.append(energy)

    # Normalize to sum to 1
    energy_array = np.array(energy_values)
    energy_normalized = energy_array / energy_array.sum()

    return pd.DataFrame({
        'hour': range(168),
        'demand': energy_normalized
    })


def plot_demand_profile(profile_df, lz_name, plot_output_path):
    """
    Generates a line plot showing the hourly hydrogen demand for the given load zone.

    Parameters: 
    - profile_df: A DataFrame containing columns 'datetime' and 'total_h2_demand'
    - lz_name: The name of the load zone for which the profile is being plotted
    - plot_output_path: the path to which the plot should be saved

    Returns: None
    """
    total_demand = profile_df['total_h2_demand'].sum()

    plt.figure(figsize=(12, 5))
    plt.plot(profile_df['datetime'], profile_df['total_h2_demand'], label='Hydrogen Demand', color='blue', linewidth=0.8)
    plt.title(f"Hourly Hydrogen Demand Profile for {lz_name}")
    plt.xlabel("Date")
    plt.ylabel("Hydrogen Demand (kg)")
    plt.legend()
    plt.grid(True)

    plt.text(
        x=0.99, y=0.01,
        s=f"Total Annual Demand: {total_demand:,.0f} kg",
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment='bottom',
        horizontalalignment='right',
        bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray')
    )

    plt.ylim(bottom=0)
    plot_output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"\n{lz_name} profile graph saved to: {plot_output_path}")
