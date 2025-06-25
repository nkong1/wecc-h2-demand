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

# Adjust these to choose what to model
model_transport_h2 = True
build_transport_demand_profiles = True

model_industry_h2 = True
build_industry_demand_profiles = True  

def model_transport_sector():

    # Adjust these according to the scenario (as percentage from 0 to 100)
    # The percent of FCEV penetration is assumed to be the same as percent of fuel decarbonization
    LD_FCEV_penetration = 2
    HD_FCEV_penetration = 20

    # ================================================================
    # Assumptions for projected values (all EIA values are from the AEO2023 Reference case):
    # ================================================================

    # Average relative efficiency of FCEVs to ICEVs on the road in 2050 
    LD_FCEV_TO_ICEV_efficiency = 101.5 / 35 # from E3-derived estimates, following methods from CEC H2 Roadmap Report
    HD_FCEV_TO_ICEV_efficiency = 10.6 / 7.7 # also from E3 derived estimates 

    # Change in fuel efficiency from 2023 to 2050
    rel_change_LD_efficiency = (26.5 - 22.6) / 22.6 # linear projection of data from Bureau of Transportation Statistics
    rel_change_HD_efficiency = (8.0 - 6.3) / 6.3 # from 2025 EIA Annual Energy Outlook 

    # Change in LD/HD VMT from 2023 to 2050
    rel_change_LD_VMT = (2524 - 2540) / 2540 # from 2025 EIA Annual Energy Outlook 
    rel_change_HD_VMT = (205.1 - 186.8) / 186.8 # from 2025 EIA Annual Energy Outlook 

    assumptions = [LD_FCEV_TO_ICEV_efficiency, HD_FCEV_TO_ICEV_efficiency, rel_change_LD_efficiency, rel_change_HD_efficiency, \
                   rel_change_LD_VMT, rel_change_HD_VMT]

    # ================================

    # Call the transport module
    lz_summary_transport = transport_h2.calc_state_demand(LD_FCEV_penetration, HD_FCEV_penetration, assumptions)
    
    # Temporally disaggregate into hourly profiles over the course of an average week
    if build_transport_demand_profiles:
        build_transport_profile.build(lz_summary_transport)

def model_industry_sector():

    sectors = ['Iron & Steel', 'Aluminum', 'Cement', 'Chemicals', 'Glass', 'Fertilizer']

    # Adjust the percentage of fuel decarbonization via hydrogen across each sector (between 0 and 100)
    # A value of 0 means that the corresponding sector is not represented in the outputs.
    pct_decarbonization = [50, 50, 50, 50, 50, 0]

    # Call the industry module
    lz_summary_industry = industry_h2.calc_industry_demand(sectors, pct_decarbonization)

    # Temporally disaggregate into hourly profiles over the course of an average week
    if build_industry_demand_profiles:
            build_industry_profile.build(lz_summary_industry)

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

        # Call the transport h2 function
        model_transport_sector()        

    if model_industry_h2:
        # Create a industry folder in the outputs
        (output_path / 'industry').mkdir()

        # Call the industry h2 function
        model_industry_sector()

    

if __name__ == "__main__":
    main()
