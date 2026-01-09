# src/phytospatial/spectral_extraction.py

import logging
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
import numpy as np
from tqdm import tqdm
from pathlib import Path

log = logging.getLogger(__name__)

def compute_basic_stats(pixel_values: np.array, prefix: str) -> dict:
    """
    Computes basic statistics for a given array of pixel values.

    Args:
        pixel_values (np.array): 1D array of pixel values.
        prefix (str): Prefix for the output statistic keys.
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

class BlockExtractor:
    def __init__(self, raster_path: str, 
                 band_names: list = None, 
                 read_indices: list = None, 
                 return_raw_pixels: bool = False,
                 gdal_cache_max: int = 512):
        """
        Initializes the BlockExtractor with a raster file and optional parameters.

        Args:
            raster_path (str): Path to raster.
            band_names (list): Names for the OUTPUT stats.
            read_indices (list): 1-based indices of bands to read.
            return_raw_pixels (bool): If True, returns raw pixel lists.
        """
        self.src = rasterio.open(raster_path)
        self.name = Path(raster_path).stem
        self.nodata = self.src.nodata
        self.return_raw_pixels = return_raw_pixels
        self.env = None

        if gdal_cache_max is not None:
            self.env = rasterio.Env(GDAL_CACHEMAX=gdal_cache_max)
            self.env.__enter__()
            log.info(f"Set GDAL_CACHEMAX to {gdal_cache_max} MB. To change, set gdal_cache_max to desired value in constructor.")
        
        # Handle Band Selection
        if read_indices:
            self.read_indices = read_indices
        else:
            self.read_indices = list(range(1, self.src.count + 1))

        # Handle Band Names
        if band_names:
            if len(band_names) != len(self.read_indices):
                raise ValueError("Length of band_names must match read_indices.")
            self.band_names = band_names
        else:
            self.band_names = [f"b{i}" for i in self.read_indices]

    def close(self):
        """
        Closes the raster file.
        """
        if self.env:
            self.env.__exit__(None, None, None)
        self.src.close()

    def process_crowns(self, crowns_gdf, threshold: float = 0.001):
        """
        Iterates over every tree in the GeoDataFrame, reads its specific window,
        and computes stats. Guarantees 1 row per tree.

        Args:
            crowns_gdf (GeoDataFrame): GeoDataFrame with tree crown geometries.
            threshold (float): Minimum pixel value to consider for stats. Internal argument passed to _extract_from_array.
        
        Yields:
            dict: Statistics for each tree crown.
        """
        # CRS Check
        if crowns_gdf.crs != self.src.crs:
            log.warning(f"Reprojecting crowns to match raster {self.name} (from {crowns_gdf.crs.name} to {self.src.crs.name})...")
            crowns_gdf = crowns_gdf.to_crs(self.src.crs)

        # Check for duplicate IDs which could cause confusion
        if 'crown_id' in crowns_gdf.columns:
            if crowns_gdf['crown_id'].duplicated().any():
                log.warning("Duplicate crown_ids found in input! Output will have multiple rows for these IDs.")

        centroids = crowns_gdf.geometry.centroid
        sorted_indices = centroids.y.argsort()
        crowns_gdf = crowns_gdf.loc[sorted_indices]

        # Loop over trees. tqdm is used as a progress bar
        for idx, row in tqdm(crowns_gdf.iterrows(), total=len(crowns_gdf), desc=f"Extracting {self.name}"):
            
            geom = row.geometry
            
            # Calculate the bounding box of the tree
            minx, miny, maxx, maxy = geom.bounds
            
            # Convert to a Raster Window and round to full pixels
            window = from_bounds(minx, miny, maxx, maxy, self.src.transform)
            window = window.round_offsets().round_lengths()
            
            # Read the data for this window
            try:
                # Read only requested bands
                block_data = self.src.read(
                    indexes=self.read_indices, 
                    window=window, 
                    boundless=True, # handles cases where the tree is partially off the edge of the map
                    fill_value=self.nodata if self.nodata is not None else 0
                )
                
                # Get the affine transform for this tiny window 
                win_transform = self.src.window_transform(window)

                # Extract Stats
                id_field = row.get('crown_id', idx)
                species_field = row.get('species', None)
                
                stats_dict = {'crown_id': id_field, 'species': species_field}
                
                extracted_data = self._extract_from_array(block_data, win_transform, geom, threshold=threshold)
                
                if extracted_data:
                    stats_dict.update(extracted_data)
                    yield stats_dict
                    
            except Exception as e:
                log.error(f"Error processing tree {idx}: {e}")
                continue

    def _extract_from_array(self, data_array, transform, geometry, threshold: float = 0.001):
        """
        Given a data array and geometry, computes stats for pixels within the geometry.

        Args:
            data_array (np.array): 3D numpy array (bands, rows, cols).
            transform (Affine): Affine transform for the data array.
            geometry (shapely.geometry): Geometry of the tree crown.
            threshold (float): Minimum pixel value to consider for stats.
        
        Returns:
            dict: Computed statistics.
        """
        out_shape = (data_array.shape[1], data_array.shape[2])
        
        try:
            # Create a boolean mask where True = Inside Tree
            mask = geometry_mask(
                [geometry], 
                out_shape=out_shape, 
                transform=transform, 
                invert=True,  # Invert so True means "inside"
                all_touched=False # Strict (center must be in)
            )
            
            # Fallback for thin trees
            if not np.any(mask):
                 mask = geometry_mask(
                     [geometry], 
                     out_shape=out_shape, 
                     transform=transform, 
                     invert=True, 
                     all_touched=True # Relaxed (any touch)
                )
        except ValueError:
            return None

        stats_out = {}
        
        for b_idx, band_name in enumerate(self.band_names):
            # Select valid pixels
            band_pixels = data_array[b_idx][mask]
            
            # Filter NoData
            if self.nodata is not None:
                band_pixels = band_pixels[band_pixels != self.nodata]

            if band_pixels.size == 0:
                # skip if no valid pixels
                continue

            col_prefix = f"{self.name}_{band_name}"
            
            if self.return_raw_pixels:
                stats_out[f"{col_prefix}_values"] = band_pixels.tolist()
            else:
                valid_pixels = band_pixels

                if threshold is not None:
                    valid_pixels = band_pixels[band_pixels > threshold]

                if valid_pixels.size == 0:
                    continue

                band_stats = compute_basic_stats(valid_pixels, col_prefix)
                stats_out.update(band_stats)
            
        return stats_out
