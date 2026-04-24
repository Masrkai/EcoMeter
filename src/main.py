import math
# import subprocess
import warnings
import polars as pl
import geopandas as gpd
import contextily as ctx
import matplotlib.pyplot as plt

from pyrosm import OSM

warnings.filterwarnings("ignore", message=".*value is being set on a copy.*")

# 1. Bounding box for Galala University area
bbox = [32.37, 29.41, 32.43, 29.45]

# 2. use buildings from Overture Maps (much better coverage than OSM for new areas)
buildings = gpd.read_file("galala_buildings.geojson")
print(f"Loaded {len(buildings)} buildings from Overture")

if len(buildings) == 0:
    raise ValueError("No buildings found in this bbox. Widen the coordinates.")

# Roads still from OSM (Overture roads are overkill here, OSM roads are fine)
osm = OSM("egypt-latest.osm.pbf", bounding_box=bbox)
roads = osm.get_network(network_type="driving")
print(f"Loaded {len(roads)} road segments from OSM")

# 3. Reproject to UTM zone 36N for accurate area calculation
buildings_proj = buildings.to_crs(epsg=32636).copy()
roads_proj = roads.to_crs(epsg=32636)
buildings_proj["area_m2"] = buildings_proj.geometry.area

# 4. Proxy emission model — all tabular work in Polars
emission_factors = {
    "house": 30,
    "apartments": 25,
    "commercial": 45,
    "industrial": 80,
    "residential": 28,
    "university": 40,
    "school": 35,
    "office": 40,
}

geometry_list = buildings_proj.geometry.tolist()

def gdf_attrs_to_polars(gdf, geom_col="geometry"):
    out = {}
    for col in gdf.columns:
        if col == geom_col:
            continue
        vals = gdf[col].tolist()
        out[col] = [
            None if (isinstance(v, float) and math.isnan(v)) else v
            for v in vals
        ]
    return pl.DataFrame(out)

buildings_df = gdf_attrs_to_polars(buildings_proj)

# Overture uses "subtype" or "class" instead of OSM's "building" column — handle both
# Map Overture building class to our emission factor keys
overture_type_col = None
for candidate in ["subtype", "class", "building"]:
    if candidate in buildings_df.columns:
        overture_type_col = candidate
        break

if overture_type_col:
    buildings_df = buildings_df.with_columns(
        pl.col(overture_type_col).fill_null("residential").alias("btype")
    )
else:
    buildings_df = buildings_df.with_columns(pl.lit("residential").alias("btype"))

# Overture "height" column can proxy for levels (assume ~3m per floor)
if "height" in buildings_df.columns:
    buildings_df = buildings_df.with_columns(
        (pl.col("height").cast(pl.Float64, strict=False).fill_null(3.0) / 3.0)
        .clip(1)
        .alias("levels")
    )
elif "num_floors" in buildings_df.columns:
    buildings_df = buildings_df.with_columns(
        pl.col("num_floors").cast(pl.Float64, strict=False).fill_null(1).clip(1).alias("levels")
    )
else:
    buildings_df = buildings_df.with_columns(pl.lit(1.0).alias("levels"))

# Map emission factors
ef_df = pl.DataFrame({
    "btype": list(emission_factors.keys()),
    "ef": list(emission_factors.values()),
})
buildings_df = buildings_df.join(ef_df, on="btype", how="left")
buildings_df = buildings_df.with_columns(pl.col("ef").fill_null(35))

# Vectorized CO₂ proxy
buildings_df = buildings_df.with_columns(
    (pl.col("area_m2") * pl.col("levels") * pl.col("ef")).alias("co2_proxy_kg_yr")
)
buildings_df = buildings_df.drop("ef")

# Rebuild GeoDataFrame
buildings_proj = gpd.GeoDataFrame(
    {col: buildings_df[col].to_list() for col in buildings_df.columns},
    geometry=geometry_list,
    crs="EPSG:32636",
)

# Reproject to WGS84 for basemap alignment
buildings = buildings_proj.to_crs(epsg=4326)
roads = roads_proj.to_crs(epsg=4326)

# 5. Visualize
fig, ax = plt.subplots(1, 1, figsize=(12, 10))

buildings.plot(
    column="co2_proxy_kg_yr",
    ax=ax,
    legend=True,
    cmap="OrRd",
    scheme="quantiles",
    k=5,
    alpha=0.8,
    legend_kwds={"fmt": "{:.0f}", "title": "CO₂ proxy (kg/yr)"},
)
roads.plot(ax=ax, color="gray", linewidth=0.3, alpha=0.5)
ax.set_title("Proxy CO₂ Emissions Estimate - Galala University", fontsize=14)
ax.axis("off")

ctx.add_basemap(ax, crs=buildings.crs, source=ctx.providers.Esri.WorldImagery)
# ax.texts.clear()  # remove ESRI attribution text

plt.tight_layout()

# output_map = "galala_co2_proxy.png"
# plt.savefig(output_map, format="png", bbox_inches="tight")

output_map = "result.svg"
plt.savefig(output_map, format="svg", bbox_inches="tight")

print(f"Map saved: {output_map}")
plt.close(fig)

# 6. Export vector data
export_cols = [c for c in ["btype", "area_m2", "levels", "co2_proxy_kg_yr", "geometry"] if c in buildings.columns]
buildings[export_cols].to_file("galala_co2_proxy.gpkg", driver="GPKG")
print("Data saved: galala_co2_proxy.gpkg")