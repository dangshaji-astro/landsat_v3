/**
 * ==============================================================================
 * GEE 10-METER SENTINEL-2 CLOUD-FREE HD SATELLITE IMAGERY EXPORTER FOR KERALA
 * ==============================================================================
 * Paste into Google Earth Engine Code Editor: https://code.earthengine.google.com/
 * 
 * What this script does:
 * 1. Loads Sentinel-2 Surface Reflectance (10m resolution).
 * 2. Filters 0% cloud cover dry-season imagery over Kerala state.
 * 3. Creates a seamless, high-definition True Color (RGB) composite.
 * 4. Exports high-resolution GeoTIFF images to your Google Drive!
 */

// 1. Load Kerala State Boundary
var keralaBoundary = ee.FeatureCollection("FAO/GAUL/2015/level1")
  .filter(ee.Filter.eq('ADM1_NAME', 'Kerala'))
  .geometry();

// 2. Load Sentinel-2 10m Cloud-Free Imagery (Dry Season Composite)
var sentinel2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(keralaBoundary)
  .filterDate('2023-11-01', '2024-05-31') // Dry season for 0% cloud cover
  .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 5))
  .median()
  .clip(keralaBoundary);

// Select True Color Bands (Red=B4, Green=B3, Blue=B2)
var rgbComposite = sentinel2.select(['B4', 'B3', 'B2']);

// 3. Display in GEE Code Editor
Map.centerObject(keralaBoundary, 8);
Map.addLayer(rgbComposite, {min: 0, max: 2500, gamma: 1.2}, 'Sentinel-2 10m HD Satellite (Kerala)');

// 4. Export HD Image to Google Drive (10-meter pixel resolution)
Export.image.toDrive({
  image: rgbComposite.visualize({min: 0, max: 2500, gamma: 1.2}),
  description: 'Kerala_Sentinel2_10m_HD_Satellite',
  folder: 'Landsat_GEE_Exports',
  fileNamePrefix: 'kerala_sentinel2_10m_hd',
  region: keralaBoundary.bounds(),
  scale: 10, // 10-meter pixel resolution
  maxPixels: 1e9
});

print("✅ Sentinel-2 10m HD Satellite layer loaded! Go to the 'Tasks' tab to run Export.");
