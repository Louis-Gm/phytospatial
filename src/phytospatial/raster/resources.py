# src/phytospatial/raster/resources.py

"""
This module performs static analysis on raster files and system hardware.

It checks two key aspects before processing:
- Memory safety for loading into RAM (Memory Estimation)
- Internal block/tile structure of the raster (Block Structure Analysis)
"""

import logging
import psutil
from pathlib import Path
from typing import Union, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

import numpy as np
import rasterio

from .utils import resolve_envi_path

log = logging.getLogger(__name__)

__all__ = [
    "ProcessingMode",
    "MemoryEstimate",
    "StrategyReport",
    "determine_strategy"
]

DEFAULT_SAFETY_FACTOR = 3.0 
MIN_FREE_GB = 2.0

class ProcessingMode(Enum):
    """
    Strategic recommendation for how to process a raster.

    Modes:
        IN_MEMORY: Load entire raster into RAM. Fastest but requires sufficient memory.
        BLOCKED: Use raster's internal blocks/tiles for optimized streaming. Best for tiled files.
        TILED: Use standard windowed reading. Safe fallback for large or scanline
    """
    IN_MEMORY = "in_memory"
    BLOCKED = "blocked"
    TILED = "tiled"

@dataclass(frozen=True)
class BlockStructure:
    """
    Analysis of a raster's internal storage layout.

    Args:
        is_tiled: True if raster has native tiles (not full-width strips)
        is_striped: True if raster is structured as strips (full-width blocks)
        block_shape: Tuple of (block_height, block_width) in pixels
    """
    is_tiled: bool
    is_striped: bool
    block_shape: Tuple[int, int]

    @property
    def _recommend_blocked(self) -> bool:
        """Helper to determine if BLOCKED mode is recommended."""
        return self.is_tiled and not self.is_striped

@dataclass(frozen=True)
class MemoryEstimate:
    """"Estimation of memory requirements and safety for loading a raster.
    
    Args:
        total_required_bytes: Total bytes required to load raster (with overhead)
        available_system_bytes: Currently available system memory in bytes
        is_safe: Boolean indicating if loading is considered safe
        reason: Explanation for the safety assessment (e.g. "Req: 10GB,
    """
    total_required_bytes: int
    available_system_bytes: int
    is_safe: bool
    reason: str

@dataclass(frozen=True)
class StrategyReport:
    """
    Contains the decision (mode) and the full context (reason, stats).

    Args:
        mode: Recommended processing mode (ProcessingMode)
        reason: Explanation for the recommendation
        memory_stats: MemoryEstimate object with details on memory safety
        structure_stats: BlockStructure object with details on raster structure
    """
    mode: ProcessingMode
    reason: str
    memory_stats: MemoryEstimate
    structure_stats: BlockStructure

def _analyze_structure(src: rasterio.DatasetReader) -> BlockStructure:
    """Helper that determines if the raster is physically tiled or striped.
    
    Args:
        src: Opened rasterio DatasetReader object.
        
    Returns:
        BlockStructure: Contains flags for tiled/striped and block shape.
    """
    try:
        if not src.block_shapes:
            # Fail safe: If block_shapes is empty, assume unsuitable for BLOCKED mode
            return BlockStructure(False, True, (0,0))

        block_h, block_w = src.block_shapes[0]
        w, h = src.width, src.height
                
        # A file is considered "striped" if it:
        #   1) has block shapes that are full width
        #   2) is structured as a single row of pixels
        is_striped = (block_w == w) or (block_h == 1)
        is_tiled = not is_striped

        return BlockStructure(
            is_tiled=is_tiled,
            is_striped=is_striped,
            block_shape=(block_h, block_w)
        )

    except Exception as e:
        # Fail safe: If structure analysis fails, assume unsuitable for BLOCKED mode
        log.warning(f"Structure analysis failed: {e}")
        return BlockStructure(False, True, (0,0))


