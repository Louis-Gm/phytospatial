# src/phytospatial/raster/io.py

"""
This module handles all disk-based operations for raster data.
"""

from functools import wraps
import inspect
import logging
from pathlib import Path
from typing import Callable, Union, Optional, List, Dict, Any

import rasterio
from rasterio.windows import Window

from phytospatial.raster.utils import resolve_envi_path, extract_band_indices, extract_band_names, extract_wavelength
from phytospatial.raster.layer import Raster
from phytospatial.raster.resources import ProcessingMode, determine_strategy

log = logging.getLogger(__name__)

__all__ = [
    "load",
    "save",
    "write_window",
    "read_info",
    "ensure_tiled_raster",
    "resolve_raster"
]

def load(
    path: Union[str, Path],
    bands: Optional[Union[int, List[int]]] = None,
    window: Optional[Window] = None,
    driver: Optional[str] = None
    ) -> Raster:
    """
    Load a raster from disk into memory.
    
    This function reads a geospatial raster file and returns a Raster object
    with data loaded into RAM. Supports loading all bands, specific bands,
    or a spatial subset via a window.
    
    Args:
        path: Path to raster file. All supported GDAL formats are accepted.
        bands: Specific band(s) to load (None=all, int=single, list=subset).
        window: Optional rasterio Window object to load only a spatial subset.
        driver: Optional GDAL driver name.
    
    Returns:
        Raster: In-memory Raster object
    """
    path = Path(path)
    path = resolve_envi_path(path)

    if not path.exists():
        raise FileNotFoundError(f"Raster file not found: {path}")

    log.debug(f"Loading raster: {path.name}")
    
    try:
        with rasterio.open(path, driver=driver) as src:
            indices = extract_band_indices(src, bands)
            data = src.read(indices, window=window)
            band_names = extract_band_names(src, indices)

            if window is not None:
                transform = src.window_transform(window)
            else:
                transform = src.transform

            return Raster(
                data=data,
                transform=transform,
                crs=src.crs,
                nodata=src.nodata,
                band_names=band_names
            )
            
    except rasterio.RasterioIOError as e:
        raise IOError(f"Failed to read raster from {path}: {e}") from e
    
def save(
    raster: Raster,
    path: Union[str, Path],
    **profile_kwargs: Any
    ) -> None:
    """
    Write a Raster object to disk.
    Creates a new geospatial raster file from the in-memory Raster object.
    
    Args:
        raster: Raster object to save
        path: Output file path. All supported GDAL formats are accepted.
        **profile_kwargs (Any): Override default rasterio profile settings.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    profile = raster.profile.copy()
    profile.update(profile_kwargs)

    log.info(f"Saving raster {raster.shape} → {path}")
    
    try:
        with rasterio.open(path, 'w', **profile) as dst:
            dst.write(raster.data)
            
            if raster.band_names:
                for name, idx in raster.band_names.items():
                    if 1 <= idx <= raster.count:
                        dst.set_band_description(idx, name)
                        
    except Exception as e:
        raise IOError(f"Failed to save raster to {path}: {e}") from e

def write_window(
    raster: Raster,
    path: Union[str, Path],
    window: Window,
    indexes: Optional[List[int]] = None
):
    """
    Write raster data to a specific window in an existing file.
    
    Useful for tile stitching. Target file must exist and handle the same schema.
    
    Args:
        raster: Raster object containing data to write
        path: Path to EXISTING raster file. All supported GDAL formats are accepted.
        window: Window defining where to write.
        indexes: Optional list of band indices to write to.
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(
            f"Cannot write to window: target file does not exist: {path}\n"
            f"Tip: Create the file first using save(), then write tiles to it."
        )

    log.debug(f"Writing window {window} → {path.name}")
    
    try:
        with rasterio.open(path, 'r+') as dst:
            if indexes:
                if len(indexes) != raster.count:
                    raise ValueError(
                        f"Indexes length ({len(indexes)}) must match "
                        f"raster band count ({raster.count})"
                    )
                dst.write(raster.data, window=window, indexes=indexes)
            else:
                dst.write(raster.data, window=window)
                
    except Exception as e:
        raise IOError(f"Failed to write window to {path}: {e}") from e

def read_info(
        path: Union[str, Path]
        ) -> Dict[str, Any]:
    """
    Intelligently inspects a raster file, extracting spatial metadata, 
    band descriptions, and spectral wavelengths in a single pass.
    """
    path = resolve_envi_path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
        
    try:
        with rasterio.open(path) as src:
            band_names = {}
            wavelengths_nm = {}
            
            for i in src.indexes:
                desc = src.descriptions[i - 1]
                band_names[desc or f"Band_{i}"] = i
                
                tags = src.tags(i)
                wvl = tags.get('WAVELENGTH') or tags.get('CENTRAL_WAVELENGTH')
                
                if wvl is None and desc:
                    wvl = extract_wavelength(desc)
                    if wvl < 0: 
                        wvl = None
                
                if wvl is not None:
                    try:
                        wavelengths_nm[float(wvl)] = i
                    except ValueError:
                        pass
                        
            return {
                'crs': src.crs,
                'transform': src.transform,
                'bounds': src.bounds,
                'width': src.width,
                'height': src.height,
                'count': src.count,
                'driver': src.driver,
                'nodata': src.nodata,
                'band_names': band_names,
                'wavelengths_nm': wavelengths_nm
            }
    except Exception as e:
        raise IOError(f"Failed to read metadata from {path}: {e}") from e
    
def ensure_tiled_raster(
    path: Union[str, Path], 
    output_dir: Optional[Union[str, Path]] = None,
    block_size: int = 512
    ) -> Path:
    """
    Analyzes raster structure and translates striped or untiled files 
    into optimized, tiled GeoTIFFs to prevent I/O thrashing.

    Args:
        path (Union[str, Path]): Path to the input raster.
        output_dir (Optional[Union[str, Path]]): Destination directory for the optimized file.
        block_size (int): Dimensions for the internal X and Y blocks.

    Returns:
        Path: Path to the optimally tiled raster (original path if no conversion was needed).
    """
    path = resolve_envi_path(Path(path))
    report = determine_strategy(path)
    
    if report.structure_stats.is_tiled and not report.structure_stats.is_striped:
        log.info(f"Raster {path.name} is natively tiled. No conversion needed.")
        return path
        
    log.warning(f"Raster {path.name} is STRIPED/UNTILED. Translating to tiled GeoTIFF...")
    
    out_dir = Path(output_dir) if output_dir else path.parent
    out_path = out_dir / f"{path.stem}_tiled.tif"
    
    with rasterio.open(path) as src:
        profile = src.profile.copy()
        
        profile.update(
            driver='GTiff',
            tiled=True,
            blockxsize=block_size,
            blockysize=block_size,
            interleave='pixel' 
        )
        
        with rasterio.open(out_path, 'w', **profile) as dst:
            for row_off in range(0, src.height, block_size):
                height = min(block_size, src.height - row_off)
                window = Window(0, row_off, src.width, height)
                
                data = src.read(window=window)
                dst.write(data, window=window)
                
    log.info(f"Successfully optimized raster into {out_path.name}")
    return out_path
    
def resolve_raster(
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
                        if report.mode != ProcessingMode.IN_MEMORY: 
                            raise MemoryError(
                                f"Unsafe to auto-load '{name}' ({val_path}).\n"
                                f"Reason: {report.reason}\n"
                                f"This function requires full in-memory loading. Use a streaming alternative."
                            )
                        
                    bound_args.arguments[name] = load(val_path)
            return func(*bound_args.args, **bound_args.kwargs)
        return wrapper
    return decorator