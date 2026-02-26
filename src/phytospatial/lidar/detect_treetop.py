# src/phytospatial/lidar/detect_treetop.py

"""
This module implements functions for detecting treetop locations from canopy height models (CHMs) derived from lidar data.
"""

import logging
from typing import Tuple, Union, Generator, Dict, Any
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy.ndimage as ndimage
from numba import jit
from skimage.morphology import reconstruction
from skimage.feature import peak_local_max
from shapely.geometry import Point

from phytospatial.raster.layer import Raster
from phytospatial.raster.partition import iter_core_halo

log = logging.getLogger(__name__)

__all__ = [
    "DetectionParams",
    "detect_treetops"
]

@dataclass
class DetectionParams:
    """
    Parameters for treetop detection algorithms.

    Args:
        detection_method (str): Method to use for treetop detection. Options: "prominence", "vws", "lmf".
        pixel_size (float): Spatial resolution of the CHM in the same units as min_tree_distance.
        min_height (float): Minimum height threshold for valid treetops (in same units as CHM).
        min_tree_distance (float): Minimum distance between detected treetops (in same units as CHM).
        prominence_height (float): Height above local background for prominence-based detection (in same units as CHM).
        vws_detection_sigma (float): Sigma for Gaussian smoothing in VWS method. Set to 0 for no smoothing.
        vws_distance_scale (float): Scaling factor for distance in VWS method (in same units as CHM).
        vws_power (float): Power to which height is raised in VWS method for distance scaling.
    """
    detection_method: str = "prominence"
    pixel_size: float = 0.25
    min_height: float = 3.0         
    min_tree_distance: float = 1.5         
    prominence_height: float = 1.0     
    vws_detection_sigma: float = 2.0   
    vws_distance_scale: float = 0.12   
    vws_power: float = 1.0

