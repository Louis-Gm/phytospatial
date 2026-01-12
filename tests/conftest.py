# tests/conftest.py

import pytest
import rasterio
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon, Point
from rasterio.transform import from_origin

@pytest.fixture
def mock_raster_factory(tmp_path):
    def _create_raster(filename, count=1, crs="EPSG:32619", width=10, height=10, descriptions=None):
        path = tmp_path / filename
        transform = from_origin(0, 10, 1, 1)
        array = np.random.randint(0, 255, size=(count, height, width)).astype(np.uint8)
        
        with rasterio.open(
            path, 'w', driver='GTiff', height=height, width=width,
            count=count, dtype=array.dtype, crs=crs, transform=transform
        ) as dst:
            dst.write(array)
            if descriptions:
                dst.descriptions = descriptions
        return str(path)
    return _create_raster

@pytest.fixture
def mock_vector_factory(tmp_path):
    def _create_vector(filename, geometries, attributes=None, crs="EPSG:32619"):
        """
        Helper to quickly create and save a shapefile/geojson for testing.
        geometries: list of shapely objects
        attributes: dict of list of values (columns)
        """
        path = tmp_path / filename
        
        data = {'geometry': geometries}
        if attributes:
            data.update(attributes)
            
        gdf = gpd.GeoDataFrame(data, crs=crs)
        
        driver = "ESRI Shapefile" if filename.endswith(".shp") else "GeoJSON"
        gdf.to_file(path, driver=driver)
        
        return str(path)
    return _create_vector