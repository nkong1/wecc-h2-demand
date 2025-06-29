"""
For each model year, this module estimates state-level hydrogen demand from the LD and HD transport sectors, then 
disaggregates each one across load zones using VMT data for LDVs and HDVs, respectively. The VMT data is derived from 
the HPMS 2023. 
"""

import pandas as pd
import os
from pathlib import Path
import shutil
from transport import plot_demand
from transport.param_projections import get_transport_parameters

# Input file paths
base_path  = Path(__file__).parent
fuel_data_path = base_path / 'input_files' / 'transport_gas_and_diesel_usage_by_state.xlsx'

# Create a new logs path
logs_path = base_path / 'logs'
if logs_path.exists():
    shutil.rmtree(logs_path)
logs_path.mkdir()

# Create output paths
logs_path = base_path / 'logs'  
state_breakdown = logs_path / 'h2_demand_breakdown'
state_breakdown.mkdir()
h2_demand_by_load_zone = base_path.parent / 'outputs' / 'transport' / 'demand_by_load_zone.csv'


def model_transport_demand(LD_penetration_by_year, HD_penetration_by_year, years):
    """
    Estimates hydrogen demand from LD and HD transport by state, and then calls the disaggregate_by_load_zone
    function to disaggregate it by load zone.

    Parameters:
    - LD_penetration_by_year: list of FCEV penetration percentages for LD transport for each model year
    - HD_penetration_by_year: list of FCEV penetration percentages for HD transport for each model year
    - years: list of model years corresponding to the above market penetration rates

    Returns:
    - a DataFrame with hydrogen demand for each load zone by year (ordered alphabetically by load zone and by 
        descending year). This DataFrame is saved to outputs from the run_model file.
    """

    print('\n===================\nTRANSPORT H2 DEMAND\n==================')

    # Conversion factors
    GASOLINE_TO_H2 = 1.0  # 1 kg H2 = 1 gallon gasoline (energy equivalence)
    DIESEL_TO_H2 = 1.0 / 0.9 # 1 kg H2 = 0.9 gallons diesel (energy equivalence)

    # Load fuel consumption data by state (2023 data from the EIA)
    fuel_data = pd.read_excel(fuel_data_path)

    # Create an output DataFrame that will contain the results for hydrogen demand across each load zone
    # for every model year
    output_load_zone_summary = pd.DataFrame()
    index = 0

    for year in years:
        print(f'\nProcessing year {year}...')
        assumptions = get_transport_parameters(year)

        # Convert percentages to decimals
        LD_penetration = LD_penetration_by_year[index] / 100
        HD_penetration = HD_penetration_by_year[index] / 100

        # Increment the index for the next model year
        index += 1

        # Process assumptions
        LD_FCEV_TO_ICEV_efficiency = assumptions[0]
        HD_FCEV_TO_ICEV_efficiency = assumptions[1]

        rel_change_LD_fuel_consumption = assumptions[2]
        rel_change_HD_fuel_consumption = assumptions[3]

        # Create a dictionary to store the hydrogen demand for each state
        # Structure: {StateFips: [LD_demand, HD_demand, total_demand]}
        state_h2_demand = {}

        # Calculate state-level H2 demand
        for _, row in fuel_data.iterrows():
            state_fips = int(row.iloc[1])
            gas_consumption_k_barrels = row.iloc[2]    # Thousand barrels
            diesel_consumption_k_barrels = row.iloc[3]   # Thousand barrels

            # Convert 2023 gas/diesel fuel consumption to gallons
            ref_gas_gallons = gas_consumption_k_barrels * 1000 * 42    # 42 gallons in a barrel
            ref_diesel_gallons = diesel_consumption_k_barrels * 1000 * 42

            # Project the gas/diesel fuel consumption from on-road transport into the model year
            gas_gallons = ref_gas_gallons * (1 + rel_change_LD_fuel_consumption)
            diesel_gallons = ref_diesel_gallons * (1 + rel_change_HD_fuel_consumption)

            # Calculate fuel consumption offset using FCEV penetrations
            gas_offset_gallons = gas_gallons * LD_penetration
            diesel_offset_gallons = diesel_gallons * HD_penetration

            # Convert fuel offset to hydrogen demand (accounting for FCEV efficiency)
            ld_h2_demand = gas_offset_gallons * \
                GASOLINE_TO_H2 / LD_FCEV_TO_ICEV_efficiency
            hd_h2_demand = diesel_offset_gallons * \
                DIESEL_TO_H2 / HD_FCEV_TO_ICEV_efficiency
            total_h2 = ld_h2_demand + hd_h2_demand

            # Add results to the dictionary
            state_h2_demand[state_fips] = [ld_h2_demand, hd_h2_demand, total_h2]

        # Save the hydrogen demand by state to a DataFrame
        state_h2_df = pd.DataFrame.from_dict(state_h2_demand, orient='index',
                                            columns=['h2_from_gas', 'h2_from_diesel', 'total_h2'])

        state_h2_df.reset_index(inplace=True)
        state_h2_df.rename(columns={'index': 'fips'}, inplace=True)

        # Add a year column to the DataFrame
        state_h2_df['year'] = year

        # Save results in the logs
        h2_demand_by_state = logs_path / f'h2_demand_by_state_{year}.csv'
        state_h2_df.to_csv(h2_demand_by_state, index=False)

        # Call the spatial disaggregation function, passing in a dictionary mapping the state FIPS to a list with the hydrogen  
        # demand from LD tranport, HD transport, and total transport, respectively
        disaggregated_by_lz = disaggregate_by_load_zone(state_h2_demand, year)

        output_load_zone_summary = pd.concat([output_load_zone_summary, disaggregated_by_lz], ignore_index=True)

    output_load_zone_summary = output_load_zone_summary.sort_values(by=['load_zone', 'year']).reset_index(drop=True)

    # Save the results for hydrogen demand by load zone
    output_load_zone_summary.to_csv(h2_demand_by_load_zone, index=False)

    return output_load_zone_summary


