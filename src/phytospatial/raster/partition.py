# src/phytospatial/raster/partition.py

"""
This module provides partitioning strategies for raster data.

It includes functions for block-based, tile-based, and window-based iteration,
as well as a TileStitcher class for reassembling raster tiles
into a single raster file on disk.
"""

import logging
from pathlib import Path
from typing import Union, Optional, List, Iterator, Tuple, Dict, Any

import rasterio
from rasterio.windows import Window
from rasterio.windows import transform as compute_window_transform

from .layer import Raster
from .utils import resolve_envi_path, extract_band_indices, extract_band_names

log = logging.getLogger(__name__)

__all__ = [
    "iter_blocks",
    "iter_tiles", 
    "iter_windows",
    "TileStitcher"
]

def iter_blocks(
    path: Union[str, Path],
    bands: Optional[Union[int, List[int]]] = None
) -> Iterator[Tuple[Window, Raster]]:
    """
    Stream data using the file's native internal block structure.
    
    This function acts as a pure mechanism. It assumes the caller (engine.py)
    has already verified that the file structure is efficient for blocking.

    Args:
        path: Path to the raster file. All GDAL-supported formats are accepted.
        bands: Specific band(s) to load (None=all, int=single, list=subset).

    Yields:
        Tuple[Window, Raster]: A window and corresponding Raster object.
    """
    path = resolve_envi_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    try:
        with rasterio.open(path) as src:
            indices = extract_band_indices(src, bands)
            for _, window in src.block_windows(1):
                data = src.read(indexes=indices, window=window)
                tile_transform = src.window_transform(window)

                band_names = extract_band_names(src, indices)
                
                yield window, Raster(
                    data=data,
                    transform=tile_transform,
                    crs=src.crs,
                    nodata=src.nodata,
                    band_names=band_names
                )
                
    except rasterio.RasterioIOError as e:
        raise IOError(f"Block iteration failed for {path}: {e}") from e


