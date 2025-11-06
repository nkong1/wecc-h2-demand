
import pandas as pd
from pathlib import Path
from industry.aggregate_and_plot import get_aggregate_by_lz, get_demand_grid
from industry.build_industry_profile import build_profile

DIESEL_FROM_ONROAD_TRANSPORT = .8801
GASOLINE_FROM_ONROAD_TRANSPORT = .9899 

base_path  = Path(__file__).parent
existing_h2_plants_path = base_path / 'wecc_existing_h2_plants_2022.csv'

def get_existing_demand_df(scaling_factor):
    existing_plants_df = pd.read_csv(existing_h2_plants_path)

    existing_plants_df['total_h2_demand_kg'] = existing_plants_df['hydrogen_demand_kg'] * scaling_factor
    existing_plants_df = existing_plants_df[['Latitude', 'Longitude', 'total_h2_demand_kg']]
    
    return existing_plants_df


def model_existing_demand(years, ld_decarb_pcts, hd_decarb_pcts, aviation_decarb_pcts):
    print('\n===================\nBASELINE H2 DEMAND\n==================')

    output_profiles_path = base_path.parent / 'outputs' / 'baseline' / 'demand_profiles'
    grid_output_path = base_path.parent / 'outputs' / 'baseline' 

    all_years_summary = pd.DataFrame()

    iteration = 0

    for year in years:
        print(f'\nProcessing year {year}...')

        # Get scaling factor
        demand_scaling_factor = calc_scaling_factor(ld_decarb_pcts[iteration], hd_decarb_pcts[iteration], aviation_decarb_pcts[iteration])

        existing_plants_df = get_existing_demand_df(demand_scaling_factor)
        baseline_by_lz = get_aggregate_by_lz(existing_plants_df)
        demand_grid = get_demand_grid(existing_plants_df)

        year_df = baseline_by_lz.copy()
        year_df['year'] = year

        all_years_summary = pd.concat([all_years_summary, year_df])

        demand_grid.to_file(grid_output_path / f'{year}_wecc_h2_demand_5km_resolution.gpkg', driver='GPKG')
        baseline_by_lz.to_csv(base_path.parent / 'outputs' / 'baseline' / f'{year}_demand_by_load_zone.csv')

        iteration += 1

    all_years_summary = all_years_summary.sort_values(by='load_zone')

    build_profile(all_years_summary, output_profiles_path, flat=True)



def calc_scaling_factor(ld_decarb_pct, hd_decarb_pct, aviation_decarb_pct):
    """From EIA: On average, U.S. refineries produce, from a 42-gallon barrel of crude oil: About 19 to 20 gallons of motor 
    gasoline, 11 to 13 gallons of distillate fuel, most of which is sold as diesel fuel, 3 to 4 gallons of jet fuel"""
    return ( 1 - ( ld_decarb_pct * 19.5 / 42 * GASOLINE_FROM_ONROAD_TRANSPORT 
            + hd_decarb_pct * 12 / 42 * DIESEL_FROM_ONROAD_TRANSPORT 
            + aviation_decarb_pct * 3.5 / 42
    ) / 100)

