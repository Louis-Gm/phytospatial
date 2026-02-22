# src/phytospatial/vector/__init__.py
#
# Copyright (c) The phytospatial project contributors
# This software is distributed under the Apache-2.0 license.
# See the NOTICE file for more information

"""
The vector subpackage provides core functionality for handling vector data (points, lines, polygons).
This includes I/O operations, spatial analysis, and integration with raster and lidar data.
"""

# I/O and data structure
from .layer import (
    Vector
)

from .io import (
    load_vector,
    save_vector,
    resolve_vector
)

# Geometric operations and spatial analysis

from .geom import (
    to_crs,
    filter_vector,
    select_columns,
    validate,
)

from .spatial_operations import (
    prepare_itcd_vectors,
    label_tree_crowns
)

# 
__all__ = [
    # I/O and data structure
    "Vector",
    "load_vector",
    "save_vector",
    "resolve_vector",

    # Geometric operations and spatial analysis
    "to_crs",
    "filter_vector",
    "select_columns",
    "validate",
    "prepare_itcd_vectors",
    "label_tree_crowns"
]