# src/phytospatial/lidar/layer.py

"""
This module defines the core data structure for holding LiDAR point cloud data.
"""

from dataclasses import dataclass
import numpy as np

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