def _detect_peaks_prominence(
    chm: np.ndarray, 
    params: DetectionParams
    ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect treetop peaks using a prominence-based method.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        params (DetectionParams): Parameters for the detection algorithm.
    """
    chm_smooth = ndimage.gaussian_filter(chm, sigma=0.5)
    apex = chm_smooth - params.prominence_height
    reconstructed = reconstruction(apex, chm_smooth, method='dilation')
    h_domes = chm_smooth - reconstructed
    
    min_dist_px = max(1, int(params.min_tree_distance / params.pixel_size))
    mask = (h_domes > 0.05) & (chm_smooth >= params.min_height)
    
    peaks = peak_local_max(chm_smooth, min_distance=min_dist_px, labels=ndimage.label(mask)[0])
    if len(peaks) == 0: 
        return np.array([]), np.array([])
    return peaks[:, 0], peaks[:, 1]

@jit(nopython=True, cache=True)
def _detect_peaks_vws(
    chm: np.ndarray, 
    base_dist_px: float, 
    height_scale_px_per_m: float, 
    threshold_abs: float, power: float
    ):
    """
    Detect treetop peaks using a variable window size method.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        base_dist_px (float): Base distance in pixels for the minimum tree distance.
        height_scale_px_per_m (float): Scaling factor to convert tree height to additional pixel distance.
        threshold_abs (float): Minimum height threshold for valid treetops.
        power (float): Power to which height is raised for distance scaling.

    Returns:
        Tuple of arrays containing the row and column indices of detected peaks.
    """
    rows, cols = chm.shape
    flat_chm = chm.ravel()
    
    valid_count = 0
    for i in range(flat_chm.size):
        if flat_chm[i] >= threshold_abs: 
            valid_count += 1
            
    valid_idxs = np.empty(valid_count, dtype=np.int64)
    valid_vals = np.empty(valid_count, dtype=chm.dtype)
    idx_c = 0
    for i in range(flat_chm.size):
        if flat_chm[i] >= threshold_abs:
            valid_idxs[idx_c] = i
            valid_vals[idx_c] = flat_chm[i]
            idx_c += 1
            
    sort_order = np.argsort(valid_vals)[::-1]
    sorted_idxs = valid_idxs[sort_order]
    
    peaks_r = []
    peaks_c = []
    mask = np.zeros((rows, cols), dtype=np.int8)
    
    for idx in sorted_idxs:
        r = idx // cols
        c = idx % cols
        if mask[r, c] == 1: 
            continue
            
        peaks_r.append(r)
        peaks_c.append(c)
        peak_height = chm[r, c]
        
        dynamic_dist_px = base_dist_px + ((peak_height ** power) * height_scale_px_per_m)
        dynamic_dist_sq = dynamic_dist_px ** 2
        
        r_min = max(0, int(r - dynamic_dist_px))
        r_max = min(rows, int(r + dynamic_dist_px + 1))
        c_min = max(0, int(c - dynamic_dist_px))
        c_max = min(cols, int(c + dynamic_dist_px + 1))
        
        for ir in range(r_min, r_max):
            for ic in range(c_min, c_max):
                if mask[ir, ic] == 0 and (ir - r)**2 + (ic - c)**2 <= dynamic_dist_sq:
                    mask[ir, ic] = 1

    return peaks_r, peaks_c

def _detect_peaks_lmf(
    chm: np.ndarray, 
    params: DetectionParams
    ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect treetop peaks using a local maximum filter method.
    
    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        params (DetectionParams): Parameters for the detection algorithm.

    Returns:
        Tuple of arrays containing the row and column indices of detected peaks.        
    """
    local_max = ndimage.maximum_filter(chm, size=params.lmf_window_size) == chm
    valid_peaks = local_max & (chm >= params.min_height)
    peaks_r, peaks_c = np.where(valid_peaks)
    return peaks_r, peaks_c

def detect_treetops(
    chm_input: Union[str, Path, Raster], 
    params: DetectionParams = DetectionParams(),
    tile_mode: str = "auto",
    tile_size: int = 1024,
    overlap: int = 64
    ) -> Generator[Dict[str, Any], None, None]:
    """
    Detects treetop locations from a canopy height model (CHM) using specified detection parameters and processing strategy.

    Args:
        chm_input (Union[str, Path, Raster]): Input CHM raster or path to CHM file.
        params (DetectionParams): Parameters for treetop detection algorithms.
        tile_mode (str): Tiling strategy for processing large rasters ('auto', 'in_memory', 'blocked', 'tiled').
        tile_size (int): Size of tiles to use if tiling is necessary.
        overlap (int): Number of pixels to overlap between tiles to avoid edge effects.

    Yields:
        Dict[str, Any]: A dictionary containing the height, detection method, and geometry of each detected treetop.
    """
    # iter_core_halo is a generator that yields core tiles of the CHM along with their halo (overlap) and the affine transform for georeferencing.
    # We use it to process the CHM in manageable chunks, which allows us to handle larger rasters that may not fit into memory all at once.
    # Without the halo, we might miss treetops that are near the edges of the tiles, so the overlap ensures we can detect those properly.
    for chm, transform, core_box, _ in iter_core_halo(chm_input, tile_mode, tile_size, overlap):
        
        # We call the appropriate method to detect peaks in the current tile of the CHM based on the specified detection method in the parameters.
        if params.detection_method == "prominence":
            peaks_r, peaks_c = _detect_peaks_prominence(chm, params)
        elif params.detection_method == "vws":
            chm_detect = ndimage.gaussian_filter(chm, sigma=params.vws_detection_sigma) if params.vws_detection_sigma > 0 else chm
            peaks_r, peaks_c = _detect_peaks_vws(
                chm_detect, 
                params.min_tree_distance / params.pixel_size, 
                params.vws_distance_scale / params.pixel_size, 
                params.min_height,
                params.vws_power
            )
        elif params.detection_method == "lmf":
            peaks_r, peaks_c = _detect_peaks_lmf(chm, params)
        else: 
            raise ValueError(f"Unknown detection method: {params.detection_method}")

        # The detected peaks are returned as row and column indices relative to the current tile.
        # We need to convert these to spatial coordinates using the affine transform, and we also filter them based on the core box
        # to ensure we only return valid detections that are not in the halo area.    
        apex_ref = np.column_stack((peaks_r, peaks_c))
        if len(apex_ref) == 0:
            continue
            
        for r, c in apex_ref:
            top_x, top_y = transform * (c + 0.5, r + 0.5)
            geom = Point(top_x, top_y)
            
            if core_box is not None and not core_box.contains(geom):
                continue

            # Finally, we yield a metadata dictionary for each detected treetop containing its height, detection method used, and its geometry (Point).    
            yield {
                "height": float(chm[r, c]),
                "det_method": params.detection_method,
                "geometry": geom
            }