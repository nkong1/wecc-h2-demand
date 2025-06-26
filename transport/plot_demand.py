"""
This file contains a plotting function that plots the hydrogen demand by load zone onto the WECC load zone map.
It is called by the transport_h2.py file.
"""

import geopandas as gpd
import matplotlib.pyplot as plt
from pathlib import Path

base_path  = Path(__file__).parent
load_zone_path = base_path / 'input_files' / 'load_zones' / 'load_zones.shp'

def plot_lz_demand(demand_df, plot_output_path):
    lz_gdf = gpd.read_file(load_zone_path)

    # Step 1: Data Processing
    lz_gdf = lz_gdf.rename(columns={'LOAD_AREA': 'load_zone'})

    # Merge the datasets
    merged = lz_gdf.merge(demand_df, on='load_zone', how='left')

    # Step 2: Visualize the data
    print('\nPlotting hydrogen demand by load zone...')

    # Create the plot
    fig, ax = plt.subplots(1, 1, figsize=(15, 12))

    # Create choropleth map
    merged.plot(column='total_h2_demand',
                cmap='viridis',
                edgecolor='black',
                legend=True,
                ax=ax,
                legend_kwds={'label': 'H2 Demand (kg)',
                            'orientation': 'vertical',
                            'shrink': 0.8})

    ax.set_title("Estimated Hydrogen Demand by Load Zone",
                fontsize=16, fontweight='bold', pad=20)
    ax.axis('off')

    # Get top 5 zones by demand
    top_zones = merged.nlargest(5, 'total_h2_demand')

    for idx, row in top_zones.iterrows():
        if row['total_h2_demand'] > 0:
            # Get centroid for label placement
            centroid = row.geometry.centroid
            ax.annotate(f"{row['load_zone']}\n{row['total_h2_demand']:,.0f} kg",
                        xy=(centroid.x, centroid.y),
                        xytext=(5, 5),
                        textcoords='offset points',
                        fontsize=8,
                        bbox=dict(boxstyle='round,pad=0.3',
                                facecolor='white', alpha=0.7),
                        ha='left')
            
    total_demand = merged['total_h2_demand'].sum()
    plt.text(
        x=0.05, y=1,
        s=f"WECC Total Annual Demand: {total_demand/1e6:,.0f} million kg",
        transform=plt.gca().transAxes,
        fontsize=12,
        verticalalignment='top',
        bbox=dict(facecolor='white', alpha=0.7, edgecolor='gray')
    )

    plt.tight_layout()

    # Save the plot
    plt.savefig(plot_output_path, dpi=300, bbox_inches='tight')
    print(f"Map saved to: {plot_output_path}")