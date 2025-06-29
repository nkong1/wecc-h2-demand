"""
Use this file to run the WECC hydrogen demand model and adjust inputs. 

This model generates hydrogen demand profiles from the transport and industry end-use sectors at an hourly resolution over
the course of one or more model years. These profiles are generated for 47 load zones in the SWITCH-WECC model (excluding 2 
load zones in Canada and one in Mexico). The sectors are broken down by vehicle type (light-duty/heavy-duty) and industry.
The percentage of fuel decarbonization across LD transport, HD transport, and industry can be modified for each model year.
"""

from pathlib import Path
import shutil
from industry import industry_h2, build_industry_profile
from transport import transport_h2, build_transport_profile
from combine_results import combine

# ============================================
# Choose what sectors to model
model_transport_h2 = True
model_industry_h2 = True

# Choose model years between 2023 and 2050 (inclusive)
years = [2030, 2040, 2050]
# ============================================


def model_transport_sector():
    """
    Contains user input parameters for transport and runs the transport-side model. Adjust the penetration of LD and 
    HD vehicles among projected gasoline and diesel vehicle stock, respectively.
    """

    # ============================================
    # Choose the percentage of FCEV mark penetration (as a percentage from 0 to 100)
    # The percentage of FCEV penetration is assumed to be the same as percentage of fuel decarbonization
    LD_FCEV_penetration = [5, 10, 15]
    HD_FCEV_penetration = [10, 20, 30]
    # ============================================

    # Call the transport module
    lz_summary_transport = transport_h2.model_transport_demand(LD_FCEV_penetration, HD_FCEV_penetration, years)
    
    # Temporally disaggregate into hourly profiles over the course of an average week
    build_transport_profile.build_profile(lz_summary_transport)


def model_industry_sector():
    """
    Contains user input parameters for industry and runs the industry-side model. The model is currently capable of
    modeling demand from 6 hard-to-decarbonize industries: Iron & Steel, Aluminum, Cement, Chemicals, Glass, and 
    Fertilizer. Adjust the percentage of fuel decarbonization via hydrogen in each industry and, if desired, 
    scale the demand.
    """

    sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Glass', 'Fertilizer']

    # ============================================
    # Adjust the percentage of fuel decarbonization across each sector (between 0 and 100) for each model year
    # A value of 0 means that the corresponding sector will not be modeled
    pct_decarbonization = [[10] * 6, 
                           [30] * 6, 
                           [50] * 6]
    
    # Scale the hydrogen demand across all facilities by a factor
    scale_demand = 1
    # ============================================

    # Call the industry module
    lz_summary_industry = industry_h2.model_industry_demand(sectors, pct_decarbonization, years, scale_demand)

    # Temporally disaggregate into hourly profiles over the course of an average week
    build_industry_profile.build_profile(lz_summary_industry)


def main():
    # Create a new outputs folder
    output_path = Path(__file__).parent / 'outputs'
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir()

    # Call the transport and industry hydrogen modules
    if model_transport_h2:
        # Create a transport folder in the outputs
        (output_path / 'transport').mkdir()

        # Call the transport h2 function
        model_transport_sector()        

    if model_industry_h2:
        # Create an industry folder in the outputs
        (output_path / 'industry').mkdir()

        # Call the industry h2 function
        model_industry_sector()

    # Aggregate results from industry and transport
    if model_industry_h2 and model_transport_h2:
        combine()

if __name__ == "__main__":
    main()
