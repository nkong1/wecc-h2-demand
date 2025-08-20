"""
This file contains three functions: aggregate_by_lz, plot, and create_demand_grid. aggregate_by_lz 
aggregates the hydrogen demand from all industrial facilities within a load zone and returns the 
aggregated results. The plot function plots the hydrogen demand by facility onto a map of the WECC.
The create_dmeand_grid function saves a .gpkg file with the total industrial hydrogen demand in the WECC, 
broken down into 5x5km squares for a high spatial resolution output.
"""

import geopandas as gp
import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
import pandas as pd
from pathlib import Path

base_path  = Path(__file__).parent

# Import load zones file
load_zones = gp.read_file(base_path / 'inputs' / 'load_zones' / 'load_zones.shp')

def aggregate_by_lz(facility_df):
    """
    Calculates the total hydrogen demand from industry by load zone.

    Parameters:
    - facility_df: a DataFrame containing latitute and longitude values for each facility, among 
        other data, including total hydrogen demand

    Returns:
    A DataFrame displaying the total hydrogen demand across all facilities in each WECC load zone
    """
    
    # Filter out any facilities with zero H2 demand 
    results_by_facility_df = facility_df[facility_df['total_h2_demand_kg'] > 0].copy()

    # Convert to GeoDataFrame
    geometry = gp.points_from_xy(results_by_facility_df['Longitude'], results_by_facility_df['Latitude'])
    facilities_gdf = gp.GeoDataFrame(results_by_facility_df, geometry=geometry, crs='EPSG:4326')

    # Ensure CRS consistency
    if load_zones.crs is None:
        load_zones.set_crs("EPSG:4326", inplace=True)
    facilities_gdf = facilities_gdf.to_crs(load_zones.crs)

    # Spatial join to get load areas
    facilities_gdf = gp.sjoin(
        facilities_gdf, 
        load_zones[['LOAD_AREA', 'geometry']],  
        how='inner',
        predicate='within'
    ).copy()

    # Keep only desired columns
    facilities_gdf = facilities_gdf[results_by_facility_df.columns.tolist() + ['LOAD_AREA', 'geometry']]

    # Create summary grouped by LOAD_AREA
    load_zone_summary = facilities_gdf.groupby('LOAD_AREA', as_index=False)[
        ['total_h2_demand_kg']
    ].sum()

    load_zone_summary.rename(columns={'LOAD_AREA': 'load_zone'}, inplace=True)

    return load_zone_summary


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
    filtered_df['Sector'] = filtered_df['Sector'].replace('Iron_and_Steel', 'Iron & Steel')
    sectors = filtered_df['Sector'].unique()

    colors = plt.cm.Set1(np.linspace(0, 1, len(sectors)))
    color_map = {sector: colors[i] for i, sector in enumerate(sectors)}
    filtered_df['color'] = filtered_df['Sector'].map(color_map)

    # Normalize marker sizes
    max_h2_demand = filtered_df['total_h2_demand_kg'].max()
    max_size = 900  # Adjust as needed
    filtered_df['marker_size'] = (
        (filtered_df['total_h2_demand_kg'] / max_h2_demand * max_size).clip(lower=1)
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
    lat_min, lat_max = filtered_df['Latitude'].min(), filtered_df['Latitude'].max()
    lon_min, lon_max = filtered_df['Longitude'].min(), filtered_df['Longitude'].max()
    lat_padding = (lat_max - lat_min) * 0.1
    lon_padding = (lon_max - lon_min) * 0.1
    ax.set_xlim(lon_min - lon_padding, lon_max + lon_padding)
    ax.set_ylim(lat_min - lat_padding, lat_max + lat_padding)

    # Plot each sector 
    legend_handles = []
    for sector in sectors:
        subset = filtered_df[filtered_df['Sector'] == sector]
        if not subset.empty:
            ax.scatter(
                subset['Longitude'], 
                subset['Latitude'],
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
    actual_max = (filtered_df['total_h2_demand_kg']).max()
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
    total_h2_kg = filtered_df['total_h2_demand_kg'].sum()
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
        filtered_df.groupby('Sector')['total_h2_demand_kg']
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


def create_demand_grid(filtered_df, year):
    """
    Geographically aggregates hydrogen demand from industrial facilities in the WECC, producing
    a raster file with 5x5km resolution.
    
    Inputs:
    - filtered_df: a DataFrame containing hydrogen demand projections from industrial facilities
    - year: the model year

    Outputs:
    - Saves a GeoPackage containing the estimated hydrogen demand from industry in 5x5km-sized 
        square geometries. These squares constitute the entire WECC. 
    """
    wecc_grid_path = base_path.parent / 'transport' / 'input_files' / 'vmt_grid_wecc.gpkg'
    wecc_grid = gp.read_file(wecc_grid_path).copy()

    # Convert to GeoDataFrame
    geometry = gp.points_from_xy(filtered_df['Longitude'], filtered_df['Latitude'])
    facilities_gdf = gp.GeoDataFrame(filtered_df, geometry=geometry, crs='EPSG:4326')

    # Ensure CRS match
    if wecc_grid.crs != facilities_gdf.crs:
        facilities_gdf = facilities_gdf.to_crs(wecc_grid.crs)

    # Spatial join: assign each facility to a grid cell
    joined = gp.sjoin(facilities_gdf, wecc_grid, how='left', predicate='intersects')
    
    # Aggregate demand per grid cell
    demand_by_cell = joined.groupby('index_right')['total_h2_demand_kg'].sum().reset_index()

    # Merge demand back onto the grid
    result_grid = wecc_grid.merge(demand_by_cell, left_index=True, right_on='index_right', how='left')
    result_grid['total_h2_demand_kg'] = result_grid['total_h2_demand_kg'].fillna(0)

    # Drop unwanted columns
    result_grid = result_grid.drop(columns=['LD_VMT', 'HD_VMT'])

    grid_output_path = base_path.parent / 'outputs' / 'industry' / f'{year}_wecc_h2_demand_5km_resolution.gpkg'
    result_grid.to_file(grid_output_path, driver='GPKG')
