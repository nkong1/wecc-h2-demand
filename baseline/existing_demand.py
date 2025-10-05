
import pandas as pd
from pathlib import Path
from industry.aggregate_and_plot import get_aggregate_by_lz, get_demand_grid
from industry.build_industry_profile import build_profile

#======================
# File paths:
#======================

base_path  = Path(__file__).parent
existing_h2_plants_path = base_path / 'wecc_existing_h2_plants_2022.csv'

def get_existing_demand_df():
    existing_plants_df = pd.read_csv(existing_h2_plants_path)

    existing_plants_df['total_h2_demand_kg'] = existing_plants_df['hydrogen_demand_kg'] 
    existing_plants_df = existing_plants_df[['Latitude', 'Longitude', 'total_h2_demand_kg']]
    
    return existing_plants_df

def model_existing_demand(years):
    print('\n===================\nBASELINE H2 DEMAND\n==================')

    existing_plants_df = get_existing_demand_df()
    baseline_by_lz = get_aggregate_by_lz(existing_plants_df)
    demand_grid = get_demand_grid(existing_plants_df)

    output_profiles_path = base_path.parent / 'outputs' / 'baseline' / 'demand_profiles'
    grid_output_path = base_path.parent / 'outputs' / 'baseline' 

    baseline_by_lz.to_csv(base_path.parent / 'outputs' / 'demand_by_load_zone.csv')

    all_years_summary = pd.DataFrame()
    for year in years:
        print(f'\nProcessing year {year}...')

        year_df = baseline_by_lz.copy()
        year_df['year'] = year

        all_years_summary = pd.concat([all_years_summary, year_df])

        demand_grid.to_file(grid_output_path / f'{year}_wecc_h2_demand_5km_resolution.gpkg', driver='GPKG')

    all_years_summary = all_years_summary.sort_values(by='load_zone')

    build_profile(all_years_summary, output_profiles_path, flat=True)




