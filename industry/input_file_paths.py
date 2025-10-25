from pathlib import Path

# ======================
# File paths:
# ======================

base_path = Path(__file__).parent

# Fuel consumption by facility unit and fuel
units_and_fuel_folder = base_path / "inputs" / "sector_breakdown_by_unit_fuel"

# Emissions factors (kg CO2 / mmBtu) for each fuel
fuel_emissions_factor_path = base_path / "inputs" / "epa_fuel_ghg_emission_factors.xlsx"

# Fuel consumption totals by industrial sector across the West Census Region
mecs_data_path = base_path / "inputs" / "eia_mecs_fuel_consumption.csv"

# Facilities in the GHGRP that are missing stationary combustion emissions data:
missing_combustion_data_folder = base_path / "inputs" / "facilities_missing_combustion_data"

# Fuel use projections taken from the EIA Energy Outlook 2050 Reference Case Table 2:
fuel_use_projection_path = base_path / "inputs" / "eia_aeo_industrial_fuel_use_projections.csv"

# CO2 emissions breakdown by sector (from DOE Pathways to Commercial Liftoff: Industrial Decarbonization Fig 2a.2)
co2_emissions_breakdown_path = base_path / "inputs" / "doe_co2_emissions_breakdown_by_industry.csv"