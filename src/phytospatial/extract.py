# src/phytospatial/extract.py

"""
This module performs object-based extraction from raster data.

It manages interactions between raster and vector data, orchestrating the extraction
of pixel values for specified geometries. Features include adaptive processing
strategies (in-memory, tiled, blocked), handling of boundary-crossing geometries,
and optimized I/O operations.
"""

import logging
from typing import Union, List, Optional, Generator, Dict, Any, Literal, Tuple
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window, transform as window_transform
from rasterio.errors import WindowError
from shapely.geometry import box
from tqdm import tqdm

from .raster.layer import Raster
from .raster.utils import resolve_envi_path
from .raster.io import load, read_info
from .raster.partition import iter_tiles, iter_blocks
from .raster.resources import estimate_memory_safety, ProcessingMode
from .vector import Vector

log = logging.getLogger(__name__)

__all__ = [
    "extract_features",
    "extract_to_dataframe"
]

def _compute_basic_stats(pixel_values: np.ndarray, prefix: str) -> Dict[str, float]:
    """
    Computes basic statistics (Mean, Median, SD, Min, Max) for a pixel array.
    """
    if pixel_values.size == 0:
        return {}

    return {
        f"{prefix}_mean": float(np.mean(pixel_values)),
        f"{prefix}_med":  float(np.median(pixel_values)),
        f"{prefix}_sd":   float(np.std(pixel_values)),
        f"{prefix}_min":  float(np.min(pixel_values)),
        f"{prefix}_max":  float(np.max(pixel_values))
    }

def _process_geometry_in_memory(
    raster: Raster, 
    geometry: Any, 
    threshold: Optional[float] = None,
    return_raw: bool = False
) -> Dict[str, Any]:
    """
    Extracts pixel data for a single geometry from an in-memory Raster object.
    
    Adapted to work with the new phytospatial.raster.layer.Raster object.
    """
    try:
        raster_window = Window(0, 0, raster.width, raster.height)
        geom_window = from_bounds(
            *geometry.bounds, 
            transform=raster.transform
        ).round_offsets().round_lengths()

        try:
            safe_window = raster_window.intersection(geom_window)
        except WindowError:
            return {}
        
        row_slice, col_slice = safe_window.toslices()
        data_slice = raster.data[:, row_slice, col_slice]
        if data_slice.size == 0:
            return {}

        slice_transform = window_transform(safe_window, raster.transform)

    except (ValueError, AttributeError):
        return {}

    out_shape = (data_slice.shape[1], data_slice.shape[2])
    
    try:
        mask = geometry_mask(
            [geometry],
            out_shape=out_shape,
            transform=slice_transform,
            invert=True,
            all_touched=False
        )
        
        if not np.any(mask):
            mask = geometry_mask(
                [geometry],
                out_shape=out_shape,
                transform=slice_transform,
                invert=True,
                all_touched=True
            )

    except Exception:
        return {}

    stats_out = {}
    
    for b_idx in range(raster.count):
        band_num = b_idx + 1
        band_name = f"b{band_num}"        
        for name, idx in raster.band_names.items():
            if idx == band_num:
                band_name = name
                break
        
        band_pixels = data_slice[b_idx][mask]
        if raster.nodata is not None:
            band_pixels = band_pixels[band_pixels != raster.nodata]

        if threshold is not None:
            band_pixels = band_pixels[band_pixels > threshold]

        if band_pixels.size == 0:
            continue
        
        col_prefix = band_name
        
        if return_raw:
            stats_out[f"{col_prefix}_values"] = band_pixels.tolist()
        else:
            stats_out.update(_compute_basic_stats(band_pixels, col_prefix))

    return stats_out

def _validate_geometry(geom):
    """
    Validate and fix geometry if possible.
    """
    if not geom.is_valid:
        log.warning(f"Invalid geometry detected, attempting to fix...")
        geom = geom.buffer(0)
    return geom

