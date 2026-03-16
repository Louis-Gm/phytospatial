# src/phytospatial/extract.py

"""
This module performs object-based extraction from raster data.

It manages interactions between raster and vector data, orchestrating the extraction
of pixel values for specified geometries. Features include adaptive processing
strategies, handling of boundary-crossing geometries, and optimized Polars output.
"""

import logging
from typing import Union, List, Optional, Generator, Dict, Any, Literal
from pathlib import Path
from collections import defaultdict

import numpy as np
import polars as pl
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window, transform as window_transform
from rasterio.errors import WindowError
from shapely.geometry import box

from phytospatial.raster.layer import Raster
from phytospatial.raster.utils import resolve_envi_path, extract_band_indices, extract_band_names, compute_statistics
from phytospatial.raster.resources import ProcessingMode, determine_strategy
from phytospatial.raster.partition import iter_tiles, iter_blocks

from phytospatial.vector.layer import Vector
from phytospatial.vector.io import load_vector
from phytospatial.vector.geom import validate, to_crs

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
    Extracts pixel values for a single geometry from an in-memory raster tile, applying masking and thresholding as needed.

    Args:
        raster (Raster): The in-memory raster tile to extract from.
        geometry (Any): The geometry defining the area of interest for extraction.
        threshold (Optional[float]): Minimum pixel value to consider valid during extraction.
        return_raw (bool): If True, returns raw pixel values instead of statistics.
        idx_to_name (Optional[Dict[int, str]]): Mapping from band indices to human-readable names for output keys.

    Returns:
        Dict[str, Any]: A dictionary containing either raw pixel values or computed statistics for the geometry.
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
        out_shape = (data_slice.shape[1], data_slice.shape[2])
        
        needs_all_touched = (safe_window.width <= 2) or (safe_window.height <= 2)
        
        mask = geometry_mask(
            [geometry],
            out_shape=out_shape,
            transform=slice_transform,
            invert=True,
            all_touched=needs_all_touched
        )
        
        if not needs_all_touched and not np.any(mask):
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

    raw_pixels = data_slice[:, mask]
    valid_cols = np.ones(raw_pixels.shape[1], dtype=bool)

    if raster.nodata is not None:
        if np.isnan(raster.nodata):
            valid_cols &= ~np.isnan(raw_pixels).any(axis=0)
        else:
            valid_cols &= (raw_pixels != raster.nodata).all(axis=0)

    if threshold is not None:
        valid_cols &= (raw_pixels > threshold).all(axis=0)

    masked_pixels = raw_pixels[:, valid_cols]
    if masked_pixels.size == 0:
        return {}

    if idx_to_name is None:
        idx_to_name = {v: k for k, v in raster.band_names.items()}

    stats_out = {}
    if return_raw:
        raw_values = masked_pixels.tolist()
        stats_out = {
            f"{idx_to_name.get(b_idx + 1, f'b{b_idx + 1}')}_values": raw_values[b_idx]
            for b_idx in range(raster.count)
        }
    else:
        for b_idx in range(raster.count):
            name = idx_to_name.get(b_idx + 1, f"b{b_idx + 1}")
            p_arr = np.array(masked_pixels[b_idx], dtype=np.float64)
            if p_arr.size > 0:
                med, mean, sd, min_v, max_v = compute_statistics(p_arr)
                stats_out.update({
                    f"{name}_med": float(med),
                    f"{name}_mean": float(mean),
                    f"{name}_sd": float(sd),
                    f"{name}_min": float(min_v),
                    f"{name}_max": float(max_v)
                })

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
    Generates Raster-derived features for all Vector objects within the raster extent using a single-pass processing architecture.

    Args:
        raster_input (Union[str, Path, Raster]): The source raster data, provided as an in-memory Raster object or a filepath.
        vector_input (Union[str, Path, Vector]): The source vector data defining the extraction boundaries, provided as a Vector object or filepath.
        bands (Optional[List[int]]): Specific 1-based band indices to extract. Defaults to all bands.
        threshold (float): Minimum pixel value to consider valid during extraction.
        return_raw (bool): Yields arrays of raw pixel values rather than computed statistics when True.
        tile_mode (Literal["auto", "tiled", "blocked", "in_memory"]): Strategy for processing the raster.
        tile_size (int): Size of the processing window if tiled mode is selected.

    Yields:
        Generator[Dict[str, Any], None, None]: Successive dictionaries containing spatial identifiers and the extracted 
                                               band statistics or raw values for each vector feature.
    """
    if isinstance(vector_input, (str, Path)):
        vector_obj = load_vector(vector_input)
        vector_obj = validate(vector_obj, fix_invalid=True, drop_invalid=False)
    elif isinstance(vector_input, Vector):
        vector_obj = validate(vector_input, fix_invalid=True, drop_invalid=False)
    else:
        raise TypeError("vector_input must be a path or Vector object")
    
    boundary_buffer = defaultdict(lambda: defaultdict(list))
    crown_metadata = {} 
    fully_processed_ids = set()

    def _execute_intersection(
            raster_iterator, 
            source_name, 
            vector_layer: Vector
            ) -> Generator[Dict[str, Any], None, None]:
        """
        Coordinates the continuous intersection of vector geometries against streamed raster tiles utilizing 
        optimized native Rust RTree indexing and vectorized Shapely C-arrays for primary spatial filtering.

        Args:
            raster_iterator (Iterator[Tuple[Window, Raster]]): An active generator yielding spatial partition windows 
            and their corresponding loaded Raster matrices.
            source_name (str): The nomenclature identifier of the active raster source file.
            vector_layer (Vector): The fully projected vector dataset manager holding the geometries and spatial cache.

        Yields:
        Generator[Dict[str, Any], None, None]: A comprehensive mapping containing spatial relational identifiers and aggregated 
            spectral metrics for verified topologies.
        """
        _ = vector_layer.spatial_index

        for window, tile_raster in raster_iterator:
            t_minx, t_miny, t_maxx, t_maxy = tile_raster.bounds
            
            candidate_indices = vector_layer.query_bounds(t_minx, t_miny, t_maxx, t_maxy)
            
            if len(candidate_indices) == 0:
                continue
                
            local_trees = vector_layer.data.iloc[candidate_indices].copy()
            tile_box = box(t_minx, t_miny, t_maxx, t_maxy)
            
            intersects_mask = local_trees.geometry.intersects(tile_box)
            local_trees = local_trees[intersects_mask]

            if local_trees.empty:
                continue

            if window is not None:
                local_trees['is_fully_within'] = local_trees.geometry.within(tile_box)
            else:
                local_trees['is_fully_within'] = True

            idx_to_name = {v: k for k, v in tile_raster.band_names.items()}
            for idx, row in local_trees.iterrows():
                crown_id = row.get('crown_id', idx)
                if crown_id in fully_processed_ids:
                    continue

                is_fully_within = row['is_fully_within']
                force_raw = not is_fully_within
                species = row.get('species', None)

                feats = _process_geometry_in_memory(
                    raster=tile_raster,
                    geometry=row.geometry,
                    threshold=threshold,
                    return_raw=(return_raw or force_raw),
                    idx_to_name=idx_to_name
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
                                p_arr = np.array(pixels, dtype=np.float64)
                                if p_arr.size > 0:
                                    med, mean, sd, min_v, max_v = compute_statistics(p_arr)
                                    final_stats[f"{band_name}_med"] = float(med)
                                    final_stats[f"{band_name}_mean"] = float(mean)
                                    final_stats[f"{band_name}_sd"] = float(sd)
                                    final_stats[f"{band_name}_min"] = float(min_v)
                                    final_stats[f"{band_name}_max"] = float(max_v)
                        feats = final_stats

                    result = {'crown_id': crown_id, 'species': species, 'raster_source': source_name}
                    result.update(feats)
                    yield result

                else:
                    if crown_id not in crown_metadata:
                        crown_metadata[crown_id] = {'species': species, 'raster_source': source_name}
                    for key, val in feats.items():
                        boundary_buffer[crown_id][key].extend(val)

    if isinstance(raster_input, Raster):
        if vector_obj.crs != raster_input.crs:
            vector_obj = to_crs(vector_obj, raster_input.crs, inplace=False)
        yield from _execute_intersection([(None, raster_input)], "memory_raster", vector_obj)

    else:
        path = resolve_envi_path(Path(raster_input))
        source_name = path.stem
        
        with rasterio.open(path) as src:
            if vector_obj.crs != src.crs:
                vector_obj = to_crs(vector_obj, src.crs, inplace=False)
            
            report = determine_strategy(src, user_mode=tile_mode)
            
            if report.mode == ProcessingMode.IN_MEMORY:
                indices = extract_band_indices(src, bands)
                band_names = extract_band_names(src, indices)
                data = src.read(indexes=indices)
                raster_iterator = [(None, Raster(data, src.transform, src.crs, src.nodata, band_names))]
            elif report.mode == ProcessingMode.BLOCKED:
                raster_iterator = iter_blocks(src, bands=bands)
            else: 
                raster_iterator = iter_tiles(src, tile_size=tile_size, bands=bands)

            yield from _execute_intersection(raster_iterator, source_name, vector_obj)

    for crown_id, band_data in boundary_buffer.items():
        if crown_id in fully_processed_ids:
            continue

        result = {'crown_id': crown_id}
        result.update(crown_metadata.get(crown_id, {}))
        
        extracted_data = {}
        for key, all_pixels in band_data.items():
            pixel_array = np.array(all_pixels, dtype=np.float64)
            if pixel_array.size == 0:
                continue
            if return_raw:
                extracted_data[key] = pixel_array.tolist()
            else:
                prefix = key.replace("_values", "")
                med, mean, sd, min_v, max_v = compute_statistics(pixel_array)
                extracted_data[f"{prefix}_med"] = float(med)
                extracted_data[f"{prefix}_mean"] = float(mean)
                extracted_data[f"{prefix}_sd"] = float(sd)
                extracted_data[f"{prefix}_min"] = float(min_v)
                extracted_data[f"{prefix}_max"] = float(max_v)
        
        if extracted_data:
            result.update(extracted_data)
            yield result

def extract_to_dataframe(
    raster_input: Union[str, Path, Raster],
    vector_input: Union[str, Path, Vector],
    tile_mode: Literal["auto", "tiled", "blocked", "in_memory"] = "auto",
    tile_size: int = 512,
    **kwargs: Any
    ) -> pl.DataFrame:
    """
    Consumes the feature generator to immediately build an optimized Polars DataFrame.

    Args:
        raster_input (Union[str, Path, Raster]): Target raster dataset.
        vector_input (Union[str, Path, Vector]): Target vector boundaries.
        tile_mode (Literal["auto", "tiled", "blocked", "in_memory"]): Evaluation strategy. Defaults to auto.
        tile_size (int): Tile block dimension.
        **kwargs (Any): Extraneous arguments passed directly to extract_features.

    Returns:
        pl.DataFrame: A Polars DataFrame populated with the extracted multi-band properties for each vector unit.
    """
    results_gen = extract_features(
        raster_input, 
        vector_input, 
        tile_mode=tile_mode,
        tile_size=tile_size,
        **kwargs
    )
    
    try:
        df = pl.from_dicts(results_gen, infer_schema_length=5000)
    except Exception:
        results = list(results_gen)
        df = pl.DataFrame(results)
    return df