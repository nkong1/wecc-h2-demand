"""
This file contains a function that calculates hydrogen demand from industrial facilities. 2023 emissions data from 
US facilities with NAICS codes that match the industries we are modeling was collected. These emissions are broken down
by facility, unit, and fuel. Emissions for each unit across all facilities are converted directly to an input energy value, 
then to an amount of hydrogen (in kg) needed to provide an equivalent fuel energy for each facility.
"""

import pandas as pd
import os
import shutil
from pathlib import Path
from industry import filter_and_plot 
from industry.sector_naics_info import * 

# File paths
base_path  = Path(__file__).parent
units_and_fuel_folder = base_path / 'inputs' / 'sector_unit_fuel'
fuel_emissions_factor_path = base_path / 'inputs' / 'fuel_ghg_emission_factors.xlsx'

# Create a new logs folder
logs_path = base_path / 'logs'
if logs_path.exists() and logs_path.is_dir():
    shutil.rmtree(logs_path)
logs_path.mkdir()

facilities_output_path = logs_path / 'demand_by_facility.csv'
load_zone_output_path = base_path.parent / 'outputs' / 'industry' / 'load_zone_results.csv'


# Constants
ONE_MILLION = 10 ** 6
BTU_IN_1LB_H2 = 61013
LB_TO_KG = 0.453592


