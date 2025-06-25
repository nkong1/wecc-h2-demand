from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

"""
This module uses data from the EPRI Load Shape Library to temporally disaggregate annual hydrogen demand 
into an hourly profile over the course of a week. Although the profile is taken from a offpeak week in the 
WSCC/CNV region, the profile is also representative of weeks in peak weeks and of other regions in the WSCC.
This is because the profiles across WSCC regions and peak/offpeak weeks are nearly identical, according to  
Load Shape Library data.
"""

# File paths
base_path  = Path(__file__).parent
profile_path = base_path / 'inputs' / 'EPRI_Profile_WSCC_CNV_Offpeak.xlsx'

def build(demand_by_lz):
    output_profiles_path = base_path.parent / 'outputs' / 'industry' / 'industry_profiles'
    output_profiles_path.mkdir()

    print('\nBuilding transport demand profiles...')

    # Import an hourly profile for a weekend and weekday
    demand_profile_df = pd.read_excel(profile_path)

    # Make a df to build an hourly profile for an entire week
    hourly_week_profile = pd.DataFrame()

    weekday_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekday']].rename(columns={'Avg_Energy_Weekday': 'Energy'})
    weekend_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekend']].rename(columns={'Avg_Energy_Weekend': 'Energy'})

    # Build an hourly profile for a week, starting on Sunday
    for day in range(7):
        if day == 0 or day == 6:
            hourly_week_profile = pd.concat([hourly_week_profile, weekend_profile])
        else:
            hourly_week_profile = pd.concat([hourly_week_profile, weekday_profile])

    # Reset the hour column
    hourly_week_profile['Hour'] = range(7 * 24)

    # Normalize the energy values such that they sum to 1
    hourly_week_profile['Energy'] = hourly_week_profile['Energy'] / hourly_week_profile['Energy'].sum()

    # Get the highest demand load zone (for plotting purposes)
    highest_demand_lz = demand_by_lz.iloc[demand_by_lz['h2_demand_kg'].idxmax(), 0]

    # Make a hourly profile (over the course of a week) for each load zone
    for _, row in demand_by_lz.iterrows():
        load_zone = row.iloc[0]
        h2_demand = row.iloc[1]

        # Convert annual h2 demand to h2 demand in an average week
        weekly_h2_demand = h2_demand / 52.14 

        profile = hourly_week_profile.copy()
        profile['h2_demand'] = profile['Energy'] * weekly_h2_demand

        output_path = output_profiles_path / f'{load_zone}_profile.csv'

        final_demand_profile = profile[['Hour', 'h2_demand']]
        final_demand_profile.to_csv(output_path, index=False)

        if load_zone == highest_demand_lz:
            plot_output_path = base_path.parent / 'outputs' / 'industry' / f'{load_zone}_demand_profile.png'
            plot_demand_profile(final_demand_profile, highest_demand_lz, plot_output_path)

    print(f'Saved transport demand profiles to {output_profiles_path}...')


def plot_demand_profile(profile_df, lz_name, plot_output_path):
    total_demand = profile_df['h2_demand'].sum()

    plt.figure(figsize=(12, 5))
    plt.plot(profile_df['Hour'], profile_df['h2_demand'], label='Hydrogen Demand', color='blue')
    plt.title(f"Hourly Hydrogen Demand Profile for {lz_name}")
    plt.xlabel("Hour of the Week")
    plt.ylabel("Hydrogen Demand (kg)")
    plt.legend()
    plt.grid(True)

    plt.text(
        x=0.01, y=0.95,
        s=f"Total Weekly Demand: {total_demand:,.0f} kg",
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment='top',
        bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray')
    )

    plt.ylim(bottom=0)
    plot_output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(plot_output_path, dpi=300, bbox_inches='tight')
    plt.close()

    print(f"{lz_name} profile graph saved to: {plot_output_path}")

