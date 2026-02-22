# src/phytospatial/vector/layer.py

"""
This module defines the core data structure for vector data (points, lines, polygons) and basic properties.
"""

import logging

import geopandas as gpd

log = logging.getLogger(__name__)

__all__ = [
    "Vector"
]

class Vector:
    def __init__(self, data: gpd.GeoDataFrame):
        if not isinstance(data, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(data)}")
        self._data = data

    @property
    def data(self) -> gpd.GeoDataFrame:
        return self._data

    @data.setter
    def data(self, value: gpd.GeoDataFrame):
        if not isinstance(value, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(value)}")
        self._data = value

    @property
    def crs(self):
        return self._data.crs

    @property
    def bounds(self):
        return self._data.total_bounds
    
    @property
    def columns(self):
        return self._data.columns.tolist()

    def __len__(self) -> int:
        return len(self._data)
    
    def __repr__(self):
        return f"<Vector features={len(self._data)} crs={self.crs}>"