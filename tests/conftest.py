# tests/conftest.py

import pytest
import numpy as np
import geopandas as gpd
from shapely.geometry import Point, Polygon
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS

@pytest.fixture
def source_envi_path(tmp_path):
    """
    Fixture: Creates a synthetic ENVI file (.hdr + binary) in a temp dir.
    This strictly simulates the 'RAW_HDR' input format.
    """
    p = tmp_path / "synthetic_raw"
    
    width, height = 100, 100
    transform = Affine.translation(0, 1) * Affine.scale(0.01, -0.01)
    crs = CRS.from_epsg(4326)
    
    data = np.zeros((3, height, width), dtype='float32')
    data[0] = np.linspace(0, 1, width * height).reshape(height, width) # Gradient
    data[1] = np.random.rand(height, width) # Noise
    data[2].fill(0.5)
    
    profile = {
        'driver': 'ENVI', 
        'height': height,
        'width': width,
        'count': 3,
        'dtype': 'float32',
        'crs': crs,
        'transform': transform
    }

    with rasterio.open(p, 'w', **profile) as dst:
        dst.write(data)
        
    return p.with_suffix(".hdr") # tests the resolve_envi_path logic

@pytest.fixture
def valid_crown_poly():
    """Returns a simple square polygon."""
    return Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])

@pytest.fixture
def invalid_crown_poly():
    """Returns a self-intersecting 'bowtie' polygon."""
    # (0,0) -> (10,10) -> (0,10) -> (10,0) crosses itself
    return Polygon([(0, 0), (10, 10), (0, 10), (10, 0)])

@pytest.fixture
def crowns_gdf(valid_crown_poly):
    """Creates a basic GeoDataFrame with one valid crown."""
    return gpd.GeoDataFrame(
        {'id': [1], 'species': ['Abies'], 'geometry': [valid_crown_poly]},
        crs="EPSG:32619"
    )

@pytest.fixture
def shapefile_path(tmp_path, crowns_gdf):
    """Saves the basic crowns GDF to a shapefile and returns the path."""
    path = tmp_path / "crowns.shp"
    crowns_gdf.to_file(path)
    return str(path)

@pytest.fixture
def rich_gdf(valid_crown_poly):
    """
    Returns a GDF with multiple features and attributes 
    to test filtering and selection in Vector tests.
    """
    poly1 = valid_crown_poly
    # Create a second polygon offset by 20 units
    poly2 = Polygon([(20, 20), (30, 20), (30, 30), (20, 30)])
    
    return gpd.GeoDataFrame(
        {
            'crown_id': [1, 2],
            'species': ['Abies', 'Picea'],
            'height': [15.5, 22.0],
            'geometry': [poly1, poly2]
        },
        crs="EPSG:32619"
    )