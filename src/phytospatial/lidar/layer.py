# src/phytospatial/lidar/layer.py

"""
This module defines the core data structure for lidar point clouds, along with methods for loading and basic manipulation.
"""

from pathlib import Path
from dataclasses import dataclass
from typing import Union, Generator
import logging

import laspy
import numpy as np

log = logging.getLogger(__name__)

__all__ = [
    "PointCloud"
]

@dataclass
class PointCloud:
    """
    Core data structure for holding LiDAR point cloud data and bounding properties.

    Primary point cloud attributes:
        x (np.ndarray): X coordinates of points.
        y (np.ndarray): Y coordinates of points.
        z (np.ndarray): Z coordinates (elevation) of points.
        classification (np.ndarray): Point classifications (ground, vegetation, etc.).
        return_number (np.ndarray): Return number for each point (1 for first return, etc.).

    Secondary attributes for global bounding properties, useful for spatial referencing and rasterization:    
        min_x (float): Minimum X coordinate in the point cloud.
        max_x (float): Maximum X coordinate in the point cloud.
        min_y (float): Minimum Y coordinate in the point cloud.
        max_y (float): Maximum Y coordinate in the point cloud.
        max_z (float): Maximum Z coordinate in the point cloud.
    """
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    classification: np.ndarray
    return_number: np.ndarray

    min_x: float
    max_x: float
    min_y: float
    max_y: float
    max_z: float

    @classmethod
    def from_file(
        cls, 
        path: Union[str, Path]
        ) -> 'PointCloud':
        """
        Loads the entirety of a LiDAR point cloud into memory.
        
        Args:
            path (Union[str, Path]): Target .las or .laz file.
            
        Returns:
            PointCloud: Fully populated object.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Lidar file not found: {path}")

        with laspy.open(path) as fh:
            las = fh.read()
            # map laspy point attributes to our PointCloud structure
            return cls(
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

    @classmethod
    def iter_chunks(
        cls, 
        path: Union[str, Path], 
        chunk_size: int = 1_000_000
        ) -> Generator['PointCloud', None, None]:
        """
        Iterates over a LiDAR file in chunks to maintain strict memory safety.
        
        Args:
            path (Union[str, Path]): Target .las or .laz file.
            chunk_size (int): Number of points to stream per chunk.
            
        Yields:
            Generator[PointCloud, None, None]: Sequential point cloud fragments inheriting global bounding attributes.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Lidar file not found: {path}")

        with laspy.open(path) as fh:
            header = fh.header
            for chunk in fh.chunk_iterator(chunk_size):
                yield cls(
                    # Map laspy point attributes to our PointCloud structure
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