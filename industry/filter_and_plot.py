"""
This file contains two functions: filter and plot. Filter intersects the DataFrame containing hydrogen demand by facility
with the WECC shp file to filter our facilities that do not fall within WECC boundaries. The plot function, which is called by
default, plots the hydrogen demand by facility on the load zone map.
"""

import geopandas as gp
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import pandas as pd
from pathlib import Path
from industry.sector_naics_info import * 

base_path  = Path(__file__).parent

# Import load zones file
load_zones = gp.read_file(base_path / 'inputs' / 'load_zones' / 'load_zones.shp')

def filter(facility_df):
    """
    Filter out any facilities that are not located within WECC boundaries. 

    Parameters:
    - facility_df: a DataFrame containing latitute and longitude values for each facility, among 
        other data, including total hydrogen demand

    Returns:
    - A tuple containing:
    1) A DataFrame with facility-level data for facilities located in the WECC
    2) A DataFrame displaying the total hydrogen demand across all facilities in each WECC load zone
    """

    # Create a df mapping each sector name to a naics code
    rows = [(sector, code) for sector, codes in sector_by_naics.items() for code in codes]
    sectors_df = pd.DataFrame(rows, columns=['sector', 'naics'])

    # Add the sector name as a column to the results df
    results_by_facility_df = facility_df.merge(sectors_df, on='naics', how='left')

    # Filter out any facilities with zero H2 demand 
    results_by_facility_df = results_by_facility_df[results_by_facility_df['total_h2_demand'] > 0].copy()

    # Convert to GeoDataFrame
    geometry = gp.points_from_xy(results_by_facility_df['longitude'], results_by_facility_df['latitude'])
    facilities_gdf = gp.GeoDataFrame(results_by_facility_df, geometry=geometry, crs='EPSG:4326')

    # Ensure CRS consistency
    if load_zones.crs is None:
        load_zones.set_crs("EPSG:4326", inplace=True)
    facilities_gdf = facilities_gdf.to_crs(load_zones.crs)

    # Spatial join: to filter out facilities not in the WECC
    facilities_in_zones = gp.sjoin(
        facilities_gdf, 
        load_zones[['LOAD_AREA', 'geometry']],  
        how='inner',
        predicate='within'
    ).copy()

    # Keep only desired columns
    facilities_in_zones = facilities_in_zones[results_by_facility_df.columns.tolist() + ['LOAD_AREA', 'geometry']]

    # Create summary grouped by LOAD_AREA
    load_zone_summary = facilities_in_zones.groupby('LOAD_AREA', as_index=False)[
        ['total_h2_demand']
    ].sum()

    load_zone_summary.rename(columns={'LOAD_AREA': 'load_zone'}, inplace=True)

    return facilities_in_zones, load_zone_summary


def plot(filtered_df, year):
    """
    Plots the hydrogen demand from each facility onto a map of the WECC and saves the plot
    to the industry outputs folder.
    
    Parameters:
    - filtered_df: A DataFrame with facility-level data for facilities located in the WECC
    - year: the model year (for purposes of labeling)

    Returns: None
    """
    #  Plotting setup 
    sectors = filtered_df['sector'].unique()

    colors = plt.cm.Set1(np.linspace(0, 1, len(sectors)))
    color_map = {sector: colors[i] for i, sector in enumerate(sectors)}
    filtered_df['color'] = filtered_df['sector'].map(color_map)

    # Normalize marker sizes
    max_h2_demand = filtered_df['total_h2_demand'].max()
    max_size = 900  # Adjust as needed
    filtered_df['marker_size'] = (
        (filtered_df['total_h2_demand'] / max_h2_demand * max_size).clip(lower=1)
        if max_h2_demand > 0 else 10
    )

    # Create the plot
    fig, ax = plt.subplots(figsize=(15, 12))

    # Plot load zones
    try:
        load_zones.plot(ax=ax, color='lightgray', edgecolor='black', alpha=0.5)
    except Exception as e:
        print(f"Warning: Could not plot load zones: {e}")

    # Axis limits with padding
    lat_min, lat_max = filtered_df['latitude'].min(), filtered_df['latitude'].max()
    lon_min, lon_max = filtered_df['longitude'].min(), filtered_df['longitude'].max()
    lat_padding = (lat_max - lat_min) * 0.1
    lon_padding = (lon_max - lon_min) * 0.1
    ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
    ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)

    # Plot each sector 
    legend_handles = []
    for sector in sectors:
        subset = filtered_df[filtered_df['sector'] == sector]
        if not subset.empty:
            ax.scatter(
                subset['longitude'], 
                subset['latitude'],
                s=subset['marker_size'],
                c=[color_map[sector]],
                label=sector,
                alpha=0.75,
                edgecolors='black',
                linewidth=0.3
            )
            legend_handles.append(mpatches.Patch(color=color_map[sector], label=sector))

    # Sector legend
    if legend_handles:
        legend1 = ax.legend(handles=legend_handles, title="Sector", loc='upper left', 
                            fontsize='small', title_fontsize='medium', framealpha=0.9)
        ax.add_artist(legend1)

    # Size legend
    h2_legend_vals = [1e6, 1e7, 5e7]
    actual_max = (filtered_df['total_h2_demand']).max()
    size_handles = []

    for val in h2_legend_vals:
        if val <= actual_max:
            size = val / actual_max * max_size
            size_handles.append(
                ax.scatter([], [], s=size, c='gray', alpha=0.5, 
                        label=f"{int(val):,} kg H₂", edgecolors='black', linewidth=0.3)
            )


    if size_handles:
        legend2 = ax.legend(handles=size_handles, title="Hydrogen Demand", loc='lower left',
                            fontsize='small', title_fontsize='medium', framealpha=0.9)
            
    # Total hydrogen demand label
    total_h2_kg = filtered_df['total_h2_demand'].sum()
    total_h2_million_kg = total_h2_kg / 1e6

    ax.text(
        0.99, 0.01,
        f"Total H₂ Demand: {total_h2_million_kg:,.1f} million kg",
        transform=ax.transAxes,
        ha='right', va='bottom',
        fontsize=11, bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray')
    )

     # Total hydrogen demand label for each sector
    sector_totals = (
        filtered_df.groupby('sector')['total_h2_demand']
        .sum()
        .sort_values(ascending=False)
    )
    
    sector_label = "Sector H₂ Demand (million kg):\n"
    for sector, total_kg in sector_totals.items():
        sector_label += f"{sector}: {total_kg / 1e6:,.1f}\n"

    ax.text(
        1.01, 0.5,
        sector_label.strip(),
        transform=ax.transAxes,
        ha='left', va='center',
        fontsize=10, bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray')
    )

    # Final formatting 
    plt.title("Industry Hydrogen Demand by Sector and Facility", fontsize=16, pad=20)
    plt.xlabel("Longitude", fontsize=12)
    plt.ylabel("Latitude", fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_aspect('equal', adjustable='box')
    plt.tight_layout()

    output_path_map = base_path.parent / 'outputs' / 'industry' / f'{year}_demand_by_facility.png'
    plt.savefig(output_path_map, dpi=300, bbox_inches='tight')
