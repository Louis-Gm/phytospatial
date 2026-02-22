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

def load_vector(path: Union[str, Path], engine: str = "pyogrio", **kwargs) -> Vector:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Vector file not found: {path}")
    
    gdf = gpd.read_file(path, engine=engine, **kwargs)
    return Vector(gdf)

def save_vector(vector: Vector, path: Union[str, Path], driver: str = None, engine: str = "pyogrio", **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vector.data.to_file(path, driver=driver, engine=engine, **kwargs)

def resolve_vector(func: Callable):
    @wraps(func)
    def wrapper(input_obj: Union[str, Path, Vector], *args, **kwargs):
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