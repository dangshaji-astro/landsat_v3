# Google Earth Engine Setup Guide

## What is Google Earth Engine (GEE)?
GEE is a cloud platform that hosts petabytes of satellite imagery from NASA, ESA, and other sources. It allows us to fetch real-time environmental data like vegetation health, land cover, and soil moisture.

## Why Do We Need It?
For **Model 2 (Expert Geologist)**, we need:
1.  **Land Cover**: Is it forest or farmland?
2.  **5-Year Vegetation Trend**: Has deforestation occurred?
3.  **Soil Type**: Clay or Sand?
4.  **Soil Moisture**: Is the ground saturated?

This data makes our predictions scientifically accurate.

## Setup Steps

### 1. Install the Python API
Already included in `requirements.txt`. If you haven't installed dependencies yet:
```bash
pip install earthengine-api
```

### 2. Authenticate
Run this command in your terminal:
```bash
earthengine authenticate
```

**What happens:**
- A browser window will open.
- Sign in with your **Google Account** (any Gmail account works).
- Click "Allow" to grant access.
- Copy the authorization code and paste it back into the terminal.

### 3. Test the Connection
Run the test script:
```bash
cd landsat_v2
python gee_tools.py
```

**Expected Output:**
```json
{
  "coordinates": {"lat": 11.6, "lon": 76.1},
  "land_cover": {"land_cover": "Tree Cover"},
  "soil": {"soil_texture": "Clay Loam"},
  "ndvi_trend": {
    "change_percent": -12.3,
    "degradation_detected": false
  }
}
```

## Troubleshooting

### Error: "Please authenticate"
**Solution:** Run `earthengine authenticate` again.

### Error: "No data available"
**Possible Causes:**
- Location is outside satellite coverage (unlikely for Kerala).
- Cloud cover is too high (try a different date range).

### Error: "Quota exceeded"
**Solution:** GEE has usage limits. Wait 24 hours or use a different Google account.

## Data Sources Used

1.  **ESA WorldCover 10m** - Land Use/Land Cover (2021)
2.  **OpenLandMap Soil Texture** - USDA Classification
3.  **Sentinel-2 SR** - NDVI for vegetation health
4.  **NASA SMAP** - Soil Moisture (9km resolution)

All data is freely available and updated regularly.
