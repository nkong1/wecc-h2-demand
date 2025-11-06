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

def combine(years, transport, industry, aviation):
    print('\n===================\nCombining Results...\n==================')

    print('\nCombining demand profiles...')
    combine_profiles(years, transport, industry, aviation)

    print('\nCombining demand grids...')
    combine_demand_grids(transport, industry, aviation)

def combine_demand_grids(transport=False, industry=False, aviation=False):
    """
    Combines 5x5km resolution demand grids from baseline and optionally
    transport, industry, and aviation into a single grid for each model year.
    
    Parameters:
    - transport (bool): If True, merge transport grid.
    - industry (bool): If True, merge industry grid.
    - industry (bool): If True, merge aviation grid.
    """

    # Input folders
    baseline_profiles_path = outputs_path / 'baseline'
    industry_profiles_path = outputs_path / 'industry'
    transport_profiles_path = outputs_path / 'transport'
    aviation_profiles_path = outputs_path / 'aviation'

    # Loop over baseline files (this always exists)
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

        # Merge aviation if exists
        if aviation:
            aviation_grid = gpd.read_file(aviation_profiles_path / baseline_grid_path.name)
            combined = combined.merge(
                aviation_grid[['geometry', 'total_h2_demand_kg']],
                on='geometry',
                how='left'
            )
            combined.rename(columns={'total_h2_demand_kg': 'total_h2_demand_kg_aviation'}, inplace=True)
        else:
            combined['total_h2_demand_kg_aviation'] = 0

        # Compute total demand
        combined['total_h2_demand_kg'] = (
            combined['total_h2_demand_kg_baseline'] +
            combined['total_h2_demand_kg_industry'] +
            combined['total_h2_demand_kg_transport'] + 
            combined['total_h2_demand_kg_aviation']
        )

        # Save to combined grids folder
        combined_output_path = outputs_path / f"{year}_wecc_h2_demand_grid_combined.gpkg"
        combined.to_file(combined_output_path, driver='GPKG')


def combine_profiles(years, transport=False, industry=False, aviation=False):
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
        combined_df['TIMEPOINT'] = range(1, len(combined_df)+1)
        combined_df['LOAD_ZONE'] = zone
        combined_df['timeseries'] = combined_df['datetime'].dt.year.astype(str) + '_all'
        combined_df['timestamp'] = combined_df['datetime'].dt.strftime('%Y-%m-%d-%H')

        # combined_df.to_csv(combined_profiles_path / f"{zone}_profile.csv", index=False)
        h2_timepoint_demand_df = pd.concat([h2_timepoint_demand_df, combined_df])
        h2_timepoint_demand_df = h2_timepoint_demand_df.sort_values(['LOAD_ZONE', 'TIMEPOINT'])

    save_daily_profile(h2_timepoint_demand_df, aviation=aviation)

    # Organize columns
    h2_timepoint_demand_df = h2_timepoint_demand_df[['LOAD_ZONE', 'TIMEPOINT', 'zone_demand_mw_h2']]

    # Save final output
    h2_timepoint_demand_df.to_csv(outputs_path / "h2_timepoint_demand.csv", index=False)
    print("\nCombined profiles saved.")




import pandas as pd
import matplotlib.pyplot as plt

