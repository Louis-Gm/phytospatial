# preprocessing.py

import logging
from pathlib import Path
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.enums import Resampling

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

def convert_envi_to_geotiff(input_dir: str, output_dir: str, compression: str = None):
    """
    Batch converts ENVI files (via their .hdr) to Tiled GeoTIFFs.
    
    Args:
        input_dir (str): Directory containing .hdr files.
        output_dir (str): Directory to save .tif files.
        compression (str, optional): Compression type for GeoTIFFs. Defaults to None.
    """
    in_path = Path(input_dir)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Writing GeoTIFFs to absolute path: {out_path.resolve()}")

    # Find .hdr files
    hdr_files = list(in_path.glob("*.hdr"))
    logger.info(f"Found {len(hdr_files)} HDR files to process.")

    for hdr_file in hdr_files:
        try:
            # Validation Logic
           
            binary_file = hdr_file.with_suffix('')
            target_file = hdr_file 

             # Strip suffix to look for the binary ('image.hdr' -> 'image')
            if binary_file.exists():
                logger.info(f"Correcting input: Pointing to binary file '{binary_file.name}' instead of header.")
                target_file = binary_file
            else:
                logger.warning(f"Targeted {hdr_file.name} but could not find the companion binary file. GDAL might fail.")

            # Conversion
            with rasterio.open(target_file) as src:
                
                # Define output profile
                profile = src.profile.copy()
                profile.update({
                    'driver': 'GTiff',
                    'tiled': True,
                    'blockxsize': 256,
                    'blockysize': 256,
                    'bigtiff': 'IF_NEEDED'
                })

                # Handle compression
                if compression:
                    profile['compress'] = compression
                else:
                    profile.pop('compress', None) # Remove if exists
#
                output_file = out_path / f"{hdr_file.stem}.tif"
                
                logger.info(f"Converting {target_file.name} -> {output_file.name} (Compression: {compression})...")
                
                with rasterio.open(output_file, 'w', **profile) as dst:
                    for ji, window in src.block_windows(1):
                        dst.write(src.read(window=window), window=window)
                        
        except Exception as e:
            logger.error(f"Failed to convert {hdr_file.name}: {e}")

def reproject_raster(input_path: str, output_path: str, target_crs: str = "EPSG:32619", target_resolution: float = None):
    """
    Reprojects a raster to a new CRS and saves it to disk.
    
    Args:
        input_path (str): Path to source file.
        output_path (str): Path to destination file.
        target_crs (str): Destination EPSG code (default UTM Zone 19N).
        target_resolution (float, optional): Force a specific pixel size in the units of target_crs. 
                                             If None, keeps original pixel count.
    """
    dst_crs = rasterio.crs.CRS.from_string(target_crs)

    with rasterio.open(input_path) as src:
        # Calculate transform for the new CRS
        # If target_resolution is provided, this function calculates the new width/height for us.
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=target_resolution
        )
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        logger.info(f"Reprojecting {Path(input_path).name} to {target_crs}...")
        if target_resolution:
            logger.info(f" -> Forcing resolution: {target_resolution} units (meters)")
        
        with rasterio.open(output_path, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    # Bilinear is standard for continuous data (imagery/reflectance)
                    resampling=Resampling.bilinear 
                )

def stack_rasters(input_paths: list, output_path: str):
    """
    Stacks multiple single-band rasters into one multi-band GeoTIFF using 
    memory-safe windowed processing.
    """
    if not input_paths:
        return

    # Read metadata from the first file to configure the output
    with rasterio.open(input_paths[0]) as src0:
        meta = src0.meta.copy()

    # Update metadata: Set total band count and ensure Tiled format
    meta.update(
        count=len(input_paths),
        tiled=True,
        blockxsize=256,
        blockysize=256
    )

    logger.info(f"Stacking {len(input_paths)} files into {output_path}...")

    # Create the output file
    with rasterio.open(output_path, 'w', **meta) as dst:
        
        # Outer Loop: Process one file (one band) at a time
        for idx, layer_path in enumerate(input_paths, start=1):
            
            with rasterio.open(layer_path) as src:
                logger.info(f"Processing band {idx}: {Path(layer_path).name}")

                # Inner Loop: Process one window at a time
                for ji, window in src.block_windows(1):
                    block_data = src.read(1, window=window)
                    dst.write(block_data, indexes=idx, window=window)

if __name__ == "__main__":
    # Example usage
    convert_envi_to_geotiff("./data/input_hdrs", "./data/output_tifs") # use directories not files