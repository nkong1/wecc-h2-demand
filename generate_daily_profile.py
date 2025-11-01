import pandas as pd
import geopandas as gpd

# Load all load zones
load_zones_gdf = gpd.read_file("industry/inputs/load_zones/load_zones.shp")
load_zones = load_zones_gdf["LOAD_AREA"].tolist()

h2_daily_demand_df = pd.DataFrame()

for zone in load_zones:
    combined_df = pd.DataFrame()

    datetime_list = []
    for year in [2050]:
        # 8760 hours per year (ignore leap years for simplicity)
        datetime_list.extend(
            pd.date_range(start=f"{year}-01-01", periods=365, freq="d")
        )
    combined_df["datetime"] = pd.to_datetime(datetime_list)
    combined_df["zone_demand_mwh_h2"] = 0
    combined_df["LOAD_ZONE"] = zone
    combined_df["day"] = range(1, 366)

    h2_daily_demand_df = pd.concat([h2_daily_demand_df, combined_df])

h2_daily_demand_df["h2_daily_ts"] = "2050_all"
h2_daily_demand_df = h2_daily_demand_df = h2_daily_demand_df[["LOAD_ZONE", "day", "h2_daily_ts", "zone_demand_mwh_h2"]]
h2_daily_demand_df = h2_daily_demand_df.sort_values(['LOAD_ZONE', 'day']).reset_index(drop=True)


h2_daily_demand_df.to_csv("h2_daily_demand.csv", index=False)