def save_daily_profile(profile_df, aviation=False):
    """
    Aggregates hourly hydrogen demand profiles to daily resolution and optionally
    combines with aviation daily demand. Saves a CSV with one row per day (365 rows)
    and generates a cumulative stacked line plot by demand source.
    
    Parameters:
    - profile_df: pd.DataFrame with columns ['LOAD_ZONE', 'datetime', 'h2_demand_kg_baseline',
                    'h2_demand_kg_industry', 'h2_demand_kg_transport']
    - aviation: bool, whether to include aviation daily profile (from h2_daily_demand.csv)
    """
    print('saving combined dialy profile')
    # -----------------------------
    # Step 1: Compute day of year for each timestamp
    # -----------------------------
    profile_df['date'] = profile_df['datetime'].dt.dayofyear  # 1-365

    # -----------------------------
    # Step 2: Convert hourly kg demand to MW
    # -----------------------------
    for col in ['h2_demand_kg_baseline', 'h2_demand_kg_industry', 'h2_demand_kg_transport']:
        if col not in profile_df.columns:
            profile_df[col] = 0
        profile_df[col + '_mw'] = profile_df[col] * 33.39 / 1000  # MW

    # -----------------------------
    # Step 3: Aggregate across all load zones and hours to daily MWh
    # -----------------------------
    daily_profile = profile_df.groupby('date').agg({
    'h2_demand_kg_baseline_mw': 'sum',
    'h2_demand_kg_industry_mw': 'sum',
    'h2_demand_kg_transport_mw': 'sum'
    }).reset_index()

    daily_profile.rename(columns={
        'h2_demand_kg_baseline_mw': 'demand_mwh_baseline',
        'h2_demand_kg_industry_mw': 'demand_mwh_industry',
        'h2_demand_kg_transport_mw': 'demand_mwh_transport'
    }, inplace=True)

    # -----------------------------
    # Step 4: Combine with aviation daily demand if requested
    # -----------------------------
    if aviation:
        aviation_daily_profile = pd.read_csv(outputs_path / 'h2_daily_demand.csv')  # columns: ['LOAD_AREA','date','demand_mwh_h2']
        aviation_daily = aviation_daily_profile.groupby('date')['demand_mwh_h2'].sum().reset_index()
        aviation_daily.rename(columns={'demand_mwh_h2': 'demand_mwh_aviation'}, inplace=True)
        daily_profile = daily_profile.merge(aviation_daily, on='date', how='left')

    # Fill missing days with 0
    all_days = pd.DataFrame({'date': range(1, 366)})
    daily_profile = all_days.merge(daily_profile, on='date', how='left').fillna(0)

    # -----------------------------
    # Step 5: Save final daily profile
    # -----------------------------
    output_csv_path = outputs_path / 'h2_daily_profile_combined.csv'
    daily_profile.to_csv(output_csv_path, index=False)
    print(f'\nDaily combined profile saved: {output_csv_path}')

    # -----------------------------
    # Step 6: Plot cumulative stacked demand
    # -----------------------------
    sources = ['demand_mwh_baseline', 'demand_mwh_industry', 'demand_mwh_transport']
    if aviation:
        sources.append('demand_mwh_aviation')

    # Compute cumulative sums for stacking
    cum_df = daily_profile.copy()
    cum_df['baseline_cum'] = cum_df['demand_mwh_baseline']
    if 'demand_mwh_industry' in cum_df.columns:
        cum_df['industry_cum'] = cum_df['baseline_cum'] + cum_df['demand_mwh_industry']
    else:
        cum_df['industry_cum'] = cum_df['baseline_cum']
    if 'demand_mwh_transport' in cum_df.columns:
        cum_df['transport_cum'] = cum_df['industry_cum'] + cum_df['demand_mwh_transport']
    else:
        cum_df['transport_cum'] = cum_df['industry_cum']
    if 'demand_mwh_aviation' in cum_df.columns:
        cum_df['aviation_cum'] = cum_df['transport_cum'] + cum_df['demand_mwh_aviation']
    else:
        cum_df['aviation_cum'] = cum_df['transport_cum']

    # Plot
    plt.figure(figsize=(12,6))
    plt.plot(cum_df['date'], cum_df['baseline_cum'], label='Baseline', color='blue')
    plt.plot(cum_df['date'], cum_df['industry_cum'], label='Industry', color='green')
    plt.plot(cum_df['date'], cum_df['transport_cum'], label='Transport', color='orange')
    if aviation:
        plt.plot(cum_df['date'], cum_df['aviation_cum'], label='Aviation', color='red')

    # Fill between for stacked shading
    plt.fill_between(cum_df['date'], 0, cum_df['baseline_cum'], color='blue', alpha=0.3)
    plt.fill_between(cum_df['date'], cum_df['baseline_cum'], cum_df['industry_cum'], color='green', alpha=0.3)
    plt.fill_between(cum_df['date'], cum_df['industry_cum'], cum_df['transport_cum'], color='orange', alpha=0.3)
    if aviation:
        plt.fill_between(cum_df['date'], cum_df['transport_cum'], cum_df['aviation_cum'], color='red', alpha=0.3)

    plt.xlabel('Day of Year')
    plt.ylabel('Cumulative Daily Demand (MWh)')
    plt.title('Daily Hydrogen Demand by Source (Stacked)')
    plt.legend(loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    # Save figure
    output_plot_path = outputs_path / 'h2_daily_profile_combined_cumulative.png'
    plt.savefig(output_plot_path, dpi=300)
    plt.show()
    print(f'Cumulative daily demand plot saved as {output_plot_path}')
