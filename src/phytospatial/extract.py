# src/phytospatial/extract.py

"""
This module performs object-based extraction from raster data.

It manages interactions between raster and vector data, orchestrating the extraction
of pixel values for specified geometries. Features include adaptive processing
strategies, handling of boundary-crossing geometries, and optimized Polars output.
"""

import logging
from typing import Union, List, Optional, Generator, Dict, Any, Literal, Tuple
from pathlib import Path
from collections import defaultdict

import numpy as np
import polars as pl
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window, transform as window_transform
from rasterio.errors import WindowError
from shapely.geometry import box

from .raster.layer import Raster
from .raster.io import load, read_info
from .raster.partition import iter_tiles, iter_blocks
from .raster.resources import ProcessingMode, determine_strategy
from .vector import Vector

log = logging.getLogger(__name__)

__all__ = [
    "extract_features",
    "extract_to_dataframe"
]

def _process_geometry_in_memory(
    raster: Raster, 
    geometry: Any, 
    threshold: Optional[float] = None,
    return_raw: bool = False,
    idx_to_name: Optional[Dict[int, str]] = None
) -> Dict[str, Any]:
    """
    Extracts pixel data using Vectorized NumPy operations.
    """
    try:
        # Window Intersection Logic
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

        # Geometry Mask Logic
        slice_transform = window_transform(safe_window, raster.transform)
        out_shape = (data_slice.shape[1], data_slice.shape[2])
        
        mask = geometry_mask(
            [geometry],
            out_shape=out_shape,
            transform=slice_transform,
            invert=True,
            all_touched=False
        )
        
        if not np.any(mask):
            # Fallback for small polygons
            mask = geometry_mask(
                [geometry],
                out_shape=out_shape,
                transform=slice_transform,
                invert=True,
                all_touched=True
            )
            if not np.any(mask):
                return {}

    except (ValueError, AttributeError, Exception):
        return {}

    masked_pixels = data_slice[:, mask]
    
    # Handle NoData
    if raster.nodata is not None:
        if np.isnan(raster.nodata):
            valid_mask = ~np.isnan(masked_pixels)
        else:
            valid_mask = masked_pixels != raster.nodata
        
        pixel_validity = np.all(valid_mask, axis=0)
        masked_pixels = masked_pixels[:, pixel_validity]

    if masked_pixels.size == 0:
        return {}

    # Handle Threshold
    if threshold is not None:
        thresh_mask = np.all(masked_pixels > threshold, axis=0)
        masked_pixels = masked_pixels[:, thresh_mask]
        
        if masked_pixels.size == 0:
            return {}

    stats_out = {}
    
    # Lazy init of names if not provided
    if idx_to_name is None:
        idx_to_name = {v: k for k, v in raster.band_names.items()}

    if return_raw:
        raw_values = masked_pixels.tolist()
        for b_idx in range(raster.count):
            band_num = b_idx + 1
            name = idx_to_name.get(band_num, f"b{band_num}")
            stats_out[f"{name}_values"] = raw_values[b_idx]
    else:
        # Broadcasting Stats
        med = np.median(masked_pixels, axis=1)
        mean = np.mean(masked_pixels, axis=1)
        std = np.std(masked_pixels, axis=1)
        min = np.min(masked_pixels, axis=1)
        max = np.max(masked_pixels, axis=1)
        
        for b_idx in range(raster.count):
            band_num = b_idx + 1
            name = idx_to_name.get(band_num, f"b{band_num}")
            stats_out[f"{name}_med"] = float(med[b_idx])
            stats_out[f"{name}_mean"] = float(mean[b_idx])
            stats_out[f"{name}_sd"]   = float(std[b_idx])
            stats_out[f"{name}_min"]  = float(min[b_idx])
            stats_out[f"{name}_max"]  = float(max[b_idx])

    return stats_out

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
    Main extraction pipeline.
    """
    # Load Vector (Auto-Repair Enabled)
    if isinstance(vector_input, (str, Path)):
        vector_obj = Vector.from_file(vector_input, auto_repair=True)
    elif isinstance(vector_input, Vector):
        vector_obj = vector_input.validate(fix_invalid=True, drop_invalid=False)
    else:
        raise TypeError(f"vector_input must be a path or Vector object")
    
    # Determine Strategy
    if isinstance(raster_input, Raster):
        mode = ProcessingMode.IN_MEMORY
        source_name = "memory_raster"
        source_obj = raster_input
        log.info("Strategy: IN_MEMORY (Raster object provided directly)")
    else:
        path = raster_input
        report = determine_strategy(path, user_mode=tile_mode)
        mode = report.mode
        source_name = path.stem
        source_obj = path

    # Setup Iterator
    raster_iterator = []
    raster_crs = None
    
    if mode == ProcessingMode.IN_MEMORY:
        log.info(f"Extracting features from {source_name} in MEMORY...")
        if isinstance(source_obj, (str, Path)):
            full_raster = load(source_obj, bands=bands)
        else:
            full_raster = source_obj
        raster_crs = full_raster.crs
        raster_iterator = [(None, full_raster)]

    elif mode == ProcessingMode.BLOCKED:
        log.info(f"Extracting features from {source_name} using BLOCKED streaming...")
        metadata = read_info(source_obj)
        raster_crs = metadata['crs']
        raster_iterator = iter_blocks(source_obj, bands=bands)

    elif mode == ProcessingMode.TILED:
        log.info(f"Extracting features from {source_name} using TILED streaming...")
        metadata = read_info(source_obj)
        raster_crs = metadata['crs']
        raster_iterator = iter_tiles(source_obj, tile_size=tile_size, bands=bands, overlap=0)

    # CRS Alignment
    if vector_obj.crs != raster_crs:
        log.info(f"CRS Mismatch: Reprojecting vectors...")
        vector_obj = vector_obj.to_crs(raster_crs, inplace=False)
    
    crowns_gdf = vector_obj.data
    sindex = crowns_gdf.sindex

    boundary_buffer = defaultdict(lambda: defaultdict(list))
    crown_metadata = {} 
    fully_processed_ids = set()

    for window, tile_raster in raster_iterator:
        tile_box = box(*tile_raster.bounds)
        
        # Optimized Spatial Query
        if sindex:
            possible_matches_index = list(sindex.intersection(tile_box.bounds))
            local_trees = crowns_gdf.iloc[possible_matches_index]
        else:
            local_trees = crowns_gdf
        
        local_trees = local_trees[local_trees.intersects(tile_box)]

        if local_trees.empty:
            continue
            
        idx_to_name = {v: k for k, v in tile_raster.band_names.items()}
        for idx, row in local_trees.iterrows():
            crown_id = row.get('crown_id', idx)
            if crown_id in fully_processed_ids:
                continue

            geom = row.geometry
            is_fully_within = True if window is None else geom.within(tile_box)
            force_raw = not is_fully_within
            species = row.get('species', None)

            feats = _process_geometry_in_memory(
                raster=tile_raster,
                geometry=geom,
                threshold=threshold,
                return_raw=(return_raw or force_raw),
                idx_to_name=idx_to_name
            )

            if not feats:
                continue

            if is_fully_within:
                fully_processed_ids.add(crown_id)
                # Reduce if needed
                if force_raw and not return_raw:
                    final_stats = {}
                    for key, pixels in feats.items():
                        if key.endswith("_values"):
                            band_name = key.replace("_values", "")
                            p_arr = np.array(pixels)
                            final_stats[f"{band_name}_med"] = float(np.median(p_arr))
                            final_stats[f"{band_name}_mean"] = float(np.mean(p_arr))
                            final_stats[f"{band_name}_sd"] = float(np.std(p_arr))
                            final_stats[f"{band_name}_min"] = float(np.min(p_arr))
                            final_stats[f"{band_name}_max"] = float(np.max(p_arr))
                    feats = final_stats

                result = {
                    'crown_id': crown_id,
                    'species': species,
                    'raster_source': source_name
                }
                result.update(feats)
                yield result
            else:
                if crown_id not in crown_metadata:
                    crown_metadata[crown_id] = {'species': species, 'raster_source': source_name}
                for key, val in feats.items():
                    boundary_buffer[crown_id][key].extend(val)

    # Process Boundary Trees
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
                extracted_data[f"{prefix}_med"] = float(np.median(pixel_array))
                extracted_data[f"{prefix}_mean"] = float(np.mean(pixel_array))
                extracted_data[f"{prefix}_sd"] = float(np.std(pixel_array))
                extracted_data[f"{prefix}_min"] = float(np.min(pixel_array))
                extracted_data[f"{prefix}_max"] = float(np.max(pixel_array))
        
        if extracted_data:
            result.update(extracted_data)
            yield result

def extract_to_dataframe(
    raster_input: Union[str, Path, Raster],
    vector_input: Union[str, Path, Vector],
    tile_mode: Literal["auto", "tiled", "blocked", "in_memory"] = "auto",
    tile_size: int = 512,
    **kwargs
) -> pl.DataFrame:
    """
    Streams results into Polars DataFrame.
    """
    results_gen = extract_features(
        raster_input, 
        vector_input, 
        tile_mode=tile_mode,
        tile_size=tile_size,
        **kwargs
    )
    
    log.info("Streaming results into Polars DataFrame...")
    try:
        df = pl.from_dicts(results_gen, infer_schema_length=5000)
    except Exception as e:
        log.warning(f"Polars streaming failed ({e}), falling back to list collection")
        results = list(results_gen)
        df = pl.DataFrame(results)
    return df