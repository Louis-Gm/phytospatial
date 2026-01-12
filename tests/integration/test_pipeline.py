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
    # Create a raster with 3 bands: Red, Green, NIR
    raster_path = mock_raster_factory(
        "hyperspectral.tif", 
        count=3, 
        descriptions=["Red", "Green", "NIR"],
        crs="EPSG:32619"
    )
    # Create crowns: one near a point, one far away
    far_poly = box(100, 100, 102, 102)
    crown_poly = box(0, 8, 2, 10)
    
    crowns_path = mock_vector_factory(
        "crowns.shp", 
        geometries=[crown_poly, far_poly],
        attributes={'orig_id': [101, 102]}
    )
    # Create ground truth points: one close to first crown, one far away
    p1 = Point(1, 9) 
    points_path = mock_vector_factory(
        "field_data.geojson",
        geometries=[p1],
        attributes={'species_code': ['ACESA']}
    )

    gdf_crowns = loaders.load_crowns(crowns_path, id_col="orig_id")
    
    assert len(gdf_crowns) == 2
    assert "crown_id" in gdf_crowns.columns

    gdf_points = gpd.read_file(points_path)
    
    # Label crowns with species from points
    labeled_crowns = vector.label_crowns(
        gdf_crowns, 
        gdf_points, 
        label_col="species_code", 
        max_dist=2.0
    )

    assert labeled_crowns.loc[101, 'species'] == 'ACESA'
    assert pd.isna(labeled_crowns.loc[102, 'species'])

    extractor = extract.BlockExtractor(
        raster_path, 
        band_names=["Red", "Green", "NIR"]
    )
    # Extract statistics per crown
    results = list(extractor.process_crowns(labeled_crowns))
    extractor.close()

    assert len(results) >= 1 
    stats = results[0]
    assert stats['crown_id'] == 101
    assert stats['species'] == 'ACESA'
    assert "hyperspectral_Red_mean" in stats
    assert "hyperspectral_NIR_mean" in stats
    assert isinstance(stats['hyperspectral_Red_mean'], float)

def test_pipeline_crs_handling(tmp_path, mock_raster_factory, mock_vector_factory):
    """
    Test Integration of Reprojection + Extraction.
    Scenario: User has Lat/Lon crowns but a UTM raster. 
    The Extractor should handle the reprojection automatically.
    """
    # Create a raster in UTM
    raster_path = mock_raster_factory("utm_image.tif", crs="EPSG:32619")
    
    # Create crowns in WGS84
    crown_poly = Polygon([(0,0), (0,0.0001), (0.0001, 0.0001), (0.0001, 0)])
    crowns_path = mock_vector_factory("wgs84_crowns.shp", [crown_poly], crs="EPSG:4326")
    gdf_crowns = loaders.load_crowns(crowns_path)
    
    # Extract spectral stats
    extractor = extract.BlockExtractor(raster_path)
    results = list(extractor.process_crowns(gdf_crowns))
    extractor.close()
    
    # Verify extraction occurred without errors
    assert isinstance(results, list)