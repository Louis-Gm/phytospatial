import logging
from typing import Optional

import numpy as np
import geopandas as gpd
import polars as pl
from geoindex_rs import rtree as rt

log = logging.getLogger(__name__)

__all__ = [
    "Vector"
]

class Vector:
    """
    A wrapper class around a GeoPandas GeoDataFrame to represent vector spatial data with additional properties and methods.

    Attributes:
        data (gpd.GeoDataFrame): The underlying GeoDataFrame containing the spatial data.

    Properties:
        crs: The Coordinate Reference System of the geometries in the GeoDataFrame.
        bounds: The bounding box of all geometries in the GeoDataFrame as (minx, miny, maxx, maxy).
        columns: The list of column names in the GeoDataFrame.
        spatial_index (rt.RTree): A dynamically generated, zero-copy Rust spatial index containing the geometry bounds.
    """
    def __init__(self, data: gpd.GeoDataFrame):
        """
        Initializes the Vector layer and allocates internal caching structures.

        Args:
            data (gpd.GeoDataFrame): The structural geometry payload.
        
        Raises:
            TypeError: If the provided data is not a valid GeoDataFrame.
        """
        if not isinstance(data, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(data)}")
        self._data = data
        self._spatial_index: Optional[rt.RTree] = None

    @property
    def data(self) -> gpd.GeoDataFrame:
        """
        Retrieves the underlying geometry dataframe.

        Returns:
            gpd.GeoDataFrame: The primary spatial data structure.
        """
        return self._data

    @data.setter
    def data(self, value: gpd.GeoDataFrame):
        """
        Replaces the underlying geometry dataframe and invalidates any cached spatial indices.

        Args:
            value (gpd.GeoDataFrame): The new spatial data structure.

        Raises:
            TypeError: If the provided data is not a valid GeoDataFrame.
        """
        if not isinstance(value, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(value)}")
        self._data = value
        self._spatial_index = None

    @property
    def crs(self):
        """
        Retrieves the Coordinate Reference System mapping for the geometries.

        Returns:
            The CRS definition inherent to the GeoDataFrame.
        """
        return self._data.crs

    @property
    def bounds(self):
        """
        Calculates the absolute maximum spatial extents encompassing all active geometries.

        Returns:
            tuple: A strictly ordered bounding box defined as (minx, miny, maxx, maxy).
        """
        return self._data.total_bounds

    @property
    def columns(self):
        """
        Extracts the schema attributes currently associated with the geometries.

        Returns:
            list: The string identifiers corresponding to available feature columns.
        """
        return self._data.columns.tolist()

    @property
    def spatial_index(self) -> rt.RTree:
        """
        Accesses or constructs a heavily optimized C-level spatial RTree for the active geometries.

        Returns:
            rt.RTree: An immutable, binary-stable RTree index.
        """
        if self._spatial_index is None:
            bounds_df = pl.from_pandas(self._data.bounds)
            num_items = len(bounds_df)
            
            rt_builder = rt.RTreeBuilder(num_items)
            rt_builder.add(
                bounds_df["minx"].to_arrow(),
                bounds_df["miny"].to_arrow(),
                bounds_df["maxx"].to_arrow(),
                bounds_df["maxy"].to_arrow()
            )
            self._spatial_index = rt_builder.finish(method="str")
        
        return self._spatial_index

    def query_bounds(
            self, 
            minx: float, 
            miny: float, 
            maxx: float, 
            maxy: float
            ) -> np.ndarray:
        """
        Executes an accelerated broad-phase intersection search against the spatial index.

        Args:
            minx (float): The absolute minimum longitudinal constraint.
            miny (float): The absolute minimum latitudinal constraint.
            maxx (float): The absolute maximum longitudinal constraint.
            maxy (float): The absolute maximum latitudinal constraint.

        Returns:
            np.ndarray: A contiguous array of integer indices identifying geometries whose 
                        bounding boxes overlap with the specified spatial constraints.
        """
        return rt.search(self.spatial_index, minx, miny, maxx, maxy).to_numpy()

    def __len__(self) -> int:
        """
        Computes the total count of spatial features currently managed by the Vector.

        Returns:
            int: The scalar count of geometries.
        """
        return len(self._data)

    def __repr__(self):
        """
        Generates a deterministic string representation of the Vector state.

        Returns:
            str: A formatted descriptor establishing feature length and coordinate reference.
        """
        return f"<Vector features={len(self._data)} crs={self.crs}>"