def calc_industry_demand(sectors, pct_decarbonization, to_plot=True):

    naics_codes = [code for sector in sectors for code in sector_by_naics[sector]]

    # Create a dictionary mapping NAICS codes to their sector's decarbonization percentage
    naics_pct_decarbonize = {
        code: pct
        for sector, pct in zip(sectors, pct_decarbonization)
        for code in sector_by_naics[sector]
    }   

    print('\n===================\nINDUSTRY H2 DEMAND\n==================')

    # Create a dictionary mapping the fuel type to the CO2 emissions factor
    fuel_emissions_df = pd.read_excel(fuel_emissions_factor_path)
    fuel_emissions_dict = fuel_emissions_df.set_index('Fuel Type')['kg CO2 per mmBtu'].to_dict()

    # Map other names of fuels to names that can be found in the fuel_emissions_dict
    alternative_names = {'Propane': 'Propane Gas', 'Natural Gas (Weighted U.S. Average)': 'Natural Gas', \
                        'Wood and Wood Residuals (dry basis)': 'Wood and Wood Residuals', 'Bituminous': 'Bituminous Coal', \
                        'Liquefied petroleum gases (LPG)': 'Liquefied Petroleum Gases (LPG)'}

    # Create a DataFrame for the final results for hydrogen demand by facility
    results_by_facility = pd.DataFrame()

    # Create a list for a more detailed breakdown by unit and fuel
    breakdown_by_fuel = []
    
    # Process each industry
    for file_name in os.listdir(units_and_fuel_folder):
        if file_name.endswith('.csv') and not file_name.startswith('~$'):
            results_by_industry = []

            sector_facilities_df = pd.read_csv(base_path / units_and_fuel_folder / file_name)

            # Retrieve the industry's NAICS code
            naics = sector_facilities_df.iloc[0, 5]

            # Aluminum NAICS
            if str(naics).startswith(str('3313')):
                    naics = 3313

            # If the industry is not in the input industry list, skip it
            if naics not in naics_codes:
                continue

            # Group each unit and fuel by facility
            sector_facilities_grouped = sector_facilities_df.groupby('Facility Id')

            # Process each facility in the industry
            for facility_id, facility_df in sector_facilities_grouped:

                facility_name = facility_df['Facility Name_x'].iloc[0]
                latitude = facility_df['Latitude'].iloc[0]
                longitude = facility_df['Longitude'].iloc[0]

                facility_fuel_demand_mmBtu = 0

                facility_units_grouped = facility_df.groupby('Unit Name')

                # Process each unit in the facility
                for unit_name, unit_df in facility_units_grouped:
                    
                    # Assume that any missing fuel types are natural gas (the most commonly used fuel)
                    unit_df['Specific Fuel Type'] = unit_df['Specific Fuel Type'].fillna('Natural Gas')       
                    
                    # Keep a running count for the total fuel demand for the unit across all fuels
                    unit_fuel_demand_mmBtu = 0

                    # Retreive the unit's total CO2 emissions
                    unit_CO2_emissions = unit_df.iloc[0]['Unit CO2 emissions (non-biogenic)']

                    # If there are multiple fuels, find the average emissions factor and use this to
                    # calculate fuel demand in mmBtu assuming each fuel is consumed in equal quantities
                    emissions_factor_total = 0
                    
                    # Keep a running list of all the fuels that the unit consumes
                    unit_fuels = []

                    # Iterate across the different fuels for the unit
                    for _, fuel_df in unit_df.iterrows():  
                        fuel_type = fuel_df['Specific Fuel Type']

                        # Get the emissions factor for the fuel if it exists
                        try:
                            # Test if the fuel has an alternative name
                            updated_fuel_type = alternative_names.get(fuel_type, fuel_type)
                            unit_fuels.append(updated_fuel_type)

                            emissions_factor = fuel_emissions_dict[updated_fuel_type]
                            emissions_factor_total += emissions_factor
                        except:
                            print(f'The fuel {fuel_type} is not registered in the emissions factor dictionary.')

                    # Use the average emissions factor across all fuels to calculate the fuel demand for the unit
                    avg_emissions_factor = emissions_factor_total / len(unit_fuels) # emissions factor is in metric tons

                    decarb_pct = naics_pct_decarbonize[naics]
                    decarb_factor = decarb_pct / 100
                    
                    unit_fuel_demand_mmBtu = unit_CO2_emissions * 1000 / avg_emissions_factor * decarb_factor # multiplying by 1000 to convert from mt to kg

                    # Add detailed results to the breakdown in the logs
                    for fuel in unit_fuels:
                        breakdown_by_fuel.append({'facility_id': facility_id, 'facility_name': facility_name, 'unit_name': unit_name, 'fuel': fuel, \
                                    'naics': naics, 'latitude': latitude, 'longitude': longitude, \
                                    'h2_demand_mmBtu': unit_fuel_demand_mmBtu / len(unit_fuels) if unit_fuel_demand_mmBtu != 0 else 0})
                        
                    # Add the unit's fuel demand to the facility's running total for fuel demand
                    facility_fuel_demand_mmBtu += unit_fuel_demand_mmBtu    
                
                # Add the facility results to the final output result DataFrame
                results_by_industry.append({'facility_id': facility_id, 'facility_name': facility_name, 'naics': naics, \
                                        'latitude': latitude, 'longitude': longitude, 'h2_demand_mmBtu': facility_fuel_demand_mmBtu})
            
            # Save the results for hydrogen demand by facility for each industry
            industry_results_df = pd.DataFrame(results_by_industry)
            results_by_facility = pd.concat([results_by_facility, industry_results_df])

    # Save the detailed results by unit and fuel
    pd.DataFrame(breakdown_by_fuel).to_csv(logs_path / 'demand_by_unit_fuel.csv', index=False)

    # Convert the results by facility to a DataFrame and send it to the plotting function
    results_by_facility_df = pd.DataFrame(results_by_facility)

    # Convert H2 demand from mmBtu to kg
    results_by_facility_df['h2_demand_kg'] = results_by_facility_df['h2_demand_mmBtu'] * ONE_MILLION / BTU_IN_1LB_H2 * LB_TO_KG

    print('\nFinished calculating facility-level hydrogen demand')

    # Filter the facilities to only those within WECC bundaries and save this as the final result
    filtered_df, final_df = filter_and_plot.filter(results_by_facility_df, to_plot)
    filtered_df.to_csv(facilities_output_path, index = False)
    final_df.to_csv(load_zone_output_path, index = False)
