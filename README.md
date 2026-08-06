# Kerala Landslide Risk Monitor - Model 2 (Expert Geologist)

This is the **Enhanced Version** with the Expert Geologist AI system.

## 🆕 What's New in Model 2

### The Dual-Model Architecture
1.  **Model 1 (The Sentinel)**: Fast real-time monitoring (same as before).
2.  **Model 2 (The Expert)**: Deep analysis with satellite data + physics + AI explanation.

## 📊 New Data Sources

### Google Earth Engine Integration
-  **Land Cover**: Forest, Urban, Agriculture detection (ESA WorldCover).
-  **Soil Data**: Texture and type from OpenLandMap.
-  **5-Year NDVI**: Vegetation health trend to detect deforestation.
-  **Soil Moisture**: Live saturation data from NASA SMAP.

## 🧮 New Capabilities

### Physics Engine
-  Calculates **Factor of Safety (FoS)** using slope stability equations.
-  Estimates shear strength based on soil properties.

### AI Analyst
-  Fine-tuned LLM trained on Kerala landslide reports.
-  Provides natural language explanations of WHY risk is high.
-  Proactive forecasting: "If rain continues for X days..."

## Setup (Model 2)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Authenticate Google Earth Engine
```bash
earthengine authenticate
```

Follow the prompts to log in with your Google account.

### 3. Test the Data Collector
```bash
python data_collector.py
```

This will fetch satellite data for Wayanad and display a report.

## Project Structure

```
landsat_v2/
├── app/                    # Model 1 backend (unchanged)
├── frontend/               # Web UI
├── data/                   # GeoJSON files
├── gee_tools.py           # 🆕 Google Earth Engine connector
├── data_collector.py      # 🆕 Data aggregator
├── physics_engine.py      # 🆕 Slope stability calculator (Coming Soon)
├── expert_agent.py        # 🆕 LLM interface (Coming Soon)
└── training datasets/      # PDF reports for AI training
```

## Current Status

### ✅ Phase 1: The Eyes (Data Collector) - COMPLETE
-  GEE integration working
-  LULC, Soil, NDVI, Moisture fetching

### ✅ Phase 2: The Calculator (Physics Engine) - COMPLETE
-  Soil property database (12 USDA soil types)
-  Factor of Safety calculation (Infinite Slope Model)
-  Future rain simulation ("What if?" forecasting)

### ⏳ Phase 3: The Brain (AI Training) - NEXT
-  PDF text extraction from GSI reports
-  Dataset generation
-  LoRA fine-tuning

## How to Test

### Test Physics Engine
```bash
cd landsat_v2
python physics_engine.py
```

### Test Complete Integration
```bash
python test_integration.py
```

This will generate a full Expert Report for Wayanad (requires GEE authentication).

## Next Steps

1.  Extract training data from GSI PDF reports (`training datasets/training pdfs/`).
2.  Generate synthetic Q&A pairs for LLM training.
3.  Fine-tune a small LLM (Llama/Mistral) using LoRA.
4.  Add "Ask Expert" UI button to frontend.
