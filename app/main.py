import sys
import asyncio
import warnings
import logging

# Suppress noisy warnings that spam the terminal
warnings.filterwarnings("ignore", category=UserWarning, module="sklearn")

# Suppress the Windows ProactorBasePipeTransport error spam
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

# Suppress uvicorn access log spam (every HTTP request prints a line)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)



from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote
import json
from pydantic import BaseModel

# Ensure expert_agent.py (in parent folder) is importable
BASE_DIR = Path(__file__).parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

try:
    import expert_agent as ea
except ImportError:
    ea = None

from .scheduler import (
    start_scheduler, 
    stop_scheduler, 
    update_predictions,
    get_current_predictions,
    load_taluks,
    load_subgrid,
    update_subgrid_predictions,
    get_subgrid_predictions
)
from .config import get_provider, get_api_key, update_config
from . import admin
from .ws_manager import manager

FRONTEND_DIR = BASE_DIR / "frontend"
TRAINING_PDF_DIR = BASE_DIR.parent / "training datasets" / "training pdfs"


def _resolve_training_pdf_path(filename: str) -> Path:
    """Resolve and validate a requested training PDF filename."""
    safe_name = Path(filename).name
    if safe_name != filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    pdf_path = (TRAINING_PDF_DIR / safe_name).resolve()
    base_path = TRAINING_PDF_DIR.resolve()
    if base_path not in pdf_path.parents:
        raise HTTPException(status_code=400, detail="Invalid path")

    if pdf_path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")

    return pdf_path


