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
import json

import numpy as np
import polars as pl
import psycopg
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds, Window, transform as window_transform
from rasterio.errors import WindowError
from shapely.geometry import box

from phytospatial.raster.layer import Raster
from phytospatial.raster.utils import resolve_envi_path, extract_band_indices, extract_band_names
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
        med = np.median(masked_pixels, axis=1)
        mean = np.mean(masked_pixels, axis=1)
        std = np.std(masked_pixels, axis=1)
        min_val = np.min(masked_pixels, axis=1)
        max_val = np.max(masked_pixels, axis=1)
        
        for b_idx in range(raster.count):
            name = idx_to_name.get(b_idx + 1, f"b{b_idx + 1}")
            stats_out.update({
                f"{name}_med": float(med[b_idx]),
                f"{name}_mean": float(mean[b_idx]),
                f"{name}_sd": float(std[b_idx]),
                f"{name}_min": float(min_val[b_idx]),
                f"{name}_max": float(max_val[b_idx])
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
    Generates spectral features for vector polygons using a single-pass processing architecture.

    Args:
        raster_input (Union[str, Path, Raster]): The source raster data, provided as an in-memory Raster object or a filepath.
        vector_input (Union[str, Path, Vector]): The source vector data defining the extraction boundaries, provided as a Vector object or filepath.
        bands (Optional[List[int]]): Specific 1-based band indices to extract. Defaults to all bands.
        threshold (float): Minimum pixel value to consider valid during extraction.
        return_raw (bool): Yields arrays of raw pixel values rather than computed statistics when True.
        tile_mode (Literal["auto", "tiled", "blocked", "in_memory"]): Strategy for processing the raster.
        tile_size (int): Size of the processing window if tiled mode is selected.

    Yields:
        Generator[Dict[str, Any], None, None]: Successive dictionaries containing spatial identifiers and the extracted band statistics or raw values for each vector feature.
    """
    if isinstance(vector_input, (str, Path)):
        vector_obj = load_vector(vector_input)
        vector_obj = validate(vector_obj, fix_invalid=True, drop_invalid=False)
    elif isinstance(vector_input, Vector):
        vector_obj = validate(vector_input, fix_invalid=True, drop_invalid=False)
    else:
        raise TypeError(f"vector_input must be a path or Vector object")
    
    boundary_buffer = defaultdict(lambda: defaultdict(list))
    crown_metadata = {} 
    fully_processed_ids = set()

    def _execute_intersection(raster_iterator, source_name, vector_data):
        """
        Internal generator to intersect vector geometries against an active stream of raster windows.
        """
        sindex = vector_data.sindex if hasattr(vector_data, 'sindex') else None
        
        for window, tile_raster in raster_iterator:
            tile_box = box(*tile_raster.bounds)
            
            if sindex is not None:
                possible_matches_index = list(sindex.intersection(tile_box.bounds))
                local_trees = vector_data.iloc[possible_matches_index]
            else:
                local_trees = vector_data
            
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
        yield from _execute_intersection([(None, raster_input)], "memory_raster", vector_obj.data)

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

            yield from _execute_intersection(raster_iterator, source_name, vector_obj.data)

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
    Consumes the feature generator to immediately build an optimized Polars DataFrame.

    Args:
        raster_input (Union[str, Path, Raster]): Target raster dataset.
        vector_input (Union[str, Path, Vector]): Target vector boundaries.
        tile_mode (Literal["auto", "tiled", "blocked", "in_memory"]): Evaluation strategy. Defaults to auto.
        tile_size (int): Tile block dimension.
        **kwargs: Extraneous arguments passed directly to extract_features.

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

def extract_to_database(
    raster_input: Union[str, Path, Raster],
    vector_input: Union[str, Path, Vector],
    dsn: str,
    table_name: str,
    tile_mode: Literal["auto", "tiled", "blocked", "in_memory"] = "auto",
    tile_size: int = 512,
    **kwargs
) -> int:
    """
    Consumes the feature generator to stream results directly into a PostgreSQL database.
    
    This function uses the high-speed COPY protocol to insert records without 
    building an in-memory DataFrame. It maps fixed keys to relational columns 
    and packs dynamic spectral statistics into a JSONB column.

    Args:
        raster_input (Union[str, Path, Raster]): Target raster dataset.
        vector_input (Union[str, Path, Vector]): Target vector boundaries.
        dsn (str): PostgreSQL connection string (e.g., "dbname=trees user=postgres...").
        table_name (str): The target table in the database.
        tile_mode (Literal["auto", "tiled", "blocked", "in_memory"]): Evaluation strategy.
        tile_size (int): Tile block dimension.
        **kwargs: Extraneous arguments passed directly to extract_features.

    Returns:
        int: The total number of records successfully streamed and inserted.
    """

    results_gen = extract_features(
        raster_input=raster_input, 
        vector_input=vector_input, 
        tile_mode=tile_mode,
        tile_size=tile_size,
        **kwargs
    )

    total_inserted = 0

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            
            copy_query = f"COPY {table_name} (crown_id, species, raster_source, spectral_data) FROM STDIN"
            
            with cur.copy(copy_query) as copy:
                for feature in results_gen:
                    
                    crown_id = feature.pop('crown_id', None)
                    species = feature.pop('species', None)
                    raster_source = feature.pop('raster_source', None)
                    
                    spectral_data = json.dumps(feature)
                    
                    copy.write_row((crown_id, species, raster_source, spectral_data))
                    total_inserted += 1

            conn.commit()
            
    log.info(f"Successfully streamed {total_inserted} records into {table_name}.")
    return total_inserted