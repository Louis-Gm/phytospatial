# src/phytospatial/lidar/__init__.py
#
# Copyright (c) The phytospatial project contributors
# This software is distributed under the Apache-2.0 license.
# See the NOTICE file for more information

"""
The lidar subpackage provides core functionality for handling lidar data,
including I/O operations, point cloud processing, lidar-derived raster generation,
treetop detection and tree crown delineation.
"""

# Data structure
from .layer import (
    PointCloud
)

# Rasterization and DTM generation
from .rasterize import (
    points_to_grid,
    NODATA_VAL
)
from .generate_model import (
    TerrainType,
    generate_dtm,
    generate_dsm,
    calculate_chm
)

# Treetop detection
from .detect_treetop import (
    DetectionParams,
    detect_treetops
)

# Crown delineation
from .delineate_crown import (
    DelineationParams,
    delineate_crowns
)

__all__ = [
    # Data structure
    "PointCloud",

    # Rasterization and DTM generation
    "points_to_grid",
    "NODATA_VAL",

    "TerrainType",
    "generate_dtm",
    "generate_dsm",
    "calculate_chm",

    # Treetop detection
    "DetectionParams",
    "detect_treetops",

    # Crown delineation
    "DelineationParams",
    "delineate_crowns",
]