def _determine_processing_strategy(
    raster_input: Union[str, Path, Raster],
    tile_mode: str
) -> Tuple[ProcessingMode, str, Any]:
    """
    Internal helper to decide how to iterate over the raster.
    
    Returns:
        (Selected ProcessingMode, Source Name, Pre-loaded Raster OR Path)
    """
    if isinstance(raster_input, Raster):
        return ProcessingMode.IN_MEMORY, "memory_raster", raster_input

    path = resolve_envi_path(raster_input)
    source_name = path.stem

    if tile_mode == "auto":
        estimate = estimate_memory_safety(path)
        log.info(f"Resource Estimate: {estimate.reason}")
        mode = estimate.recommendation
    else:
        try:
            mode = ProcessingMode(tile_mode)
        except ValueError:
            valid_modes = [m.value for m in ProcessingMode] + ["auto"]
            raise ValueError(f"Invalid mode '{tile_mode}'. Must be one of: {valid_modes}")

    return mode, source_name, path

def extract_features(
    raster_input: Union[str, Path, Raster],
    vector_input: Union[str, Path, Vector],
    bands: Optional[List[int]] = None,
    threshold: float = 0.001,
    return_raw: bool = False,
    tile_mode: Literal["auto", "tiled", "blocked", "in_memory"] = "auto",
    tile_size: int = 512
) -> Generator[Dict[str, Any], None, None]:
    """
    Main extraction pipeline. Orchestrates the spatial intersection between
    rasters and vectors.

    Features:
    - **Adaptive Processing**: Automatically selects In-Memory, Tiled, or Blocked 
      processing based on file size and structure (via `phytospatial.raster.resources`).
    - **Boundary Trees**: Handles geometries split across tiles by buffering raw pixels.
    - **Optimized I/O**: Only reads pixels for tiles that intersect vector data.

    Args:
        raster_input: Path to raster file or existing Raster object.
        vector_input: Path to vector file or existing Vector object.
        bands: List of 1-based band indices to process.
        threshold: Minimum pixel value filter (removes shadow/background).
        return_raw: If True, returns raw pixel lists instead of summary stats.
        tile_mode: "auto" (recommended), "tiled", "blocked", or "in_memory".
        tile_size: Tile size for "tiled" mode.

    Yields:
        Dictionary containing ID, species, and extracted metrics for each valid geometry.
    """
    if isinstance(vector_input, (str, Path)):
        vector_obj = Vector.from_file(vector_input)
    elif isinstance(vector_input, Vector):
        vector_obj = vector_input
    else:
        raise TypeError(f"vector_input must be a path or Vector object, got {type(vector_input)}")
    mode, raster_source_name, source_obj = _determine_processing_strategy(raster_input, tile_mode)

    raster_iterator = []
    raster_crs = None
    
    if mode == ProcessingMode.IN_MEMORY:
        log.info(f"Extracting features from {raster_source_name} in MEMORY...")
        if isinstance(source_obj, (str, Path)):
            full_raster = load(source_obj, bands=bands)
        else:
            full_raster = source_obj
        raster_crs = full_raster.crs
        raster_iterator = [(None, full_raster)]

    elif mode == ProcessingMode.BLOCKED:
        log.info(f"Extracting features from {raster_source_name} using BLOCKED streaming...")
        metadata = read_info(source_obj)
        raster_crs = metadata['crs']
        raster_iterator = iter_blocks(source_obj, bands=bands)

    elif mode == ProcessingMode.TILED:
        log.info(f"Extracting features from {raster_source_name} using TILED streaming (size={tile_size})...")
        metadata = read_info(source_obj)
        raster_crs = metadata['crs']
        raster_iterator = iter_tiles(source_obj, tile_size=tile_size, bands=bands, overlap=0)
    else:
        raise ValueError(f"Unknown processing mode: {mode}")

    if vector_obj.crs != raster_crs:
        log.info(f"CRS Mismatch: Reprojecting vectors from {vector_obj.crs} to {raster_crs}...")
        vector_obj = vector_obj.to_crs(raster_crs, inplace=False)
    
    crowns_gdf = vector_obj.data
    
    boundary_buffer = defaultdict(lambda: defaultdict(list))
    crown_metadata = {} 
    fully_processed_ids = set()

    for window, tile_raster in raster_iterator:
        tile_box = box(*tile_raster.bounds)
        
        if crowns_gdf.sindex:
            possible_matches_index = list(crowns_gdf.sindex.intersection(tile_box.bounds))
            local_trees = crowns_gdf.iloc[possible_matches_index]
        else:
            local_trees = crowns_gdf
        
        local_trees = local_trees[local_trees.intersects(tile_box)]

        if local_trees.empty:
            continue

        for idx, row in local_trees.iterrows():
            crown_id = row.get('crown_id', idx)
            if crown_id in fully_processed_ids:
                continue

            geom = _validate_geometry(row.geometry)
            is_fully_within = True if window is None else geom.within(tile_box)
            # if tree is split, extract raw pixels for merging later
            force_raw = not is_fully_within

            species = row.get('species', None)

            feats = _process_geometry_in_memory(
                raster=tile_raster,
                geometry=geom,
                threshold=threshold,
                return_raw=(return_raw or force_raw) 
            )

            if not feats:
                continue

            if is_fully_within:
                fully_processed_ids.add(crown_id)
                if force_raw and not return_raw:
                    final_stats = {}
                    for key, pixels in feats.items():
                        if key.endswith("_values"):
                            band_name = key.replace("_values", "")
                            final_stats.update(_compute_basic_stats(np.array(pixels), band_name))
                    feats = final_stats

                result = {
                    'crown_id': crown_id,
                    'species': species,
                    'raster_source': raster_source_name
                }
                result.update(feats)
                yield result

            else:
                if crown_id not in crown_metadata:
                    crown_metadata[crown_id] = {
                        'species': species,
                        'raster_source': raster_source_name
                    }

                for key, val in feats.items():
                    boundary_buffer[crown_id][key].extend(val)

    if boundary_buffer:
        log.info(f"Processing {len(boundary_buffer)} boundary-crossing trees...")
    
    for crown_id, band_data in boundary_buffer.items():
        if crown_id in fully_processed_ids:
            continue
            
        result = {'crown_id': crown_id}
        result.update(crown_metadata.get(crown_id, {}))
        
        extracted_data = {}
        
        for key, all_pixels in band_data.items():
            pixel_array = np.array(all_pixels)
            
            if return_raw:
                extracted_data[key] = pixel_array.tolist()
            else:
                prefix = key.replace("_values", "")
                extracted_data.update(_compute_basic_stats(pixel_array, prefix))
        
        if extracted_data:
            result.update(extracted_data)
            yield result

def extract_to_dataframe(
    raster_input: Union[str, Path, Raster],
    vector_input: Union[str, Path, Vector],
    tile_mode: Literal["auto", "tiled", "blocked", "in_memory"] = "auto",
    tile_size: int = 512,
    **kwargs
) -> pd.DataFrame:
    """
    Wrapper around extract_features that consumes the generator and 
    returns a pandas DataFrame.
    
    Args:
        raster_input: Path to raster or Raster object.
        vector_input: Path to vector or Vector object.
        tile_mode: Processing strategy ("auto", "tiled", "blocked", "in_memory").
        tile_size: Tile size when tile_mode="tiled".
        **kwargs: Additional arguments passed to extract_features.

    Returns:
        DataFrame containing extracted features for all geometries.
    """
    results = list(tqdm(
        extract_features(
            raster_input, 
            vector_input, 
            tile_mode=tile_mode,
            tile_size=tile_size,
            **kwargs
        ),
        desc=f"Extracting Features ({tile_mode} mode)"
    ))
    return pd.DataFrame(results)