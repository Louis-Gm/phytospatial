# src/phytospatial/raster/utils.py

"""
This module provides shared utility functions for raster operations,
including path resolution and band extraction.
"""

from pathlib import Path
from typing import Union, List, Optional, Dict
import rasterio

def resolve_envi_path(path: Union[str, Path]) -> Path:
    """
    Resolve ENVI header/binary file confusion.
    If 'image.hdr' is passed, redirects to 'image' (binary).
    """
    path = Path(path)
    if path.suffix.lower() == '.hdr':
        binary_path = path.with_suffix('')
        if binary_path.exists():
            return binary_path
    return path

def extract_band_indices(
    src: rasterio.DatasetReader, 
    bands: Optional[Union[int, List[int]]]
) -> List[int]:
    """Normalize band selection to a list of 1-based indices."""
    if bands is None:
        return list(src.indexes)
    elif isinstance(bands, int):
        return [bands]
    return list(bands)

def extract_band_names(
    src: rasterio.DatasetReader, 
    indices: List[int]
) -> Dict[str, int]:
    """Extract descriptions/names for specific bands."""
    band_names = {}
    for i, idx in enumerate(indices):
        if 0 <= (idx - 1) < len(src.descriptions):
            desc = src.descriptions[idx - 1]
            if desc:
                band_names[desc] = i + 1
    return band_names