def disaggregate_by_load_zone(state_h2_demand, year):
    """
    Disaggregates state-level hydrogen demand to load zones using VMT data.

    Parameters:
    - state_h2_demand: dictionary mapping state FIPS codes to [LD_demand, HD_demand, total_demand] in kg
    - year: model year for which the disaggregation is occurring 

    Returns:
    - DataFrame with hydrogen demand broken down by load zone (with columns 'LD_h2_demand', 
        'HD_h2_demand', 'total_h2_demand', and 'year')
    """

    vmt_folder = base_path / 'input_files' / 'VMT_data'
    state_vmt_totals_path = base_path / 'input_files' / 'state_VMT_summary.csv'

    state_vmt_totals = pd.read_csv(state_vmt_totals_path)

    # Create a dictionary mapping the state FIPS code to a list containing LD and HD hydrogen demand
    state_vmts_totals_dict = {
        int(row.iloc[0]): [row.iloc[1], row.iloc[2]]
        for _, row in state_vmt_totals.iterrows()
    }

    # Create a load zone summary dictionary for hydrogen demand
    load_zone_summary = {} # {load zone: [LD_demand, HD_demand, total_demand]}

    # Process each state in the WECC
    for file_name in os.listdir(vmt_folder):
        if not '.csv' in file_name or '~' in file_name:
            continue

        state_df = pd.read_csv(vmt_folder / file_name)
        state_fips = int(file_name[:2].removesuffix('_'))

        # Get the state totals for HD and LD VMT
        state_ld_vmt = state_vmts_totals_dict[state_fips][0]
        state_hd_vmt = state_vmts_totals_dict[state_fips][1]

        # Get the state totals for HD and LD hydrogen demand
        state_ld_h2_demand, state_hd_h2_demand, _ = state_h2_demand[state_fips]

        hd_vmt_col = state_df.iloc[:, 2]
        ld_vmt_col = state_df.iloc[:, 3]

        # Compute h2 demand
        state_df['LD_h2_demand'] = ld_vmt_col / state_ld_vmt * state_ld_h2_demand
        state_df['HD_h2_demand'] = hd_vmt_col / state_hd_vmt * state_hd_h2_demand
        state_df['total_h2_demand'] = state_df['LD_h2_demand'] + state_df['HD_h2_demand']

        # Save the state-level hydrogen demand summary
        output_path = state_breakdown / f'{file_name.removesuffix('.csv')}_summary.csv'
        state_df.to_csv(output_path, index = False)

        # Add the h2 demand data to the load zone dictionary
        for _, row in state_df.iterrows():
            load_zone = row.iloc[0]

            if not load_zone in load_zone_summary:
                load_zone_summary[load_zone] = [0, 0, 0]

            load_zone_summary[load_zone][0] += row.iloc[4] # LD h2
            load_zone_summary[load_zone][1] += row.iloc[5] # HD h2
            load_zone_summary[load_zone][2] += row.iloc[6] # total h2

    # Transform the load zone dictionary into a Data Frame 
    load_zone_summary_df = pd.DataFrame.from_dict(load_zone_summary, orient='index',
                                        columns=['LD_h2_demand', 'HD_h2_demand', 'total_h2_demand'])
    
    # Add a year column
    load_zone_summary_df['year'] = year

    load_zone_summary_df.reset_index(inplace=True)
    load_zone_summary_df.rename(columns={'index': 'load_zone'}, inplace=True)

    # Remove Canadian/Mexican load zones that arise in the h2 demand df due to small errors in load zone shape boundaries
    load_zone_summary_df = load_zone_summary_df[~load_zone_summary_df['load_zone'].str.contains('CAN|MEX', case=False, na=False)]

    plot_output_path = base_path.parent / 'outputs' / 'transport' / f'{year}_demand_by_load_zone.png'
    plot_demand.plot_lz_demand(load_zone_summary_df, plot_output_path)

    return load_zone_summary_df


