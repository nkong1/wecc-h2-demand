"""
This module contains calculates hydrogen demand from industrial facilities over several model years. 2023 emissions data from 
US facilities with NAICS codes that match the industries we are modeling was collected. These emissions are broken down
by facility, unit, and fuel. Emissions for each unit across all facilities are converted directly to an input energy value, 
then to an amount of hydrogen (in kg) needed to provide an equivalent fuel energy for each facility.
"""

import pandas as pd
import numpy as np
import os
import shutil
from pathlib import Path
from industry import aggregate_and_plot 

# File paths
base_path  = Path(__file__).parent
units_and_fuel_folder = base_path / 'inputs' / 'sector_unit_fuel_2022'
fuel_emissions_factor_path = base_path / 'inputs' / 'epa_fuel_ghg_emission_factors.xlsx'
fuel_use_projection_path = base_path / 'inputs' / 'eia_aeo_industrial_fuel_use_projections.csv'
mecs_data_path = base_path / 'inputs' / 'eia_mecs_fuel_consumption.csv'

# Create a new logs path
logs_path = base_path / 'logs'
if logs_path.exists():
    shutil.rmtree(logs_path)
logs_path.mkdir()

# Final output path
load_zone_output_path = base_path.parent / 'outputs' / 'industry' / 'demand_by_load_zone.csv'

# Constants
ONE_MILLION = 10 ** 6
BTU_IN_1LB_H2 = 61013
LB_TO_KG = 0.453592

sector_by_naics = {'Iron_and_Steel': [331110, 331511, 3312], 'Aluminum': [3313], 'Cement': [327310],
                   'Chemicals': [325], 'Refineries': [324110], 'Glass': [ 327211, 
                    327212, 327213, 327215]}

# Create a dictionary mapping the fuel type to the CO2 emissions factor
fuel_emissions_df = pd.read_excel(fuel_emissions_factor_path)
fuel_emissions_dict = fuel_emissions_df.set_index('Fuel Type')['kg CO2 per mmBtu'].to_dict()

# Create a dictionary mapping each fuel type to a broader fuel category for which we have fuel consumption projections
aeo_fuel_category_dict = fuel_emissions_df.set_index('Fuel Type')['EIA AEO Category'].to_dict()

# Create a dictionary mapping each fuel type to its EIA MECS category (if applicable)
mecs_fuel_category_dict = fuel_emissions_df.set_index('Fuel Type')['EIA MECS Category'].to_dict()

# Load a DataFrame containing industrial projected fuel consumption from 2023 to 2050 for each fuel category
# This data is taken from the EIA Energy Outlook 2050 Reference Case Table 2
fuel_use_by_category_df = pd.read_csv(fuel_use_projection_path, header=4)


def model_industry_demand(pct_decarbonization, years):
    """
    Estimates hydrogen demand from each industrial sector over several model years, aggregated by load zone.

    Parameters:
    - pct_decarbonization: List of list of percentages of each sector's non-feedstock fuel consumption to 
        decarbonize with hydrogen. (each outer list contains paramters for one model year)
    - years: List of model years 

    Returns:
    - A DataFrame containing hydrogen demand by load zone and year in kilograms.
    """

    print('\n===================\nINDUSTRY H2 DEMAND\n==================')

    # Final output df with all of the load zones and years
    load_zone_summary = pd.DataFrame()
    index = 0

    for year in years:
        print(f'\nProcessing year {year}...')

        pct_decarbonize_by_sector = pct_decarbonization[index]

        year_result = model_one_year(pct_decarbonize_by_sector, year)
        load_zone_summary = pd.concat([load_zone_summary, year_result])

        index += 1

    load_zone_summary = load_zone_summary.sort_values(by=['load_zone', 'year']).reset_index(drop=True)
    load_zone_summary.to_csv(load_zone_output_path, index=False)

    return load_zone_summary


def get_naics_code(naics):
    naics_str = str(naics)
    for sector, codes in sector_by_naics.items():
        for code in codes:
            code_str = str(code)
            # Exact match
            if naics_str == code_str:
                return int(code_str)
            # Prefix match
            if naics_str.startswith(code_str):
                return int(code_str)
    return None

def get_sector(naics):
    naics_str = str(naics)
    sector = None
    for key, codes in sector_by_naics.items():
        for code in codes:
            if naics_str.startswith(str(code)):
                sector = key
                break
        if sector:
            break
    return sector

