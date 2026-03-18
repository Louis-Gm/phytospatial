# src/phytospatial/lidar/rasterize.py

"""
This module implements functions to rasterize lidar point clouds.
"""

import itertools
from typing import Union, Iterator, Generator
from pathlib import Path
import logging

import numpy as np
from rasterio.transform import Affine
from rasterio.crs import CRS
from numba import njit

from phytospatial.raster.layer import Raster

from phytospatial.lidar.layer import PointCloud
from phytospatial.lidar.io import resolve_pc

log = logging.getLogger(__name__)

__all__ = [
    "points_to_grid",
    "NODATA_VAL"
]

NODATA_VAL = -9999.0

def _create_affine_transform(
        min_x: float, 
        max_y: float, 
        resolution: float
        ) -> Affine:
    """
    Generates affine coordinate reference transforms for empty grids.

    Args:
        min_x (float): Minimum absolute X coordinate of the target grid footprint.
        max_y (float): Maximum absolute Y coordinate of the target grid footprint.
        resolution (float): Spatial resolution defining geographic units per pixel.

    Returns:
        Affine: Instantiated affine transformation matrix for strict georeferencing.
    """
    return Affine.translation(min_x, max_y) * Affine.scale(resolution, -resolution)

@njit(cache=True, fastmath=True)
def _process_chunk_fused(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    grid: np.ndarray,
    min_x: float,
    max_y: float,
    resolution: float,
    height: int,
    width: int,
    method_flag: int
    ) -> None:
    """
    Fuses spatial coordinate transformation, boundary validation, and statistical 
    aggregation into a single pre-compiled kernel to bypass intermediate array allocation.

    Args:
        x (np.ndarray): 1D array of horizontal x-coordinates for the current chunk.
        y (np.ndarray): 1D array of vertical y-coordinates for the current chunk.
        z (np.ndarray): 1D array of elevation z-coordinates for the current chunk.
        grid (np.ndarray): 2D target matrix acting as the raster output accumulator.
        min_x (float): Origin X coordinate representing the left-most bound of the grid.
        max_y (float): Origin Y coordinate representing the top-most bound of the grid.
        resolution (float): Spatial resolution utilized as the discrete binning divisor.
        height (int): Maximum allowable row index, derived from the grid shape.
        width (int): Maximum allowable column index, derived from the grid shape.
        method_flag (int): Directive flag mapping to the aggregation algorithm 
            (0 = Count, 1 = Maximum, 2 = Minimum).

    Returns:
        None
    """
    for i in range(x.shape[0]):
        c = int((x[i] - min_x) / resolution)
        r = int((max_y - y[i]) / resolution)

        if 0 <= r < height and 0 <= c < width:
            if method_flag == 1:
                if z[i] > grid[r, c]:
                    grid[r, c] = z[i]
            elif method_flag == 2:
                if z[i] < grid[r, c]:
                    grid[r, c] = z[i]
            elif method_flag == 0:
                grid[r, c] += 1

@resolve_pc
def points_to_grid(
    source: Union[str, Path, PointCloud, Iterator[PointCloud], Generator[PointCloud, None, None]], 
    resolution: float,
    crs: Union[str, CRS],
    method: str = 'max',
    nodata: float = NODATA_VAL,
    chunk_size: int = 2_000_000
    ) -> Raster:
    """
    Ingests and transforms unstructured 3D point cloud distributions into strict, 
    geo-aligned 2D raster grids via heavily optimized spatial hashing.

    This function relies on the `@resolve_pc` decorator to dynamically supply either a 
    fully instantiated PointCloud object or a memory-safe stream generator based on 
    the presence of a chunk_size parameter during invocation.

    Args:
        source (Union[str, Path, PointCloud, Iterator[PointCloud], Generator[PointCloud, None, None]]): 
            The target data input. Filepaths are resolved into object streams prior to execution.
        resolution (float): Granularity of the output grid defining the geographic 
            distance each pixel represents.
        crs (Union[str, CRS]): Target Coordinate Reference System for spatial alignment.
        method (str, optional): Statistical aggregator to apply when multiple points fall 
            within identical pixel bounds. Valid arguments are 'max' (highest elevation), 
            'min' (lowest elevation), or 'count' (point density). Defaults to 'max'.
        nodata (float, optional): Filler scalar designated for pixels containing zero 
            point intersections. Defaults to the module-level NODATA_VAL.
        chunk_size (int, optional): Buffer limit representing the maximum number of points 
            processed per iterative cycle. Defaults to 2,000,000.

    Raises:
        ValueError: If the `method` parameter provided does not resolve to an implemented 
            aggregation kernel, or if the resolved data stream is entirely empty.
        TypeError: If the resolved source fails to inherit from the expected PointCloud 
            or Iterator signatures.

    Returns:
        Raster: A fully populated raster object containing the processed 2D array matrix, 
            affine transformation parameters, the designated CRS, and metadata properties.
    """
    if isinstance(source, (Iterator, Generator)):
        try:
            first_chunk = next(source)
        except StopIteration:
            raise ValueError("The resolved LiDAR stream is empty.")
            
        min_x = first_chunk.min_x
        max_x = first_chunk.max_x
        min_y = first_chunk.min_y
        max_y = first_chunk.max_y
        
        iterator = itertools.chain([first_chunk], source)
        
    elif isinstance(source, PointCloud):
        min_x = source.min_x
        max_x = source.max_x
        min_y = source.min_y
        max_y = source.max_y
        
        iterator = iter([source])
        
    else:
        raise TypeError(f"Execution expected a PointCloud or Iterator, received {type(source)}")
    
    width = int((max_x - min_x) / resolution)
    height = int((max_y - min_y) / resolution)
    shape = (height, width)
    transform = _create_affine_transform(min_x, max_y, resolution)
    
    if method == 'count':
        grid = np.zeros(shape, dtype=np.uint32)
        actual_nodata = None
        method_flag = 0
    elif method == 'max':
        grid = np.full(shape, -np.inf, dtype=np.float32)
        actual_nodata = nodata
        method_flag = 1
    elif method == 'min':
        grid = np.full(shape, np.inf, dtype=np.float32)
        actual_nodata = nodata
        method_flag = 2
    else:
        raise ValueError(f"Unknown rasterization method: {method}")
        
    for pc in iterator:
        _process_chunk_fused(
            x=pc.x,
            y=pc.y,
            z=pc.z,
            grid=grid,
            min_x=min_x,
            max_y=max_y,
            resolution=resolution,
            height=height,
            width=width,
            method_flag=method_flag
        )
        
    if method == 'max':
        grid[grid == -np.inf] = nodata
    elif method == 'min':
        grid[grid == np.inf] = nodata
        
    return Raster(
        data=grid,
        transform=transform,
        crs=crs,
        nodata=actual_nodata
    )