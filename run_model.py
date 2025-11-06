"""
Use this file to run the model and adjust inputs.
"""

from pathlib import Path
import shutil
from industry import industry_h2, build_industry_profile
from onroad_transport import transport_h2, build_transport_profile
from aviation import model_aviation
from combine_results import combine
from baseline import existing_demand

# ============================================
# ADJUST INPUTS HERE
# ============================================

# Choose what sectors to model
model_transport_h2 = True
model_industry_h2 = True
model_aviation_h2 = True

# Choose model years between 2026 and 2050 (inclusive)
years = [2050]

# Choose the LD and HD FCEV penetration among projected gasoline and diesel vehicle stock
LD_FCEV_penetration_pcts = [30]
HD_FCEV_penetration_pcts = [45]

# Pct of high-temp combustion fuel use decarbonization for each sector in each model year.
high_temp_combustion_pcts_decarb = [[100]*6]

# Order of industries, for reference only (do not change)
sectors = ["Iron & Steel", "Aluminum", "Cement", "Chemicals", "Refineries", "Glass"]

# Percentage of aviation fuel to decarbonize in each model year
aviation_decarb_pcts = [60] 

# Choose whether to assume no e-kerosene (fuel cell only scenario)
fuel_cell_only = True

# ============================================

def model_baseline():
    """
    Models baseline hydrogen demand using 2022 hydrogen production estimates derived from the GHGRP.
    """
    existing_demand.model_existing_demand(years, LD_FCEV_penetration_pcts, HD_FCEV_penetration_pcts,
            aviation_decarb_pcts) 


def model_onroad_transport_sector():
    """
    Contains user input parameters for transport and runs the transport-side model.
    """

    # Call the transport module
    lz_summary_transport = transport_h2.model_transport_demand(
        LD_FCEV_penetration_pcts, HD_FCEV_penetration_pcts, years
    )

    # Temporally disaggregate into hourly profiles
    build_transport_profile.build_profile(lz_summary_transport)


def model_industry_sector():
    """
    Contains user input parameters for industry and runs the industry-side model.
    """

    # Call the industry module
    lz_summary_industry = industry_h2.model_industry_demand(
        high_temp_combustion_pcts_decarb, years
    )

    # Temporally disaggregate the new industrial demand into hourly profiles
    profiles_output_path = (
        Path(__file__).parent / "outputs" / "industry" / "demand_profiles"
    )
    build_industry_profile.build_profile(
        lz_summary_industry, profiles_output_path, flat=False
    )


def model_aviation_sector():

    model_aviation.model_aviation_demand(years, aviation_decarb_pcts, fuel_cell_only)


def main():

    # Create a new outputs folder
    output_path = Path(__file__).parent / "outputs"
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir()

    # Model baseline demand
    (output_path / "baseline" / "demand_profiles").mkdir(parents=True)
    model_baseline()

    # Model new on-road transport demand
    if model_transport_h2:
        # Create a transport folder in the outputs
        (output_path / "transport").mkdir()

        # Call the transport h2 function
        model_onroad_transport_sector()

    # Model new industry demand
    if model_industry_h2:
        # Create an industry folder and profile subfolder in the outputs
        (output_path / "industry" / "demand_profiles").mkdir(parents=True)

        # Call the industry h2 function
        model_industry_sector()

    # Model new aviation demand
    if model_aviation_h2:
        # Create an industry folder and profile subfolder in the outputs
        (output_path / "aviation" / "demand_profiles").mkdir(parents=True)

        # Call the industry h2 function
        model_aviation_sector()

    # Aggregate results across all three categories
    combine(years, model_transport_h2, model_industry_h2, model_aviation_h2)

    print("\nFinished!")


if __name__ == "__main__":
    main()