class ConfigUpdate(BaseModel):
    provider: str
    api_key: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown"""
    print("Starting Landslide Prediction System...")
    start_scheduler()
    
    # Instant startup with rain=0 — map is usable immediately
    await update_predictions(skip_rainfall=True)
    await update_subgrid_predictions(skip_rainfall=True)
    print("Map & 1km Subgrid loaded! Fetching real rainfall in background...")
    
    # Fetch real rainfall in background, then broadcast update to all WS clients
    async def fetch_rain_and_broadcast():
        await update_predictions(skip_rainfall=False)
        await update_subgrid_predictions(skip_rainfall=False)
        print("Rainfall fetched — broadcasting live update to clients...")
        await manager.broadcast({
            "type": "update",
            "taluks": get_current_predictions(),
            "subgrid": get_subgrid_predictions()
        })

    asyncio.create_task(fetch_rain_and_broadcast())

    # Pre-warm the Ollama model so first user request is instant
    asyncio.create_task(_warm_up_ollama())
    
    yield
    
    print("Shutting down...")
    stop_scheduler()


async def _warm_up_ollama():
    """Send a tiny prompt to Ollama on startup so it loads model weights into RAM.
    This eliminates the 10-30s cold-start delay on the first user request."""
    import httpx
    OLLAMA_URL = "http://localhost:11434"
    try:
        # Detect which model is available
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            models = [m["name"].split(":")[0] for m in resp.json().get("models", [])]
            if not models:
                print("[Warm-up] No Ollama models found, skipping.")
                return
            model = "llama3.1" if "llama3.1" in models else models[0]

        print(f"[Warm-up] Pre-loading {model} into RAM...")
        async with httpx.AsyncClient(timeout=120) as client:
            await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": "Ready.",
                    "stream": False,
                    "options": {"num_predict": 1}  # Generate just 1 token — enough to load weights
                }
            )
        print(f"[Warm-up] ✅ {model} is warm and ready — first user request will be fast!")
    except Exception as e:
        print(f"[Warm-up] Skipped (Ollama not running or model not found): {e}")


app = FastAPI(
    title="Kerala Landslide Prediction",
    lifespan=lifespan
)

# Register admin router
app.include_router(admin.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== API Endpoints ==========

class SettingsSchema(BaseModel):
    provider: str
    api_key: str

@app.get("/api/settings")
async def get_settings():
    return {
        "provider": get_provider(),
        "api_key": get_api_key()
    }

@app.post("/api/settings")
async def save_settings(settings: SettingsSchema):
    update_config(settings.provider, settings.api_key)
    return {"status": "saved"}

@app.get("/")
async def root():
    return FileResponse(FRONTEND_DIR / "scientific.html")



@app.get("/legacy")
async def legacy():
    """Old interface"""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/scientific-v2", response_class=HTMLResponse)
async def get_scientific_v2():
    """Serve the ISOLATED Scientific Dashboard V2"""
    return FileResponse(FRONTEND_DIR / "scientific_v2.html")


@app.get("/scientific")
async def scientific():
    """Scientific control panel view (Stitch Design 2)"""
    return FileResponse(FRONTEND_DIR / "scientific.html")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/predictions")
async def get_predictions():
    # Prevent mobile browser caching
    return JSONResponse(
        content=get_current_predictions(),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/taluks")
async def get_taluks():
    """Return full polygon data"""
    taluks = load_taluks()
    return JSONResponse(taluks)


@app.get("/api/subgrid")
async def get_subgrid():
    """Return full 1km subgrid GeoJSON data"""
    subgrid = load_subgrid()
    return JSONResponse(subgrid)


@app.get("/api/subgrid-predictions")
async def get_subgrid_predictions_api():
    """Return latest subgrid risk predictions"""
    return JSONResponse(
        content=get_subgrid_predictions(),
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/api/training-pdfs")
async def list_training_pdfs():
    """List available training PDFs for the scientific dashboard."""
    if not TRAINING_PDF_DIR.exists():
        return {"files": []}

    files = sorted(
        [f for f in TRAINING_PDF_DIR.iterdir() if f.is_file() and f.suffix.lower() == ".pdf"],
        key=lambda f: f.name.lower()
    )
    return {
        "files": [
            {"name": f.name, "url": f"/api/training-pdfs/{quote(f.name)}"}
            for f in files
        ]
    }


@app.get("/api/training-pdfs/{filename}")
async def get_training_pdf(filename: str):
    """Serve a single training PDF file."""
    pdf_path = _resolve_training_pdf_path(filename)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.name,
        content_disposition_type="inline",
    )


@app.get("/health")
async def health_check():
    """Lightweight endpoint for connectivity check"""
    return {"status": "ok"}


@app.post("/api/refresh")
async def refresh():
    """Trigger background refresh"""
    asyncio.create_task(do_refresh())
    return {"status": "refresh_started"}


class ExpertRequest(BaseModel):
    taluk_id: str
    lat: float
    lon: float
    question: str = None  # Optional user question




@app.get("/api/expert-status")
async def expert_status():
    """Check if the real AI model is loaded"""
    try:
        from .expert_agent import get_expert_analysis, _expert_instance
        if _expert_instance is None:
            return {"status": "not_loaded", "message": "Model not initialized yet"}
        if _expert_instance.model is None:
            return {"status": "failed", "message": "Model failed to load"}
        return {"status": "ready", "message": "Real AI model is loaded and ready!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/ask-expert")
async def ask_expert(req: ExpertRequest):
    """
    Get analysis from the Expert AI Agent.
    If 'question' is provided, performs QA on the location context.
    Falls back to a simulated response if the model is not loaded/available.
    """
    try:
        # Try to load real expert (relative import from landsat_v2 package)
        try:
            from ..expert_agent import get_expert_analysis
        except ImportError:
            # Fallback for different run environments
            import sys
            sys.path.append(str(BASE_DIR))
            from expert_agent import get_expert_analysis
        
        # 1. Fetch the real prediction data for this ID from the scheduler cache
        from .scheduler import get_current_predictions
        preds = get_current_predictions()
        
        # Find the specific prediction
        p_data = next((p for p in preds["predictions"] if p["taluk_id"] == req.taluk_id), None)
        
        if p_data:
            # Format for Agent
            data_input = {
                "location_name": p_data.get("taluk_name", "Unknown"),
                "slope": p_data.get("slope", 0),
                "soil_type": "Laterite", # Regional characteristic
                "rainfall_mm": p_data.get("rain7", 0),
                "ndvi": 0.45 # Placeholder until GEE trend is fully integrated
            }
            # Approximate FoS from risk level for the assistant
            # (In the final version, the Physics Engine will provide this directly)
            fos_map = {"LOW": 1.4, "MEDIUM": 1.1, "HIGH": 0.8}
            fos_value = fos_map.get(p_data.get("risk_level", "LOW"), 1.2)
            fos_data = {"factor_of_safety": fos_value}
            
            # Generate REAL Analysis
            analysis = get_expert_analysis(data_input, fos_data, user_question=req.question)
            return {"analysis": analysis}
        
        # If no data found, fall to simulation
        raise ValueError(f"Location data not found for ID: {req.taluk_id}")

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"=" * 60)
        print(f"[ERROR] Expert model failed to load!")
        print(f"Error: {e}")
        print(f"Full traceback:\n{error_details}")
        print(f"=" * 60)
        print(f"Falling back to simulation mode...")
        
        # SIMULATED RESPONSE (Fallback)
        import random
        risk_level = "LOW"
        if random.random() > 0.7: risk_level = "MODERATE"
        
        # Custom answer for simulation
        # Custom answer for simulation
        if req.question:
            q_lower = req.question.lower()
            answer = ""
            
            if "build" in q_lower or "construct" in q_lower:
                answer = "Construction in this area appears feasible given the low slope angle (< 20°). However, standard foundation precautions for Laterite soil are recommended."
            elif "rain" in q_lower or "water" in q_lower:
                answer = "Recent rainfall has been minimal. There is no immediate threat of waterlogging or saturation-induced instability."
            elif "soil" in q_lower:
                answer = "The local soil is predominantly Laterite, which is generally stable but can lose cohesion under extreme saturation. Currently, it is stable."
            elif "safe" in q_lower or "risk" in q_lower:
                answer = "Based on current telemetry, the area is categorized as LOW RISK. It is considered safe for normal activities."
            else:
                answer = "Based on the geological parameters (Slope: Stable, Rainfall: Nominal), the location is currently stable. I do not detect any immediate anomalies."
            
            analysis = (
                f"{answer}\n\n"
                f"*(Simulation Mode)*"
            )
        else:
            analysis = (
                f"Based on the terrain analysis at {req.lat:.4f}, {req.lon:.4f}:\n\n"
                f"1. **Topography**: The slope is within safe limits (< 20 degrees), indicating stability.\n"
                f"2. **Soil Saturation**: Recent rainfall has been minimal, so soil pore pressure is low.\n"
                f"3. **Conclusion**: The landslide risk is currently **{risk_level}**.\n\n"
                f"*(Generated by Expert Geologist AI - Simulation Mode)*"
            )
        return {"analysis": analysis}


async def do_refresh():
    await update_predictions(skip_rainfall=False)
    await update_subgrid_predictions(skip_rainfall=False)
    await manager.broadcast({
        "type": "update",
        "taluks": get_current_predictions(),
        "subgrid": get_subgrid_predictions()
    })


@app.post("/api/ask-expert-stream")
async def ask_expert_stream(req: ExpertRequest):
    """
    Streaming endpoint: returns Llama tokens via SSE as they're generated.
    The frontend reads these with a ReadableStream / EventSource.
    """
    async def generate():
        try:
            # Ensure expert agent is ready
            if ea is None:
                 yield f"data: {json.dumps({'token': 'Error: expert_agent.py not found in path.'})}\n\n"
                 yield "data: [DONE]\n\n"
                 return

            if ea._expert_instance is None:
                ea.get_expert_analysis(
                    {"location_name": "init", "slope": 0, "soil_type": "Laterite", "rainfall_mm": 0, "ndvi": 0},
                    {"factor_of_safety": 1.5}
                )
            agent = ea._expert_instance

            # Fetch real prediction data
            from .scheduler import get_current_predictions
            preds = get_current_predictions()
            p_data = next((p for p in preds["predictions"] if p["taluk_id"] == req.taluk_id), None)

            if p_data:
                data_input = {
                    "location_name": p_data.get("taluk_name", "Unknown"),
                    "slope": p_data.get("slope", 0),
                    "soil_type": "Laterite",
                    "rainfall_mm": p_data.get("rain7", 0),
                    "ndvi": 0.45,
                    "risk_level": p_data.get("risk_level", "LOW"),
                    "probability": round(p_data.get("probability", 0) * 100, 1),
                    "swi": p_data.get("swi"),
                    "soil_saturation": p_data.get("soil_saturation"),
                    "field_capacity": p_data.get("field_capacity"),
                }
                # Use real Physics Engine for FoS
                try:
                    from physics_engine import calculate_factor_of_safety
                    sat = p_data.get("soil_saturation")
                    sat_ratio = (sat / 100.0) if sat is not None else 0.0
                    slope_deg = p_data.get("slope", 15)
                    fos_result = calculate_factor_of_safety(
                        slope_degrees=slope_deg,
                        soil_texture="Laterite",
                        saturation_ratio=sat_ratio
                    )
                    fos = fos_result["factor_of_safety"]
                except Exception as e:
                    print(f"Physics Engine error: {e}")
                    fos = 1.4

                # Format zone context string (passed to ALL questions so AI never forgets)
                zone_context = agent._format_context(data_input, fos)

                if req.question:
                    # Detect rainfall/what-if scenario questions
                    q_lower = req.question.lower()
                    rain_keywords = ["month", "week", "days", "rain", "rainfall", "monsoon", "flood", "heavy", "more rain", "what if"]
                    is_rain_scenario = any(k in q_lower for k in rain_keywords)

                    sim_note = ""
                    if is_rain_scenario:
                        from .predictor import predict_risk as _predict_risk
                        if "month" in q_lower:
                            scenario_rain = p_data.get("rain7", 0) * 4  # ~4 weeks
                        elif "week" in q_lower:
                            scenario_rain = p_data.get("rain7", 0) * 2
                        else:
                            scenario_rain = p_data.get("rain7", 0) * 3

                        # Use history for SWI-based simulation
                        scenario_history = [scenario_rain / 7.0] * 7
                        sim = _predict_risk(
                            dem=p_data.get("dem", 500),
                            slope=p_data.get("slope", 15),
                            rain7=scenario_rain,
                            history=scenario_history,
                            soil_type="Laterite"
                        )
                        sim_note = (
                            f"\n\n[SIMULATION RESULT — DO NOT IGNORE: If rainfall were {scenario_rain:.0f}mm over 7 days, "
                            f"Soil Saturation={sim.get('soil_saturation', 'N/A')}%, "
                            f"Probability={sim['probability']*100:.1f}%, "
                            f"Risk Level={sim['risk_level']}. Use these exact numbers in your answer.]"
                        )

                    token_gen = agent.stream_followup(req.question + sim_note, context=zone_context)
                else:
                    token_gen = agent.stream_analysis(data_input, fos)

                # Yield each token as an SSE data line
                for token in token_gen:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    await asyncio.sleep(0)

                yield "data: [DONE]\n\n"
            else:
                yield f"data: {json.dumps({'token': 'Error: location not found.'})}\n\n"
                yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'token': f'Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        }
    )



@app.get("/api/simulate")
async def simulate_risk(taluk_id: str, rain_mm: float):
    """What-if simulation: run predict_risk with a custom rainfall value."""
    from .scheduler import get_current_predictions
    from .predictor import predict_risk

    preds = get_current_predictions()
    p_data = next((p for p in preds["predictions"] if p["taluk_id"] == taluk_id), None)
    if not p_data:
        return JSONResponse({"error": "taluk_id not found"}, status_code=404)

    result = predict_risk(
        dem=p_data.get("dem", 500),
        slope=p_data.get("slope", 15),
        rain7=rain_mm
    )
    return {
        "taluk_id": taluk_id,
        "taluk_name": p_data.get("taluk_name"),
        "rain_mm": rain_mm,
        "probability": round(result["probability"] * 100, 1),
        "risk_level": result["risk_level"],
        "current_rain_mm": p_data.get("rain7", 0),
        "current_risk_level": p_data.get("risk_level")
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    await ws.send_json({
        "type": "init",
        "taluks": get_current_predictions(),
        "subgrid": get_subgrid_predictions()
    })
    
    try:
        while True:
            await asyncio.sleep(300)
            await ws.send_json({
                "type": "update",
                "taluks": get_current_predictions(),
                "subgrid": get_subgrid_predictions()
            })
    except WebSocketDisconnect:
        manager.disconnect(ws)


# Static files
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
