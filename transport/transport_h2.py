import pandas as pd
import os
from pathlib import Path
from transport import plot_demand
import shutil

# Input file paths
base_path  = Path(__file__).parent
fuel_data_path = base_path / 'input_files' / 'transport_gas_and_diesel_usage_by_state.xlsx'

# Create a new logs folder
logs_path = base_path / 'logs'
if logs_path.exists() and logs_path.is_dir():
    shutil.rmtree(logs_path)
logs_path.mkdir()

# Output file paths    
detailed_state_breakdown = logs_path / 'h2_demand_breakdown'
detailed_state_breakdown.mkdir()

h2_demand_by_state = logs_path / 'h2_demand_by_state.csv'
h2_demand_by_load_zone = base_path.parent / 'outputs' / 'transport' / 'transport_demand_by_load_zone.csv'


def calc_state_demand(LD_penetration_pct, HD_penetration_pct, FCEV_ICE_RELATIVE_EFFICIENCY):
    print('\n================\nTRANSPORT H2 DEMAND\n===============')
    print(f'\nScenario: {LD_penetration_pct}% LD and {HD_penetration_pct}% HD FCEV market penetration')

    # FCEV penetration rates 
    LD_penetration = LD_penetration_pct / 100
    HD_penetration = HD_penetration_pct / 100

    # Conversion factors
    GASOLINE_TO_H2 = 1.0  # 1 kg H2 = 1 gallon gasoline (energy equivalence)
    DIESEL_TO_H2 = 1.0 / 0.9 # 1 kg H2 = 0.9 gallons diesel (energy equivalence)

    # Load fuel consumption data by state
    fuel_data = pd.read_excel(fuel_data_path)

    # Create a dictionary to store the hydrogen demand for each state
    # Structure: {StateFips: [LD_demand, HD_demand, total_demand]}
    state_h2_demand = {}

    # Calculate state-level H2 demand
    for _, row in fuel_data.iterrows():
        state_fips = int(row.iloc[1])
        gas_consumption_k_barrels = row.iloc[2]    # Thousand barrels
        diesel_consumption_k_barrels = row.iloc[3]   # Thousand barrels

        # Convert fuel consumption to gallons
        gas_gallons = gas_consumption_k_barrels * 1000 * 42    # 42 gallons in a barrel
        diesel_gallons = diesel_consumption_k_barrels * 1000 * 42

        # Calculate fuel consumption offset using FCEV penetrations
        gas_offset_gallons = gas_gallons * LD_penetration
        diesel_offset_gallons = diesel_gallons * HD_penetration

        # Convert fuel offset to hydrogen demand (accounting for FCEV efficiency)
        ld_h2_demand = gas_offset_gallons * \
            GASOLINE_TO_H2 / FCEV_ICE_RELATIVE_EFFICIENCY
        hd_h2_demand = diesel_offset_gallons * \
            DIESEL_TO_H2 / FCEV_ICE_RELATIVE_EFFICIENCY
        total_h2 = ld_h2_demand + hd_h2_demand

        # Add results to the dictionary
        state_h2_demand[state_fips] = [ld_h2_demand, hd_h2_demand, total_h2]

    # Save the hydrogen demand by state to a DataFrame
    state_h2_df = pd.DataFrame.from_dict(state_h2_demand, orient='index',
                                        columns=['h2_from_gas', 'h2_from_diesel', 'total_h2'])

    state_h2_df.reset_index(inplace=True)
    state_h2_df.rename(columns={'index': 'fips'}, inplace=True)

    # Save results in the logs
    state_h2_df.to_csv(h2_demand_by_state, index=False)

    print('\nSaved results for hydrogen demand by state')

    # Call the spatial disaggregation function, passing in a dictionary mapping the state FIPS to a list with the hydrogen  
    # demand from LD tranport, HD transport, and total transport, respectively
    return spatial_disaggregation(state_h2_demand)

# Spatially disaggregate state-wide demand across load zone, county intersections, then aggregate by load zone
def spatial_disaggregation(state_h2_demand):
    print('\nSpatially disaggregating hydrogen demand...')

    vmt_folder = base_path / 'input_files' / 'VMT_data'
    state_vmt_totals_path = base_path / 'input_files' / 'state_VMT_summary.csv'

    state_vmt_totals = pd.read_csv(state_vmt_totals_path)

    # Create a dictionary mapping the state FIPS code to a list containing LD and HD hydrogen demand
    state_vmts_totals_dict = {
        int(row.iloc[0]): [row.iloc[1], row.iloc[2]]
        for _, row in state_vmt_totals.iterrows()
    }

    # Create a load zone summary dictionary for hydrogen demand
    load_zone_summary = {} # {load zone: [HD_demand, LD_demand, total_demand]}

    # Process each state in the WECC
    for file_name in os.listdir(vmt_folder):
        if not '.csv' in file_name:
            continue

        state_df = pd.read_csv(vmt_folder / file_name)
        state_fips = state_df.iloc[0, 0] // 1000

        hd_vmt_col = state_df.iloc[:, 7]
        ld_vmt_col = state_df.iloc[:, 8]

        # Get the state totals for HD (truck and busses) and LD VMT
        state_LD_vmt = state_vmts_totals_dict[state_fips][0]
        state_HD_vmt = state_vmts_totals_dict[state_fips][1]

        # Extract the values from the demand dictionary once
        state_ld_h2_demand, state_hd_h2_demand, _ = state_h2_demand[state_fips]

        # Compute h2 demand
        state_df['LD_h2_demand'] = ld_vmt_col / state_LD_vmt * state_ld_h2_demand
        state_df['HD_h2_demand'] = hd_vmt_col / state_HD_vmt * state_hd_h2_demand
        state_df['total_h2_demand'] = state_df['LD_h2_demand'] + state_df['HD_h2_demand']

        # Save the state-level hydrogen demand summary
        output_path = detailed_state_breakdown / file_name
        state_df.to_csv(output_path, index = False)

        # Add the h2 demand data to the load zone dictionary
        for load_zone, area_df in state_df.groupby('LOAD_AREA'):
            if not load_zone in load_zone_summary:
                load_zone_summary[load_zone] = [0, 0, 0]

            load_zone_summary[load_zone][0] += area_df.iloc[:, 9].sum() # LD h2
            load_zone_summary[load_zone][1] += area_df.iloc[:, 10].sum() # HD h2
            load_zone_summary[load_zone][2] += area_df.iloc[:, 11].sum() # total h2

    # Transform the load zone dictionary into a Data Frame 
    load_zone_summary_df = pd.DataFrame.from_dict(load_zone_summary, orient='index',
                                        columns=['LD_h2_demand', 'HD_h2_demand', 'total_h2_demand'])

    load_zone_summary_df.reset_index(inplace=True)
    load_zone_summary_df.rename(columns={'index': 'load_zone'}, inplace=True)

    # Save the results for hydrogen demand by load zone
    load_zone_summary_df.to_csv(h2_demand_by_load_zone, index=False)

    print('Saved results for hydrogen demand by load zone')

    plot_demand.plot_lz_demand(load_zone_summary_df)

    return load_zone_summary_df


