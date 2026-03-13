# src/phytospatial/vector/io.py

"""
This module provides functions for reading and writing vector data (points, lines, polygons) using GeoPandas.
"""

from pathlib import Path
from typing import Union, Callable
from functools import wraps
import logging

import geopandas as gpd

from phytospatial.vector.layer import Vector

log = logging.getLogger(__name__)

__all__ = [
    "load_vector",
    "save_vector",
    "resolve_vector"
]

def load_vector(
        path: Union[str, Path], 
        engine: str = "pyogrio", 
        **kwargs
        ) -> Vector:
    """Loads a vector dataset from the specified file path into a Vector object.
    Args:
        path (Union[str, Path]): The absolute or relative system path resolving to the vector file.
        engine (str): The GeoPandas engine to use for reading the file. Defaults to "pyogrio".
        **kwargs: Additional keyword arguments to pass to the GeoPandas read_file function.
        
    Returns:
        Vector: A Vector object encapsulating the loaded GeoDataFrame. 
    """

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Vector file not found: {path}")
    
    gdf = gpd.read_file(path, engine=engine, **kwargs)
    return Vector(gdf)

def save_vector(
        vector: Vector, 
        path: Union[str, Path], 
        driver: str = None, 
        engine: str = "pyogrio", 
        **kwargs
        ):
    """
    Saves a Vector object to the specified file path in a geospatial format.
    
    Args:
        vector (Vector): The Vector object to save.
        path (Union[str, Path]): The absolute or relative system path where the vector file will be saved.
        driver (str, optional): The OGR driver to use for writing the file. Defaults to None.
        engine (str): The GeoPandas engine to use for writing the file. Defaults to "pyogrio".
        **kwargs: Additional keyword arguments to pass to the GeoPandas to_file function.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vector.data.to_file(path, driver=driver, engine=engine, **kwargs)

def resolve_vector(func: Callable):
    @wraps(func)
    def wrapper(
        input_obj: Union[str, Path, Vector], 
        *args, 
        **kwargs
        ):
        """Decorator to resolve a vector input that can be either a file path or a Vector object.
        
        Args:
            input_obj (Union[str, Path, Vector]): The input vector, which can be a file path or a Vector object.
            *args: Additional positional arguments to pass to the decorated function.
            **kwargs: Additional keyword arguments to pass to the decorated function.

        Returns:
            The result of the decorated function, with the input vector resolved to a Vector object.        
        """
        if input_obj is None:
            return func(None, *args, **kwargs)

        if isinstance(input_obj, (str, Path)):
            vector_obj = load_vector(input_obj)
        elif isinstance(input_obj, Vector):
            vector_obj = input_obj
        else:
            raise TypeError(f"Expected file path or Vector object, got {type(input_obj)}")

        return func(vector_obj, *args, **kwargs)
    return wrapper