def iter_tiles(
    path: Union[str, Path],
    tile_size: Union[int, Tuple[int, int]] = 512,
    overlap: int = 0,
    bands: Optional[Union[int, List[int]]] = None
) -> Iterator[Tuple[Window, Raster]]:
    """
    Stream data using a virtual grid of fixed-size tiles.

    Args:
        path: Path to the raster file. All GDAL-supported formats are accepted.
        tile_size: Dimensions (width, height) or single int for square tiles.
        overlap: Pixels of overlap between tiles.
        bands: Specific band(s) to load (None=all, int=single, list=subset).

    Yields:
        Tuple[Window, Raster]: A window and corresponding Raster object.
    """
    path = resolve_envi_path(path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
        
    if isinstance(tile_size, int):
        t_width, t_height = tile_size, tile_size
    else:
        t_width, t_height = tile_size

    if overlap >= min(t_width, t_height):
        raise ValueError(f"Overlap ({overlap}) must be smaller than tile dimensions")

    step_w = t_width - overlap
    step_h = t_height - overlap

    try:
        with rasterio.open(path) as src:
            indices = extract_band_indices(src, bands)
            
            for row_off in range(0, src.height, step_h):
                for col_off in range(0, src.width, step_w):
                    
                    width = min(t_width, src.width - col_off)
                    height = min(t_height, src.height - row_off)
                    
                    window = Window(col_off, row_off, width, height)
                    
                    data = src.read(indexes=indices, window=window)
                    tile_transform = src.window_transform(window)
                    band_names = extract_band_names(src, indices)
                    
                    yield window, Raster(
                        data=data,
                        transform=tile_transform,
                        crs=src.crs,
                        nodata=src.nodata,
                        band_names=band_names
                    )
                    
    except rasterio.RasterioIOError as e:
        raise IOError(f"Tile iteration failed for {path}: {e}") from e

def iter_windows(
    raster: Raster,
    tile_size: Union[int, Tuple[int, int]] = 512,
    overlap: int = 0
) -> Iterator[Tuple[Window, Raster]]:
    """
    Partition an in-memory Raster object into smaller Raster tiles.
    
    Useful for batch processing a loaded raster, notably for neural networks.
    
    Args:
        raster: The source Raster object (already in memory).
        tile_size: Dimensions (width, height) or single int for square tiles.
        overlap: Pixels of overlap.
        
    Yields:
        Tuple[Window, Raster]: A deep copy of the sliced data as a new Raster.
    """
    if isinstance(tile_size, int):
        t_width, t_height = tile_size, tile_size
    else:
        t_width, t_height = tile_size

    if overlap >= min(t_width, t_height):
        raise ValueError(f"Overlap ({overlap}) must be smaller than tile dimensions")

    step_w = t_width - overlap
    step_h = t_height - overlap
    
    for row_off in range(0, raster.height, step_h):
        for col_off in range(0, raster.width, step_w):
            
            width = min(t_width, raster.width - col_off)
            height = min(t_height, raster.height - row_off)
            
            window = Window(
                col_off=col_off,
                row_off=row_off,
                width=width,
                height=height
            )

            tile_data = raster.data[
                :, 
                row_off : row_off + height, 
                col_off : col_off + width
            ].copy() # Deep copy to ensure independence
            
            tile_transform = compute_window_transform(window, raster.transform)
            
            tile_raster = Raster(
                data=tile_data,
                transform=tile_transform,
                crs=raster.crs,
                nodata=raster.nodata,
                band_names=raster.band_names.copy()
            )
            
            yield window, tile_raster


class TileStitcher:
    """
    Reassembles Raster tiles into a single file on disk.
    
    Acts as a context manager to ensure the output file is closed properly.
    Checks bounds to ensure tiles are written exactly where they are intended.
    """
    
    def __init__(
        self,
        output_path: Union[str, Path],
        profile: Dict[str, Any],
        **profile_overrides
    ):
        """
        Open a new raster file for writing.
        
        Args:
            output_path: Destination path.
            profile: Rasterio profile (metadata).
            **profile_overrides: Changes to the profile (e.g., dtype, compression).

        Raises:
            IOError: If the file cannot be created/opened.
        """
        self.output_path = Path(output_path)
        self.profile = profile.copy()
        self.profile.update(profile_overrides)
        
        # Ensure directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        self._dst = None
        self._tiles_written = 0
        
        try:
            # We open in 'w' mode to create/overwrite, but we need to keep it open
            self._dst = rasterio.open(self.output_path, 'w', **self.profile)
        except Exception as e:
            raise IOError(f"Failed to initialize stitcher at {self.output_path}: {e}") from e

    def add_tile(
        self,
        window: Window,
        tile: Raster,
        indexes: Optional[List[int]] = None
    ):
        """
        Write a tile to the output file.
        
        Args:
            window: The specific window in the output file where this data goes.
            tile: The Raster object containing the data.
            indexes: Specific bands to write to.
            
        Raises:
            ValueError: If the tile shape does not match the window shape.
            RuntimeError: If the stitcher is closed.
        """
        if self._dst is None:
            raise RuntimeError("Attempted to write to a closed TileStitcher.")
            
        if (tile.height != window.height) or (tile.width != window.width):
            raise ValueError(
                f"Dimension Mismatch: Window is {window.width}x{window.height}, "
                f"but Tile is {tile.width}x{tile.height}."
            )
            
        try:
            self._dst.write(tile.data, window=window, indexes=indexes)
            self._tiles_written += 1
        except Exception as e:
            raise IOError(f"Failed to write tile to {window}: {e}") from e

    def finalize(self):
        """Flush and close the file."""
        if self._dst:
            self._dst.close()
            self._dst = None
            log.debug(f"Stitcher closed. Total tiles written: {self._tiles_written}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.finalize()