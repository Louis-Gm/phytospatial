# src/phytospatial/raster/resources.py

"""
This module performs static analysis on raster files and 
system hardware to answer two critical questions:
1. Is there enough RAM to load this file? (Memory Safety)
2. Is this file structured efficiently for streaming? (Structure Analysis)
"""

import logging
import psutil
from pathlib import Path
from typing import Union, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

import numpy as np
import rasterio

from .utils import resolve_envi_path

log = logging.getLogger(__name__)

__all__ = [
    "ProcessingMode",
    "BlockStructure",
    "MemoryEstimate",
    "analyze_structure",
    "estimate_memory_safety"
]

DEFAULT_SAFETY_FACTOR = 3.0 
MIN_FREE_GB = 2.0
MAX_BLOCK_ASPECT_RATIO = 4.0

class ProcessingMode(Enum):
    """
    Strategic recommendation for how to process a raster.
    """
    IN_MEMORY = "in_memory"  # Fastest, requires loading full file.
    TILED = "tiled"          # Standard streaming. Reliable memory usage.
    BLOCKED = "blocked"      # Optimized streaming. Uses file's internal chunks.

@dataclass
class BlockStructure:
    """
    Analysis of a raster's internal storage layout.
    
    Attributes:
        is_tiled (bool): True if stored in rectangular tiles.
        is_striped (bool): True if stored in rows/strips.
        block_shape (Tuple[int, int]): The dimensions (height, width) of a single block.
        total_blocks (int): Total number of blocks in the file.
        efficiency_score (float): 0.0 to 1.0. A score of how suitable this structure 
                                  is for spatial processing.
                                  - 1.0 = Perfect square tiles.
                                  - 0.0 = Scanlines (1px height).
    """
    is_tiled: bool
    is_striped: bool
    block_shape: Tuple[int, int]
    total_blocks: int
    efficiency_score: float

    @property
    def is_efficient(self) -> bool:
        """Helper to determine if BLOCKED mode is recommended."""
        return self.efficiency_score >= 0.7

@dataclass
class MemoryEstimate:
    """
    Detailed breakdown of memory requirements and safety status.

    Attributes:
        raw_bytes (int): The pure C-buffer size of the pixel data.
        overhead_bytes (int): Estimated Python overhead.
        total_required_bytes (int): raw + overhead.
        available_system_bytes (int): Current available system RAM.
        is_safe (bool): True if load fits in RAM with safety margin.
        margin (float): Percentage (0.0-1.0) of RAM free after
                            loading the raster.
        recommendation (ProcessingMode): Suggested processing mode.
        reason (str): Human-readable explanation of the recommendation.
    """
    raw_bytes: int
    overhead_bytes: int
    total_required_bytes: int
    available_system_bytes: int
    is_safe: bool
    margin: float
    recommendation: ProcessingMode
    reason: str


def _calculate_efficiency(block_h: int, block_w: int, raster_w: int) -> float:
    """
    Helper to score block efficiency for spatial processing.
    """
    ratio = max(block_h, block_w) / min(block_h, block_w)
    aspect_score = max(0.0, 1.0 - (math.log(ratio) / math.log(20)))
    is_scanline = (block_h == 1)
    is_full_width_strip = (block_w >= raster_w and block_h < 128)
    
    if is_scanline:
        return 0.0
    if is_full_width_strip:
        return 0.2
    
    pixels = block_h * block_w
    ideal_pixels = 512 * 512
    
    if pixels < (64 * 64):
        size_score = 0.5
    elif pixels > (4096 * 4096):
        size_score = 0.4
    else:
        size_score = 1.0

    return (aspect_score * 0.6) + (size_score * 0.4)

