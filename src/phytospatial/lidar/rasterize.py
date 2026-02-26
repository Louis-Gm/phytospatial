# src/phytospatial/lidar/rasterize.py

"""
This module implements functions to rasterize lidar point clouds.
"""

from typing import Union
from pathlib import Path
import logging

import numpy as np
from rasterio.transform import Affine
from rasterio.crs import CRS
from numba import jit

from phytospatial.raster.layer import Raster

from .layer import PointCloud

log = logging.getLogger(__name__)

__all__ = [
    "points_to_grid",
    "NODATA_VAL"
]

NODATA_VAL = -9999.0

def _create_affine_transform(min_x: float, max_y: float, resolution: float) -> Affine:
    """
    Generates affine coordinate reference transforms for empty grids.

    Args:
        min_x (float): Minimum X coordinate of the grid.
        max_y (float): Maximum Y coordinate of the grid.
        resolution (float): Geographic units per pixel.

    Returns:
        Affine: Affine transformation object for georeferencing the raster grid.
    """
    # Translate spatial coordinates into discrete pixel space through a combination of scaling and translation
    return Affine.translation(min_x, max_y) * Affine.scale(resolution, -resolution)

@jit(nopython=True, cache=True)
def _rasterize_chunk(
    grid: np.ndarray,
    rows: np.ndarray,
    cols: np.ndarray,
    z: np.ndarray,
    method_flag: int
    ):
    """
    Helper function to rasterize a chunk of points into the grid using explicit loops for numba optimization.
    
    Args:
        grid: 2D array representing the raster grid to update.
        rows: Row indices for each point.
        cols: Column indices for each point.
        z: Z values for each point.
        method_flag: Integer flag indicating the aggregation method (0=count, 1=max, 2=min).

    Returns:
        None (the grid is modified in place).
    """
    for i in range(len(rows)):
        r = rows[i]
        c = cols[i]
        # For each point, update the corresponding grid cell based on the specified method:
        # Count simply increments the cell value;
        # Max updates if the point's Z is greater;
        # Min updates if the point's Z is smaller.
        if method_flag == 0:  # count
            grid[r, c] += 1
        elif method_flag == 1:  # max
            if z[i] > grid[r, c]:
                grid[r, c] = z[i]
        elif method_flag == 2:  # min
            if z[i] < grid[r, c]:
                grid[r, c] = z[i]

def points_to_grid(
    source: Union[str, Path, PointCloud], 
    resolution: float,
    crs: Union[str, CRS],
    method: str = 'max',
    nodata: float = NODATA_VAL,
    chunk_size: int = 2_000_000
) -> Raster:
    """
    Rasterizes point cloud distributions sequentially into dense grids using NumPy vectorization.

    This function can be used to create DSMs, DTMs, or point density maps by specifying the appropriate method.
    It handles large datasets by processing points in manageable chunks.
    
    Args:
        source (Union[str, Path, PointCloud]): Filepath to stream from or existing PointCloud object.
        resolution (float): Geographic units per pixel.
        crs (Union[str, CRS]): Coordinate reference system of the points.
        method (str): Statistical aggregator ('max', 'min', 'count').
        nodata (float): Filler value.
        chunk_size (int): Points processed simultaneously.
        
    Returns:
        Raster: Compiled and geo-aligned pixel array.
    """
    if isinstance(source, (str, Path)):
        import laspy
        # If path is provided, we need to read the header first to get bounds for grid sizing, then stream in chunks
        with laspy.open(source) as fh:
            # Extract global bounds from the LAS header for accurate grid sizing
            min_x = fh.header.x_min
            max_x = fh.header.x_max
            min_y = fh.header.y_min
            max_y = fh.header.y_max
        iterator = PointCloud.iter_chunks(source, chunk_size=chunk_size)
    else:
        # If a PointCloud object is provided directly, we can use its bounding attributes to define the grid
        min_x = source.min_x
        max_x = source.max_x
        min_y = source.min_y
        max_y = source.max_y
        iterator = [source]
    
    # Calculate grid dimensions and prepare the affine transform based on the bounds and resolution provided
    width = int((max_x - min_x) / resolution)
    height = int((max_y - min_y) / resolution)
    shape = (height, width)
    transform = _create_affine_transform(min_x, max_y, resolution)
    
    if method == 'count':
        # For counting, we can use a simple integer grid initialized to zero
        # and nodata is not applicable since zero counts are valid
        grid = np.zeros(shape, dtype=np.uint32)
        actual_nodata = None
        method_flag = 0
    elif method == 'max':
        # For max, we initialize with -inf so any real point will be greater, and we set nodata after processing
        grid = np.full(shape, -np.inf, dtype=np.float32)
        actual_nodata = nodata
        method_flag = 1
    elif method == 'min':
        # For min, we initialize with inf so any real point will be smaller, and we set nodata after processing
        grid = np.full(shape, np.inf, dtype=np.float32)
        actual_nodata = nodata
        method_flag = 2
    else:
        raise ValueError(f"Unknown rasterization method: {method}")
        
    for pc in iterator:
        # Convert point coordinates to grid indices.
        # We only process points that fall within the defined grid bounds
        cols = np.floor((pc.x - min_x) / resolution).astype(np.int32)
        rows = np.floor((max_y - pc.y) / resolution).astype(np.int32)
        valid_mask = (rows >= 0) & (rows < shape[0]) & (cols >= 0) & (cols < shape[1])
        
        if not np.any(valid_mask):
            continue

        # Filter points to those that are valid and within the grid bounds, then rasterize this chunk into the grid    
        r_valid = rows[valid_mask]
        c_valid = cols[valid_mask]
        z_valid = pc.z[valid_mask]
        
        _rasterize_chunk(grid, r_valid, c_valid, z_valid, method_flag)
        
    # After processing all chunks, we need to replace the initial extreme values 
    # with the nodata value for max and min methods
    if method == 'max':
        grid[grid == -np.inf] = nodata
    elif method == 'min':
        grid[grid == np.inf] = nodata
        
    return Raster(
        # we initialize a Raster object with the final grid, affine transform, CRS, and nodata value
        data=grid,
        transform=transform,
        crs=crs,
        nodata=actual_nodata
    )