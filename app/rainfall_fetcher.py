"""
Rainfall Fetcher with Multi-Provider Support
Switches between Open-Meteo and OpenWeatherMap
"""
import httpx
from datetime import datetime
import asyncio
from .config import get_provider, get_api_key

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OWM_URL = "https://api.openweathermap.org/data/2.5/forecast"


async def fetch_open_meteo(lat: float, lon: float, client: httpx.AsyncClient) -> dict:
    """Fetch 7-day past rainfall from Open-Meteo (Free, No Key)"""
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "precipitation_sum",
        "past_days": 7,
        "forecast_days": 1, 
        "timezone": "Asia/Kolkata"
    }
    
    try:
        response = await client.get(OPEN_METEO_URL, params=params)
        
        # Handle rate limits specifically
        if response.status_code == 429:
            return {"rain7": 0.0, "history": [], "error": "Rate limit exceeded"}
            
        response.raise_for_status()
        data = response.json()
        
        daily_precip = data.get("daily", {}).get("precipitation_sum", [])
        
        # Take the past 7 days (Open-Meteo returns past + forecast list)
        # We asked for past_days=7 and forecast_days=1, so we likely get 8-9 items.
        # We just want the last 7 items (excluding today/tomorrow if needed, or including).
        # Let's verify the logical "7-day accumulated". Usually it means "Past 7 Days".
        
        # Slicing: Last 7 relevant days.
        history = daily_precip[:7] if len(daily_precip) >= 7 else daily_precip
        rain7 = sum(r for r in history if r is not None)
        
        # Replace None with 0 for history
        clean_history = [x if x is not None else 0.0 for x in history]
        
        return {"rain7": round(rain7, 2), "history": clean_history}
    except Exception as e:
        return {"rain7": 0.0, "history": [], "error": str(e)}


async def fetch_openweathermap(lat: float, lon: float, client: httpx.AsyncClient) -> dict:
    """Fetch rainfall from OpenWeatherMap (Requires Key)"""
    api_key = get_api_key()
    if not api_key:
        return {"rain7": 0.0, "history": [], "error": "API Key missing"}
        
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    
    try:
        # Uses 5-day forecast API (Free tier compatible) as proxy for "accumulated rain risk"
        response = await client.get(OWM_URL, params=params)
        
        if response.status_code == 401:
            return {"rain7": 0.0, "history": [], "error": "Invalid API Key"}
        if response.status_code == 429:
            return {"rain7": 0.0, "history": [], "error": "Rate limit exceeded"}
            
        response.raise_for_status()
        data = response.json()
        
        # Group by Day
        daily_map = {}
        
        total_rain = 0.0
        for item in data.get("list", []):
            if "rain" in item:
                val = item["rain"].get("3h", 0.0)
                total_rain += val
                
                # Date YYYY-MM-DD
                date_str = item["dt_txt"].split(" ")[0]
                daily_map[date_str] = daily_map.get(date_str, 0.0) + val
                
        # Convert map to list (sorted by date)
        sorted_days = sorted(daily_map.items())
        history = [round(val, 1) for _, val in sorted_days]
        
        # Pad if less than 7 days (since OWM only gives 5 forecast)
        while len(history) < 5:
            history.append(0.0)
                
        return {"rain7": round(total_rain, 2), "history": history}
    except Exception as e:
        return {"rain7": 0.0, "history": [], "error": str(e)}


async def fetch_rainfall_batch(locations: list) -> list:
    """
    Fetch rainfall with Grid-based Optimization
    Reduces 1533 calls to ~30 calls by grouping grouped nearby locations
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        provider = get_provider()
        use_owm = (provider.lower() == "openweathermap")
        
        # 1. Group locations by grid cell (0.2 degree ~ 22km)
        # This provides good enough local accuracy while drastically reducing API calls
        GRID_SIZE = 0.2
        grid_groups = {}
        
        for i, loc in enumerate(locations):
            # Round to nearest grid point
            grid_lat = round(loc["latitude"] / GRID_SIZE) * GRID_SIZE
            grid_lon = round(loc["longitude"] / GRID_SIZE) * GRID_SIZE
            
            key = (round(grid_lat, 2), round(grid_lon, 2))
            
            if key not in grid_groups:
                grid_groups[key] = []
            grid_groups[key].append(i)  # Store index of original location
        
        print(f"Optimized: Grouped {len(locations)} locations into {len(grid_groups)} weather grid points ({provider}).")
        
        # 2. Fetch weather for each unique grid point
        grid_weather = {}
        unique_keys = list(grid_groups.keys())
        
        batch_size = 5
        delay = 0.5
        error_count = 0
        
        for i in range(0, len(unique_keys), batch_size):
            batch_keys = unique_keys[i:i + batch_size]
            
            tasks = []
            for lat, lon in batch_keys:
                if use_owm:
                    tasks.append(fetch_openweathermap(lat, lon, client))
                else:
                    tasks.append(fetch_open_meteo(lat, lon, client))
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for key, result in zip(batch_keys, batch_results):
                if isinstance(result, Exception):
                    grid_weather[key] = {"rain7": 0.0, "error": str(result)}
                    error_count += 1
                elif isinstance(result, dict) and "error" in result:
                    grid_weather[key] = {"rain7": 0.0}
                    error_count += 1
                else:
                    grid_weather[key] = result
            
            if i + batch_size < len(unique_keys):
                await asyncio.sleep(delay)
        
        if error_count > 0:
            print(f"⚠ {error_count}/{len(unique_keys)} grid points failed (using rain=0 for those)")
        
        # 3. Assign grid weather back to original locations
        final_results = [None] * len(locations)
        
        for key, indices in grid_groups.items():
            weather = grid_weather.get(key, {"rain7": 0.0})
            for idx in indices:
                final_results[idx] = weather
                
        return final_results
