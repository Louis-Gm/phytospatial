# src/phytospatial/raster/__init__.py
#
# Copyright (c) The phytospatial project contributors
# This software is distributed under the Apache-2.0 license.
# See the NOTICE file for more information

"""
This subpackage provides core functionality for handling raster data,
including I/O operations, partitioning strategies, resource management,
engine dispatching and geometry utilities.

Architecture Tiers:
- Tier 1: Core data structures and I/O operations
- Tier 2: Partitioning strategies and resource management
- Tier 3: Engine dispatching and resolution utilities
- Tier 4: Geometry utilities for raster manipulation
"""

# Shared utilities
from .utils import (
    resolve_envi_path,
    extract_band_names,
    extract_band_indices
)

# Core data structure
from .layer import (
    Raster
)

# I/O operations
from .io import (
    load,
    save,
    write_window,
    read_info
)

# Resource management
from .resources import (
    ProcessingMode,
    BlockStructure,
    MemoryEstimate,
    analyze_structure,
    estimate_memory_safety
)

# Partition operations
from .partition import (
    iter_blocks,
    iter_tiles,
    iter_windows,
    TileStitcher
)

# Engine operations
from .engine import (
    AggregationType,
    DispatchConfig,
    select_strategy,
    dispatch
)

# Geometry utilities
from .geom import (
    auto_load,
    reproject, 
    resample, 
    stack_bands, 
    split_bands, 
    crop, 
    align_rasters
)

__all__ = [
    # Utils
    "resolve_envi_path",
    "extract_band_names",
    "extract_band_indices",

    # Layer
    "Raster",

    # I/O
    "load",
    "save",
    "write_window",
    "read_info",

    # Partition
    "iter_blocks",
    "iter_tiles",
    "iter_windows",
    "TileStitcher",

    # Resources
    "ProcessingMode",
    "BlockStructure",
    "MemoryEstimate",
    "analyze_structure",
    "estimate_memory_safety",

    # Engine
    "AggregationType",
    "DispatchConfig",
    "select_strategy",
    "dispatch",

    # Geom utilities
    "auto_load",
    "reproject", 
    "resample", 
    "stack_bands", 
    "split_bands", 
    "crop", 
    "align_rasters"
]