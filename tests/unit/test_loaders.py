# tests/unit/test_loaders.py

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from phytospatial import loaders

def test_load_crowns_basic(tmp_path):
    # Create a valid shapefile
    d = {'col1': ['name1'], 'geometry': [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:32619")
    
    shapefile_path = tmp_path / "valid.shp"
    gdf.to_file(shapefile_path)
    
    result = loaders.load_crowns(str(shapefile_path))
    
    assert len(result) == 1
    assert result.data.index.name is None
    assert 'crown_id' in result.columns

def test_load_crowns_removes_invalid_geometries(tmp_path):
    valid_poly = Polygon([(0, 0), (0, 10), (10, 10), (10, 0)])
    invalid_poly = Polygon([(0, 0), (1, 1), (0, 1), (1, 0)]) # Self-intersection
    
    gdf = gpd.GeoDataFrame(
        {'id': [1, 2], 'geometry': [valid_poly, invalid_poly]}, 
        crs="EPSG:32619"
    )
    
    path = tmp_path / "dirty.shp"
    gdf.to_file(path)
    
    result = loaders.load_crowns(str(path), fix_invalid=False)
    
    assert len(result) == 1
    assert result.data.iloc[0]['geometry'].is_valid

def test_load_crowns_custom_ids(tmp_path):
    d = {'tree_code': ['A100'], 'geometry': [Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])]}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:32619")
    
    path = tmp_path / "custom_id.shp"
    gdf.to_file(path)
    
    result = loaders.load_crowns(str(path), id_col="tree_code")
    
    # "tree_code" should be renamed to "crown_id"
    assert "crown_id" in result.columns
    assert result.data.iloc[0]['crown_id'] == 'A100'

def test_load_crowns_missing_file():
    with pytest.raises(IOError):
        loaders.load_crowns("non_existent_file.shp")