def calc_discrepancies(breakdown_by_fuel_df):

    west_breakdown_by_fuel_df = breakdown_by_fuel_df[breakdown_by_fuel_df['inWestCensus'] == True].copy()
    west_breakdown_by_fuel_df['naics'] = west_breakdown_by_fuel_df['naics'].astype(str).str.split('.').str[0]
    west_breakdown_by_fuel_df_grouped = west_breakdown_by_fuel_df.groupby('naics')
    mecs_data = pd.read_csv(mecs_data_path, index_col='NAICS Code', dtype={"NAICS Code": str})

    discrepancy_list = []

    all_naics = [str(code) for codes in sector_by_naics.values() for code in codes]

    for naics in all_naics:
        naics = str(naics)

        try:
            fuel_df = west_breakdown_by_fuel_df_grouped.get_group(naics)
            ghgrp_fuel_total_mmbtu = fuel_df['fuel_demand_mmBtu'].sum() 
        except:
            ghgrp_fuel_total_mmbtu = 0
        
        mecs_fuel_total_mmbtu = mecs_data.loc[naics]['Fossil Fuels Total'] * 1e6
        print(f'naics: {naics} mecs total: {mecs_fuel_total_mmbtu}, ghgrp total: {ghgrp_fuel_total_mmbtu // 1e6}')

        discrepancy_mmbtu = int(mecs_fuel_total_mmbtu) - ghgrp_fuel_total_mmbtu
        if ghgrp_fuel_total_mmbtu != 0:
            mecs_to_ghgrp_ratio = mecs_fuel_total_mmbtu / ghgrp_fuel_total_mmbtu
        else:
            mecs_to_ghgrp_ratio = np.inf

        discrepancy_list.append({'naics': naics, 'sector': get_sector(naics), 'mecs_mmbtu': mecs_fuel_total_mmbtu, 'ghgrp_mmbtu': ghgrp_fuel_total_mmbtu, \
                                 'discrepancy_mmbtu': discrepancy_mmbtu, 'mecs_to_ghgrp_ratio': mecs_to_ghgrp_ratio})
        
    naics_discrepancy_df = pd.DataFrame(discrepancy_list)

    # Sum discrepancies within each sector
    sector_discrepancy_df = naics_discrepancy_df.groupby('sector').agg(
        discrepancy_mmbtu=('discrepancy_mmbtu', 'sum'),
        mecs_mmbtu=('mecs_mmbtu', 'sum'),
        ghgrp_mmbtu=('ghgrp_mmbtu', 'sum'),
    ).reset_index()

    # Compute sector-level MECS-to-GHGRP ratio as weighted average
    sector_discrepancy_df['mecs_to_ghgrp_ratio'] = sector_discrepancy_df['mecs_mmbtu'] / sector_discrepancy_df['ghgrp_mmbtu']

    # Sort by largest discrepancy
    sector_discrepancy_df = sector_discrepancy_df.sort_values('discrepancy_mmbtu', ascending=False)

    # Save outputs
    naics_discrepancy_df.to_csv(logs_path / 'discrepancies_by_naics.csv', index=False)
    sector_discrepancy_df.to_csv(logs_path / 'sector_discrepancies.csv', index=False)

    return sector_discrepancy_df


