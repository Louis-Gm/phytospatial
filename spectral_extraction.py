# spectral_extraction.py
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import from_bounds
import numpy as np
from tqdm import tqdm
from pathlib import Path

def compute_basic_stats(pixel_values: np.array, prefix: str) -> dict:
    """
    Standard strategy: Mean, Median, SD.
    Args:
        pixel_values: 1D numpy array of valid pixels (no nodata).
        prefix: Naming prefix (e.g. 'Ortho_Red')
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
    def __init__(self, raster_path: str, band_names: list = None, read_indices: list = None, return_raw_pixels: bool = False):
        """
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
        self.src.close()

    def process_crowns(self, crowns_gdf, threshold: float = 0.001):
        """
        Iterates over every tree in the GeoDataFrame, reads its specific window,
        and computes stats. Guarantees 1 row per tree.
        """
        # CRS Check
        if crowns_gdf.crs != self.src.crs:
            print(f"Warning: Reprojecting crowns to match raster {self.name}...")
            crowns_gdf = crowns_gdf.to_crs(self.src.crs)

        # Optional: Check for duplicate IDs which could cause confusion
        if 'crown_id' in crowns_gdf.columns:
            if crowns_gdf['crown_id'].duplicated().any():
                print("Warning: Duplicate crown_ids found in input! Output will have multiple rows for these IDs.")

        # Loop over TREES (not blocks)
        # Using tqdm to show progress
        for idx, row in tqdm(crowns_gdf.iterrows(), total=len(crowns_gdf), desc=f"Extracting {self.name}"):
            
            geom = row.geometry
            
            # 1. Calculate the bounding box of the tree
            minx, miny, maxx, maxy = geom.bounds
            
            # 2. Convert to a Raster Window
            # specific to this tree's location
            window = from_bounds(minx, miny, maxx, maxy, self.src.transform)
            
            # Round the window to integers (pixels) to avoid partial-pixel read errors
            # We pad slightly to ensure we catch the edges
            window = window.round_offsets().round_lengths()
            
            # 3. Read the data for this window
            # boundless=True handles cases where the tree is partially off the edge of the map
            try:
                # Read only requested bands
                block_data = self.src.read(
                    indexes=self.read_indices, 
                    window=window, 
                    boundless=True,
                    fill_value=self.nodata if self.nodata is not None else 0
                )
                
                # Get the affine transform for this tiny window 
                # (needed to map the polygon onto the pixel grid)
                win_transform = self.src.window_transform(window)

                # 4. Extract Stats
                id_field = row.get('crown_id', idx)
                species_field = row.get('species', None)
                
                stats_dict = {'crown_id': id_field, 'species': species_field}
                
                extracted_data = self._extract_from_array(block_data, win_transform, geom, threshold=threshold)
                
                if extracted_data:
                    stats_dict.update(extracted_data)
                    yield stats_dict
                    
            except Exception as e:
                print(f"Error processing tree {idx}: {e}")
                continue

    def _extract_from_array(self, data_array, transform, geometry, threshold: float = 0.001):
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