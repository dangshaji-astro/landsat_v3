/**
 * ==============================================================================
 * GOOGLE EARTH ENGINE (GEE) 1KM SUB-GRID LANDSLIDE FEATURE EXTRACTOR (KERALA ONLY)
 * ==============================================================================
 * Copy and paste this code directly into the Google Earth Engine Code Editor:
 * https://code.earthengine.google.com/
 *
 * What this script does:
 * 1. Loads official FAO GAUL Administrative Boundary for KERALA STATE ONLY.
 * 2. Creates a 1 km x 1 km Sub-Grid Mesh strictly clipped to Kerala's borders.
 * 3. Ingests SRTM 30m DEM elevation and computes slope.
 * 4. Ingests USDA Soil Texture Class (OpenLandMap).
 * 5. Extracts dem_avg, slope_max, slope_avg, and soil_code for every 1km cell in Kerala.
 * 6. Visualizes Kerala layers and exports GeoJSON to your Google Drive.
 */

// =============================================================================
// 1. DEFINE KERALA STATE BOUNDARY (OFFICIAL FAO GAUL BOUNDARY)
// =============================================================================
var keralaBoundary = ee.FeatureCollection("FAO/GAUL/2015/level1")
  .filter(ee.Filter.eq('ADM1_NAME', 'Kerala'))
  .geometry();

var keralaBounds = keralaBoundary.bounds();

// =============================================================================
// 2. LOAD SATELLITE DATASETS (CLIPPED TO KERALA)
// =============================================================================

// SRTM 30m Digital Elevation Model
var dem = ee.Image("USGS/SRTMGL1_003").select('elevation').clip(keralaBoundary);

// Slope in degrees
var slope = ee.Terrain.slope(dem);

// USDA Soil Texture Class from OpenLandMap (0–5cm depth)
var soilTexture = ee.Image("OpenLandMap/SOL/SOL_TEXTURE-CLASS_USDA-TT_M/v02")
  .select('b0')
  .clip(keralaBoundary);

// =============================================================================
// 3. BUILD 1 KM x 1 KM SUB-GRID MESH (FILTERED STRICTLY WITHIN KERALA)
// =============================================================================
var cellSize = 0.009; // 0.009 degrees ≈ 1 km

// Extract bounding coordinates of Kerala
var boundsCoords = ee.List(keralaBounds.coordinates().get(0));
var minPt = ee.List(boundsCoords.get(0));
var maxPt = ee.List(boundsCoords.get(2));

var minLon = ee.Number(minPt.get(0));
var minLat = ee.Number(minPt.get(1));
var maxLon = ee.Number(maxPt.get(0));
var maxLat = ee.Number(maxPt.get(1));

var lonList = ee.List.sequence(minLon, maxLon.subtract(cellSize), cellSize);
var latList = ee.List.sequence(minLat, maxLat.subtract(cellSize), cellSize);

var gridCells = lonList.map(function(lon) {
  return latList.map(function(lat) {
    var x1 = ee.Number(lon);
    var y1 = ee.Number(lat);
    var x2 = x1.add(cellSize);
    var y2 = y1.add(cellSize);

    var coords = ee.List([x1, y1, x2, y2]);
    var cellGeom = ee.Geometry.Rectangle(coords, null, false);

    return ee.Feature(cellGeom, {
      'cell_id': ee.String('CELL_').cat(x1.format('%.3f')).cat('_').cat(y1.format('%.3f')),
      'center_lon': x1.add(cellSize / 2),
      'center_lat': y1.add(cellSize / 2)
    });
  });
}).flatten();

// Filter grid cells strictly within Kerala State Boundary (eliminates Tamil Nadu, Karnataka, and Ocean)
var gridFC = ee.FeatureCollection(gridCells).filterBounds(keralaBoundary);

// =============================================================================
// 4. EXTRACT TERRAIN FEATURES PER 1KM CELL IN KERALA
// =============================================================================
var enrichedGrid = gridFC.map(function(feature) {
  var geom = feature.geometry();

  // DEM Mean (elevation)
  var demStats = dem.reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: geom,
    scale: 30,
    maxPixels: 1e5,
    bestEffort: true
  });

  // Slope Max (peak steepness) & Slope Mean
  var slopeStats = slope.reduceRegion({
    reducer: ee.Reducer.max().combine({
      reducer2: ee.Reducer.mean(),
      sharedInputs: true
    }),
    geometry: geom,
    scale: 30,
    maxPixels: 1e5,
    bestEffort: true
  });

  // Dominant Soil Texture Class
  var soilStats = soilTexture.reduceRegion({
    reducer: ee.Reducer.mode(),
    geometry: geom,
    scale: 250,
    maxPixels: 1e5,
    bestEffort: true
  });

  // Extract safely with null checks
  var demMean = ee.Number(ee.Algorithms.If(
    demStats.contains('elevation'), demStats.get('elevation'), null
  ));

  var slopeMax = ee.Number(ee.Algorithms.If(
    slopeStats.contains('slope_max'), slopeStats.get('slope_max'), 0
  ));

  var slopeMean = ee.Number(ee.Algorithms.If(
    slopeStats.contains('slope_mean'), slopeStats.get('slope_mean'), 0
  ));

  var rawSoil = soilStats.get('b0');
  var soilCode = ee.Number(ee.Algorithms.If(
    ee.Algorithms.IsEqual(rawSoil, null), -1, rawSoil
  )).int();

  return feature.set({
    'dem_avg'   : demMean,
    'slope_max' : slopeMax,
    'slope_avg' : slopeMean,
    'soil_code' : soilCode,
    'state'     : 'Kerala'
  });
});

// Strictly keep land cells inside Kerala with valid DEM data
var keralaGrid = enrichedGrid.filter(ee.Filter.notNull(['dem_avg']));

// =============================================================================
// 5. VISUALIZATION
// =============================================================================
Map.centerObject(keralaBoundary, 8);

Map.addLayer(
  dem,
  {min: 0, max: 2000, palette: ['blue', 'green', 'yellow', 'orange', 'white']},
  'Kerala SRTM DEM (30m)'
);

Map.addLayer(
  slope,
  {min: 0, max: 60, palette: ['green', 'yellow', 'orange', 'red']},
  'Kerala Slope Angle (degrees)'
);

// Print total count to GEE Console
print('Total 1km grid cells strictly inside Kerala state:', keralaGrid.size());

// =============================================================================
// 6. EXPORT TO GOOGLE DRIVE
// =============================================================================
Export.table.toDrive({
  collection: keralaGrid,
  description: 'Kerala_Only_1km_Subgrid_Geospatial_Data',
  folder: 'Landsat_GEE_Exports',
  fileNamePrefix: 'kerala_only_1km_subgrid',
  fileFormat: 'GeoJSON'
});

print("✅ Kerala-only export task created! Go to 'Tasks' tab (top right) and click RUN.");
