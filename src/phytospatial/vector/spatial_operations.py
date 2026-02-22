#src/phytospatial/vector/spatial_operations.py

"""
This module provides spatial operations for vector data, including attribute transfer, treetop labeling, and crown delineation.
"""

from typing import Optional
import logging

import geopandas as gpd

from phytospatial.vector.layer import Vector
from phytospatial.vector.io import resolve_vector
from phytospatial.vector.geom import validate

log = logging.getLogger(__name__)

__all__ = [
    "prepare_itcd_vectors",
    "label_tree_crowns"
]

def _transfer_attributes(
    target_gdf: gpd.GeoDataFrame,
    source_gdf: gpd.GeoDataFrame,
    transfer_col: str, 
    max_dist: float,
    target_col_name: str
) -> gpd.GeoDataFrame:
    
    if transfer_col not in source_gdf.columns:
        raise ValueError(f"Column '{transfer_col}' not found in source vector.")

    if target_gdf.crs != source_gdf.crs:
        source_gdf = source_gdf.to_crs(target_gdf.crs)

    temp_col = "transfer_temp_col"
    source_subset = source_gdf[[transfer_col, 'geometry']].rename(columns={transfer_col: temp_col})

    joined = gpd.sjoin_nearest(
        target_gdf,
        source_subset,
        how='left',
        max_distance=max_dist,
        distance_col="dist"
    )

    joined = joined[~joined.index.duplicated(keep='first')]

    if target_col_name not in target_gdf.columns:
        target_gdf[target_col_name] = None
    
    target_gdf[target_col_name] = target_gdf[target_col_name].combine_first(joined[temp_col])
    
    return target_gdf

@resolve_vector
def prepare_itcd_vectors(
    vector: Vector, 
    id_col: Optional[str] = None, 
    species_col: Optional[str] = None,
    do_validate: bool = True,
    fix_invalid: bool = True
) -> Vector:
    
    if do_validate:
        vector = validate(vector, fix_invalid=fix_invalid, drop_invalid=True, inplace=False)
        if len(vector) == 0:
            raise ValueError("No valid geometries remaining after validation!")
    
    gdf = vector.data.copy()

    if id_col and id_col in gdf.columns:
        if id_col != 'crown_id':
            gdf = gdf.rename(columns={id_col: 'crown_id'})
        
        if gdf['crown_id'].duplicated().any():
            gdf['crown_id'] = gdf.index
    else:
        gdf['crown_id'] = gdf.index

    try:
        gdf['crown_id'] = gdf['crown_id'].astype(int)
    except (ValueError, TypeError):
        pass

    if species_col and species_col in gdf.columns:
        if species_col != 'species':
            gdf = gdf.rename(columns={species_col: 'species'})
    else:
        if 'species' not in gdf.columns:
            gdf['species'] = None

    gdf.index = gdf['crown_id']
    gdf.index.name = None
    
    return Vector(gdf)

@resolve_vector
def label_tree_crowns(
    target_vector: Vector,
    source_points: Vector,
    label_col: str, 
    max_dist: float = 2.0
) -> Vector:
    
    target_gdf = target_vector.data.copy()
    source_gdf = source_points.data

    updated_gdf = _transfer_attributes(
        target_gdf=target_gdf,
        source_gdf=source_gdf,
        transfer_col=label_col,
        max_dist=max_dist,
        target_col_name='species'
    )
    
    return Vector(updated_gdf)