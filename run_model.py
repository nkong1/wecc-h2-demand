"""
Use this file to run the WECC hydrogen demand model and adjust inputs. 

This model generates hydrogen demand profiles from the on-road transport and industry end-use sectors at an hourly resolution 
over one or more model years. These profiles are generated for 47 load zones in the SWITCH-WECC model (excluding 2 load zones 
in Canada and one in Mexico). 

The sectors are broken down by vehicle type (light-duty/heavy-duty) and by industry. The percentage of fuel decarbonization 
across LD on-road transport, HD on-road transport, and industry can be modified for each model year. For industry, this 
percentage is specifically the percent decarbonization of high-temperature combustion fuel consumption (the type of fuel use 
that is most promising for hydrogen). Existing hydrogen demand can also be modeled. LD on-road transport is defined as gasoline 
vehicles, and HD on-road transport is defined as diesel-powered vehicles.
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
    # Choose the LD and HD FCEV penetration among projected gasoline and diesel vehicle stock (as a percentage from 0 to 100)
    # The percentage of FCEV penetration is assumed to be the same as percentage of fuel use decarbonization
    LD_FCEV_penetration = [0, 0, 0]
    HD_FCEV_penetration = [5, 10, 20]
    # ============================================

    # Call the transport module
    lz_summary_transport = transport_h2.model_transport_demand(LD_FCEV_penetration, HD_FCEV_penetration, years)
    
    # Temporally disaggregate into hourly profiles over the course of an average week
    build_transport_profile.build_profile(lz_summary_transport)


def model_industry_sector():
    """
    Contains user input parameters for industry and runs the industry-side model. The model is capable of
    modeling demand from 6 hard-to-decarbonize industries: Iron & Steel, Aluminum, Cement, Chemicals, Refineries, and
    Glass, in addition to existing demand from hydrogen production plants. Adjust the percent decarbonization of 
    projected high-temp combustion fuel use via hydrogen in each industry in each model year. For the existing demand, 
    adjust the percentage of existing hydrogen production to include in the model outputs (helpful for modeling 
    zero-emissions hydrogen scenarios).
    """

    new_demand_sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Refineries', 'Glass']

    # ============================================
    # Adjust the percentage of high-temp combustion fuel use decarbonization across each new demand sector 
    # (between 0 and 100) for each model year. 

    high_temp_combustion_pct_decarb = [[5, 5, 5, 5, 5, 5], 
                                        [10, 10, 10, 10, 10, 10],
                                        [20, 20, 20, 20, 20, 20]]
    
    existing_h2_pct_decarb = [5, 10, 20]
    # ============================================

    # Call the industry module
    lz_summary_industry = industry_h2.model_industry_demand(existing_h2_pct_decarb, high_temp_combustion_pct_decarb, years)

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
