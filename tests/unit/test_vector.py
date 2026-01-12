# tests/unit/test_vector.py

import pytest
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from phytospatial import vector

def test_label_crowns_basic_success():
    crown_geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    crowns = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [crown_geom]}, 
        crs="EPSG:32619"
    )
    
    point_geom = Point(0.5, 0.5)
    points = gpd.GeoDataFrame(
        {'species_label': ['Oak'], 'geometry': [point_geom]}, 
        crs="EPSG:32619"
    )
    
    result = vector.label_crowns(crowns, points, label_col='species_label', max_dist=1.0)
    
    assert 'species' in result.columns
    assert result.iloc[0]['species'] == 'Oak'

def test_label_crowns_max_distance_logic():
    crown_geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    crowns = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [crown_geom]}, 
        crs="EPSG:32619"
    )
    
    point_geom = Point(10, 10)
    points = gpd.GeoDataFrame(
        {'species_label': ['Oak'], 'geometry': [point_geom]}, 
        crs="EPSG:32619"
    )
    
    result = vector.label_crowns(crowns, points, label_col='species_label', max_dist=2.0)
    
    assert pd.isna(result.iloc[0]['species'])

def test_label_crowns_crs_mismatch_reprojection():
    crown_geom = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    crowns = gpd.GeoDataFrame(
        {'crown_id': [1], 'geometry': [crown_geom]}, 
        crs="EPSG:32619"
    )
    
    point_geom = Point(-68.0, 46.0)
    points = gpd.GeoDataFrame(
        {'species_label': ['Maple'], 'geometry': [point_geom]}, 
        crs="EPSG:4326"
    )
    
    result = vector.label_crowns(crowns, points, label_col='species_label')
    
    assert result.crs.to_string() == "EPSG:32619" 

def test_label_crowns_validates_missing_column():
    crowns = gpd.GeoDataFrame(
        {'geometry': [Point(0,0)]}, 
        crs="EPSG:32619"
    )
    points = gpd.GeoDataFrame(
        {'wrong_col': ['A'], 'geometry': [Point(0,0)]}, 
        crs="EPSG:32619"
    )
    
    with pytest.raises(ValueError, match="not found in points"):
        vector.label_crowns(crowns, points, label_col='species_label')

def test_label_crowns_deduplication():
    crown_geom = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    crowns = gpd.GeoDataFrame(
        {'crown_id': [101], 'geometry': [crown_geom]}, 
        crs="EPSG:32619"
    )
    
    p1 = Point(0.2, 0.2)
    p2 = Point(0.8, 0.8)
    points = gpd.GeoDataFrame(
        {'species_label': ['Birch', 'Birch'], 'geometry': [p1, p2]}, 
        crs="EPSG:32619"
    )
    
    result = vector.label_crowns(crowns, points, label_col='species_label')
    
    assert len(result) == 1
    assert result.index.is_unique