"""
Use this file to run the hydrogen demand model and adjust inputs. 

This model estimates hydrogen demand from the transport and industry end-use sectors with high spatial and temporal resolution. 
These sectors are further broken down by vehicle type (light-duty/heavy-duty) and industry. The percentage of fuel decarbonization 
across LD transport, HD transport, and industry can be modified. The industries that are modeled can be changed as well. 

Spatial resolution: by load zone in the WECC
Temporal resolution: hourly over the course of an average week (for transport) or every week (for industry)
"""

from pathlib import Path
import shutil
from industry import industry_h2, build_industry_profile
from transport import transport_h2, build_transport_profile
from combine_results import combine

# Choose the model year
year = 2050

# Choose what sectors to model
model_transport_h2 = True
build_transport_demand_profiles = True

model_industry_h2 = False
build_industry_demand_profiles = False  

def model_transport_sector():

    # Choose the percentage of FCEV mark penetration (as a percentage from 0 to 100)
    # The percent of FCEV penetration is assumed to be the same as percent of fuel decarbonization
    LD_FCEV_penetration = 50
    HD_FCEV_penetration = 0

    # Call the transport module
    lz_summary_transport = transport_h2.calc_state_demand(LD_FCEV_penetration, HD_FCEV_penetration, year)
    
    # Temporally disaggregate into hourly profiles over the course of an average week
    if build_transport_demand_profiles:
        build_transport_profile.build(lz_summary_transport)

def model_industry_sector():
    sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Glass', 'Fertilizer']

    # Adjust the percentage of fuel decarbonization via hydrogen across each sector (between 0 and 100)
    # A value of 0 means that the corresponding sector is not represented in the outputs.
    pct_decarbonization = [70, 50, 50, 50, 50, 0]

    # Call the industry module
    lz_summary_industry = industry_h2.calc_industry_demand(sectors, pct_decarbonization)

    # Temporally disaggregate into hourly profiles over the course of an average week
    if build_industry_demand_profiles:
            build_industry_profile.build(lz_summary_industry)

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
        # Create a industry folder in the outputs
        (output_path / 'industry').mkdir()

        # Call the industry h2 function
        model_industry_sector()

    # Aggregate results from industry and transport
    #if model_industry_h2 and model_industry_h2:
        #combine()

if __name__ == "__main__":
    main()
