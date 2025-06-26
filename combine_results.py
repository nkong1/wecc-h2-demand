"""
This module is only called when both the industry and transport parts of the model are run.

For each load zone, this module combines the results for hydrogen demand from industry and from 
transport into a csv file showing combined hourly demand over a week. This resulting profile is 
graphed for the load zone with the highest total demand over the week.

This module also combines the annual hydrogen demand values by load zone, outputs this data in csv, 
and displays it on a map (of the entire WECC). 
"""

from transport.plot_demand import plot_lz_demand
import pandas as pd
import os
import shutil
from pathlib import Path

outputs_path = Path(__file__).parent / 'outputs' 
combined_outputs_path = outputs_path / 'combined'

if combined_outputs_path.exists():
    shutil.rmtree(combined_outputs_path)
combined_outputs_path.mkdir()

def combine():
    industry_profiles_path = outputs_path / 'industry' / 'demand_profiles'
    transport_profiles_path = outputs_path / 'transport' / 'demand_profile'

    industry_profiles = sorted(os.listdir(industry_profiles_path))
    transport_profiles = sorted(os.listdir(transport_profiles_path))

    transport_idx = 0
    industry_idx = 0

'''    while transport_idx < len(transport_profiles):
        transport
        if '.csv' in transport_lz_profile and '~' not in transport_lz_profile:
            lz_profile_path = transport_profiles_path / transport_lz_profile
'''


