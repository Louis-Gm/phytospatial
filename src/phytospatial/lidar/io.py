import inspect
from functools import wraps
from pathlib import Path
from typing import Union, Generator, Iterator, Callable, Any, get_type_hints, get_origin, get_args
import logging

import laspy
import numpy as np

from phytospatial.lidar.layer import PointCloud

log = logging.getLogger(__name__)

__all__ = [
    "load_pc",
    "iter_pc",
    "resolve_pc"
]

def load_pc(
    path: Union[str, Path]
    ) -> PointCloud:
    """
    Loads the entirety of a LiDAR point cloud into memory.
    
    Args:
        path (Union[str, Path]): Target .las or .laz file.
        
    Returns:
        PointCloud: Fully populated object containing coordinates, classifications, and bounds.
        
    Raises:
        FileNotFoundError: If the specified file path does not exist on the filesystem.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lidar file not found: {path}")

    with laspy.open(path) as fh:
        las = fh.read()
        return PointCloud(
            x=np.array(las.x),
            y=np.array(las.y),
            z=np.array(las.z),
            classification=np.array(las.classification),
            return_number=np.array(las.return_number),
            min_x=las.header.x_min,
            max_x=las.header.x_max,
            min_y=las.header.y_min,
            max_y=las.header.y_max,
            max_z=las.header.z_max
        )

def iter_pc(
    path: Union[str, Path], 
    chunk_size: int = 1_000_000
) -> Generator[PointCloud, None, None]:
    """
    Iterates over a LiDAR file in chunks to maintain strict memory safety.
    
    Args:
        path (Union[str, Path]): Target .las or .laz file.
        chunk_size (int): Number of points to stream per chunk. Defaults to 1,000,000.
        
    Yields:
        Generator[PointCloud, None, None]: Sequential point cloud fragments inheriting global bounding attributes.
        
    Raises:
        FileNotFoundError: If the specified file path does not exist on the filesystem.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Lidar file not found: {path}")

    with laspy.open(path) as fh:
        header = fh.header
        for chunk in fh.chunk_iterator(chunk_size):
            yield PointCloud(
                x=np.array(chunk.x),
                y=np.array(chunk.y),
                z=np.array(chunk.z),
                classification=np.array(chunk.classification),
                return_number=np.array(chunk.return_number),
                min_x=header.x_min,
                max_x=header.x_max,
                min_y=header.y_min,
                max_y=header.y_max,
                max_z=header.z_max
            )

def resolve_pc(
    func: Callable[..., Any]
) -> Callable[..., Any]:
    """
    A polymorphic, stream-aware decorator that resolves LiDAR point cloud inputs into 
    either instantiated PointCloud objects or memory-safe PointCloud generators.

    This function analyzes the target method's signature and runtime arguments. If a target 
    parameter receives a file path (str or Path), the decorator checks the bound arguments 
    for the presence of a `chunk_size` parameter. If `chunk_size` is populated, it streams 
    the file via `iter_pc()`. If omitted, it fully loads the file via `load_pc()`. 
    
    Args:
        func (Callable[..., Any]): The target function expecting a PointCloud or stream input.
        
    Returns:
        Callable[..., Any]: The wrapped function executing with fully resolved dependencies.
        
    Raises:
        TypeError: If a resolved target parameter receives an argument that is not a valid 
            system path, a PointCloud object, or an active Iterator/Generator.
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
            
        chunk_size = bound_args.arguments.get('chunk_size', None)
        
        for name, param in sig.parameters.items():
            val = bound_args.arguments[name]
            
            if val is None:
                continue

            param_type = hints.get(name, Any)
            expects_pc = False
            
            if param_type is PointCloud:
                expects_pc = True
            else:
                origin = get_origin(param_type)
                if origin is not None:
                    args_types = get_args(param_type)
                    if PointCloud in args_types:
                        expects_pc = True
            
            if not expects_pc and ("pc" in name.lower() or "pointcloud" in name.lower() or "source" in name.lower()):
                expects_pc = True
            
            if expects_pc:
                if isinstance(val, (str, Path)):
                    if chunk_size is not None:
                        bound_args.arguments[name] = iter_pc(val, chunk_size=chunk_size)
                    else:
                        bound_args.arguments[name] = load_pc(val)
                elif not isinstance(val, (PointCloud, Generator, Iterator)):
                    raise TypeError(
                        f"Expected file path, PointCloud object, or Iterator for parameter '{name}', got {type(val)}"
                    )

        return func(*bound_args.args, **bound_args.kwargs)

    return wrapper