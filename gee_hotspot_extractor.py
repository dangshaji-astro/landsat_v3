"""
GEE Elevation Hotspot Extractor
================================
Run ONCE to enrich kerala_taluks.json with high-elevation hotspot coords.

Requirements:
    pip install earthengine-api
    earthengine authenticate   ← run this first in terminal

Output:
    data/kerala_taluks_enriched.json

The scheduler will automatically use it if present.
"""
import ee
import json
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILE = DATA_DIR / "kerala_taluks.json"
OUTPUT_FILE = DATA_DIR / "kerala_taluks_enriched.json"

GEE_PROJECT = "golden-operator-475716-q4"

# ── Top N% elevation threshold: we look at pixels in top 20% elevation ──────
HOTSPOT_PERCENTILE = 80  # Use 80th percentile elevation as the "high zone"


def authenticate():
    """Initialize GEE with project ID."""
    try:
        ee.Initialize(project=GEE_PROJECT)
        print(f"✅ GEE Initialized with project: {GEE_PROJECT}")
    except Exception as e:
        print(f"❌ GEE init failed: {e}")
        print("Run: earthengine authenticate")
        raise


def get_hotspot_for_polygon(geometry_coords, polygon_type="Polygon"):
    """
    For a given polygon, find the centroid of the high-elevation sub-zone
    using SRTM DEM and terrain slope from GEE.

    Returns: dict with hotspot_lat, hotspot_lon, dem_hotspot, slope_hotspot
    """
    try:
        # Build GEE geometry
        if polygon_type == "Polygon":
            geom = ee.Geometry.Polygon(geometry_coords)
        else:  # MultiPolygon
            geom = ee.Geometry.MultiPolygon(geometry_coords)

        # SRTM Digital Elevation Model (30m resolution)
        dem = ee.Image("USGS/SRTMGL1_003")
        slope = ee.Terrain.slope(dem)

        # Get percentile threshold for this polygon
        dem_stats = dem.reduceRegion(
            reducer=ee.Reducer.percentile([HOTSPOT_PERCENTILE]),
            geometry=geom,
            scale=90,  # 90m for speed (SRTM is 30m but we don't need full res)
            maxPixels=1e6
        )

        threshold = dem_stats.get("elevation").getInfo()

        if threshold is None:
            # Fallback: polygon is too small or over water
            centroid = geom.centroid().coordinates().getInfo()
            dem_mean = dem.reduceRegion(ee.Reducer.mean(), geom, 90, maxPixels=1e5).get("elevation").getInfo()
            slope_mean = slope.reduceRegion(ee.Reducer.mean(), geom, 90, maxPixels=1e5).get("slope").getInfo()
            return {
                "hotspot_lat": centroid[1],
                "hotspot_lon": centroid[0],
                "dem_hotspot": round(dem_mean or 0, 2),
                "slope_hotspot": round(slope_mean or 0, 2),
                "hotspot_type": "centroid_fallback"
            }

        # Mask to high-elevation zone (above 80th percentile)
        high_zone = dem.updateMask(dem.gte(threshold))

        # Get slope values in that high zone
        high_zone_slope = slope.updateMask(dem.gte(threshold))

        # Compute weighted centroid using elevation as weight
        hotspot_coords = high_zone.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=90,
            maxPixels=1e6
        ).getInfo()

        # Get the actual centroid of the high zone pixels
        centroid = high_zone.reduceRegion(
            reducer=ee.Reducer.centroid().setOutputs(["longitude", "latitude"]),
            geometry=geom,
            scale=90,
            maxPixels=1e6
        ).getInfo()

        # Fallback if centroid reduction fails
        if not centroid or centroid.get("latitude") is None:
            centroid_pt = geom.centroid().coordinates().getInfo()
            lat, lon = centroid_pt[1], centroid_pt[0]
        else:
            lat = centroid.get("latitude", 0)
            lon = centroid.get("longitude", 0)

        # Mean elevation and slope of the HIGH zone
        dem_high = hotspot_coords.get("elevation", 0) or 0
        slope_high = high_zone_slope.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=90,
            maxPixels=1e6
        ).getInfo().get("slope", 0) or 0

        return {
            "hotspot_lat": round(lat, 6),
            "hotspot_lon": round(lon, 6),
            "dem_hotspot": round(dem_high, 2),
            "slope_hotspot": round(slope_high, 2),
            "hotspot_type": "gee_high_zone"
        }

    except Exception as e:
        print(f"    ⚠ GEE error: {e} — using centroid fallback")
        return None  # Signal to caller to keep original values


def enrich_taluks():
    """
    Main enrichment loop. Processes each village polygon and adds hotspot data.
    """
    authenticate()

    print(f"\n📂 Loading: {INPUT_FILE}")
    with open(INPUT_FILE, "r") as f:
        data = json.load(f)

    features = data.get("features", [])
    total = len(features)
    print(f"📍 Processing {total} village polygons...\n")

    enriched_features = []
    success = 0
    fallback = 0

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        geom = feature.get("geometry", {})
        name = props.get("name", f"Unknown-{i}")
        geom_type = geom.get("type", "Polygon")
        coords = geom.get("coordinates", [])

        print(f"[{i+1}/{total}] {name} ...", end=" ", flush=True)

        hotspot = get_hotspot_for_polygon(coords, geom_type)

        if hotspot:
            props.update(hotspot)
            success += 1
            print(f"✅ hotspot: {hotspot['hotspot_lat']:.4f}, {hotspot['hotspot_lon']:.4f} | dem={hotspot['dem_hotspot']:.0f}m slope={hotspot['slope_hotspot']:.1f}°")
        else:
            # Keep original centroid data, mark as not enriched
            centroid = props.get("centroid", {})
            props["hotspot_lat"] = centroid.get("lat", props.get("latitude", 0))
            props["hotspot_lon"] = centroid.get("lon", props.get("longitude", 0))
            props["dem_hotspot"] = props.get("dem_avg", 0)
            props["slope_hotspot"] = props.get("slope_avg", 0)
            props["hotspot_type"] = "centroid_fallback"
            fallback += 1
            print("⚠ fallback")

        enriched_features.append({**feature, "properties": props})

        # Rate limiting — GEE allows ~1000 requests/100s
        if (i + 1) % 50 == 0:
            print(f"\n⏳ Processed {i+1}/{total}... pausing 2s\n")
            time.sleep(2)

    # Save output
    output_data = {**data, "features": enriched_features}
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output_data, f)

    print(f"\n{'='*60}")
    print(f"✅ Done! {success} enriched, {fallback} fallback")
    print(f"📁 Saved to: {OUTPUT_FILE}")
    print(f"{'='*60}")
    print("\nNext step: restart the server — it will auto-load enriched data.")


if __name__ == "__main__":
    enrich_taluks()
