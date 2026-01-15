# src/phytospatial/raster_geometry.py

import logging
from typing import Union, List, Optional, Tuple
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject as rio_reproject
from rasterio.crs import CRS
from rasterio.windows import from_bounds
from rasterio.transform import window_transform, Affine

from phytospatial.raster_layer import Raster, resolve_raster, RasterValidationError

log = logging.getLogger(__name__)

__all__ = ["reproject", "resample", "stack_bands", "split_bands", "crop", "align_rasters"]

@resolve_raster
def reproject(
    raster: Raster, 
    target_crs: Union[str, CRS], 
    res: Optional[float] = None, 
    resampling: Resampling = Resampling.bilinear
) -> Raster:
    """
    Reprojects a Raster to a new Coordinate Reference System (CRS).

    This function handles the geospatial warping of the pixel grid. It computes
    the new transform and dimensions required to fit the data in the new CRS.
    
    Args:
        raster (Raster): The input raster (auto-resolved from path or object).
        target_crs (str | CRS): Destination CRS (EPSG code or proj string).
        res (float, optional): Force a specific resolution in destination units. 
                               If None, preserves the original pixel density.
        resampling (Resampling): Interpolation method (default: Bilinear). 
                                 Use Resampling.nearest for categorical data.

    Returns:
        Raster: A new Raster object in the target CRS.
    """
    # Normalize CRS
    if isinstance(target_crs, str):
        dst_crs = CRS.from_string(target_crs)
    else:
        dst_crs = target_crs

    log.info(f"Reprojecting raster to {dst_crs} (Resampling: {resampling.name})")

    # Calculate new Geospatial Transform and Dimensions
    dst_transform, dst_width, dst_height = calculate_default_transform(
        raster.crs, 
        dst_crs, 
        raster.width, 
        raster.height, 
        *raster.bounds, 
        resolution=res
    )

    # Allocate memory for the new pixel grid
    new_data = np.zeros((raster.count, dst_height, dst_width), dtype=raster.data.dtype)

    # Perform the Warp
    rio_reproject(
        source=raster.data,
        destination=new_data,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling
    )

    # Return new Raster object
    return Raster(
        data=new_data,
        transform=dst_transform,
        crs=dst_crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

@resolve_raster
def resample(
    raster: Raster, 
    scale_factor: float, 
    resampling: Resampling = Resampling.bilinear
) -> Raster:
    """
    Resamples a raster by a scaling factor without changing the CRS.
    Used for downsampling (scale < 1.0) or upsampling (scale > 1.0).
    
    Args:
        raster (Raster): Input raster.
        scale_factor (float): Multiplier for dimensions (0.5 = half size).
        resampling (Resampling): Interpolation method.

    Returns:
        Raster: A new rescaled Raster object.
    """
    new_height = int(raster.height * scale_factor)
    new_width = int(raster.width * scale_factor)
    
    log.info(f"Resampling raster by {scale_factor}x ({raster.shape} -> {(raster.count, new_height, new_width)})")

    # Update transform for new resolution (pixel size changes, origin stays same)
    dst_transform = raster.transform * Affine.scale(1/scale_factor, 1/scale_factor)

    new_data = np.zeros((raster.count, new_height, new_width), dtype=raster.data.dtype)

    # Process all bands at once
    rio_reproject(
        source=raster.data,
        destination=new_data,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=dst_transform,
        dst_crs=raster.crs,
        resampling=resampling
    )

    # Return new Raster object    
    return Raster(
        data=new_data,
        transform=dst_transform,
        crs=raster.crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

def stack_bands(rasters: List[Union[str, Path, Raster]]) -> Raster:
    """
    Combines a list of Rasters into a single multi-band Raster.
    
    All inputs must share the same spatial grid (CRS, Transform, Dimensions).
    If they do not, consider running "align_rasters" first.

    Args:
        rasters: List of paths or Raster objects.

    Returns:
        Raster: A single multi-band Raster object.
        
    Raises:
        RasterValidationError: If dimensions mismatch.
    """
    if not rasters:
        raise ValueError("Cannot stack empty list of rasters.")

    # Resolve the first raster as reference
    ref_obj = rasters[0]
    if isinstance(ref_obj, (str, Path)):
        ref = Raster.from_file(ref_obj)
    else:
        ref = ref_obj
    
    processing_list = [ref] + rasters[1:]

    # Prepare metadata
    total_bands = ref.count

    for r in processing_list:
        if isinstance(r, (str, Path)):
            # Just read metadata without loading data
            with rasterio.open(r) as src:
                if (src.width != ref.width) or (src.height != ref.height):
                     raise RasterValidationError(f"Dimension mismatch in {r}")
                total_bands += src.count
        else:
            # Check object in memory (instant)
            if (r.width != ref.width) or (r.height != ref.height):
                 raise RasterValidationError(f"Dimension mismatch in object")
            total_bands += r.count

    # Allocate memory for stacked data
    stacked_data = np.zeros((total_bands, ref.height, ref.width), dtype=ref.data.dtype)

    current_band = 0
    new_band_names = {}

    # Iterate over the full list to stack everything including the reference
    for item in processing_list:
        # Load data (if path) or use data (if object)
        if isinstance(item, (str, Path)):
            r = Raster.from_file(item)
        else:
            r = item
        
        # Copy bands into the stacked array
        band_count = r.count
        stacked_data[current_band : current_band + band_count] = r.data

        if r.band_names:
            for name, _ in r.band_names.items():
                new_band_names[name] = current_band + 1  # +1 for 1-based indexing

        current_band += band_count

    log.info(f"Stacked {len(rasters)} rasters into new shape {stacked_data.shape}")

    # Return stacked Raster as an object
    return Raster(
        data=stacked_data,
        transform=ref.transform,
        crs=ref.crs,
        nodata=ref.nodata,
        band_names=new_band_names
    )

@resolve_raster
def split_bands(raster: Raster) -> List[Raster]:
    """
    Splits a multi-band Raster into a list of single-band Rasters.
    
    Args:
        raster: Multi-band input raster.
        
    Returns:
        List[Raster]: One Raster object per band.
    """
    outputs = []
    
    for i in range(raster.count):
        # Extract single band data
        band_data = raster.data[i : i+1, :, :].copy() # copy to ensure independence
        
        # Determine band name if available
        band_name = None
        current_idx = i + 1
        for name, idx in raster.band_names.items():
            if idx == current_idx:
                band_name = name
                break
        
        single_band_names = {band_name: 1} if band_name else {}
        
        # Append new Raster object
        outputs.append(Raster(
            data=band_data,
            transform=raster.transform,
            crs=raster.crs,
            nodata=raster.nodata,
            band_names=single_band_names
        ))
        
    log.info(f"Split raster into {len(outputs)} single-band objects.")
    return outputs

@resolve_raster
def crop(raster: Raster, bounds: Tuple[float, float, float, float]) -> Raster:
    """
    Crop raster to specific geographic bounds.
    
    Args:
        raster (Raster): Input raster.
        bounds (Tuple): (minx, miny, maxx, maxy) in the same CRS as the raster.

    Returns:
        Raster: A new cropped Raster object.
    """
    minx, miny, maxx, maxy = bounds
    log.info(f"Cropping raster to bounds: {bounds}")

    # Calculate the window in pixel coordinates
    window = from_bounds(minx, miny, maxx, maxy, transform=raster.transform)

    # Rounding offsets snaps to the nearest pixel grid (avoids half-pixels)
    window = window.round_offsets(op='round').round_shape(op='ceil')
    
    # Calculate array slices
    row_start = int(window.row_off)
    row_end = row_start + int(window.height)
    col_start = int(window.col_off)
    col_end = col_start + int(window.width)

    # Handle boundary conditions (clamping to image dimensions)
    row_start = max(0, row_start)
    row_end = min(raster.height, row_end)
    col_start = max(0, col_start)
    col_end = min(raster.width, col_end)

    # Slice the data
    new_data = raster.data[:, row_start:row_end, col_start:col_end].copy()
    
    # Update transform for the new top-left corner
    # NOTE: We calculate transform based on the actual sliced window
    new_transform = window_transform(
        window, 
        raster.transform
    )

    # Return new Raster object
    return Raster(
        data=new_data,
        transform=new_transform,
        crs=raster.crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

def align_rasters(
    rasters: List[Union[str, Path, Raster]], 
    method: str = 'first',
    resampling: Resampling = Resampling.nearest
) -> List[Raster]:
    """
    Align multiple rasters to a common grid (CRS, Transform, Dimensions).
    
    This is essential before stacking bands or performing pixel-wise arithmetic
    between different rasters.

    Args:
        rasters (List[Raster]): List of input rasters.
        method (str): Alignment strategy. Currently supports 'first'.
        resampling (Resampling): Interpolation method for warping.

    Returns:
        List[Raster]: List of aligned Raster objects.
    """
    if not rasters:
        return []

    # Resolve all inputs to objects first
    resolved_rasters = []
    for r in rasters:
        if isinstance(r, (str, Path)):
            resolved_rasters.append(Raster.from_file(r))
        else:
            resolved_rasters.append(r)

    if method == 'first':
        ref = resolved_rasters[0]
        log.info(f"Aligning {len(resolved_rasters)} rasters to reference: {ref.shape}")
    else:
        raise NotImplementedError(f"Alignment method '{method}' not implemented.")

    aligned_output = []
    
    for r in resolved_rasters:
        # Check if already aligned (CRS, Transform, Shape)
        # We use a small tolerance for transform comparison
        if (r.crs == ref.crs and 
            r.shape == ref.shape and 
            np.allclose(np.array(r.transform), np.array(ref.transform), atol=1e-6)):
            aligned_output.append(r)
            continue
            
        # Perform warping to match reference exactly
        new_data = np.zeros((r.count, ref.height, ref.width), dtype=r.data.dtype)
        
        rio_reproject(
            source=r.data,
            destination=new_data,
            src_transform=r.transform,
            src_crs=r.crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=resampling
        )
        
        # Append the new Raster object
        aligned_output.append(Raster(
            data=new_data,
            transform=ref.transform,
            crs=ref.crs,
            nodata=r.nodata,
            band_names=r.band_names.copy()
        ))

    return aligned_output