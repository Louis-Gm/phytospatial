# src/phytospatial/vector/geom.py

"""
This module provides geometric operations and spatial analysis functions for vector data.
"""

from typing import Union, Callable
import logging

import geopandas as gpd
import pandas as pd

from phytospatial.vector.layer import Vector

log = logging.getLogger(__name__)

__all__ = [
    "to_crs",
    "validate",
    "filter_vector",
    "select_columns"
]

def to_crs(
        vector: Vector, 
        target_crs, 
        inplace: bool = False
        ) -> Vector:
    """
    Reprojects the geometries in the Vector to a specified target Coordinate Reference System (CRS).
    
    Args:
        vector (Vector): The input Vector object containing geometries to be reprojected.
        target_crs: The target CRS to which the geometries will be reprojected.
        inplace (bool): If True, modifies the input Vector in place. 
                        If False, returns a new Vector with reprojected geometries. Defaults to False.
    
    Returns:
        Vector: A Vector object with geometries reprojected to the target CRS. If inplace is True, returns the modified input Vector.
    """
    if vector.crs is None:
        raise ValueError("Vector has no CRS. Cannot reproject.")
        
    new_gdf = vector.data.to_crs(target_crs)
    
    if inplace:
        vector.data = new_gdf
        return vector
    return Vector(new_gdf)

def validate(
        vector: Vector, 
        fix_invalid: bool = True, 
        drop_invalid: bool = True, 
        inplace: bool = False
        ) -> Vector:
    """
    Validates the geometries in the Vector, optionally fixing or dropping invalid geometries.

    Args:
        vector (Vector): The input Vector object containing geometries to be validated.
        fix_invalid (bool): If True, attempts to fix invalid geometries using a zero-width buffer. Defaults to True.
        drop_invalid (bool): If True, drops geometries that remain invalid after the fix attempt. Defaults to True.
        inplace (bool): If True, modifies the input Vector in place. 
                        If False, returns a new Vector with validated geometries. Defaults to False

    Returns:
        Vector: A Vector object with validated geometries. If inplace is True, returns the modified input Vector.
    """                    
    gdf = vector.data if inplace else vector.data.copy()
    invalid_mask = ~gdf.is_valid
    
    if not invalid_mask.any():
        return vector if inplace else Vector(gdf)
    
    if fix_invalid:
        gdf.loc[invalid_mask, 'geometry'] = gdf.loc[invalid_mask, 'geometry'].buffer(0)
        still_invalid = ~gdf.is_valid
        
        if still_invalid.any() and drop_invalid:
            gdf = gdf[gdf.is_valid]
    elif drop_invalid:
        gdf = gdf[gdf.is_valid]
    
    if inplace:
        vector.data = gdf
        return vector
    return Vector(gdf)

def filter_vector(
        vector: Vector, 
        condition: Union[pd.Series, Callable], 
        inplace: bool = False
        ) -> Vector:
    """
    Filters the geometries in the Vector based on a boolean condition.

    Args:
        vector (Vector): The input Vector object containing geometries to be filtered.
        condition (Union[pd.Series, Callable]): A boolean Series or a callable function that returns a boolean Series for filtering.
        inplace (bool): If True, modifies the input Vector in place. 
                        If False, returns a new Vector with filtered geometries. Defaults to False.

    Returns:
        Vector: A Vector object with geometries filtered based on the condition. If inplace is True, returns the modified input Vector.
    """                    
    mask = condition(vector.data) if callable(condition) else condition
    filtered_gdf = vector.data[mask]
    
    if inplace:
        vector.data = filtered_gdf
        return vector
    return Vector(filtered_gdf.copy())

def select_columns(
        vector: Vector, 
        columns: list, 
        inplace: bool = False
        ) -> Vector:
    """
    Selects a subset of columns from the Vector's GeoDataFrame, ensuring that the geometry column is retained.
    
    Args:
        vector (Vector): The input Vector object containing the GeoDataFrame.
        columns (list): A list of column names to select.
        inplace (bool): If True, modifies the input Vector in place. 
                        If False, returns a new Vector with the selected columns. Defaults to False.

    Returns:
        Vector: A Vector object with the selected columns. If inplace is True, returns the modified input Vector.
    """
    if 'geometry' not in columns:
        columns = columns + ['geometry']
    
    selected_gdf = vector.data[columns]
    
    if inplace:
        vector.data = selected_gdf
        return vector
    return Vector(selected_gdf.copy())