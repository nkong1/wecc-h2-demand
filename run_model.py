"""
Use this file to run the model and adjust inputs. 
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
years = [2030, 2040]
# ============================================


def model_transport_sector():
    """
    Contains user input parameters for transport and runs the transport-side model. Adjust the penetration of LD and 
    HD vehicles among projected gasoline and diesel vehicle stock, respectively.
    """

    # ============================================
    # Choose the LD and HD FCEV penetration among projected gasoline and diesel vehicle stock (as a percentage from 0 to 100)
    # The percentage of FCEV penetration is assumed to be the same as percentage of fuel use decarbonization
    LD_FCEV_penetration = [0, 0,]
    HD_FCEV_penetration = [10, 20]
    # ============================================

    # Call the transport module
    lz_summary_transport = transport_h2.model_transport_demand(LD_FCEV_penetration, HD_FCEV_penetration, years)
    
    # Temporally disaggregate into hourly profiles 
    build_transport_profile.build_profile(lz_summary_transport)


def model_industry_sector():
    """
    Contains user input parameters for industry and runs the industry-side model. 
    Adjust the decarbonization of projected high-temp combustion fuel use via hydrogen in each industry and model year.
    """
    sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Refineries', 'Glass']

    # ============================================
    # Adjust the percentage of high-temp combustion fuel use decarbonization in corresponding sector 
    # (between 0 and 100) for each model year. 

    high_temp_combustion_pct_decarb = [[10, 10, 10, 10, 10, 10], 
                                        [40, 40, 40, 40, 40, 40]]
    
    # ============================================
    # Call the industry module
    lz_summary_industry = industry_h2.model_industry_demand(high_temp_combustion_pct_decarb, years)

    # Temporally disaggregate into hourly profiles 
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

    print('\nFinished!')

if __name__ == "__main__":
    main()

