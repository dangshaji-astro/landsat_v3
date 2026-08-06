"""
Scheduler for periodic rainfall updates
Simple and clean implementation supporting Taluk and 1km Subgrid predictions
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import json
import asyncio
from pathlib import Path

from .rainfall_fetcher import fetch_rainfall_batch
from .predictor import predict_batch

# Global state
current_predictions = {}
current_subgrid_predictions = {}
last_update_time = None
last_subgrid_update_time = None
_taluks_cache = None
_subgrid_cache = None

# Path to data
DATA_DIR = Path(__file__).parent.parent / "data"
BASE_DIR = Path(__file__).parent.parent
TALUKS_FILE = DATA_DIR / "kerala_taluks.json"
ENRICHED_FILE = DATA_DIR / "kerala_taluks_enriched.json"  # GEE hotspot version
SUBGRID_FILE = DATA_DIR / "kerala_only_1km_subgrid.geojson"
SUBGRID_FILE_ALT = BASE_DIR / "kerala_only_1km_subgrid.geojson"

# USDA soil texture class codes from OpenLandMap (SOL_TEXTURE-CLASS_USDA-TT_M/v02)
# Kerala distribution: code 6 (Sandy Clay Loam) = 54%, code 4 (Clay Loam) = 41%
# These map to Kerala's dominant Lateritic soil types — SWI field capacity is calibrated accordingly
SOIL_CODE_MAP = {
    1: "Clay",               # Heavy alluvial clay (river valleys)
    2: "Silty Clay",         # Coastal/estuary silty clay
    3: "Sandy Clay",         # Coastal sandy clay
    4: "Clay Loam",          # Lateritic clay loam (41% of Kerala cells)
    5: "Silty Clay Loam",    # Silty laterite
    6: "Sandy Clay Loam",    # Sandy laterite — DOMINANT Kerala soil (54% of cells)
    7: "Loam",               # Highland forest loam (Shola/Western Ghats)
    8: "Silt Loam",          # River terrace silt loam
    9: "Silt",               # Estuarine silt
    10: "Sandy Loam",        # Coastal sandy loam
    11: "Loamy Sand",        # Coastal sand fringe
    12: "Sand",              # Beach/dune sand
    -1: "Sandy Clay Loam",   # Null/water cells — default to Kerala dominant
}

scheduler = AsyncIOScheduler()


def load_taluks():
    """Load taluk data — prefers GEE-enriched file if available (Cached)"""
    global _taluks_cache
    if _taluks_cache:
        return _taluks_cache

    source = ENRICHED_FILE if ENRICHED_FILE.exists() else TALUKS_FILE
    if source.exists():
        print(f"[Scheduler] Loading from: {source.name}")
        with open(source, "r") as f:
            _taluks_cache = json.load(f)
            return _taluks_cache
    return {"features": []}


def load_subgrid():
    """Load 1km subgrid data (Cached)"""
    global _subgrid_cache
    if _subgrid_cache:
        return _subgrid_cache

    source = SUBGRID_FILE if SUBGRID_FILE.exists() else SUBGRID_FILE_ALT
    if source.exists():
        print(f"[Scheduler] Loading subgrid from: {source.name}")
        with open(source, "r") as f:
            _subgrid_cache = json.load(f)
            return _subgrid_cache
    return {"features": []}


async def update_predictions(skip_rainfall: bool = False):
    """Update predictions for all taluks"""
    global current_predictions, last_update_time
    
    print(f"[{datetime.now()}] Updating taluk predictions (skip_rainfall={skip_rainfall})...")
    
    taluks_data = load_taluks()
    features = taluks_data.get("features", [])
    
    if not features:
        print("No taluk data found!")
        return
    
    locations = []
    for feature in features:
        props = feature.get("properties", {})
        centroid = props.get("centroid", {})

        has_hotspot = "hotspot_lat" in props and "hotspot_lon" in props
        fetch_lat = props.get("hotspot_lat") if has_hotspot else centroid.get("lat", props.get("latitude", 0))
        fetch_lon = props.get("hotspot_lon") if has_hotspot else centroid.get("lon", props.get("longitude", 0))

        locations.append({
            "taluk_id": props.get("taluk_id"),
            "taluk_name": props.get("name"),
            "latitude": centroid.get("lat", props.get("latitude", 0)),
            "longitude": centroid.get("lon", props.get("longitude", 0)),
            "hotspot_lat": fetch_lat,
            "hotspot_lon": fetch_lon,
            "hotspot_type": props.get("hotspot_type", "centroid"),
            "dem": props.get("dem_hotspot", props.get("dem_avg", 500)),
            "slope": props.get("slope_hotspot", props.get("slope_avg", 15)),
        })
    
    if skip_rainfall:
        rainfall_data = [{"rain7": 0} for _ in locations]
    else:
        print(f"Fetching rainfall for {len(locations)} locations...")
        rainfall_data = await fetch_rainfall_batch([
            {"latitude": loc["hotspot_lat"], "longitude": loc["hotspot_lon"]}
            for loc in locations
        ])
    
    prediction_inputs = []
    for i, loc in enumerate(locations):
        data = rainfall_data[i] if isinstance(rainfall_data[i], dict) else {}
        rain7 = data.get("rain7", 0)
        history = data.get("history", [])
        prediction_inputs.append({
            "dem": loc["dem"],
            "slope": loc["slope"],
            "rain7": rain7,
            "history": history,
            "soil_type": "Laterite"
        })
    
    predictions = await asyncio.to_thread(predict_batch, prediction_inputs)
    
    for i, loc in enumerate(locations):
        data = rainfall_data[i] if isinstance(rainfall_data[i], dict) else {}
        rain7 = data.get("rain7", 0)
        history = data.get("history", [])
        
        current_predictions[loc["taluk_id"]] = {
            "taluk_id": loc["taluk_id"],
            "taluk_name": loc["taluk_name"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "hotspot_lat": loc["hotspot_lat"],
            "hotspot_lon": loc["hotspot_lon"],
            "hotspot_type": loc["hotspot_type"],
            "dem": loc["dem"],
            "slope": loc["slope"],
            "rain7": rain7,
            "rain_history": history,
            **predictions[i]
        }
    
    last_update_time = datetime.now().isoformat()
    print(f"[{datetime.now()}] Updated {len(predictions)} taluk predictions")


async def update_subgrid_predictions(skip_rainfall: bool = False):
    """Update predictions for 1km subgrid cells"""
    global current_subgrid_predictions, last_subgrid_update_time
    
    print(f"[{datetime.now()}] Updating 1km subgrid predictions (skip_rainfall={skip_rainfall})...")
    subgrid_data = load_subgrid()
    features = subgrid_data.get("features", [])
    
    if not features:
        print("No 1km subgrid data found!")
        return

    locations = []
    for feature in features:
        props = feature.get("properties", {})
        cell_id = props.get("cell_id", "")
        center_lat = props.get("center_lat", 0.0)
        center_lon = props.get("center_lon", 0.0)
        dem = props.get("dem_avg", 500)
        slope = props.get("slope_max", props.get("slope_avg", 15))
        soil_code = props.get("soil_code", -1)
        soil_type = SOIL_CODE_MAP.get(soil_code, "Laterite")

        locations.append({
            "cell_id": cell_id,
            "latitude": center_lat,
            "longitude": center_lon,
            "dem": dem if dem is not None else 500,
            "slope": slope if slope is not None else 15,
            "soil_type": soil_type
        })

    if skip_rainfall:
        rainfall_data = [{"rain7": 0} for _ in locations]
    else:
        rainfall_data = await fetch_rainfall_batch(locations)

    prediction_inputs = []
    for i, loc in enumerate(locations):
        data = rainfall_data[i] if isinstance(rainfall_data[i], dict) else {}
        prediction_inputs.append({
            "dem": loc["dem"],
            "slope": loc["slope"],
            "rain7": data.get("rain7", 0),
            "history": data.get("history", []),
            "soil_type": loc["soil_type"]
        })

    predictions = await asyncio.to_thread(predict_batch, prediction_inputs)

    new_subgrid = {}
    for i, loc in enumerate(locations):
        data = rainfall_data[i] if isinstance(rainfall_data[i], dict) else {}
        cell_id = loc["cell_id"]
        new_subgrid[cell_id] = {
            "cell_id": cell_id,
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "dem": loc["dem"],
            "slope": loc["slope"],
            "soil_type": loc["soil_type"],
            "rain7": data.get("rain7", 0),
            **predictions[i]
        }
    current_subgrid_predictions = new_subgrid
    last_subgrid_update_time = datetime.now().isoformat()
    print(f"[{datetime.now()}] Updated {len(predictions)} subgrid cell predictions")


def start_scheduler():
    """Start the background scheduler"""
    scheduler.add_job(
        update_predictions,
        trigger=IntervalTrigger(minutes=5),
        id="prediction_update",
        replace_existing=True
    )
    scheduler.add_job(
        update_subgrid_predictions,
        trigger=IntervalTrigger(minutes=15),
        id="subgrid_update",
        replace_existing=True
    )
    scheduler.start()
    print("Scheduler started")


def stop_scheduler():
    """Stop the scheduler"""
    scheduler.shutdown()


def get_current_predictions():
    """Get the latest taluk predictions"""
    return {
        "predictions": list(current_predictions.values()),
        "last_update": last_update_time,
        "count": len(current_predictions)
    }


def get_subgrid_predictions():
    """Get the latest subgrid predictions"""
    return {
        "predictions": current_subgrid_predictions,
        "last_update": last_subgrid_update_time,
        "count": len(current_subgrid_predictions)
    }
