# src/phytospatial/vector.py

"""
This module loads vector data into memory as Vector objects.

It supports various vector file formats (Shapefile, GeoJSON, GeoPackage, etc.)
and provides functionality for reprojection, validation, filtering,
and saving vector data. 

All spatial primitives (Points, Lines, Polygons) are supported.
"""

import logging
from pathlib import Path
from typing import Union, Callable
from functools import wraps

import geopandas as gpd
import pandas as pd

log = logging.getLogger(__name__)

class Vector:
    """
    In-memory container for vector data (Points, Lines, Polygons).
    """
    def __init__(self, data: gpd.GeoDataFrame):
        """
        Initialize Vector with a GeoDataFrame.
        
        Args:
            data: GeoDataFrame containing geometries and attributes
        """
        if not isinstance(data, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(data)}")
        self._data = data

    @classmethod
    def from_file(cls, path: Union[str, Path], auto_repair: bool = False, **kwargs) -> 'Vector':
        """
        Load vector file into memory.
        
        Args:
            path: Path to vector file (Shapefile, GeoJSON, GeoPackage, etc.)
            **kwargs: Additional arguments passed to geopandas.read_file()
        
        Returns:
            Vector object
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Vector file not found: {path}")
        
        log.debug(f"Loading Vector from: {path.name}")

        # define optimization arguments for pyogrio and arrow
        optimization_args = {}
        if "engine" not in kwargs:
            kwargs["engine"] = "pyogrio"
            if "use_arrow" not in kwargs:
                optimization_args["use_arrow"] = True  

        try:
            # attempt fast load with pyogrio and arrow optimization
            try:
                # fallback to standard load if failure occurs
                gdf = gpd.read_file(path, **kwargs, **optimization_args)
                log.debug("Loaded vector using Pyogrio with Arrow optimization")
            except (ImportError, TypeError, ValueError):
                if kwargs.get("engine") == "pyogrio":
                    del kwargs["engine"]                
                gdf = gpd.read_file(path, **kwargs)

            vector_obj = cls(gdf)    

            # validate geometries and optionally fix/drop invalid ones
            if auto_repair:
                log.info("Auto-repair enabled: validating geometries and fixing/dropping invalid ones")
                vector_obj = vector_obj.validate(fix_invalid=True, drop_invalid=True)

            return vector_obj
        
        except Exception as e:
            raise IOError(f"Failed to load vector {path}: {e}") from e

    @property
    def data(self) -> gpd.GeoDataFrame:
        """
        Access the underlying GeoDataFrame.
        """
        return self._data

    @data.setter
    def data(self, value: gpd.GeoDataFrame):
        """
        Update the underlying GeoDataFrame.
        """
        if not isinstance(value, gpd.GeoDataFrame):
            raise TypeError(f"Expected GeoDataFrame, got {type(value)}")
        self._data = value

    @property
    def crs(self):
        """
        Coordinate Reference System.
        """
        return self._data.crs

    @property
    def bounds(self):
        """
        Total bounds (minx, miny, maxx, maxy).
        """
        return self._data.total_bounds
    
    @property
    def columns(self):
        """
        Column names in the vector data.
        """
        return self._data.columns.tolist()

    def __len__(self) -> int:
        """
        Number of features.
        """
        return len(self._data)
    
    def __repr__(self):
        return f"<Vector features={len(self._data)} crs={self.crs}>"

    def copy(self) -> 'Vector':
        """
        Create a deep copy of the Vector.
        
        Returns:
            Vector: Independent copy with duplicated data
        """
        return Vector(self._data.copy())

    def save(self, path: Union[str, Path], driver: str = None, **kwargs):
        """
        Write to disk.
        
        Args:
            path: Output file path
            driver: Optional driver name ('GeoJSON', 'ESRI Shapefile', 'GPKG')
            **kwargs: Additional arguments for to_file()
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        log.info(f"Saving Vector to {path}")
        self._data.to_file(path, driver=driver, **kwargs)

    def to_crs(self, target_crs, inplace: bool = False) -> 'Vector':
        """
        Reproject geometries to a new CRS.
        
        Args:
            target_crs: Target CRS (EPSG code, proj string, or CRS object)
            inplace: If True, modifies this Vector. If False, returns new Vector.
        
        Returns:
            Vector: Reprojected Vector (self if inplace=True, new copy otherwise)
            
        Raises:
            ValueError: If Vector has no CRS
        """
        if self.crs is None:
            raise ValueError("Vector has no CRS. Cannot reproject.")
            
        new_gdf = self._data.to_crs(target_crs)
        
        if inplace:
            self._data = new_gdf
            return self
        return Vector(new_gdf)

    def validate(self, fix_invalid: bool = True, drop_invalid: bool = True) -> 'Vector':
        """
        Validate and optionally fix/remove invalid geometries.
        
        Args:
            fix_invalid: If True, attempts to fix invalid geometries using buffer(0)
            drop_invalid: If True, removes geometries that can't be fixed
        
        Returns:
            Vector: New Vector object with valid geometries
        """
        gdf = self._data.copy()
        
        invalid_mask = ~gdf.is_valid
        
        if not invalid_mask.any():
            log.debug("All geometries are valid")
            return self
        
        invalid_count = invalid_mask.sum()
        log.warning(f"Found {invalid_count} invalid geometries")
        
        if fix_invalid:
            log.info("Attempting to fix invalid geometries with buffer(0)...")
            gdf.loc[invalid_mask, 'geometry'] = gdf.loc[invalid_mask, 'geometry'].buffer(0)
            
            still_invalid = ~gdf.is_valid
            fixed_count = invalid_count - still_invalid.sum()
            log.info(f"Fixed {fixed_count} geometries")
            
            if still_invalid.any() and drop_invalid:
                drop_count = still_invalid.sum()
                log.warning(f"Dropping {drop_count} geometries that couldn't be fixed")
                gdf = gdf[gdf.is_valid].copy()
        
        elif drop_invalid:
            log.warning(f"Dropping {invalid_count} invalid geometries")
            gdf = gdf[gdf.is_valid].copy()
        
        return Vector(gdf)

    def filter(self, condition: Union[pd.Series, Callable]) -> 'Vector':
        """
        Filter features based on a condition.
        
        Args:
            condition: Boolean Series or callable that takes GeoDataFrame and returns bool Series
        
        Returns:
            Vector: New Vector with filtered features
        """
        if callable(condition):
            mask = condition(self._data)
        else:
            mask = condition
        
        filtered_gdf = self._data[mask].copy()
        log.debug(f"Filtered {len(self._data)} features → {len(filtered_gdf)} features")
        return Vector(filtered_gdf)

    def select(self, columns: list) -> 'Vector':
        """
        Select specific columns (always includes geometry).
        
        Args:
            columns: List of column names to keep
        
        Returns:
            Vector: New Vector with selected columns
        """
        if 'geometry' not in columns:
            columns = columns + ['geometry']
        
        selected_gdf = self._data[columns].copy()
        return Vector(selected_gdf)


def resolve_vector(func: Callable):
    """
    Decorator: Automatically loads file paths into Vector objects.

    Args:
        func: Function that takes a Vector as first argument

    Returns:
        Wrapped function that accepts file paths or Vector objects
    """
    @wraps(func)
    def wrapper(input_obj: Union[str, Path, Vector], *args, **kwargs):
        if input_obj is None:
            return func(None, *args, **kwargs)

        if isinstance(input_obj, (str, Path)):
            vector_obj = Vector.from_file(input_obj)
        elif isinstance(input_obj, Vector):
            vector_obj = input_obj
        else:
            raise TypeError(f"Expected file path or Vector object, got {type(input_obj)}")

        return func(vector_obj, *args, **kwargs)
    return wrapper