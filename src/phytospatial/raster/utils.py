# src/phytospatial/raster/utils.py

"""
This module provides shared utility functions for raster operations.

Functions include path resolution for ENVI files,
band extraction, and other common tasks.
"""
import logging
import re
from pathlib import Path
from typing import Union, List, Optional, Dict

import numpy as np
import rasterio

log = logging.getLogger(__name__)

__all__ = [
    "resolve_envi_path",
    "extract_band_indices",
    "extract_band_names",
    "map_wavelengths",
    "extract_wavelength"
]

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
    """
    Normalize band selection to a list of 1-based indices.
    """
    if bands is None:
        return list(src.indexes)
    elif isinstance(bands, int):
        return [bands]
    return list(bands)

def extract_band_names(
    src: rasterio.DatasetReader, 
    indices: List[int]
) -> Dict[str, int]:
    """
    Extract descriptions/names for specific bands.
    """
    band_names = {}
    for i, idx in enumerate(indices):
        if 0 <= (idx - 1) < len(src.descriptions):
            desc = src.descriptions[idx - 1]
            if desc:
                band_names[desc] = i + 1
    return band_names

def extract_wavelength(band_name: str) -> float:
    match = re.search(r'(\d+(?:\.\d+)?)\s*(?:nm|nanometers?)', band_name, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return -1.0

def map_wavelengths(
    parsed_wavelengths: Dict[float, int], 
    required_wavelengths: Dict[str, float],
    max_tolerance: float = 20.0
) -> Dict[str, int]:
    """
    Matches required formula variables to actual 1-based band indices based on wavelength proximity.
    """
    if not parsed_wavelengths:
        raise ValueError("No parsable wavelengths found in file metadata or descriptions.")
        
    available_wvl = np.array(list(parsed_wavelengths.keys()))
    mapping = {}
    
    for var_name, target_wvl in required_wavelengths.items():
        idx = np.argmin(np.abs(available_wvl - target_wvl))
        matched_wvl = available_wvl[idx]
        
        if abs(matched_wvl - target_wvl) > max_tolerance:
            raise ValueError(f"No band found within {max_tolerance}nm of {target_wvl}nm for '{var_name}'")
            
        mapping[var_name] = parsed_wavelengths[matched_wvl]
        
    return mapping