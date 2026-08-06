"""
Google Earth Engine Data Tools
Fetches satellite data for Expert Geologist Model
"""
import ee
from typing import Dict, List, Optional
from datetime import datetime, timedelta


class GEEDataCollector:
    """Collects satellite data from Google Earth Engine"""
    
    def __init__(self):
        """Initialize and authenticate with GEE"""
        try:
            ee.Initialize()
        except Exception as e:
            print(f"GEE Initialization failed: {e}")
            print("Run: earthengine authenticate")
    
    def get_land_cover(self, lat: float, lon: float) -> Dict:
        """
        Fetch Land Use/Land Cover (LULC) for a point
        Uses ESA WorldCover 10m 2021 dataset
        """
        point = ee.Geometry.Point([lon, lat])
        
        # ESA WorldCover dataset
        worldcover = ee.ImageCollection("ESA/WorldCover/v200").first()
        
        # Sample the point
        lulc_value = worldcover.sample(point, 10).first().get('Map').getInfo()
        
        # Classification mapping
        lulc_classes = {
            10: "Tree Cover",
            20: "Shrubland",
            30: "Grassland",
            40: "Cropland",
            50: "Built-up",
            60: "Bare/Sparse Vegetation",
            70: "Snow and Ice",
            80: "Water Bodies",
            90: "Herbaceous Wetland",
            95: "Mangroves",
            100: "Moss and Lichen"
        }
        
        return {
            "land_cover": lulc_classes.get(lulc_value, "Unknown"),
            "raw_value": lulc_value
        }
    
    def get_soil_properties(self, lat: float, lon: float) -> Dict:
        """
        Fetch Soil Type and Properties
        Uses OpenLandMap Soil Texture dataset
        """
        point = ee.Geometry.Point([lon, lat])
        
        # Soil Texture (Clay/Sand/Silt content)
        clay = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02") \
            .select('b0').sample(point, 250).first().get('b0').getInfo()
        
        # Soil texture classes (USDA)
        texture_map = {
            1: "Clay",
            2: "Silty Clay",
            3: "Sandy Clay",
            4: "Clay Loam",
            5: "Silty Clay Loam",
            6: "Sandy Clay Loam",
            7: "Loam",
            8: "Silty Loam",
            9: "Sandy Loam",
            10: "Silt",
            11: "Loamy Sand",
            12: "Sand"
        }
        
        return {
            "soil_texture": texture_map.get(clay, "Unknown"),
            "raw_value": clay
        }
    
    def get_ndvi_trend(self, lat: float, lon: float, years: int = 5) -> Dict:
        """
        Get NDVI (Vegetation health) trend for past N years
        Uses Sentinel-2 data
        """
        point = ee.Geometry.Point([lon, lat])
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years*365)
        
        # Sentinel-2 collection
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(point) \
            .filterDate(start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
        
        def calculate_ndvi(image):
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return image.addBands(ndvi)
        
        ndvi_collection = s2.map(calculate_ndvi).select('NDVI')
        
        # Get yearly averages
        yearly_ndvi = []
        for year in range(years):
            year_start = (end_date - timedelta(days=(years-year)*365)).strftime('%Y-%m-%d')
            year_end = (end_date - timedelta(days=(years-year-1)*365)).strftime('%Y-%m-%d')
            
            yearly_mean = ndvi_collection \
                .filterDate(year_start, year_end) \
                .mean() \
                .sample(point, 10) \
                .first()
            
            if yearly_mean:
                ndvi_val = yearly_mean.get('NDVI').getInfo()
                yearly_ndvi.append({
                    "year": int(year_start[:4]),
                    "ndvi": round(ndvi_val, 3) if ndvi_val else None
                })
        
        # Calculate trend (degradation?)
        if len(yearly_ndvi) >= 2 and yearly_ndvi[0]['ndvi'] and yearly_ndvi[-1]['ndvi']:
            change = yearly_ndvi[-1]['ndvi'] - yearly_ndvi[0]['ndvi']
            change_percent = (change / yearly_ndvi[0]['ndvi']) * 100
        else:
            change_percent = 0
        
        return {
            "yearly_data": yearly_ndvi,
            "change_percent": round(change_percent, 1),
            "degradation_detected": change_percent < -15  # 15% loss is critical
        }
    
    def get_soil_moisture(self, lat: float, lon: float) -> Dict:
        """
        Get current soil moisture from NASA SMAP
        """
        point = ee.Geometry.Point([lon, lat])
        
        # NASA SMAP Soil Moisture
        smap = ee.ImageCollection('NASA/SMAP/SPL4SMGP/007') \
            .filterDate(ee.Date(datetime.now() - timedelta(days=7)), ee.Date(datetime.now())) \
            .select('sm_surface') \
            .mean()
        
        moisture = smap.sample(point, 10000).first()
        
        if moisture:
            sm_value = moisture.get('sm_surface').getInfo()
            return {
                "soil_moisture_m3m3": round(sm_value, 3) if sm_value else None,
                "saturation_level": "High" if sm_value and sm_value > 0.35 else "Normal"
            }
        
        return {"soil_moisture_m3m3": None, "saturation_level": "Unknown"}


def fetch_location_context(lat: float, lon: float) -> Dict:
    """
    Main function: Fetch all satellite data for a location
    """
    collector = GEEDataCollector()
    
    return {
        "coordinates": {"lat": lat, "lon": lon},
        "land_cover": collector.get_land_cover(lat, lon),
        "soil": collector.get_soil_properties(lat, lon),
        "ndvi_trend": collector.get_ndvi_trend(lat, lon, years=5),
        "soil_moisture": collector.get_soil_moisture(lat, lon),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    # Test with Wayanad coordinates
    print("Testing GEE Data Collector...")
    data = fetch_location_context(11.6, 76.1)
    
    import json
    print(json.dumps(data, indent=2))