def model_one_year(decarb_by_sector, year):
    """
    Calculates hydrogen demand for a single model year.

    Parameters:
    - decarb_by_sector: Dictionary mapping from sector code to percent decarbonization via hydrogen (e.g., {'Iron_and_Steel': 75}).
    - year: The model year for which hydrogen demand is being modeled.

    Returns:
    - DataFrame containing total hydrogen demand (kg) by load zone for the specified year.
    """
    #========================
    # Step 1: Calculate fuel consumption using EPA GHGRP stationary combustion emissions and emissions factors
    #========================
    # Filter the fuel_use_by_category DataFrame for the base year (2022) and the model year
    # Since the AEO25 only has projections starting from 2023, we assume 2022-2023 has the same percent change as 2023-2024
    fuel_use_by_category_filtered = fuel_use_by_category_df[fuel_use_by_category_df['Year'].isin([2022, year])].reset_index(drop=True)

    # Create a dictionary mapping each fuel category to the relative growth it experiences from 2023 to the model year
    fuel_growth_by_category_dict = {
        col: (fuel_use_by_category_filtered[col].iloc[1] - fuel_use_by_category_filtered[col].iloc[0]) / fuel_use_by_category_filtered[col].iloc[0]
        for col in fuel_use_by_category_filtered.columns if col != 'Year'
    }

    results_by_facility, breakdown_by_fuel = calc_epa_ghgrp_fuel_consumption(decarb_by_sector, fuel_growth_by_category_dict)

    results_by_facility_df = pd.DataFrame(results_by_facility)
    breakdown_by_fuel_df = pd.DataFrame(breakdown_by_fuel)

    # Save the detailed results by unit and fuel
    breakdown_by_fuel_df.to_csv(logs_path / f'{year}_demand_by_unit_fuel.csv', index=False)

    """
    # Save an output of the total fuel consumption by sector and fuel
    sector_fuel_breakdown = (
        breakdown_by_fuel_df
        .groupby(['naics', 'fuel'])['fuel_demand_mmBtu']
        .sum()
        .reset_index()
    )

    # Pivot so that fuels are columns
    sector_fuel_pivot = sector_fuel_breakdown.pivot(
        index='naics',
        columns='fuel',
        values='fuel_demand_mmBtu'
    ).fillna(0)

    # Optional: add a total column
    sector_fuel_pivot['Total'] = sector_fuel_pivot.sum(axis=1)

    # Save to Excel
    sector_fuel_pivot.to_csv(logs_path / "sector_fuel_breakdown.csv")
    print("Saved sector_fuel_breakdown.csv")
    """

    #========================
    # Step 2: Call the calc_discrepancies function to calculate the discrepancy in fuel consumption between that 
    # found in Step 1 using the EPA GHGRP data and the fuel consumption totals from the EIA MECS Survey in the 
    # West Census Region. 
    #========================

    discrepancies_by_sector = calc_discrepancies(breakdown_by_fuel_df)

    # Next: get a list of all facilities in the EPA FRS not in the EPA GHGRP (that we used) and disaggregate across those

    # Convert H2 demand from mmBtu to kg
    results_by_facility_df['total_h2_demand_kg'] = results_by_facility_df['proj_fuel_demand_mmBtu'] * ONE_MILLION / BTU_IN_1LB_H2 * LB_TO_KG

    # Filter the facilities to only those within WECC bundaries and save this as the final result
    filtered_df = results_by_facility_df[results_by_facility_df['inWECC'] == True].copy()
    filtered_df['sector'] = filtered_df['naics'].map(get_sector)
    
    aggregated_by_lz = aggregate_and_plot.aggregate_by_lz(results_by_facility_df)

    # Plot the filtered facilities and their corresponding hydrogen demand
    aggregate_and_plot.plot(filtered_df, year)

    filtered_df.to_csv(logs_path / f'{year}_demand_by_facility.csv', index = False)
    aggregated_by_lz['year'] = year

    return aggregated_by_lz

