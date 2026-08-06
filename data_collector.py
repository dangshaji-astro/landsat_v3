"""
Data Collector - Aggregates all inputs for Expert Model
Combines: GEE Satellite Data + Weather Data + Terrain Data
"""
import sys
from pathlib import Path
from typing import Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gee_tools import fetch_location_context
from app.rainfall_fetcher import get_rainfall_data
import pandas as pd


def get_terrain_data(lat: float, lon: float, geojson_path: str = "data/kerala_taluks.geojson") -> Dict:
    """
    Extract DEM and Slope from the existing GeoJSON
    """
    import geopandas as gpd
    from shapely.geometry import Point
    
    gdf = gpd.read_file(geojson_path)
    point = Point(lon, lat)
    
    # Find the taluk containing this point
    matching = gdf[gdf.contains(point)]
    
    if not matching.empty:
        row = matching.iloc[0]
        return {
            "taluk_name": row.get('NAME', 'Unknown'),
            "dem": row.get('dem', 0),
            "slope": row.get('slope', 0)
        }
    
    return {"taluk_name": "Unknown", "dem": 0, "slope": 0}


def collect_all_data(lat: float, lon: float) -> Dict:
    """
    Main Aggregator: Collects ALL data needed for Expert Analysis
    
    Returns a complete "Medical Report" for the location
    """
    print(f"🔍 Collecting data for ({lat}, {lon})...")
    
    # 1. Satellite Data (The Eyes)
    print("  📡 Fetching satellite data from GEE...")
    try:
        satellite_data = fetch_location_context(lat, lon)
    except Exception as e:
        print(f"  ⚠️  GEE Error: {e}")
        satellite_data = {
            "land_cover": {"land_cover": "Unknown"},
            "soil": {"soil_texture": "Unknown"},
            "ndvi_trend": {"change_percent": 0},
            "soil_moisture": {"saturation_level": "Unknown"}
        }
    
    # 2. Terrain Data (From DEM)
    print("  🏔️  Extracting terrain data...")
    terrain = get_terrain_data(lat, lon)
    
    # 3. Weather Data (Rainfall)
    print("  🌧️  Fetching rainfall data...")
    try:
        rainfall = get_rainfall_data(lat, lon)
    except Exception as e:
        print(f"  ⚠️  Rainfall Error: {e}")
        rainfall = {"rain7": 0}
    
    # 4. Aggregate into a structured report
    report = {
        "location": {
            "lat": lat,
            "lon": lon,
            "taluk": terrain.get("taluk_name", "Unknown")
        },
        "terrain": {
            "elevation_m": terrain.get("dem", 0),
            "slope_degrees": terrain.get("slope", 0)
        },
        "land_cover": satellite_data["land_cover"]["land_cover"],
        "soil": {
            "texture": satellite_data["soil"]["soil_texture"],
            "moisture_status": satellite_data["soil_moisture"]["saturation_level"]
        },
        "vegetation": {
            "ndvi_change_5yr": satellite_data["ndvi_trend"]["change_percent"],
            "degradation_flag": satellite_data["ndvi_trend"]["degradation_detected"]
        },
        "rainfall": {
            "7day_mm": rainfall.get("rain7", 0)
        }
    }
    
    print("✅ Data collection complete!")
    return report


if __name__ == "__main__":
    # Test
    import json
    
    # Wayanad test location
    data = collect_all_data(11.6, 76.1)
    print("\n📄 LOCATION REPORT:")
    print(json.dumps(data, indent=2))
