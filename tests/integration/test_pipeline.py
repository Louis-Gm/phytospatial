# tests/integration/test_pipeline.py

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, Point, box
from phytospatial import loaders, vector, raster, extract

def test_full_spectral_extraction_pipeline(tmp_path, mock_raster_factory, mock_vector_factory):
    """
    Simulates a standard user workflow:
    1. Prepare Data: Have a raster and a shapefile of tree crowns.
    2. Load: Load and clean the vectors.
    3. Enrich: Label the trees using ground truth GPS points.
    4. Extract: Get spectral statistics for each labeled tree.
    """
    
    # --- 1. SETUP DATA (Simulating files on disk) ---
    
    # Create a 3-band "Hyperspectral" Raster (10x10 pixels)
    # CRS: UTM Zone 19N (EPSG:32619)
    raster_path = mock_raster_factory(
        "hyperspectral.tif", 
        count=3, 
        descriptions=["Red", "Green", "NIR"],
        crs="EPSG:32619"
    )

    # Create Tree Crowns (Vectors)
    # Place one crown perfectly in the top-left corner (0,0 to 2,2)
    # Place another one far away (should have valid geometry but might have 0 pixels)
    crown_poly = box(0, 8, 2, 10) # 2x2 pixel box in top-left (Raster coords are flipped Y)
    far_poly = box(100, 100, 102, 102)
    
    crowns_path = mock_vector_factory(
        "crowns.shp", 
        geometries=[crown_poly, far_poly],
        attributes={'orig_id': [101, 102]}
    )

    # Create Ground Truth Points (for labeling)
    # Place a point inside the first crown
    p1 = Point(1, 9) 
    points_path = mock_vector_factory(
        "field_data.geojson",
        geometries=[p1],
        attributes={'species_code': ['ACESA']} # Sugar Maple
    )

    # --- 2. THE PIPELINE EXECUTION ---

    # A. Load & Validate Crowns
    # User loads raw shapefile, specifying which column is the ID
    gdf_crowns = loaders.load_crowns(crowns_path, id_col="orig_id")
    
    assert len(gdf_crowns) == 2
    assert "crown_id" in gdf_crowns.columns

    # B. Label Crowns Spatially
    # User loads points and joins them to crowns
    gdf_points = gpd.read_file(points_path)
    
    labeled_crowns = vector.label_crowns(
        gdf_crowns, 
        gdf_points, 
        label_col="species_code", 
        max_dist=2.0
    )
    
    # Check that labeling worked
    # The first tree (101) should match the point 'ACESA'
    assert labeled_crowns.loc[101, 'species'] == 'ACESA'
    # The second tree (102) is too far, should be None/NaN
    assert pd.isna(labeled_crowns.loc[102, 'species'])

    # C. Extract Spectra
    # User initializes extractor on the raster
    extractor = extract.BlockExtractor(
        raster_path, 
        band_names=["Red", "Green", "NIR"]
    )
    
    # Run extraction
    results = list(extractor.process_crowns(labeled_crowns))
    extractor.close()

    # --- 3. FINAL VALIDATION ---

    # We expect results only for the tree that overlaps the raster
    # Tree 102 is at (100, 100), raster is only 10x10, so it should be skipped or return empty stats
    # The extractor logic usually yields a dict if pixels are found.
    assert len(results) >= 1 
    
    stats = results[0]
    
    # Check Data Integrity
    assert stats['crown_id'] == 101
    assert stats['species'] == 'ACESA'
    
    # Check Spectral Data
    # We expect keys like "hyperspectral_Red_mean", "hyperspectral_NIR_max"
    assert "hyperspectral_Red_mean" in stats
    assert "hyperspectral_NIR_mean" in stats
    
    # Verify values are numeric
    assert isinstance(stats['hyperspectral_Red_mean'], float)

def test_pipeline_crs_handling(tmp_path, mock_raster_factory, mock_vector_factory):
    """
    Test Integration of Reprojection + Extraction.
    Scenario: User has Lat/Lon crowns but a UTM raster. 
    The Extractor should handle the reprojection automatically.
    """
    # Raster in UTM
    raster_path = mock_raster_factory("utm_image.tif", crs="EPSG:32619")
    
    # Crowns in Lat/Lon (WGS84)
    # We create a dummy polygon. The actual coordinates don't map perfectly 
    # to the mock raster, we just want to ensure the pipeline runs without crashing.
    crown_poly = Polygon([(0,0), (0,0.0001), (0.0001, 0.0001), (0.0001, 0)])
    crowns_path = mock_vector_factory("wgs84_crowns.shp", [crown_poly], crs="EPSG:4326")
    
    # Pipeline
    gdf_crowns = loaders.load_crowns(crowns_path)
    
    extractor = extract.BlockExtractor(raster_path)
    
    # This should trigger the internal .to_crs() warning in extract.py
    # and finish without error (yielding 0 results because of no overlap is fine)
    results = list(extractor.process_crowns(gdf_crowns))
    extractor.close()
    
    # Verification: Use caplog if you want to be strict, but running without error is a good baseline.
    assert isinstance(results, list)