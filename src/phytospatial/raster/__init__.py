# src/phytospatial/raster/__init__.py
#
# Copyright (c) The phytospatial project contributors
# This software is distributed under the Apache-2.0 license.
# See the NOTICE file for more information

"""
The raster subpackage provides core functionality for handling raster data,
including I/O operations, partitioning strategies, resource management,
engine dispatching and geometry utilities.
"""
# Core data structure
from .layer import (
    Raster
)

# I/O operations
from .io import (
    load,
    save,
    write_window,
    read_info,
    ensure_tiled_raster
)

# Resource management
from .resources import (
    ProcessingMode,
    MemoryEstimate,
    StrategyReport,
    determine_strategy
)

# Partition operations
from .partition import (
    iter_blocks,
    iter_tiles,
    iter_windows,
    TileStitcher,
    iter_core_halo
)

# Engine operations
from .engine import (
    AggregationType,
    DispatchConfig,
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

# Shared utilities
from .utils import (
    resolve_envi_path,
    extract_band_names,
    extract_band_indices,
    extract_wavelength,
    map_wavelengths
)

# Spectral index registry
from .indices import (
    SpectralIndex,
    IndexCatalog
)

# Compute functions
from .compute_index import (
    calculate_index_block,
    generate_index
)

__all__ = [
    # Index generation
    "calculate_index_block",
    "generate_index",

    # Spectral registry
    "SpectralIndex",
    "IndexCatalog",

    # Utils
    "resolve_envi_path",
    "extract_band_names",
    "extract_band_indices",
    "extract_wavelength",
    "map_wavelengths",

    # Layer
    "Raster",

    # I/O
    "load",
    "save",
    "write_window",
    "read_info",
    "ensure_tiled_raster",

    # Partition
    "iter_blocks",
    "iter_tiles",
    "iter_windows",
    "TileStitcher",
    "iter_core_halo",

    # Resources
    "ProcessingMode",
    "MemoryEstimate",
    "StrategyReport",
    "determine_strategy",
    
    # Engine
    "AggregationType",
    "DispatchConfig",
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