from pathlib import Path
import pandas as pd
import numpy as np
from onroad_transport.build_transport_profile import disaggregate_annual_to_hourly

# File paths
base_path  = Path(__file__).parent
profile_path = base_path / 'inputs' / 'EPRI_Profile_WSCC_CNV_Offpeak.xlsx'

def build_profile(lz_yearly_summary_df, output_profiles_path, flat=False, by_industry=False):
    """
    Disaggregates annual hydrogen demand totals by load zone into an hourly profiles by load zone over each model year. 
    Saves the output profiles to the given path. By default, this function uses an industrial heating energy use
    profile from EPRI's End Use Load Shape Library. Specifically we use the profile for the WSCC/CNV region for 
    an "offpeak week", but note that the profiles across WSCC regions and peak/offpeak weeks are nearly identical. 

    Parameters:
    - lz_summary_df: a DataFrame containing the industry hydrogen demand of each load zone in each model year.
        Has columns 'load_zone', 'total_h2_demand', 'year'. Load zones should be sorted alphabetically and by descending year.
    - output_profiles_path: the path to the folder where the hydrogen demand profiles will be saved 
    - flat: if True, then a flat, contant profile is created, and the EPRI profile is not used.
    - by_industry: if True, have a more detailed breakdown of demand by industry. if True, then flat must be False
    
    Returns: None
    """

    print('\nBuilding demand profiles...')

    # Load hourly profiles for weekday and weekend
    demand_profile_df = pd.read_excel(profile_path)
    weekday_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekday']]
    weekend_profile = demand_profile_df[['Hour', 'Avg_Energy_Weekend']]

    # Create an array containing the hourly fuel demand profile from industry over the course of a week (starting Sunday)
    weekly_profile = generate_one_week_normalized_profile(weekday_profile, weekend_profile)
    weekly_profile_array = weekly_profile['demand'].values

    # Get the first load_zone in the DataFrame
    previous_load_zone = lz_yearly_summary_df.iloc[0].loc['load_zone']
    
    # Create a DataFrame which will contain the all the yearly profiles for one load zone, stacked on top of each other
    profile_across_years = pd.DataFrame()

    # Process each load zone/year combination
    for _, lz_row in lz_yearly_summary_df.iterrows():
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

        h2_demand = lz_row['total_h2_demand_kg']

        # Generate the profile for one year
        if not flat:
            one_year_profile = disaggregate_annual_to_hourly(h2_demand, weekly_profile_array, np.full(53, 1), year)

            if by_industry:
                industries = ["Iron_and_Steel", "Aluminum", "Cement", "Chemicals", "Refineries", "Glass"]
                industry_profiles = []

                for industry in industries:
                    industry_demand = lz_row[industry]

                    single_industry_profile = disaggregate_annual_to_hourly(
                        industry_demand,
                        weekly_profile_array,
                        np.full(53, 1),
                        year
                    )

                    single_industry_profile.rename(
                        columns={'hourly_value': industry},
                        inplace=True
                    )

                    industry_profiles.append(single_industry_profile)

                # Start from one_year_profile (the base total profile)
                one_year_profile.rename(columns={'hourly_value': 'total_h2_demand_kg'}, inplace=True)

                # Merge all industry columns at once
                for df in industry_profiles:
                    one_year_profile = one_year_profile.merge(df, on=['datetime', 'day_of_week'], how='left')
                
        else:
            one_year_profile = disaggregate_annual_to_hourly(h2_demand, np.full(168, 1), np.full(53, 1), year)

        one_year_profile = one_year_profile.rename(columns={'hourly_value': 'total_h2_demand_kg'})

        # Join to make a combined DataFrame with the profiles across all years within a load zone
        profile_across_years = pd.concat([profile_across_years, one_year_profile], ignore_index=True)

    profile_across_years.to_csv(output_profiles_path / f'{load_zone}_profile.csv', index=False)
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