# tests/unit/test_loaders.py

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from phytospatial import loaders
from phytospatial.vector import Vector

def test_load_crowns_basic(shapefile_path):
    """Test loading a standard valid shapefile."""
    result = loaders.load_crowns(shapefile_path)
    
    assert hasattr(result, 'data')
    gdf = result.data
    assert len(gdf) == 1
    assert 'crown_id' in gdf.columns

def test_load_crowns_removes_invalid_geometries(tmp_path, valid_crown_poly, invalid_crown_poly):
    """
    Test that invalid geometries are DROPPED when fix_invalid is False.
    
    Note: If fix_invalid=True (default), the 'bowtie' polygon would be fixed 
    (becoming valid) and kept. We use fix_invalid=False to ensure it gets dropped.
    """
    gdf = gpd.GeoDataFrame(
        {'id': [1, 2], 'geometry': [valid_crown_poly, invalid_crown_poly]}, 
        crs="EPSG:32619"
    )
    
    path = tmp_path / "dirty.shp"
    gdf.to_file(path)
    
    # STRICTLY disable fixing to ensure the invalid one is dropped
    result = loaders.load_crowns(str(path), validate=True, fix_invalid=False)
    
    assert len(result.data) == 1
    assert result.data.iloc[0]['geometry'].is_valid

def test_load_crowns_custom_ids(tmp_path, valid_crown_poly):
    """Test renaming a custom ID column to 'crown_id'."""
    d = {'tree_code': ['A100'], 'geometry': [valid_crown_poly]}
    gdf = gpd.GeoDataFrame(d, crs="EPSG:32619")
    path = tmp_path / "custom_id.shp"
    gdf.to_file(path)
    
    result = loaders.load_crowns(str(path), id_col="tree_code")
    
    assert "crown_id" in result.data.columns
    assert result.data.iloc[0]['crown_id'] == 'A100'

def test_load_crowns_missing_file():
    with pytest.raises(FileNotFoundError): 
        # The Vector.from_file method raises FileNotFoundError
        loaders.load_crowns("non_existent_file.shp")

def test_label_crowns(tmp_path, valid_crown_poly):
    """Test the label_crowns function using spatial join."""
    
    # 1. Targets (Crowns)
    crowns_gdf = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [valid_crown_poly]}, 
        crs="EPSG:32619"
    )
    crown_path = tmp_path / "targets.shp"
    crowns_gdf.to_file(crown_path)

    # 2. Source (Points) - Point inside the crown (5, 5)
    points_gdf = gpd.GeoDataFrame(
        {'obs_id': [101], 'tree_type': ['Conifer'], 'geometry': [Point(5, 5)]},
        crs="EPSG:32619"
    )
    points_path = tmp_path / "source.shp"
    points_gdf.to_file(points_path)

    # 3. Execution
    # IMPORTANT: 
    # - First arg must be positional so the decorator captures it.
    # - Second arg (source_points) is NOT auto-resolved by the decorator, 
    #   so we must pass a Vector object.
    source_vec = Vector.from_file(points_path)
    
    result = loaders.label_crowns(
        str(crown_path),        # Positional arg (handled by decorator)
        source_vec,             # Explicit Vector object
        label_col="tree_type",
        max_dist=2.0
    )

    assert 'species' in result.data.columns
    assert result.data.iloc[0]['species'] == 'Conifer'

def test_label_crowns_distance_threshold(tmp_path, valid_crown_poly):
    """Test that points outside max_dist are ignored."""
    crowns_gdf = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [valid_crown_poly]}, 
        crs="EPSG:32619"
    )
    crown_path = tmp_path / "targets_dist.shp"
    crowns_gdf.to_file(crown_path)

    # Point far away at (100, 100)
    points_gdf = gpd.GeoDataFrame(
        {'type': ['Conifer'], 'geometry': [Point(100, 100)]},
        crs="EPSG:32619"
    )
    points_path = tmp_path / "source_dist.shp"
    points_gdf.to_file(points_path)

    source_vec = Vector.from_file(points_path)

    result = loaders.label_crowns(
        str(crown_path), 
        source_vec,
        label_col="type",
        max_dist=5.0
    )

    # Should be None/NaN
    assert pd.isna(result.data.iloc[0]['species'])