def _estimate_memory_safety(
    src: rasterio.DatasetReader,
    bands: Optional[int] = None,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    min_free_gb: float = MIN_FREE_GB
) -> MemoryEstimate:
    """
    Helper that checks if raster fits in RAM safely checking all band dtypes.

    args:
        src: Opened rasterio DatasetReader object.
        bands: Optional number of bands to consider (default all)
        safety_factor: Multiplier to account for overhead (default 3.0)
        min_free_gb: Minimum free GB to leave available after loading (default 2.0)

    Returns:
        MemoryEstimate: Contains total required bytes, available bytes, safety boolean, and reason.
    """
    # Sum exact byte size per pixel for all required bands
    num_bands = bands if bands is not None else src.count
    bytes_per_pixel = sum(np.dtype(src.dtypes[i]).itemsize for i in range(num_bands))
    
    raw_bytes = src.width * src.height * bytes_per_pixel
    overhead_bytes = int(raw_bytes * (safety_factor - 1.0))
    total_required = raw_bytes + overhead_bytes

    mem = psutil.virtual_memory()
    min_free_bytes = int(min_free_gb * (1024**3))
    is_safe = (total_required + min_free_bytes) <= mem.available
    
    reason = f"Req: {total_required/1e9:.2f}GB, Avail: {mem.available/1e9:.2f}GB"
        
    return MemoryEstimate(total_required, mem.available, is_safe, reason)

def determine_strategy(
    raster_path: Union[str, Path],
    user_mode: str = "auto"
) -> StrategyReport:
    """
    Determines the optimal processing strategy for a raster based on memory and internal structure.

    Args:
        raster_path: Path to the raster file to analyze.
        user_mode: Defines available processing modes ('auto', 'in_memory', 'blocked', 'tiled')
            auto: Automatically determine best mode based on analysis
            in_memory: Force loading entire raster into RAM (only if safe)
            blocked: Force using BLOCKED mode (only if structure is suitable)
            tiled: Force using TILED mode (safe fallback)

    Returns:
        StrategyReport: Contains the recommended mode and the context for that decision.
    """
    path = resolve_envi_path(Path(raster_path))
    
    # SINGLE PASS I/O
    try:
        with rasterio.open(path) as src:
            estimate = _estimate_memory_safety(src)
            struct = _analyze_structure(src)
    except Exception as e:
        log.error(f"Failed to analyze resources for {path}: {e}")
        # Fail safe fallback if file cannot be read properly
        estimate = MemoryEstimate(0, 0, False, f"Read Error: {e}")
        struct = BlockStructure(False, True, (0,0))

    # User Override Logic
    if user_mode != "auto":
        try:
            mode = ProcessingMode(user_mode)
            reason = f"User forced mode: {user_mode}"
            
            if mode == ProcessingMode.BLOCKED and not struct._recommend_blocked:
                mode = ProcessingMode.TILED
                reason = "Override: Forced TILED because file is STRIPED (User requested BLOCKED)"
                
            return StrategyReport(mode, reason, estimate, struct)
            
        except ValueError:
            valid_modes = [m.value for m in ProcessingMode] + ["auto"]
            raise ValueError(f"Invalid mode '{user_mode}'. Must be one of: {valid_modes}")

    # Auto Logic
    if estimate.is_safe:
        return StrategyReport(
            mode=ProcessingMode.IN_MEMORY,
            reason=f"Safe for RAM. {estimate.reason}",
            memory_stats=estimate,
            structure_stats=struct
        )
    
    if struct._recommend_blocked:
        return StrategyReport(
            mode=ProcessingMode.BLOCKED,
            reason="RAM full, but detected NATIVE TILES. Using BLOCKED mode.",
            memory_stats=estimate,
            structure_stats=struct
        )
    else:
        return StrategyReport(
            mode=ProcessingMode.TILED,
            reason="RAM full and detected STRIPS. Using TILED mode.",
            memory_stats=estimate,
            structure_stats=struct
        )