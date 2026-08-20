"""
prepare_geojson.py

Processes the raw NHS England region boundary GeoJSON (downloaded manually
from ONS's Open Geography Portal — see README) into a lightweight file
ready for Leaflet:
  - reprojects from British National Grid (EPSG:27700) to WGS84 (EPSG:4326),
    which is what Leaflet/web maps expect
  - simplifies geometry so the map loads quickly in the browser
  - keeps only the region name + geometry (drops BNG_E, BNG_N, Shape__Area etc.)
  - renames the name field to "region" so it joins cleanly against the
    "region" field in nhs111_tidy.json

Usage:
    python scripts/prepare_geojson.py
"""

from pathlib import Path

import geopandas as gpd

RAW_PATH = Path(__file__).parent.parent / "data" / "raw" / "nhs_regions_raw.geojson"
OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "nhs_regions.geojson"

# How aggressively to simplify geometry (in degrees, since we simplify after
# reprojecting to WGS84). 0.001 is a reasonable starting point for a
# region-level (not local-authority-level) map; raise it if the file is
# still large/slow, lower it if boundaries look too blocky.
SIMPLIFY_TOLERANCE = 0.001


def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_PATH} not found.\n\n"
            "Download it first:\n"
            "1. Open this URL in your browser:\n"
            "   https://services1.arcgis.com/ESMARspQHYMw9BZ9/arcgis/rest/services/"
            "NHS_England_Regions_January_2024_EN_BSC/FeatureServer/0/query?"
            "where=1=1&outFields=*&f=geojson\n"
            "2. Save the downloaded file as data/raw/nhs_regions_raw.geojson\n"
        )

    print(f"Loading {RAW_PATH}...")
    gdf = gpd.read_file(RAW_PATH)
    print(f"  {len(gdf)} regions, CRS: {gdf.crs}")

    # The source is in British National Grid; reproject to WGS84 for Leaflet
    if gdf.crs is None or gdf.crs.to_epsg() != 4326:
        print("Reprojecting to EPSG:4326 (WGS84)...")
        gdf = gdf.to_crs(epsg=4326)

    print(f"Simplifying geometry (tolerance={SIMPLIFY_TOLERANCE})...")
    gdf["geometry"] = gdf["geometry"].simplify(SIMPLIFY_TOLERANCE, preserve_topology=True)

    # Keep only what we need, and rename the region name field so it matches
    # the "region" key used in nhs111_tidy.json
    name_col = "NHSER24NM" if "NHSER24NM" in gdf.columns else "NHSER23NM"
    gdf = gdf[[name_col, "geometry"]].rename(columns={name_col: "region"})

    print("Regions found:", sorted(gdf["region"].tolist()))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"Wrote {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
