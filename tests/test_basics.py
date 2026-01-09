# tests/test_basics.py
import numpy as np
import pytest
import geopandas as gpd
from shapely.geometry import Polygon, Point
from phytospatial import extract, raster, vector, loaders

def test_imports():
    """Simple smoke test to ensure modules import correctly."""
    assert extract is not None
    assert raster is not None
    assert vector is not None
    assert loaders is not None

def test_compute_stats():
    """
    Module: extract
    Function: compute_basic_stats
    Test: logic verification on dummy pixels (no file needed).
    """
    dummy_pixels = np.array([1, 2, 3, 4, 5])
    stats = extract.compute_basic_stats(dummy_pixels, prefix="test")
    
    assert stats['test_max'] == 5.0
    assert stats['test_mean'] == 3.0
    assert 'test_sd' in stats

def test_loaders_io(tmp_path):
    """
    Module: loaders
    Function: load_crowns
    Test: Saves a dummy GeoJSON and verifies loader reads/cleans it.
    """
    d = {'col1': ['name1'], 'geometry': [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:4326")
    
    fake_file = tmp_path / "test_crowns.geojson"
    gdf.to_file(fake_file, driver="GeoJSON")
    
    loaded_gdf = loaders.load_crowns(str(fake_file))
    
    assert len(loaded_gdf) == 1
    assert "crown_id" in loaded_gdf.columns

def test_vector_labeling(tmp_path):
    """
    Module: vector
    Function: label_crowns
    Test: Creates dummy crown and point files to test spatial join logic.
    """
    crown_geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    
    crowns = gpd.GeoDataFrame({
        'crown_id': [1], 
        'geometry': [crown_geom],
        'species': [None] 
    }, crs="EPSG:32619")
    
    point_geom = Point(0.5, 0.5)
    points = gpd.GeoDataFrame({'species': ['Oak'], 'geometry': [point_geom]}, crs="EPSG:32619")
    
    points_path = tmp_path / "points.geojson"
    points.to_file(points_path, driver="GeoJSON")
    
    result = vector.label_crowns(crowns, str(points_path), label_col='species')
    
    assert 'species' in result.columns
    assert result.iloc[0]['species'] == 'Oak'

def test_raster_empty_run(tmp_path):
    """
    Module: raster
    Function: convert_envi_to_geotiff
    Test: Runs the batch converter on an empty directory to ensure it doesn't crash.
    """
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    
    raster.convert_envi_to_geotiff(str(input_dir), str(output_dir))
    
    assert output_dir.exists()