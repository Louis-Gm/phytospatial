# tests/unit/test_extract.py

import pytest
import rasterio
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, box
from phytospatial import extract

def test_compute_basic_stats_logic():
    """Verify the math of the helper function independently."""
    pixels = np.array([1, 5, 9])
    stats = extract.compute_basic_stats(pixels, prefix="test")
    
    assert stats['test_mean'] == 5.0
    assert stats['test_min'] == 1.0
    assert stats['test_max'] == 9.0
    assert stats['test_med'] == 5.0
    assert abs(stats['test_sd'] - 3.2659) < 0.001

def test_compute_stats_empty_input():
    pixels = np.array([])
    stats = extract.compute_basic_stats(pixels, prefix="test")
    assert stats == {}

def test_extractor_initialization(tmp_path, mock_raster_factory):
    """Test that the class loads metadata correctly."""
    path = mock_raster_factory("init_test.tif", count=3)
    
    extractor = extract.BlockExtractor(path, band_names=["R", "G", "B"])
    
    assert extractor.name == "init_test"
    assert len(extractor.read_indices) == 3
    assert extractor.band_names == ["R", "G", "B"]
    extractor.close()

def test_extraction_perfect_alignment(tmp_path, mock_raster_factory):
    """
    Create a raster with constant value 100.
    Place a square polygon exactly over some pixels.
    Expect exact stats.
    """
    path = mock_raster_factory("const_100.tif", count=1, crs="EPSG:32619")
    
    import rasterio
    with rasterio.open(path, 'r+') as dst:
        dst.write(np.full((1, 10, 10), 100, dtype=np.uint8))

    poly = box(0, 8, 2, 10) 
    
    crowns = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [poly]}, 
        crs="EPSG:32619"
    )

    extractor = extract.BlockExtractor(path, band_names=["Band1"])
    results = list(extractor.process_crowns(crowns))
    extractor.close()
    
    assert len(results) == 1
    stats = results[0]
    
    assert stats['const_100_Band1_mean'] == 100.0
    assert stats['const_100_Band1_min'] == 100.0

def test_extraction_threshold_filtering(tmp_path, mock_raster_factory):
    """Ensure pixels below threshold (e.g. shadow/background) are ignored."""
    path = mock_raster_factory("threshold.tif", count=1, crs="EPSG:32619")
    
    data = np.zeros((1, 10, 10), dtype=np.uint8)
    data[0, 0:3, 0:3] = [[200, 200, 10], 
                         [200, 200, 0], 
                         [200, 200, 200]]
    
    with rasterio.open(path, 'r+') as dst:
        dst.write(data)
        
    poly = box(0, 7, 3, 10)
    crowns = gpd.GeoDataFrame({'crown_id': [1], 'geometry': [poly]}, crs="EPSG:32619")
    
    extractor = extract.BlockExtractor(path, band_names=["B1"])
    results = list(extractor.process_crowns(crowns, threshold=15))
    extractor.close()
    
    stats = results[0]
    
    assert stats['threshold_B1_min'] == 200.0
    assert stats['threshold_B1_mean'] == 200.0

def test_extraction_raw_pixels(tmp_path, mock_raster_factory):
    """Test return_raw_pixels=True mode."""
    path = mock_raster_factory("raw.tif", count=1, crs="EPSG:32619")
    
    data = np.zeros((1, 10, 10), dtype=np.uint8)
    data[0, 0, 0] = 1
    data[0, 0, 1] = 2
    data[0, 1, 0] = 3
    
    with rasterio.open(path, 'r+') as dst:
        dst.write(data)
    
    poly = box(0, 8, 2, 10)
    crowns = gpd.GeoDataFrame({'crown_id': [1], 'geometry': [poly]}, crs="EPSG:32619")
    
    extractor = extract.BlockExtractor(path, band_names=["B1"], return_raw_pixels=True)
    results = list(extractor.process_crowns(crowns, threshold=0))
    extractor.close()
    
    raw_vals = results[0]['raw_B1_values']
    
    assert isinstance(raw_vals, list)
    assert 1 in raw_vals
    assert 2 in raw_vals
    assert 3 in raw_vals

def test_crs_mismatch_warning(tmp_path, mock_raster_factory, caplog):
    """Test that it warns and reprojects if CRSs don't match."""
    path = mock_raster_factory("crs_test.tif", crs="EPSG:32619")
    
    poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    crowns = gpd.GeoDataFrame({'crown_id': [1], 'geometry': [poly]}, crs="EPSG:4326")
    
    extractor = extract.BlockExtractor(path)

    list(extractor.process_crowns(crowns))
    extractor.close()
    
    assert "Reprojecting crowns" in caplog.text