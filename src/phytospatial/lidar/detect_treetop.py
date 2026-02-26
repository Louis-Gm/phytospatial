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
    lmf_window_size: int = 5

def _detect_peaks_prominence(
    chm: np.ndarray, 
    params: DetectionParams
    ) -> Tuple[np.ndarray, np.ndarray]:
    """
    Detect treetop peaks using a morphological prominence-based algorithm.
    
    This method isolates true canopy apexes by evaluating their relative height 
    against their immediate topological surroundings rather than relying strictly 
    on absolute elevation.

    Steps:
        1. Applies a mild Gaussian filter (sigma=0.5) to the CHM to reduce artificial 
           micro-peaks caused by noisy LiDAR returns.
        2. Subtracts the user-defined `prominence_height` from the smoothed CHM to 
           create a basal elevation layer.
        3. Executes a morphological reconstruction (dilation) using the basal layer 
           as a seed and the smoothed CHM as a mask. This effectively 'fills in' 
           the valleys up to the base of the peaks.
        4. Subtracts the reconstructed surface from the smoothed CHM to isolate 
           h-domes (the standalone structural peaks separated from the continuous canopy).
        5. Generates a Boolean mask to retain only domes exhibiting a prominence greater 
           than 0.05 meters and an absolute elevation exceeding `params.min_height`.
        6. Applies a standard local maximum filter (`peak_local_max`) exclusively 
           within the masked valid dome regions to extract the final coordinates.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        params (DetectionParams): Configuration object containing prominence thresholds.

    Returns:
        Tuple[np.ndarray, np.ndarray]: Row and column indices of detected peaks.
    """
    # Smooth the CHM to reduce noise-induced micro-peaks
    chm_smooth = ndimage.gaussian_filter(chm, sigma=0.5)

    # Create a basal layer by subtracting the prominence height from the smoothed CHM
    apex = chm_smooth - params.prominence_height

    # Perform morphological reconstruction to fill in the valleys up to the base of the peaks
    reconstructed = reconstruction(apex, chm_smooth, method='dilation')
    
    # Subtract the reconstructed surface from the smoothed CHM to isolate the h-domes (the peaks)
    h_domes = chm_smooth - reconstructed
    
    # Create a mask to retain only domes that are sufficiently prominent and above the minimum height threshold
    min_dist_px = max(1, int(params.min_tree_distance / params.pixel_size))
    mask = (h_domes > 0.05) & (chm_smooth >= params.min_height)
    
    # Use peak_local_max to find the coordinates of the peaks within the masked valid dome regions
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
    Detect treetop peaks using a Variable Window Smoothing (VWS) spatial inhibition algorithm.
    
    This algorithm dynamically scales the search radius based on the localized height 
    of the canopy, adhering to the biological principle that taller trees naturally 
    exhibit wider crown diameters. It is JIT-compiled via Numba for extreme performance.

    Steps:
        1. Flattens the 2D CHM into a 1D array to optimize iteration speed.
        2. Iterates over the array to count and subsequently extract all pixels that 
           meet or exceed the absolute minimum height threshold (`threshold_abs`).
        3. Sorts the valid candidate pixels in descending order based on their elevation, 
           ensuring the algorithm evaluates the tallest apexes first.
        4. Initializes an empty 2D binary mask matching the CHM dimensions to track 
           spatial exclusion zones.
        5. Iterates through the sorted candidates:
           a. If the current pixel's spatial coordinate falls within an existing 
              exclusion zone in the mask, it is skipped.
           b. Otherwise, it is registered as a dominant peak.
           c. A dynamic suppression radius is calculated based on the peak's height:
              Radius = base_distance + (peak_height^power * scaling_factor).
           d. All pixels falling within this newly calculated radial boundary are 
              flagged as 1 in the exclusion mask, preventing them from being classified 
              as secondary peaks in future iterations.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        base_dist_px (float): Base exclusion distance in pixels.
        height_scale_px_per_m (float): Scaling factor multiplying tree height into pixel distance.
        threshold_abs (float): Minimum height threshold for valid candidates.
        power (float): Exponential multiplier dictating how aggressively the window scales with height.

    Returns:
        Tuple[list, list]: Lists containing the row and column indices of detected peaks.
    """
    # First, we flatten the 2D CHM into a 1D array for faster iteration and processing.
    rows, cols = chm.shape
    flat_chm = chm.ravel()
    
    # We count how many pixels meet the absolute height threshold to pre-allocate arrays for valid candidates.
    valid_count = 0
    for i in range(flat_chm.size):
        if flat_chm[i] >= threshold_abs: 
            valid_count += 1

    # We create arrays to hold the indices and values of the valid candidate pixels that exceed the height threshold.        
    valid_idxs = np.empty(valid_count, dtype=np.int64)
    valid_vals = np.empty(valid_count, dtype=chm.dtype)
    idx_c = 0
    # We populate the valid candidate arrays with the indices and corresponding CHM values of pixels that meet the height threshold.
    for i in range(flat_chm.size):
        if flat_chm[i] >= threshold_abs:
            valid_idxs[idx_c] = i
            valid_vals[idx_c] = flat_chm[i]
            idx_c += 1
            
    sort_order = np.argsort(valid_vals)[::-1]
    sorted_idxs = valid_idxs[sort_order]
    
    # We initialize an empty 2D binary mask to track the exclusion zones around detected peaks. 
    # This mask will be updated as we identify new peaks and their corresponding suppression areas.
    peaks_r = []
    peaks_c = []
    mask = np.zeros((rows, cols), dtype=np.int8)
    
    # We iterate through the sorted candidate pixels, starting with the tallest peaks. For each candidate:
    for idx in sorted_idxs:
        r = idx // cols
        c = idx % cols
        if mask[r, c] == 1: 
            continue

        # If the current pixel is not already within an exclusion zone, 
        # we register it as a detected peak and calculate a dynamic suppression radius based on its height.    
        peaks_r.append(r)
        peaks_c.append(c)
        peak_height = chm[r, c]
        
        # The dynamic suppression radius is calculated using the formula:
        # Radius = base_distance + (peak_height^power * scaling_factor)
        dynamic_dist_px = base_dist_px + ((peak_height ** power) * height_scale_px_per_m)
        dynamic_dist_sq = dynamic_dist_px ** 2
        
        # We determine the bounding box of pixels that fall within the dynamic suppression radius around the detected peak.
        r_min = max(0, int(r - dynamic_dist_px))
        r_max = min(rows, int(r + dynamic_dist_px + 1))
        c_min = max(0, int(c - dynamic_dist_px))
        c_max = min(cols, int(c + dynamic_dist_px + 1))
        
        # We iterate through the pixels within the bounding box defined by the dynamic radius and flag those that fall 
        # within the circular suppression area in the mask.
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
    Detect treetop peaks utilizing a static Local Maximum Filter (LMF).
    
    This is the traditional, computationally simple approach to stem detection, 
    ideal for uniform, single-species plantations where crown diameters do not 
    vary significantly.

    Steps:
        1. Convolves a fixed-size focal window (`params.lmf_window_size`) across 
           the entire CHM. At every pixel location, it calculates the maximum 
           elevation value within that window neighborhood.
        2. Creates a Boolean array where pixels are marked as True only if their 
           original CHM elevation is exactly equal to the maximum elevation found 
           in their focal window (identifying the local peaks).
        3. Applies an additional logical AND mask to ensure these isolated peaks 
           also exceed the absolute global minimum height threshold (`params.min_height`).
        4. Extracts the 2D spatial coordinates of all True values using `np.where`.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        params (DetectionParams): Configuration object dictating window size.

    Returns:
        Tuple[np.ndarray, np.ndarray]: Arrays containing row and column indices of peaks.      
    """
    # We apply a maximum filter to the CHM using a square window defined by `params.lmf_window_size`. 
    # This will give us an array where each pixel's value is the maximum value found in its neighborhood defined by the window size.
    local_max = ndimage.maximum_filter(chm, size=params.lmf_window_size) == chm
    
    # We create a Boolean mask to identify pixels that are local maxima and also exceed the minimum height threshold.
    valid_peaks = local_max & (chm >= params.min_height)
    
    # Finally, we extract the row and column indices of the valid peaks using `np.where` and return them as separate arrays.
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
    Detects treetop locations from a canopy height model (CHM) using specified 
    detection parameters and memory-safe processing strategies.
    
    Steps:
        1. Utilizes `iter_core_halo` to stream the CHM in partitioned spatial blocks. 
           Each block includes a core processing area and a halo overlap to eliminate 
           edge artifacts during algorithmic focal filtering.
        2. Routes the active block array to the specified detection function 
           (Prominence, VWS, or LMF) based on the `DetectionParams` configuration.
        3. Receives localized row and column peak indices from the algorithmic subroutines.
        4. Projects these localized pixel coordinates into global coordinate reference 
           system (CRS) points via the block's Affine transform matrix.
        5. Performs spatial filtering using `core_box.contains()` to discard any 
           detected tops that occurred within the halo overlap region, preventing 
           duplicate stem registrations across neighboring blocks.
        6. Yields a standardized dictionary mapping the verified geometric point, 
           associated elevation, and execution metadata back to the orchestrator.

    Args:
        chm_input (Union[str, Path, Raster]): Input CHM raster or path to CHM file.
        params (DetectionParams): Parameters dictating the active treetop detection algorithm.
        tile_mode (str): Tiling strategy for processing large rasters ('auto', 'in_memory', 'blocked', 'tiled').
        tile_size (int): Dimensions of the spatial partitions if streaming is necessary.
        overlap (int): Margin of pixels surrounding each block to ensure algorithm continuity.

    Yields:
        Dict[str, Any]: Structured payload containing 'height' (float), 'det_method' (str), and 'geometry' (shapely.Point).
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