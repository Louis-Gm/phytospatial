# src/phytospatial/raster/geom.py

"""
This module applies various geometric transformations to raster data.

It uses other raster modules under the hood to balance performance 
and safety (memory-awareness).
"""

import inspect
import logging
from pathlib import Path
from typing import Union, List, Optional, Tuple, Callable, Any
from functools import wraps

import numpy as np
from rasterio.warp import Resampling, calculate_default_transform, reproject as rio_reproject
from rasterio.crs import CRS
from rasterio.windows import from_bounds, transform as window_transform
from rasterio.transform import Affine

from phytospatial.raster.layer import Raster
from phytospatial.raster.io import load
from phytospatial.raster.resources import determine_strategy, ProcessingMode

log = logging.getLogger(__name__)

__all__ = [
    "auto_load",
    "reproject", 
    "resample", 
    "stack_bands", 
    "split_bands", 
    "crop", 
    "align_rasters"
]

def auto_load(
        safe: bool = True
        ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    A signature-aware polymorphic decorator that resolves raster filepaths into in-memory Raster objects.
    
    It selectively intercepts arguments passed as strings or Paths only if the target parameter's 
    signature explicitly expects a 'Raster'. 

    Args:
        safe (bool): Instructs the decorator to perform a preemptive memory safety assessment using 
            the resource subpackage before loading. If True, it prevents Out-Of-Memory (OOM) 
            errors by raising an exception if the raster exceeds safe capacity. Defaults to True.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: The wrapped function executed with fully 
            resolved Raster dependencies.

    Raises:
        MemoryError: If 'safe' is True and the target raster is evaluated as too large to safely 
            fit within the available system RAM for an in-memory operation.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        sig = inspect.signature(func)
        
        @wraps(func)
        def wrapper(
            *args: Any, 
            **kwargs: Any
            ) -> Any:
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            for name, param in sig.parameters.items():
                val = bound_args.arguments[name]
                
                if val is None:
                    continue
                    
                annot_str = str(param.annotation)
                expects_raster = "Raster" in annot_str or "raster" in name.lower()
                
                if expects_raster and isinstance(val, (str, Path)):
                    val_path = Path(val)
                    if not val_path.exists():
                        continue
                        
                    if safe:
                        report = determine_strategy(val_path, user_mode="auto")
                        if report.mode == ProcessingMode.IN_MEMORY:
                            raise MemoryError(
                                f"Unsafe to auto-load '{name}' ({val_path}).\n"
                                f"Reason: {report.reason}\n"
                                f"This function requires full in-memory loading. Use a streaming alternative."
                            )
                            
                    bound_args.arguments[name] = load(val_path)
                    
            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper
    return decorator

@auto_load(safe=True)
def reproject(
    raster: Raster, 
    target_crs: Union[str, CRS], 
    res: Optional[float] = None, 
    resampling: Resampling = Resampling.bilinear
    ) -> Raster:
    """
    Reproject a Raster to a new Coordinate Reference System (CRS).

    Args:
        raster: Input raster (Path or Raster object).
        target_crs: Destination CRS (EPSG code or proj string).
        res: Force a specific resolution in destination units. 
        resampling: Interpolation method (default: Bilinear).
                    Accepts other rasterio.warp.Resampling methods.

    Returns:
        Raster: A new Raster object in the target CRS.
    """
    # Normalize CRS
    dst_crs = CRS.from_string(target_crs) if isinstance(target_crs, str) else target_crs

    log.info(f"Reprojecting raster to {dst_crs} (Resampling: {resampling.name})")

    # Calculate new geospatial transform and dimensions
    dst_transform, dst_width, dst_height = calculate_default_transform(
        raster.crs, 
        dst_crs, 
        raster.width, 
        raster.height, 
        *raster.bounds, 
        resolution=res
    )

    # Allocate new array
    if raster.nodata is not None:
        new_data = np.full((raster.count, dst_height, dst_width), raster.nodata, dtype=raster.data.dtype)
    else:
        new_data = np.zeros((raster.count, dst_height, dst_width), dtype=raster.data.dtype)

    # Perform the warp
    rio_reproject(
        source=raster.data,
        destination=new_data,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        resampling=resampling
    )

    return Raster(
        data=new_data,
        transform=dst_transform,
        crs=dst_crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

@auto_load(safe=True)
def resample(
    raster: Raster, 
    scale_factor: float, 
    resampling: Resampling = Resampling.bilinear
    ) -> Raster:
    """
    Resample a raster by a scaling factor (Up/Down sampling).
    
    Args:
        raster: Input raster.
        scale_factor: Multiplier for dimensions (0.5 = half size).
        resampling: Interpolation method.
                    Accepts other rasterio.warp.Resampling methods.

    Returns:
        Raster: A new rescaled Raster object.
    """
    new_height = int(raster.height * scale_factor)
    new_width = int(raster.width * scale_factor)
    
    log.info(f"Resampling raster by {scale_factor}x ({raster.shape} -> {(raster.count, new_height, new_width)})")

    dst_transform = raster.transform * Affine.scale(1/scale_factor, 1/scale_factor)

    if raster.nodata is not None:
        new_data = np.full((raster.count, new_height, new_width), raster.nodata, dtype=raster.data.dtype)
    else:
        new_data = np.zeros((raster.count, new_height, new_width), dtype=raster.data.dtype)

    rio_reproject(
        source=raster.data,
        destination=new_data,
        src_transform=raster.transform,
        src_crs=raster.crs,
        dst_transform=dst_transform,
        dst_crs=raster.crs,
        resampling=resampling
    )

    return Raster(
        data=new_data,
        transform=dst_transform,
        crs=raster.crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

@auto_load(safe=True)
def crop(
    raster: Raster, 
    bounds: Tuple[float, float, float, float]
    ) -> Raster:
    """
    Crop raster to specified geographic bounds.
    
    Args:
        raster: Input raster.
        bounds: (minx, miny, maxx, maxy) in the same CRS as the raster.

    Returns:
        Raster: A new cropped Raster object.
    """
    minx, miny, maxx, maxy = bounds
    log.info(f"Cropping raster to bounds: {bounds}")

    window = from_bounds(minx, miny, maxx, maxy, transform=raster.transform)
    window = window.round_offsets(op='round').round_lengths(op='ceil')    
    
    row_start = max(0, int(window.row_off))
    row_end = min(raster.height, row_start + int(window.height))
    col_start = max(0, int(window.col_off))
    col_end = min(raster.width, col_start + int(window.width))

    if row_start >= row_end or col_start >= col_end:
        raise ValueError(
            f"Crop bounds {bounds} result in empty raster. "
            f"Raster bounds: {raster.bounds}"
        )

    new_data = raster.data[:, row_start:row_end, col_start:col_end].copy()
    new_transform = window_transform(window, raster.transform)

    return Raster(
        data=new_data,
        transform=new_transform,
        crs=raster.crs,
        nodata=raster.nodata,
        band_names=raster.band_names.copy()
    )

@auto_load(safe=True)
def split_bands(
    raster: Raster
    ) -> List[Raster]:
    """
    Splits a multi-band Raster into a list of single-band Rasters.
    
    Args:
        raster: Multi-band input raster.
        
    Returns:
        List[Raster]: One Raster object per band.
    """
    outputs = []
    
    for i in range(raster.count):
        # Single bands maintain 3D shape (1, H, W)
        band_data = raster.data[i : i+1, :, :].copy()
        band_name = None
        current_idx = i + 1
        for name, idx in raster.band_names.items():
            if idx == current_idx:
                band_name = name
                break
        
        single_band_names = {band_name: 1} if band_name else {}
        
        outputs.append(Raster(
            data=band_data,
            transform=raster.transform,
            crs=raster.crs,
            nodata=raster.nodata,
            band_names=single_band_names
        ))
        
    log.info(f"Split raster into {len(outputs)} single-band objects.")
    return outputs

def stack_bands(
        rasters: List[Union[str, Path, Raster]]
        ) -> Raster:
    """
    Combines a list of Rasters into a single multi-band Raster.

    Args:
        rasters: List of paths or Raster objects.

    Returns:
        Raster: A single multi-band Raster object.
    """
    if not rasters:
        raise ValueError("Cannot stack empty list of rasters.")

    loaded_rasters = []
    for r in rasters:
        if isinstance(r, (str, Path)):
            loaded_rasters.append(load(r))
        else:
            loaded_rasters.append(r)

    ref = loaded_rasters[0]
    total_bands = sum(r.count for r in loaded_rasters)

    for r in loaded_rasters[1:]:
        # Must have same dimensions and CRS
        if (r.width, r.height, r.crs, r.transform) != (ref.width, ref.height, ref.crs, ref.transform):
             raise ValueError(f"Dimension mismatch during stack: {r.shape} vs {ref.shape}")

    stacked_data = np.zeros((total_bands, ref.height, ref.width), dtype=ref.data.dtype)

    current_band = 0
    new_band_names = {}

    for r in loaded_rasters:
        band_count = r.count
        stacked_data[current_band : current_band + band_count] = r.data
        if r.band_names:
            for name, original_idx in r.band_names.items():
                new_band_names[name] = current_band + original_idx

        current_band += band_count

    log.info(f"Stacked {len(loaded_rasters)} rasters into new shape {stacked_data.shape}")

    return Raster(
        data=stacked_data,
        transform=ref.transform,
        crs=ref.crs,
        nodata=ref.nodata,
        band_names=new_band_names
    )

def align_rasters(
    rasters: List[Union[str, Path, Raster]], 
    method: str = 'first',
    resampling: Resampling = Resampling.nearest
    ) -> List[Raster]:
    """
    Align multiple rasters to a common grid.

    Args:
        rasters: List of input rasters (Paths or Objects).
        method: Alignment strategy. Default is 'first' (align to first raster).
        resampling: Interpolation method.

    Returns:
        List[Raster]: List of aligned Raster objects.
    """
    if not rasters:
        return []

    loaded_rasters = []
    for r in rasters:
        if isinstance(r, (str, Path)):
            loaded_rasters.append(load(r))
        else:
            loaded_rasters.append(r)

    if method == 'first':
        ref = loaded_rasters[0]
        log.info(f"Aligning {len(loaded_rasters)} rasters to reference: {ref.shape}")
    else:
        raise NotImplementedError(f"Alignment method '{method}' not implemented.")

    aligned_output = []
    
    for r in loaded_rasters:
        if (r.crs == ref.crs and 
            r.shape == ref.shape and 
            np.allclose(np.array(r.transform), np.array(ref.transform), atol=1e-6)):
            aligned_output.append(r)
            continue
            
        new_data = np.empty((r.count, ref.height, ref.width), dtype=r.data.dtype)
        
        rio_reproject(
            source=r.data,
            destination=new_data,
            src_transform=r.transform,
            src_crs=r.crs,
            dst_transform=ref.transform,
            dst_crs=ref.crs,
            resampling=resampling
        )
        
        aligned_output.append(Raster(
            data=new_data,
            transform=ref.transform,
            crs=ref.crs,
            nodata=r.nodata,
            band_names=r.band_names.copy()
        ))

    return aligned_output