# tests/unit/test_vector.py

import pytest
import geopandas as gpd
from shapely.geometry import Polygon
from pathlib import Path

from phytospatial.vector import Vector, resolve_vector

# --- Initialization & I/O Tests ---

def test_init_valid(crowns_gdf):
    """Test initializing Vector with a valid GeoDataFrame."""
    v = Vector(crowns_gdf)
    assert len(v) == 1
    assert v.crs == crowns_gdf.crs

def test_init_invalid_type():
    """Test that initializing with non-GDF raises TypeError."""
    with pytest.raises(TypeError):
        Vector("not a dataframe")

def test_from_file(shapefile_path):
    """Test loading from a file path."""
    v = Vector.from_file(shapefile_path)
    assert isinstance(v, Vector)
    assert len(v) == 1

def test_from_file_missing():
    """Test loading a non-existent file."""
    with pytest.raises(FileNotFoundError):
        Vector.from_file("ghost.shp")

def test_save_vector(tmp_path, crowns_gdf):
    """Test saving the vector to disk."""
    v = Vector(crowns_gdf)
    out_path = tmp_path / "saved.gpkg"
    
    v.save(out_path, driver="GPKG")
    
    assert out_path.exists()
    # Verify we can load it back
    loaded = gpd.read_file(out_path)
    assert len(loaded) == len(v)

# --- Property Tests ---

def test_properties(crowns_gdf):
    v = Vector(crowns_gdf)
    # Check simple properties delegation
    assert v.crs == crowns_gdf.crs
    assert (v.bounds == crowns_gdf.total_bounds).all()
    assert v.columns == crowns_gdf.columns.tolist()

# --- Method Tests ---

def test_to_crs(crowns_gdf):
    """Test reprojection."""
    v = Vector(crowns_gdf)
    original_crs = v.crs
    target_crs = "EPSG:4326"
    
    # 1. Test returning new object
    v_new = v.to_crs(target_crs)
    assert v_new.crs != original_crs
    assert v_new.crs == target_crs
    assert v.crs == original_crs  # Original should be unchanged
    
    # 2. Test inplace
    v.to_crs(target_crs, inplace=True)
    assert v.crs == target_crs

def test_to_crs_missing_crs(valid_crown_poly):
    """Test error when reprojecting a naive geometry."""
    naive_gdf = gpd.GeoDataFrame(
        {'geometry': [valid_crown_poly]} 
    )
    
    v = Vector(naive_gdf)
    with pytest.raises(ValueError, match="no CRS"):
        v.to_crs("EPSG:4326")

def test_validate_fix(valid_crown_poly, invalid_crown_poly):
    """Test validating with fix_invalid=True."""
    gdf = gpd.GeoDataFrame(
        {'id': [1, 2], 'geometry': [valid_crown_poly, invalid_crown_poly]}, 
        crs="EPSG:32619"
    )
    v = Vector(gdf)
    
    # Should fix the bowtie polygon (buffer(0)) resulting in 2 valid polys
    v_clean = v.validate(fix_invalid=True, drop_invalid=True)
    
    assert len(v_clean) == 2
    assert v_clean.data.is_valid.all()

def test_validate_drop(valid_crown_poly, invalid_crown_poly):
    """Test validating with fix_invalid=False (strict drop)."""
    gdf = gpd.GeoDataFrame(
        {'id': [1, 2], 'geometry': [valid_crown_poly, invalid_crown_poly]}, 
        crs="EPSG:32619"
    )
    v = Vector(gdf)
    
    # Should drop the invalid one immediately
    v_clean = v.validate(fix_invalid=False, drop_invalid=True)
    
    assert len(v_clean) == 1
    assert v_clean.data.iloc[0]['id'] == 1

def test_filter_series(rich_gdf):
    """Test filtering using a boolean series."""
    v = Vector(rich_gdf)
    
    # Filter for trees taller than 20m
    condition = v.data['height'] > 20
    v_filtered = v.filter(condition)
    
    assert len(v_filtered) == 1
    assert v_filtered.data.iloc[0]['species'] == 'Picea'

def test_filter_callable(rich_gdf):
    """Test filtering using a lambda function."""
    v = Vector(rich_gdf)
    
    # Filter for Species == Abies
    v_filtered = v.filter(lambda df: df['species'] == 'Abies')
    
    assert len(v_filtered) == 1
    assert v_filtered.data.iloc[0]['species'] == 'Abies'

def test_select(rich_gdf):
    """Test column selection ensures geometry is kept."""
    v = Vector(rich_gdf)
    
    # Select only 'species' (geometry should be auto-included)
    v_sel = v.select(['species'])
    
    assert 'species' in v_sel.columns
    assert 'geometry' in v_sel.columns
    assert 'height' not in v_sel.columns
    assert 'crown_id' not in v_sel.columns

# --- Decorator Tests ---

def test_resolve_vector_decorator(shapefile_path, crowns_gdf):
    """
    Test that the decorator correctly handles both file paths 
    and existing Vector objects.
    """
    
    @resolve_vector
    def get_feature_count(vector_obj):
        # Helper to verify we received a Vector
        assert isinstance(vector_obj, Vector)
        return len(vector_obj)

    count_from_path = get_feature_count(shapefile_path)
    assert count_from_path == 1

    v = Vector(crowns_gdf)
    count_from_obj = get_feature_count(v)
    assert count_from_obj == 1

    count_from_pathlib = get_feature_count(Path(shapefile_path))
    assert count_from_pathlib == 1

def test_resolve_vector_pass_none():
    """Test that decorator handles None input gracefully."""
    
    @resolve_vector
    def process(vector_obj):
        return vector_obj
        
    assert process(None) is None