def analyze_structure(path: Union[str, Path]) -> BlockStructure:
    """
    Inspect a raster's internal block/tile layout.
    
    This function opens the file in a lightweight mode to read metadata tags
    regarding TIFF structuring (TILED vs STRIPED).
    
    Args:
        path: Path to the raster file.
        
    Returns:
        BlockStructure: Detailed analysis of the file's layout.
        
    Raises:
        FileNotFoundError: If path does not exist.
        IOError: If rasterio cannot inspect the file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Cannot analyze structure: file not found {path}")

    path = resolve_envi_path(path)

    try:
        with rasterio.open(path) as src:
            if not src.block_shapes:
                log.warning(f"Driver {src.driver} does not report block shapes. Assuming inefficient.")
                return BlockStructure(
                    is_tiled=False, is_striped=False, 
                    block_shape=(0,0), total_blocks=0, efficiency_score=0.0
                )

            block_h, block_w = src.block_shapes[0]
            
            try:
                n_rows = math.ceil(src.height / block_h)
                n_cols = math.ceil(src.width / block_w)
                total_blocks = n_rows * n_cols
            except Exception:
                total_blocks = 0
            
            is_striped = (block_w == src.width) or (block_h == 1)
            is_explicitly_tiled = src.profile.get('tiled', False)
            ratio = max(block_h, block_w) / min(block_h, block_w)
            is_geometrically_tiled = (ratio < 2.0) and (not is_striped)
            
            is_tiled = is_explicitly_tiled or is_geometrically_tiled

            score = _calculate_efficiency(block_h, block_w, src.width)

            return BlockStructure(
                is_tiled=is_tiled,
                is_striped=is_striped,
                block_shape=(block_h, block_w),
                total_blocks=total_blocks,
                efficiency_score=score
            )

    except Exception as e:
        log.error(f"Failed to analyze block structure for {path}: {e}")
        raise IOError(f"Structure analysis failed: {e}") from e


def estimate_memory_safety(
    path: Union[str, Path],
    bands: Optional[int] = None,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    min_free_gb: float = MIN_FREE_GB
) -> MemoryEstimate:
    """
    Determine if a raster is safe to load into system RAM.
    
    Args:
        path: File path.
        bands: Number of bands to load. If None, uses all bands in file.
        safety_factor: Multiplier for overhead (3.0 = 3x raw size).
        min_free_gb: Absolute floor for free RAM to preserve OS stability.
        
    Returns:
        MemoryEstimate: Data class with bytes and recommendation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    path = resolve_envi_path(path)

    try:
        with rasterio.open(path) as src:
            width = src.width
            height = src.height
            count = bands if bands is not None else src.count
            dtype_size = np.dtype(src.dtypes[0]).itemsize
            struct_info = analyze_structure(path)

        total_pixels = width * height * count
        raw_bytes = total_pixels * dtype_size
        overhead_bytes = int(raw_bytes * (safety_factor - 1.0))
        total_required = raw_bytes + overhead_bytes

        mem = psutil.virtual_memory()
        available = mem.available
        min_free_bytes = int(min_free_gb * (1024**3))
        is_safe = (total_required + min_free_bytes) <= available
        
        if available > 0:
            margin = (available - total_required) / available
        else:
            margin = 0.0

        if is_safe:
            rec = ProcessingMode.IN_MEMORY
            reason = (
                f"Safe to load. Req: {total_required / 1024**3:.2f}GB, "
                f"Avail: {available / 1024**3:.2f}GB"
            )
        else:
            if struct_info.is_efficient:
                rec = ProcessingMode.BLOCKED
                reason = (
                    f"Too large for RAM (Req: {total_required / 1024**3:.2f}GB). "
                    f"File is tiled efficienty (score {struct_info.efficiency_score:.2f}), "
                    f"recommending BLOCKED mode."
                )
            else:
                rec = ProcessingMode.TILED
                reason = (
                    f"Too large for RAM (Req: {total_required / 1024**3:.2f}GB). "
                    f"File structure is inefficient (score {struct_info.efficiency_score:.2f}), "
                    f"recommending TILED mode."
                )

        return MemoryEstimate(
            raw_bytes=raw_bytes,
            overhead_bytes=overhead_bytes,
            total_required_bytes=total_required,
            available_system_bytes=available,
            is_safe=is_safe,
            margin=margin,
            recommendation=rec,
            reason=reason
        )

    except Exception as e:
        log.error(f"Memory estimation failed for {path}: {e}")
        raise IOError(f"Could not estimate memory: {e}") from e