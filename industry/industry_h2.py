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
from functools import lru_cache


#======================
# File paths:
#======================

base_path  = Path(__file__).parent

# Fuel consumption by facility unit and fuel
units_and_fuel_folder = base_path / 'inputs' / 'sector_breakdown_by_unit_fuel' 

# Emissions factors (kg CO2 / mmBtu) for each fuel
fuel_emissions_factor_path = base_path / 'inputs' / 'epa_fuel_ghg_emission_factors.xlsx' 

# Fuel consumption totals by industrial sector across the West Census Region
mecs_data_path = base_path / 'inputs' / 'eia_mecs_fuel_consumption.csv'

# Facilities in the GHGRP that are missing stationary combustion emissions data:
missing_combustion_data_folder = base_path / 'inputs' / 'facilities_missing_combustion_data' 

# Fuel use projections taken from the EIA Energy Outlook 2050 Reference Case Table 2:
fuel_use_projection_path = base_path / 'inputs' / 'eia_aeo_industrial_fuel_use_projections.csv'

# CO2 emissions breakdown by sector (from DOE Pathways to Commercial Liftoff: Industrial Decarbonization Fig 2a.2)
co2_emissions_breakdown_path = base_path / 'inputs' / 'doe_co2_emissions_breakdown_by_industry.csv'

# Existing hydrogen production facilities (EPA GHGRP facilities with 'Hydrogen Production' emissions)
existing_h2_plants_path = base_path / 'inputs' / 'existing_hydrogen_plants_wecc_2023.csv'

# Create a new logs path
logs_path = base_path / 'logs'
if logs_path.exists():
    shutil.rmtree(logs_path)
logs_path.mkdir()

# Final output path
load_zone_output_path = base_path.parent / 'outputs' / 'industry' / 'demand_by_load_zone.csv'


#====================
# Constants:
#====================
ONE_MILLION = 10 ** 6
BTU_IN_1LB_H2 = 61013
LB_TO_KG = 0.453592
ONE_MILLION = 10 ** 6

sector_by_naics = {'Iron_and_Steel': [331110, 331511, 3312], 'Aluminum': [3313], 'Cement': [327310],
                   'Chemicals': [325], 'Refineries': [324110], 'Glass': [ 327211, 
                    327212, 327213, 327215]}

#====================
# Helper Functions:
#====================

def get_naics_code(naics):
    """
    Returns the naics code (int) used in our model, corresponding to the input naics code (str or int).

    Ex: 325121 -> 325, 327211 -> 327211
    """
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
    """
    Returns the sector (str) that corresponds to the input naics code (str or int).
    """
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

def get_high_heat_emissions_share(sector):
    """
    Returns the share of CO2 emissions associated with high-temperature combustion 
    relative to all combustion emissions in the given sector.
    """
    
    # Read the input data from the DOE Pathways from Commercial Liftoff: Industrial Decarbonization report
    co2_emissions_df = pd.read_csv(co2_emissions_breakdown_path)

    # Filter for the input sector
    sector_row = co2_emissions_df[co2_emissions_df['Sector'] == sector]
    
    # Compute total combustion (denominator)
    total_combustion = sector_row[['low_temp_heat', 'mid_temp_heat', 'high_temp_heat', 'on_site_power']].sum(axis=1).iloc[0]

    # Compute share (high-temp / total combustion)
    high_heat_share = sector_row['high_temp_heat'].iloc[0] / total_combustion

    return high_heat_share
    

