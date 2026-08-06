"""
Admin endpoints for demo purposes
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import pandas as pd
from app.scheduler import get_current_predictions, current_predictions
from app.predictor import predict_risk
from .ws_manager import manager

router = APIRouter(prefix="/admin", tags=["admin"])

# Store original data for reset
_original_data = None

class RainfallUpdate(BaseModel):
    location_name: str
    rainfall_mm: float
    password: Optional[str] = None

@router.post("/update-rainfall")
async def update_rainfall(update: RainfallUpdate):
    """
    Manually update rainfall for a specific location (for demo purposes)
    """
    # Simple password check (optional)
    ADMIN_PASSWORD = "demo123"  # Change this!
    if update.password and update.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")
    
    # Get current predictions data
    data = get_current_predictions()
    if not data or "predictions" not in data:
        raise HTTPException(status_code=500, detail="No prediction data available")
    
    predictions_list = data["predictions"]
    
    # Find the location
    # Support both 'taluk_name' (new) and 'name' (old/fallback)
    matching = []
    for p in predictions_list:
        p_name = p.get('taluk_name') or p.get('name') or ""
        if update.location_name.lower() in p_name.lower():
            matching.append(p)
    
    if not matching:
        raise HTTPException(status_code=404, detail=f"Location '{update.location_name}' not found")
    
    if len(matching) > 1:
        matches = [p.get('taluk_name') or p.get('name') for p in matching]
        raise HTTPException(
            status_code=400, 
            detail=f"Multiple matches found: {matches}. Please be more specific."
        )
    
    location = matching[0]
    taluk_id = location.get('taluk_id')
    old_rain = location.get('rain7', 0)
    
    # Calculate new prediction with updated rainfall
    result = predict_risk(
        dem=location['dem'],
        slope=location['slope'],
        rain7=update.rainfall_mm
    )
    
    # Update the actual current_predictions dictionary (not a copy!)
    if taluk_id and taluk_id in current_predictions:
        current_predictions[taluk_id]['rain7'] = update.rainfall_mm
        current_predictions[taluk_id]['probability'] = result['probability']  # Keep 0-1 range
        current_predictions[taluk_id]['risk_level'] = result['risk_level']
        current_predictions[taluk_id]['color'] = result['color']
    
    # Broadcast full prediction data so all connected clients update
    await manager.broadcast(get_current_predictions())
    
    loc_name = location.get('taluk_name') or location.get('name') or 'Unknown'
    
    return {
        "success": True,
        "location": loc_name,
        "old_rainfall": round(old_rain, 2),
        "new_rainfall": round(update.rainfall_mm, 2),
        "probability": round(result['probability'] * 100, 2),
        "risk_level": result['risk_level'],
        "message": f"Rainfall updated from {old_rain:.1f}mm to {update.rainfall_mm:.1f}mm. Risk: {result['risk_level']} ({result['probability']*100:.1f}%)"
    }

@router.get("/reset")
async def reset_rainfall():
    """
    Reset all rainfall values to original (trigger a fresh prediction update)
    """
    from app.scheduler import update_predictions
    import asyncio
    
    async def do_reset_and_broadcast():
        await update_predictions(skip_rainfall=False)
        # Broadcast the new (original) values to all clients
        # We need to import get_current_predictions here or use the one imported at top
        from app.scheduler import get_current_predictions
        await manager.broadcast(get_current_predictions())

    # Trigger a fresh update (will broadcast when done)
    asyncio.create_task(do_reset_and_broadcast())
    
    return {"success": True, "message": "Triggering fresh rainfall data fetch..."}


class PreviewRequest(BaseModel):
    location_name: str
    rainfall_mm: float


@router.post("/preview")
async def preview_prediction(req: PreviewRequest):
    """
    Get the REAL ML prediction for a location with given rainfall (without updating the map).
    Used by Admin GUI for accurate live preview.
    """
    data = get_current_predictions()
    if not data or "predictions" not in data:
        raise HTTPException(status_code=500, detail="No prediction data available")
    
    predictions_list = data["predictions"]
    
    # Find the location
    matching = []
    for p in predictions_list:
        p_name = p.get('taluk_name') or p.get('name') or ""
        if req.location_name.lower() == p_name.lower():  # Exact match
            matching.append(p)
            break
    
    if not matching:
        # Try partial match
        for p in predictions_list:
            p_name = p.get('taluk_name') or p.get('name') or ""
            if req.location_name.lower() in p_name.lower():
                matching.append(p)
                break
    
    if not matching:
        raise HTTPException(status_code=404, detail=f"Location '{req.location_name}' not found")
    
    location = matching[0]
    
    # Get REAL prediction from ML model
    result = predict_risk(
        dem=location['dem'],
        slope=location['slope'],
        rain7=req.rainfall_mm
    )
    
    loc_name = location.get('taluk_name') or location.get('name') or 'Unknown'
    
    return {
        "location": loc_name,
        "rainfall_mm": req.rainfall_mm,
        "probability": round(result['probability'] * 100, 2),
        "risk_level": result['risk_level'],
        "color": result['color'],
        "dem": location['dem'],
        "slope": location['slope']
    }
