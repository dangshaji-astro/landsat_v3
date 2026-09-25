"""
Landslide Risk Predictor
Uses Soil Water Index (SWI) for antecedent moisture accounting.
"""
import joblib
import pandas as pd
from pathlib import Path
from typing import List, Optional

# Load model at module level
MODEL_PATH = Path(__file__).parent.parent / "landslide_rf_model.pkl"
model = None

# Field capacity by soil type (mm water stored per 1m soil depth)
# Laterite: ~280mm, Clay: ~400mm, Sand: ~220mm
# Kerala USDA codes from OpenLandMap: 6=Sandy Clay Loam (most of Kerala), 4=Clay Loam, 7=Loam
FIELD_CAPACITY = {
    "Laterite": 280,
    "Laterite (Kerala)": 280,
    "Clay": 400,
    "Silty Clay": 400,
    "Sandy Clay": 330,
    "Clay Loam": 350,            # USDA code 4 — lateritic clay loam
    "Silty Clay Loam": 370,
    "Sandy Clay Loam": 300,      # USDA code 6 — dominant Kerala laterite texture
    "Loam": 320,                 # USDA code 7 — highland forest loam
    "Silt Loam": 310,
    "Silt": 290,
    "Sandy Loam": 260,
    "Loamy Sand": 230,
    "Sand": 200,
    "Unknown": 300,
}
DEFAULT_FIELD_CAPACITY = 300  # mm


def load_model():
    """Load the trained model"""
    global model
    if model is None:
        model = joblib.load(MODEL_PATH)
    return model


def compute_swi(history: List[float], soil_type: str = "Laterite") -> dict:
    """
    Compute the Soil Water Index (SWI) from daily rainfall history.

    Uses an exponential decay model:
        SWI = Σ rain[day] × k^(n-1-day)
    where k=0.85 means soil retains 85% of moisture each day (drains 15%/day).

    This correctly handles scenarios like:
    - "10mm for a week" vs "70mm on one day then dry" → same rain7, different SWI
    - "heavy rain all month" → SWI approaches field capacity → high pore pressure

    Returns:
        swi: Weighted soil moisture (mm)
        saturation: 0.0–1.0 ratio vs field capacity
        field_capacity: max soil can hold (mm)
    """
    k = 0.85  # Retention factor: soil drains 15%/day
    fc = FIELD_CAPACITY.get(soil_type, DEFAULT_FIELD_CAPACITY)

    if not history:
        return {"swi": 0.0, "saturation": 0.0, "field_capacity": fc}

    n = len(history)
    swi = sum(rain * (k ** (n - 1 - i)) for i, rain in enumerate(history))
    swi = round(min(swi, fc), 2)  # Cap at field capacity (saturated)
    saturation = round(swi / fc, 3)

    return {"swi": swi, "saturation": saturation, "field_capacity": fc}


