from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

"""
This module uses data from the EPRI Load Shape Library to temporally disaggregate annual hydrogen demand 
into an hourly profile over the course of a week. Although the profile is taken from a offpeak week in the 
WSCC/CNV region, the profile is also representative of weeks in peak weeks and of other regions in the WSCC.
This is because the profiles across WSCC regions and peak/offpeak weeks are nearly identical when considering 
average weekends and weekdays. The End Use Shape for Industrial Process Heating is used.
"""

# File paths
base_path  = Path(__file__).parent
profile_path = base_path / 'inputs' / 'EPRI_Profile_WSCC_CNV_Offpeak.xlsx'
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# File paths
base_path = Path(__file__).parent
profile_path = base_path / 'inputs' / 'EPRI_Profile_WSCC_CNV_Offpeak.xlsx'

def build(demand_by_lz, year):
    """
    Disaggregates the annual total for industrial hydrogen demand in each load zone into an hourly profile
    spanning a year. Saves the output profiles and plots the profile for the load zone with the highest
    annual demand.
    """
    output_profiles_path = base_path.parent / 'outputs' / 'industry' / 'demand_profiles'
    output_profiles_path.mkdir(parents=True, exist_ok=True)

    print('\nBuilding industry demand profiles...')

    # Load hourly profiles for weekday and weekend
    demand_profile_df = pd.read_excel(profile_path)
    weekday_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekday']].rename(columns={'Avg_Energy_Weekday': 'Energy'})
    weekend_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekend']].rename(columns={'Avg_Energy_Weekend': 'Energy'})

    # Generate full-year datetime index
    hours = pd.date_range(start=f'{year}-01-01 00:00', end=f'{year}-12-31 23:00', freq='h')
    full_year_df = pd.DataFrame({'datetime': hours})
    full_year_df['weekday'] = full_year_df['datetime'].dt.weekday  # 0=Monday
    full_year_df['day_of_week'] = full_year_df['datetime'].dt.day_name()  # e.g., 'Monday'
    full_year_df['hour'] = full_year_df['datetime'].dt.hour

    # Assign profile values (weekday vs weekend)
    profile_values = []
    for _, row in full_year_df.iterrows():
        hour = int(row['hour'])
        if row['day_of_week'] in [5, 6]:  # Saturday or Sunday
            profile_values.append(weekend_profile.loc[hour, 'Energy'])
        else:
            profile_values.append(weekday_profile.loc[hour, 'Energy'])

    full_year_df['Energy'] = profile_values

    # Normalize over the whole year
    full_year_df['Energy'] = full_year_df['Energy'] / full_year_df['Energy'].sum()

    # Get load zone with highest demand (for plotting)
    highest_demand_lz = demand_by_lz.loc[demand_by_lz['h2_demand_kg'].idxmax(), 'load_zone']

    for _, row in demand_by_lz.iterrows():
        load_zone = row['load_zone']
        annual_h2_demand = row['h2_demand_kg']

        profile_df = full_year_df.copy()
        profile_df['h2_demand'] = profile_df['Energy'] * annual_h2_demand


        output_path = output_profiles_path / f'{load_zone}_profile.csv'
        profile_df[['datetime', 'day_of_week', 'h2_demand']].to_csv(output_path, index=False)

        if load_zone == highest_demand_lz:
            plot_output_path = base_path.parent / 'outputs' / 'industry' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(profile_df, load_zone, plot_output_path)

    print(f'Saved industry demand profiles to {output_profiles_path}...')


def plot_demand_profile(profile_df, lz_name, plot_output_path):
    """
    Generates a line plot showing the hourly hydrogen demand for the given load zone.
    """
    total_demand = profile_df['h2_demand'].sum()

    plt.figure(figsize=(12, 5))
    plt.plot(profile_df['datetime'], profile_df['h2_demand'], label='Hydrogen Demand', color='blue', linewidth=0.8)
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

    print(f"{lz_name} profile graph saved to: {plot_output_path}")