def calc_epa_ghgrp_fuel_consumption(pct_decarbonize_by_sector, fuel_growth_by_category_dict):
    """
    Returns
    """

    # Create a DataFrame for the results for hydrogen demand from each facility
    all_results_by_facility = pd.DataFrame()

    # Create a list for a more detailed breakdown by facility unit and fuel type
    breakdown_by_fuel = []
    
    # Process each industry
    for file_name in os.listdir(units_and_fuel_folder):
        if not file_name.endswith('.csv') or file_name.startswith('~$'):
            continue
        
        sector_name = file_name.replace('_facilities_breakdown.csv', '')

        results_by_sector = []
        industry_facilities_df = pd.read_csv(base_path / units_and_fuel_folder / file_name)

        if industry_facilities_df.empty:
            continue

        # Group each unit and fuel by facility
        sector_facilities_grouped = industry_facilities_df.groupby('Facility Id')

        # Process each facility in the industry
        for facility_id, facility_df in sector_facilities_grouped:

            facility_name = facility_df['Facility Name_x'].iloc[0]
            latitude = facility_df['Latitude'].iloc[0]
            longitude = facility_df['Longitude'].iloc[0]

            # Retrieve the industry's NAICS code
            naics = get_naics_code(int(industry_facilities_df.iloc[0]['Primary NAICS Code_y']))

            inWECC = facility_df['inWECC'].iloc[0]
            inWestCensus = facility_df['inWestCensus'].iloc[0]

            proj_facility_fuel_demand_mmBtu = 0
            facility_units_grouped = facility_df.groupby('Unit Name')

            # Process each unit in the facility
            for unit_name, unit_df in facility_units_grouped:
                
                consumes_biofuels = False

                # Assume that any missing fuel types are natural gas (the most commonly used fuel)
                unit_df['Specific Fuel Type'] = unit_df['Specific Fuel Type'].fillna('Natural Gas')       

                # Retreive the unit's total CO2 emissions
                unit_CO2_emissions = unit_df.iloc[0]['Unit CO2 emissions (non-biogenic)']

                # If there are multiple fuels, find the average emissions factor and use this to
                # calculate fuel demand in mmBtu assuming each fuel is consumed in equal quantities
                emissions_factor_total = 0
                
                # Keep a running list of all the fuels that the unit consumes
                unit_fuels = []

                # Iterate across the different fuels for the unit
                for _, fuel_df in unit_df.iterrows():  
                    fuel = fuel_df['Specific Fuel Type']

                    # Skip if the fuel is a biofuel
                    if 'Biofuels' in aeo_fuel_category_dict[fuel]:
                        consumes_biofuels = False
                        continue

                    # Get the emissions factor for the fuel if it exists
                    try:
                        unit_fuels.append(fuel)

                        emissions_factor = fuel_emissions_dict[fuel]
                        emissions_factor_total += emissions_factor
                    except:
                        print(f'The fuel {fuel} is not registered in the emissions factor dictionary. Skipping this unit.')

                # Use the average emissions factor across all fuels to calculate the fuel demand for the unit
                if emissions_factor_total == 0:
                    continue 
                
                avg_emissions_factor = emissions_factor_total / len(unit_fuels) # emissions factor is in metric tons

                decarb_pct = pct_decarbonize_by_sector[list(sector_by_naics.keys()).index(sector_name)]

                decarb_factor = decarb_pct / 100

                unit_demand_mmBtu = unit_CO2_emissions * 1000 / avg_emissions_factor  # multiplying by 1000 to convert from mt to kg
                unit_fuel_CO2_emissions = unit_CO2_emissions / len(unit_fuels)
                unit_fuel_energy_demand = unit_demand_mmBtu / len(unit_fuels)

                if consumes_biofuels:
                    unit_demand_mmBtu *= len(unit_fuels) / (len(unit_fuels) + 1)
                    unit_fuel_CO2_emissions = unit_CO2_emissions / (len(unit_fuels) + 1)
                    unit_fuel_energy_demand = unit_demand_mmBtu / (len(unit_fuels) + 1)

                # Add detailed results to the breakdown in the logs and adjust for the model year
                for fuel in unit_fuels:
                    unit_fuel_demand = unit_demand_mmBtu / len(unit_fuels) if unit_demand_mmBtu != 0 else 0

                    # Project fuel use for fuels that are in the EIA AEO 25 projections
                    aeo_fuel_category = aeo_fuel_category_dict[fuel]

                    if aeo_fuel_category == np.nan: 
                        print(f'projected 0 for {fuel}')
                        projected_fuel_growth = 0
                    else:
                        projected_fuel_growth =  fuel_growth_by_category_dict[aeo_fuel_category]

                    projected_fuel_demand = (1 + projected_fuel_growth) * unit_fuel_demand * decarb_factor

                    breakdown_by_fuel.append({'facility_id': facility_id, 'facility_name': facility_name, 'unit_name': unit_name, 'fuel': fuel, \
                                'naics': naics, 'latitude': latitude, 'longitude': longitude, 'co2_emissions': unit_fuel_CO2_emissions, \
                                'fuel_demand_mmBtu': unit_fuel_energy_demand, 'proj_fuel_demand_mmBtu': projected_fuel_demand, \
                                'inWestCensus': fuel_df['inWestCensus']})
                    
                    # Add the unit's fuel demand to the facility's running total for fuel demand, scaled by scale_demand
                    proj_facility_fuel_demand_mmBtu += projected_fuel_demand
            
            # Add the facility results to the final output result DataFrame
            results_by_sector.append({'facility_id': facility_id, 'facility_name': facility_name, 'naics': naics, \
                                    'latitude': latitude, 'longitude': longitude, 'proj_fuel_demand_mmBtu': proj_facility_fuel_demand_mmBtu, \
                                    'inWestCensus': inWestCensus,'inWECC': inWECC})
        
        # Save the results for hydrogen demand by facility for each industry
        industry_results_df = pd.DataFrame(results_by_sector)

        all_results_by_facility = pd.concat([all_results_by_facility, industry_results_df])

    
    return all_results_by_facility, breakdown_by_fuel