def predict_risk(dem: float, slope: float, rain7: float,
                 history: Optional[List[float]] = None,
                 soil_type: str = "Laterite") -> dict:
    """
    Predict landslide risk for given features.

    If daily history is provided, uses Soil Water Index (SWI) for the
    rainfall component — correctly penalizing prolonged rainfall and
    pre-wetted soils. Falls back to raw rain7 if no history available.
    """
    load_model()

    features = pd.DataFrame([{
        'DEM': dem,
        'SLOPE': slope,
        'rain7': rain7
    }])

    raw_prob = model.predict_proba(features)[0][1]  # ML terrain-based probability (0-1)
    # Calibrate: RF on imbalanced data outputs low positives. /0.6 rescales without over-inflating.
    ml_prob = min(raw_prob / 0.6, 1.0)

    # ── Effective Rainfall: SWI or raw sum ──────────────────────────────────
    swi_data = None
    if history:
        swi_data = compute_swi(history, soil_type)
        # SWI saturation of 1.0 (fully saturated) → 180mm equivalent effective rain.
        # Lowered from 250 to avoid moderate saturation instantly triggering HIGH.
        effective_rain = swi_data["saturation"] * 180
    else:
        effective_rain = rain7

    # ── Rainfall Component (Kerala IMD thresholds) ───────────────────────────
    if effective_rain < 15:
        rain_component = 0.0
    elif effective_rain < 64:
        rain_component = 0.05 + (effective_rain - 15) / 49 * 0.15   # 0.05 → 0.20
    elif effective_rain < 115:
        rain_component = 0.20 + (effective_rain - 64) / 51 * 0.25   # 0.20 → 0.45
    elif effective_rain < 204:
        rain_component = 0.45 + (effective_rain - 115) / 89 * 0.25  # 0.45 → 0.70
    else:
        rain_component = min(0.70 + (effective_rain - 204) / 200 * 0.15, 0.85)  # → 0.85

    # Blend: rain weight capped at 0.55 so terrain still contributes during heavy rain
    rain_weight = min(effective_rain / 150, 0.55)
    probability = (1 - rain_weight) * ml_prob + rain_weight * rain_component
    probability = round(min(max(probability, 0.0), 1.0), 3)

    if probability < 0.45:
        level, color = "LOW", "#22c55e"
    elif probability < 0.72:
        level, color = "MEDIUM", "#eab308"
    else:
        level, color = "HIGH", "#ef4444"

    result = {
        "probability": probability,
        "risk_level": level,
        "color": color
    }

    if swi_data:
        result["swi"] = swi_data["swi"]
        result["soil_saturation"] = round(swi_data["saturation"] * 100, 1)
        result["field_capacity"] = swi_data["field_capacity"]

    return result


def predict_batch(locations: list) -> list:
    """Predict risk for multiple locations in a single vectorized pass, using SWI if history is available."""
    if not locations:
        return []
    load_model()
    
    df = pd.DataFrame([{
        'DEM': loc['dem'],
        'SLOPE': loc['slope'],
        'rain7': loc['rain7']
    } for loc in locations])

    raw_probs = model.predict_proba(df)[:, 1]
    # Calibrate: /0.6 rescales without over-inflating low-base RF positives
    ml_probs = [min(p / 0.6, 1.0) for p in raw_probs]

    results = []
    for i, loc in enumerate(locations):
        ml_prob = ml_probs[i]
        history = loc.get('history')
        soil_type = loc.get('soil_type', 'Laterite')
        rain7 = loc['rain7']

        swi_data = None
        if history:
            swi_data = compute_swi(history, soil_type)
            # SWI saturation of 1.0 → 180mm equivalent; avoids moderate rain → instant HIGH
            effective_rain = swi_data["saturation"] * 180
        else:
            effective_rain = rain7

        if effective_rain < 15:
            rain_component = 0.0
        elif effective_rain < 64:
            rain_component = 0.05 + (effective_rain - 15) / 49 * 0.15
        elif effective_rain < 115:
            rain_component = 0.20 + (effective_rain - 64) / 51 * 0.25
        elif effective_rain < 204:
            rain_component = 0.45 + (effective_rain - 115) / 89 * 0.25
        else:
            rain_component = min(0.70 + (effective_rain - 204) / 200 * 0.15, 0.85)

        # Rain weight capped at 0.55 — terrain still contributes during heavy rainfall
        rain_weight = min(effective_rain / 150, 0.55)
        probability = (1 - rain_weight) * ml_prob + rain_weight * rain_component
        probability = round(min(max(float(probability), 0.0), 1.0), 3)

        if probability < 0.45:
            level, color = "LOW", "#22c55e"
        elif probability < 0.72:
            level, color = "MEDIUM", "#eab308"
        else:
            level, color = "HIGH", "#ef4444"

        res = {
            "probability": probability,
            "risk_level": level,
            "color": color
        }
        if swi_data:
            res["swi"] = swi_data["swi"]
            res["soil_saturation"] = round(swi_data["saturation"] * 100, 1)
            res["field_capacity"] = swi_data["field_capacity"]
        results.append(res)

    return results


