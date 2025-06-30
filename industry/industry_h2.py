"""
This module contains calculates hydrogen demand from industrial facilities over several model years. 2023 emissions data from 
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

# Create a dictionary mapping the fuel type to the CO2 emissions factor
fuel_emissions_df = pd.read_excel(fuel_emissions_factor_path)
fuel_emissions_dict = fuel_emissions_df.set_index('Fuel Type')['kg CO2 per mmBtu'].to_dict()

# Create a dictionary mapping each fuel type to a broader fuel category for which we have fuel consumption projections
fuel_category_dict = fuel_emissions_df.set_index('Fuel Type')['Category'].to_dict()

# Load a DataFrame containing industrial projected fuel consumption from 2023 to 2050 for each fuel category
# This data is taken from the EIA Energy Outlook 2050 Reference Case Table 2
fuel_use_by_category_df = pd.read_csv('industry/inputs/Industry_Fuel_Consumption_Projections.csv', header=4)

# Map other names of fuels to names that can be found in the fuel_emissions_dict
alternative_names = {'Natural Gas (Weighted U.S. Average)': 'Natural Gas', \
                    'Wood and Wood Residuals (dry basis)': 'Wood and Wood Residuals', 'Bituminous': 'Bituminous Coal', \
                    'Liquefied petroleum gases (LPG)': 'Liquefied Petroleum Gases (LPG)'}


def model_industry_demand(sectors, pct_decarbonization, years, scale_demand, to_plot=True):
    """
    Estimates hydrogen demand from each industrial sector over several model years, aggregated by load zone.

    Parameters:
    - sectors: List of names of industrial sectors to model (must match keys in 'sector_by_naics').
    - pct_decarbonization: List of list of percentages of each sector's non-feedstock fuel consumption to 
        decarbonize with hydrogen. (each outer list contains paramters for one model year)
    - years: List of model years 
    - scale_demand: Factor to scale hydrogen demand across all facilities
    - to_plot (bool): Whether to generate spatial plots of facility-level hydrogen demand.

    Returns:
    - A DataFrame containing hydrogen demand by load zone and year in kilograms.
    """

    print('\n===================\nINDUSTRY H2 DEMAND\n==================')

    # Create a dictionary mapping NAICS codes to their sector's decarbonization percentage

    # Final output df with all of the load zones and years
    load_zone_summary = pd.DataFrame()
    index = 0

    for year in years:
        print(f'\nProcessing year {year}...')

        naics_pct_decarbonize = {
        code: pct
        for sector, pct in zip(sectors, pct_decarbonization[index])
        for code in sector_by_naics[sector] }   

        year_result = model_one_year(naics_pct_decarbonize, year, scale_demand, to_plot)
        load_zone_summary = pd.concat([load_zone_summary, year_result])

        index += 1

    load_zone_summary = load_zone_summary.sort_values(by=['load_zone', 'year']).reset_index(drop=True)
    load_zone_summary.to_csv(load_zone_output_path, index=False)

    return load_zone_summary


def model_one_year(decarb_by_sector, year, scale_demand, to_plot):
    """
    Calculates hydrogen demand for a single model year.

    Parameters:
    - decarb_by_sector: Dictionary mapping from NAICS code to percent decarbonization via hydrogen (e.g., {32411: 75}).
    - year: The model year for which hydrogen demand is being modeled.
    - scale_demand: Factor used to scale projected fuel demand 
    - to_plot: If True, generates a map of facilities in the WECC and their hydrogen demand.

    Returns:
    - DataFrame containing total hydrogen demand (kg) by load zone for the specified year.
    """
        
    naics_pct_decarbonize = decarb_by_sector 

    # Create a DataFrame for the results for hydrogen demand from each facility
    results_by_facility = pd.DataFrame()

    # Create a list for a more detailed breakdown by unit and fuel
    breakdown_by_fuel = []

    # Filter the fuel_use_by_category DataFrame for the base year (2023) and the model year
    fuel_use_by_category_filtered = fuel_use_by_category_df[fuel_use_by_category_df['Year'].isin([2023, year])].reset_index(drop=True)

    # Create a dictionary mapping each fuel category to the relative growth it experiences from 2023 to the model year
    fuel_growth_by_category_dict = {
        col: (fuel_use_by_category_filtered[col].iloc[1] - fuel_use_by_category_filtered[col].iloc[0]) / fuel_use_by_category_filtered[col].iloc[0]
        for col in fuel_use_by_category_filtered.columns if col != 'Year'
    }
    
    # Process each industry
    for file_name in os.listdir(units_and_fuel_folder):
        if file_name.endswith('.csv') and not file_name.startswith('~$'):
            results_by_industry = []

            industry_facilities_df = pd.read_csv(base_path / units_and_fuel_folder / file_name)

            # Retrieve the industry's NAICS code
            naics = int(industry_facilities_df.iloc[0, 5])

            # Aluminum NAICS
            if str(naics).startswith(str('3313')):
                    naics = 3313        
            
            # Group each unit and fuel by facility
            sector_facilities_grouped = industry_facilities_df.groupby('Facility Id')

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

                    unit_demand_mmBtu = unit_CO2_emissions * 1000 / avg_emissions_factor * decarb_factor # multiplying by 1000 to convert from mt to kg

                    # Add detailed results to the breakdown in the logs and adjust for the model year
                    for fuel in unit_fuels:
                        unit_fuel_demand = unit_demand_mmBtu / len(unit_fuels) if unit_demand_mmBtu != 0 else 0
                        fuel_category = fuel_category_dict[fuel]
                        projected_fuel_growth =  fuel_growth_by_category_dict[fuel_category]
                        projected_fuel_demand = (1 + projected_fuel_growth) * unit_fuel_demand * scale_demand

                        breakdown_by_fuel.append({'facility_id': facility_id, 'facility_name': facility_name, 'unit_name': unit_name, 'fuel': fuel, \
                                    'naics': naics, 'latitude': latitude, 'longitude': longitude, \
                                    'h2_demand_mmBtu': projected_fuel_demand})
                        
                        # Add the unit's fuel demand to the facility's running total for fuel demand, scaled by scale_demand
                        facility_fuel_demand_mmBtu += projected_fuel_demand
                
                # Add the facility results to the final output result DataFrame
                results_by_industry.append({'facility_id': facility_id, 'facility_name': facility_name, 'naics': naics, \
                                        'latitude': latitude, 'longitude': longitude, 'h2_demand_mmBtu': facility_fuel_demand_mmBtu})
            
            # Save the results for hydrogen demand by facility for each industry
            industry_results_df = pd.DataFrame(results_by_industry)
            results_by_facility = pd.concat([results_by_facility, industry_results_df])

    # Save the detailed results by unit and fuel
    pd.DataFrame(breakdown_by_fuel).to_csv(logs_path / f'{year}_demand_by_unit_fuel.csv', index=False)

    # Convert the results by facility to a DataFrame and send it to the plotting function
    results_by_facility_df = pd.DataFrame(results_by_facility)

    # Convert H2 demand from mmBtu to kg
    results_by_facility_df['total_h2_demand'] = results_by_facility_df['h2_demand_mmBtu'] * ONE_MILLION / BTU_IN_1LB_H2 * LB_TO_KG

    # Filter the facilities to only those within WECC bundaries and save this as the final result
    filtered_df, final_df = filter_and_plot.filter(results_by_facility_df)

    # Plot the filtered facilities and their corresponding hydrogen demand
    if to_plot:
        filter_and_plot.plot(filtered_df, year)

    filtered_df.to_csv(logs_path / f'{year}_demand_by_facility.csv', index = False)
    final_df['year'] = year

    return final_df
