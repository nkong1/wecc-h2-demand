"""
Plotting the hydroegn demand profiles for each of the four scenarios at a daily resolution. Each profile is broken
down by subsector, such as LD transport, Fertilizers, Refineries, Baseline, etc. Create one figure with four plots.
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# File paths
bau_path = "scenario_profiles/bau.csv"
limited_progress_path = "scenario_profiles/limited_progress.csv"
moderate_action_path = "scenario_profiles/moderate_action.csv"
clean_air_path = "scenario_profiles/clean_air.csv"

# Load CSVs
dfs = [
    pd.read_csv(bau_path),
    pd.read_csv(limited_progress_path),
    pd.read_csv(moderate_action_path),
    pd.read_csv(clean_air_path)
]

# Convert day_of_year to datetime
for df in dfs:
    df['day_of_year'] = df['day_of_year'].astype(int)
    df['date'] = pd.Timestamp('2050-01-01') + pd.to_timedelta(df['day_of_year'] - 1, unit='D')

# Define subsectors and readable names
subsectors = [
    'demand_mwh_baseline',
    'demand_mwh_Iron_and_Steel',
    'demand_mwh_Aluminum',
    'demand_mwh_Cement',
    'demand_mwh_Chemicals',
    'demand_mwh_Refineries',
    'demand_mwh_Glass',
    'demand_mwh_Light_Duty_Transport',
    'demand_mwh_Heavy_Duty_Transport',
    'demand_mwh_aviation'
]

sector_names = [
    'Baseline',
    'Iron & Steel',
    'Aluminum',
    'Cement',
    'Chemicals',
    'Refineries',
    'Glass',
    'LD On-Road Transport',
    'HD On-Road Transport',
    'Aviation'
]

colors = [
    "#F1B7B7", "#C870F1", '#8DA0CB', '#FFD92F', '#E78AC3', 
    "#D85454", "#D1DFCE", "#2BFC3C", "#3E80FA", "#E0DE51"
]

scenarios = ['Business As Usual (BAU)', 'Limited Progress', 'Moderate Action', 'Clean Air']

# Create figure with 4 subplots (share y-axis still okay for scaling)
fig, axes = plt.subplots(2, 2, figsize=(18, 12), sharey=True)
axes = axes.flatten()

# Define x-axis limits
start_date = pd.Timestamp('2050-01-01')
end_date = pd.Timestamp('2050-12-31')

# Plot each scenario
for i, ax in enumerate(axes):
    df = dfs[i]

    # Plot the month on the x axis
    ax.stackplot(df['date'], [df[sub] / 1000 for sub in subsectors], colors=colors)
    ax.set_title(scenarios[i], fontsize=14)
    ax.set_xlabel("Month", fontsize=12, labelpad=8)
    ax.set_ylabel("Hydrogen Demand (GWh)", fontsize=12, labelpad=8)
    
    # Month ticks
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))

    # Remove extra padding at edges
    ax.set_xlim(start_date, end_date)
    

    """
    # Plot the day of the year on the x axis
    ax.stackplot(df['day_of_year'], [df[sub] / 1000 for sub in subsectors], colors=colors)
    ax.set_xlabel("Day of Year", fontsize=12, labelpad=8)
    ax.set_xlim(1, 365)
    ax.set_xticks(range(0, 366, 30))  
    ax.set_xticklabels([str(x) for x in range(0, 366, 30)])"""

    # Force y-axis tick labels to show
    ax.tick_params(axis='y', labelleft=True)


# Single legend below all subplots
fig.legend(
    sector_names,
    loc='lower center',
    ncol=5,
    fontsize=12,
    frameon=False,
    bbox_to_anchor=(0.5, 0.06)
)

# Adjust spacing between subplots and leave space for legend
plt.subplots_adjust(
    left=0.05, right=0.95, top=0.95, bottom=0.18,
    wspace=0.2, hspace=0.3
)

plt.savefig('scenario_profiles/profiles_v1', dpi=300, bbox_inches='tight', pad_inches=0.3)
