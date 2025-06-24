from pathlib import Path
import shutil
from industry import industry_h2
from transport import transport_h2, build_profile

"""
Choose what to model industry or transport or both
Inputs:
LD/HD vehicle penetration, 
"""

model_transport_h2 = True
build_transport_demand_profiles = False

model_industry_h2 = True

# to be implemented soon:
# build_industry_demand_profiles = False  


def model_transport_sector():

    # Adjust these according to the scenario (percentages from 0 to 100)
    LD_FCEV_penetration = 0
    HD_FCEV_penetration = 25

    # Adjust this for any vehicle efficiency assumptions (default = 115/26)
    FCEV_TO_ICEV_EFFICIENCY = 115/26 

    # Call the transport module
    lz_summary = transport_h2.calc_state_demand(LD_FCEV_penetration, HD_FCEV_penetration, FCEV_TO_ICEV_EFFICIENCY)

    # Temporally disaggregate into hourly profiles over the course of an average week
    if build_transport_demand_profiles:
        build_profile.build(lz_summary)

def model_industry_sector():

    # Adjust which sectors to include (among Iron & Steel, Aluminum, Cement, Chemicals, Glass, Fertilizer)
    sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Glass', 'Fertilizer']

    # Adjust the percentage of fuel decarbonization (via hydrogen) across all sectors 
    pct_decarbonize = 100

    # Call the industry module
    industry_h2.calc_industry_demand(sectors, pct_decarbonize)

def main():
    # Create a new outputs folder
    output_path = Path(__file__).parent / 'outputs'

    if output_path.exists() and output_path.is_dir():
        shutil.rmtree(output_path)

    output_path.mkdir()

    # Call the transport and industry hydrogen modules
    if model_transport_h2:

        # Create a transport folder in the outputs
        (output_path / 'transport').mkdir()

        model_transport_sector()        

    if model_industry_h2:
        # Create a industry folder in the outputs
        (output_path / 'industry').mkdir()

        model_industry_sector()


    

if __name__ == "__main__":
    main()
