# src/phytospatial/vector/io.py

"""
This module provides functions for reading and writing vector data (points, lines, polygons) using GeoPandas.
"""

from pathlib import Path
from typing import Union, Callable, Any, get_type_hints, get_origin, get_args
import inspect
import logging
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
        **kwargs: Any
        ) -> Vector:
    """Loads a vector dataset from the specified file path into a Vector object.
    Args:
        path (Union[str, Path]): The absolute or relative system path resolving to the vector file.
        engine (str): The GeoPandas engine to use for reading the file. Defaults to "pyogrio".
        **kwargs (Any): Additional keyword arguments to pass to the GeoPandas read_file function.
        
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
        **kwargs: Any
        ):
    """
    Saves a Vector object to the specified file path in a geospatial format.
    
    Args:
        vector (Vector): The Vector object to save.
        path (Union[str, Path]): The absolute or relative system path where the vector file will be saved.
        driver (str, optional): The OGR driver to use for writing the file. Defaults to None.
        engine (str): The GeoPandas engine to use for writing the file. Defaults to "pyogrio".
        **kwargs (Any): Additional keyword arguments to pass to the GeoPandas to_file function.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    vector.data.to_file(path, driver=driver, engine=engine, **kwargs)

def resolve_vector(
        func: Callable[..., Any]
        ) -> Callable[..., Any]:
    """
    A polymorphic decorator that intelligently resolves vector inputs into instantiated Vector objects.
    
    This function analyzes the target method's signature, evaluating type annotations and parameter 
    nomenclature. If a parameter expects a Vector but receives a string or Path, it intercepts the 
    execution to perform disk I/O, seamlessly injecting the loaded Vector object before runtime.
    
    Args:
        func (Callable[..., Any]): The target function or class method expecting a Vector input.
        
    Returns:
        Callable[..., Any]: The wrapped function executing with fully resolved Vector dependencies.
        
    Raises:
        TypeError: If a resolved target parameter receives an argument that is neither a valid 
            system path nor an instantiated Vector object.
    """
    sig = inspect.signature(func)
    
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        try:
            hints = get_type_hints(func)
        except Exception:
            hints = {}
        
        for name, param in sig.parameters.items():
            val = bound_args.arguments[name]
            
            if val is None:
                continue

            param_type = hints.get(name, Any)
            expects_vector = False
            
            if param_type is Vector:
                expects_vector = True
            else:
                origin = get_origin(param_type)
                if origin is not None:
                    args_types = get_args(param_type)
                    if Vector in args_types:
                        expects_vector = True
            
            if not expects_vector and "vector" in name.lower():
                expects_vector = True

            if expects_vector:
                if isinstance(val, (str, Path)):
                    bound_args.arguments[name] = load_vector(val)
                elif not isinstance(val, Vector):
                    raise TypeError(
                        f"Expected file path or Vector object for parameter '{name}', got {type(val)}"
                    )

        return func(*bound_args.args, **bound_args.kwargs)

    return wrapper