def calc_discrepancies(breakdown_by_fuel_df):
    """
    Calculates the discrepancy between our fuel consumption estimates obtained using EPA GHGRP data
    and fuel consumption totals from the EIA MECS Survey. The comparison is made across the West Census
    Region. 

    Parameters:
    - breakdown_by_fuel_df: a DataFrame containing GHGRP-derived fuel consumption estimates by each fuel
        used in each industrial unit (a subset of each industrial facilitiy)

    Returns:
    - a DataFrame containing the discrepancy in fuel demand for each sector (in MMBtu) 
    """

    west_breakdown_by_fuel_df = breakdown_by_fuel_df[breakdown_by_fuel_df['inWestCensus'] == True].copy()
    west_breakdown_by_fuel_df['NAICS Code'] = west_breakdown_by_fuel_df['NAICS Code'].astype(str).str.split('.').str[0]

    west_breakdown_by_fuel_df_grouped = west_breakdown_by_fuel_df.groupby('NAICS Code')
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

        discrepancy_mmbtu = int(mecs_fuel_total_mmbtu) - ghgrp_fuel_total_mmbtu
        if ghgrp_fuel_total_mmbtu != 0:
            mecs_to_ghgrp_ratio = mecs_fuel_total_mmbtu / ghgrp_fuel_total_mmbtu
        else:
            mecs_to_ghgrp_ratio = np.inf

        discrepancy_list.append({'NAICS Code': naics, 'Sector': get_sector(naics), 'mecs_mmbtu': mecs_fuel_total_mmbtu, 'ghgrp_mmbtu': ghgrp_fuel_total_mmbtu, \
                                 'discrepancy_mmbtu': discrepancy_mmbtu, 'mecs_to_ghgrp_ratio': mecs_to_ghgrp_ratio})
        
    naics_discrepancy_df = pd.DataFrame(discrepancy_list)

    # Sum discrepancies within each sector
    sector_discrepancy_df = naics_discrepancy_df.groupby('Sector').agg(
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

def project_sector_consumption(sector, fuel_use, year):
    """
    Projects the total fuel consumption for an entire given sector into the input year.

    Parameters:
    - sector: an industry sector (str)
    - fuel use: the total fuel use in the given sector in the base year of 2022 
    - year: a future model year (int)

    Returns:
    -  a fuel use value projected to the future year, in the same units as the input fuel use
    """
    mecs_fuel_data = pd.read_csv(mecs_data_path)

    # Rename to match classifications used in the MECS fuel data DataFrame
    if sector == 'Iron_and_Steel':
        sector = 'Iron & Steel'

    mecs_sector_row = (
        mecs_fuel_data
        .drop(columns=['EIA Sector:', 'NAICS Code', 'Total', 'Net Electricity', 'Other', 'Fossil Fuels Total'])
        .replace('*', 0)                               # turn '*' into 0
        .apply(pd.to_numeric, errors='coerce')         # force all remaining values numeric
        .groupby(mecs_fuel_data['Sector Category'])    # group by sector
        .sum(numeric_only=True)                        # sum only numeric cols
        .loc[sector]                                  # first row
    )    
    sector_fuel_consumption = mecs_sector_row[1:]

    # Create a dictionary mapping each MECS fuel type to its corresponding AEO25 fuel category
    emissions_factors_df = pd.read_excel(fuel_emissions_factor_path)
    emissions_factors_df = emissions_factors_df[~emissions_factors_df['EIA MECS Category'].isna()].groupby('EIA MECS Category').first().reset_index()

    mecs_to_aeo_fuel_category_map = (
        emissions_factors_df[['EIA MECS Category', 'EIA AEO Category']]
        .set_index('EIA MECS Category')['EIA AEO Category']
        .to_dict()
    )

    # Get the fuel use projections by AEO25 category
    fuel_use_projections_df = pd.read_csv(fuel_use_projection_path, header=4)
    fuel_use_by_category_filtered = fuel_use_projections_df[fuel_use_projections_df['Year'].isin([2022, year])].reset_index(drop=True)

    # Create a dictionary mapping each fuel category to the relative growth it experiences from 2022 to the model year
    fuel_growth_by_category_dict = {
        col: (fuel_use_by_category_filtered[col].iloc[1] - fuel_use_by_category_filtered[col].iloc[0]) / fuel_use_by_category_filtered[col].iloc[0]
        for col in fuel_use_by_category_filtered.columns if col != 'Year'
    }

    # Get the scaling factor from 2022 to the input year for the sector
    base_year_fuel_use = 0
    projected_fuel_use = 0

    for mecs_fuel_type in sector_fuel_consumption.index:
        fuel_use_mmbtu = sector_fuel_consumption[mecs_fuel_type] * 1e6

        if fuel_use_mmbtu != 0:
            base_year_fuel_use += fuel_use_mmbtu

            aeo_fuel_type = mecs_to_aeo_fuel_category_map[mecs_fuel_type]
            projected_fuel_use += fuel_use_mmbtu * (1 + fuel_growth_by_category_dict[aeo_fuel_type])

    growth_factor = projected_fuel_use / base_year_fuel_use

    return growth_factor * fuel_use

# Wrap the function so it can be cached
@lru_cache(maxsize=None)
def cached_project_sector_consumption(sector, fuel_demand, year):
    return project_sector_consumption(sector, fuel_demand, year)


def model_one_year(existing_h2_pct_decarb, high_temp_decarb_by_sector, year):
    """
    Models industrial hydrogen demand for a single model year.

    Parameters:
    - existing_h2_pct_decarb: the percentage of existing hydrogen demand to model
    - high_temp_decarb_by_sector: A list containing the percent decarbonization of projected 
        fuel use high-temp combustion via hydrogen for each industrial sector.
    - year: The model year for which industrial hydrogen demand is being modeled.

    Returns:
    - A DataFrame containing total hydrogen demand (kg) by load zone for the specified year.
    """
    #========================
    # Step 1: Calculate fuel consumption using EPA GHGRP stationary combustion emissions and emissions factors
    #========================

    # Load industrial fuel use projections from 2022 to 2050 (assuming 2022-2023 has the same relative change as 2023-2024)
    fuel_use_by_category_df = pd.read_csv(fuel_use_projection_path, header=4)

    # Filter for the base year (2022) and the model year
    fuel_use_by_category_filtered = fuel_use_by_category_df[fuel_use_by_category_df['Year'].isin([2022, year])].reset_index(drop=True)

    # Create a dictionary mapping each fuel category to the relative growth it experiences from 2022 to the model year
    fuel_growth_by_category_dict = {
        col: (fuel_use_by_category_filtered[col].iloc[1] - fuel_use_by_category_filtered[col].iloc[0]) / fuel_use_by_category_filtered[col].iloc[0]
        for col in fuel_use_by_category_filtered.columns if col != 'Year'
    }

    # Call the helper function to perform calculcations and retrieve results
    results_by_facility, breakdown_by_fuel = calc_epa_ghgrp_fuel_consumption(high_temp_decarb_by_sector, fuel_growth_by_category_dict)

    # Save output lists as DataFrames
    results_by_facility_df = pd.DataFrame(results_by_facility)
    breakdown_by_fuel_df = pd.DataFrame(breakdown_by_fuel)

    # Save the detailed results by facility unit and fuel type
    breakdown_by_fuel_df.to_csv(logs_path / f'{year}_unadjusted_demand_by_unit_fuel.csv', index=False)
    results_by_facility_df.to_csv(logs_path / f'{year}_unadjusted_demand_by_facility.csv', index = False)

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
    # Step 2: For GHGRP facilities with missing stationary combustion data, fill in fuel demand using sector-wide averages.
    #========================

    # Get average fuel consumption totals by facility for each sector
    average_facility_proj_demand_by_sector = results_by_facility_df.groupby('Sector')['proj_fuel_demand_mmBtu'].mean()
    average_facility_demand_by_sector = results_by_facility_df.groupby('Sector')['fuel_demand_mmBtu'].mean()

    # Iterate through the files containing the facilities with missing data for each sector
    for file_path in missing_combustion_data_folder.glob('*csv'):
        missing_facilities_df = pd.read_csv(file_path)

        if missing_facilities_df.empty:
            continue

        sector = file_path.stem.replace('_facilities', '')

        # Fill in fuel demand with sector-wide averages
        missing_facilities_df['proj_fuel_demand_mmBtu'] = average_facility_proj_demand_by_sector[sector]
        missing_facilities_df['fuel_demand_mmBtu'] = average_facility_demand_by_sector[sector]

        # Format to match columns in the results_by_facility_df
        missing_facilities_df = missing_facilities_df[['Facility Id', 'Facility Name', 'Primary NAICS Code', 'Latitude', \
                    'Longitude', 'fuel_demand_mmBtu', 'proj_fuel_demand_mmBtu', 'inWestCensus', 'inWECC']].rename({'Primary NAICS Code': 'NAICS Code'})
        
        # Add results to the running list
        results_by_facility_df = pd.concat([results_by_facility_df, missing_facilities_df])

    #========================
    # Step 3: Handle discrepancies in fuel consumption between our data and fuel use totals from the EIA MECS
    #========================
    
    # Calculate the discrepancy in fuel use for each sector in the West Census Region (similar to the WECC)
    discrepancies_by_sector = calc_discrepancies(breakdown_by_fuel_df)

    # Iterate by sector to handle the discrepancies
    for sector in sector_by_naics.keys():
        sector_row = discrepancies_by_sector[discrepancies_by_sector['Sector'] == sector].iloc[0]
        discrepancy_mmbtu = sector_row['discrepancy_mmbtu']

        # If we overestimate fuel consumption, we adjust by scaling down our estimates uniformly across all facilities in that sector
        if discrepancy_mmbtu < 0:
            # Get the scaling factor
            mecs_to_ghgrp_ratio = sector_row['mecs_to_ghgrp_ratio']

            # Scale down fuel demand (and projected fuel demand) accordingly
            results_by_facility_df.loc[results_by_facility_df['Sector'] == sector, 'fuel_demand_mmBtu'] *= mecs_to_ghgrp_ratio
            results_by_facility_df.loc[results_by_facility_df['Sector'] == sector, 'proj_fuel_demand_mmBtu'] *= mecs_to_ghgrp_ratio

        # If our estimates are low, we adjust by disaggregating "unaccounted-for demand" across non-GHGRP facilities in the West Census
        elif discrepancy_mmbtu > 0:
            # Load the non-GHGRP facilities in each sector
            extra_facities_path = base_path / 'inputs' / 'extra_epa_frs_facilities_west' / f'{sector}_facilities.csv'
            extra_facilities_df = pd.read_csv(extra_facities_path)

            # Fill in the fuel demand
            extra_facilities_df['fuel_demand_mmBtu'] = discrepancy_mmbtu / len(extra_facilities_df)

            high_temp_decarb_pct = high_temp_decarb_by_sector[list(sector_by_naics.keys()).index(sector)]

            # Apply cached function to the DataFrame
            extra_facilities_df['proj_fuel_demand_mmBtu'] = extra_facilities_df['fuel_demand_mmBtu'].apply(
                lambda x: cached_project_sector_consumption(sector, x, year) * high_temp_decarb_pct / 100 * \
                    get_high_heat_emissions_share(sector)
            )
            extra_facilities_df['inWestCensus'] = True

            # Format to match columns in the results_by_facility_df
            extra_facilities_df = extra_facilities_df[['registry_id', 'primary_name', 'naics_code', 'latitude83', 
                  'longitude83', 'fuel_demand_mmBtu', 'proj_fuel_demand_mmBtu', 'inWestCensus', 'inWECC']].rename(
                      columns={'primary_name': 'Facility Name', 'naics_code': 'NAICS Code', 'latitude83': 'Latitude', 
                               'longitude83': 'Longitude'})

            # Add results to the running list
            results_by_facility_df = pd.concat([results_by_facility_df, extra_facilities_df])

    #========================
    # Step 4: Filter for facilities in the WECC and convert hydrogen demand to kg
    #========================

    # Convert H2 demand from mmBtu to kg
    results_by_facility_df['total_h2_demand_kg'] = results_by_facility_df['proj_fuel_demand_mmBtu'] * ONE_MILLION / BTU_IN_1LB_H2 * LB_TO_KG

    # Filter the facilities to only those within WECC bundaries and save this as the final result
    filtered_df = results_by_facility_df[results_by_facility_df['inWECC'] == True].copy()
    filtered_df['Sector'] = filtered_df['NAICS Code'].map(get_sector)
    
    #========================
    # Step 5: Include demand from existing hydrogen facilities
    #========================
    existing_h2_plants_df = pd.read_csv(existing_h2_plants_path)

    existing_h2_plants_df['inWECC'] = True
    existing_h2_plants_df['total_h2_demand_kg'] = existing_h2_plants_df['hydrogen_demand_kg'] * existing_h2_pct_decarb / 100
    existing_h2_plants_df['Sector'] = 'Existing Hydrogen Plants'

    existing_h2_plants_df = existing_h2_plants_df.rename(columns={'Primary NAICS Code': 'NAICS Code'})
    existing_h2_plants_df = existing_h2_plants_df[['Facility Id', 'Facility Name', 'NAICS Code', 'Sector', 'Latitude', \
                    'Longitude', 'hydrogen_demand_kg', 'total_h2_demand_kg', 'inWECC']]

    filtered_df = pd.concat([filtered_df, existing_h2_plants_df])

    #========================
    # Step 6: Plot results, and create demand profiles
    #========================
    aggregated_by_lz = aggregate_and_plot.aggregate_by_lz(results_by_facility_df)

    # Plot the filtered facilities and their corresponding hydrogen demand
    aggregate_and_plot.plot(filtered_df, year)

    # Create the raster output for the 5x5km resolution of industry demand
    aggregate_and_plot.create_demand_grid(filtered_df, year)

    filtered_df.to_csv(logs_path / f'{year}_final_demand_by_facility.csv', index = False)
    aggregated_by_lz['year'] = year

    return aggregated_by_lz


def calc_epa_ghgrp_fuel_consumption(high_temp_pct_decarb_by_sector: list, fuel_growth_by_category_dict: dict):
    """
    Estimates fuel consumption for industrial facilities in the West Census Region and the WECC
    based on CO2 emissions, fuel type, and decarbonization projections. Generates both facility-level 
    totals and detailed unit-level breakdowns by facility units and fuel types.

    Parameters:
    high_temp_pct_decarb_by_sector (list of float):
        The percent decarbonization of projected high-temp combustion fuel-use applied to each sector. 
        The order should correspond to the keys in 'sector_by_naics'
    fuel_growth_by_category_dict (dict):
        A mapping of EIA fuel categories to projected growth factors between the baseline year 
        (2022) and the model year.

    Returns:
    all_results_by_facility (DataFrame):
        Contains facility-level fuel consumption and projected fuel demand. Columns include:
            - Facility Id
            - Facility Name
            - NAICS Code
            - Sector
            - Latitude, Longitude
            - fuel_demand_mmBtu
            - proj_fuel_demand_mmBtu
            - inWestCensus
            - inWECC

    breakdown_by_fuel : list of dict
        A detailed list of fuel consumption by individual units within each facility. Columns include:
            - Facility Id, Facility Name, Unit Name
            - Fuel
            - NAICS Code
            - Latitude, Longitude
            - CO2_Emissions
            - fuel_demand_mmBtu
            - proj_fuel_demand_mmBtu
            - inWestCensus

    Notes
    -----
    - Units with missing fuel types are assumed to use Natural Gas by default.
    - Biofuels are excluded from projected fuel demand calculations.
    """

    # Create a dictionary mapping the fuel type to the CO2 emissions factor
    fuel_emissions_df = pd.read_excel(fuel_emissions_factor_path)
    fuel_emissions_dict = fuel_emissions_df.set_index('Fuel Type')['kg CO2 per mmBtu'].to_dict()

    # Create a dictionary mapping each fuel type to a broader fuel category for which we have fuel consumption projections
    aeo_fuel_category_dict = fuel_emissions_df.set_index('Fuel Type')['EIA AEO Category'].to_dict() 

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
            facility_fuel_demand_mmBtu = 0

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

                high_temp_decarb_pct = high_temp_pct_decarb_by_sector[list(sector_by_naics.keys()).index(sector_name)]

                high_temp_decarb_factor = high_temp_decarb_pct / 100

                unit_demand_mmBtu = unit_CO2_emissions * 1000 / avg_emissions_factor  # multiplying by 1000 to convert from mt to kg

                if consumes_biofuels:
                    unit_demand_mmBtu *= len(unit_fuels) / (len(unit_fuels) + 1)
                    unit_demand_mmBtu *= len(unit_fuels) / (len(unit_fuels) + 1)

                CO2_emissions_by_unit_fuel = unit_CO2_emissions / len(unit_fuels)
                fuel_demand_by_unit_fuel = unit_demand_mmBtu / len(unit_fuels)
                
                # Add detailed results to the breakdown in the logs and adjust for the model year
                for fuel in unit_fuels:
                    # Project fuel use for fuels that are in the EIA AEO 25 projections
                    aeo_fuel_category = aeo_fuel_category_dict[fuel]

                    if aeo_fuel_category == np.nan: 
                        print(f'projected 0% growth for {fuel}')
                        projected_fuel_growth = 0
                    else:
                        projected_fuel_growth =  fuel_growth_by_category_dict[aeo_fuel_category]

                    projected_fuel_demand_mmbtu = (1 + projected_fuel_growth) * fuel_demand_by_unit_fuel * high_temp_decarb_factor \
                        * get_high_heat_emissions_share(sector_name)

                    breakdown_by_fuel.append({'Facility Id': facility_id, 'Facility Name': facility_name, 'Unit Name': unit_name, 'Fuel': fuel, \
                                'NAICS Code': naics, 'Latitude': latitude, 'Longitude': longitude, 'CO2_Emissions': CO2_emissions_by_unit_fuel, \
                                'fuel_demand_mmBtu': fuel_demand_by_unit_fuel, 'proj_fuel_demand_mmBtu': projected_fuel_demand_mmbtu, \
                                'inWestCensus': fuel_df['inWestCensus']})
                    
                    # Add the unit's fuel demand to the facility's running total for fuel demand, scaled by scale_demand
                    proj_facility_fuel_demand_mmBtu += projected_fuel_demand_mmbtu
                    facility_fuel_demand_mmBtu += fuel_demand_by_unit_fuel
            
            # Add the facility results to the final output result DataFrame
            results_by_sector.append({'Facility Id': facility_id, 'Facility Name': facility_name, 'NAICS Code': naics, 'Sector': get_sector(naics), \
                                    'Latitude': latitude, 'Longitude': longitude, 'fuel_demand_mmBtu': facility_fuel_demand_mmBtu, 'proj_fuel_demand_mmBtu': \
                                        proj_facility_fuel_demand_mmBtu, 'inWestCensus': inWestCensus,'inWECC': inWECC})
        
        # Save the results for hydrogen demand by facility for each industry
        industry_results_df = pd.DataFrame(results_by_sector)

        all_results_by_facility = pd.concat([all_results_by_facility, industry_results_df])

    return all_results_by_facility, breakdown_by_fuel

#====================
# Main Function:
#====================
def model_industry_demand(existing_h2_pct_decarb, high_temp_pct_decarbonization, years):
    """
    Estimates hydrogen demand from each industrial sector over several model years, aggregated by load zone.

    Parameters:
    - existing_h2_pct_decarb: List of floats representing the percent of existing h2 demand to decarbonize in each year
    - pct_decarbonization: List of list of percentages of each sector's fuel consumed via high-temperature combustion  
        to decarbonize with hydrogen. (each outer list contains paramters for one model year)
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

        pct_decarbonize_by_sector = high_temp_pct_decarbonization[index]
        pct_decarbonize_existing_h2 = existing_h2_pct_decarb[index]

        year_result = model_one_year(pct_decarbonize_existing_h2, pct_decarbonize_by_sector, year)
        load_zone_summary = pd.concat([load_zone_summary, year_result])

        index += 1

    load_zone_summary = load_zone_summary.sort_values(by=['load_zone', 'year']).reset_index(drop=True)
    load_zone_summary.to_csv(load_zone_output_path, index=False)

    return load_zone_summary

