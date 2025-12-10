from genericpath import exists
import rasterio

from phytospatial import preprocessing as prep
from pathlib import Path

# 1. HDR mosaic
RAW_HDR_DIR = "./data/input_hdrs"
PROCESSED_TIF_DIR = "./data/output_tifs"

if not exists("./data/output_tifs/mosaic_test.tif"):
    prep.convert_envi_to_geotiff(RAW_HDR_DIR, PROCESSED_TIF_DIR)

# 1. Input: TIFF orthomosaic (in degrees/LatLon)
tif_files = list(Path(PROCESSED_TIF_DIR).glob("*test.tif"))

# 2. Output: The corrected file (in meters)
output_tif = "./data/output_tifs/mosaic_test_32619.tif"

# 3. Run Reprojection

if not exists(output_tif):
    prep.reproject_raster(
        input_path=tif_files[0],
        output_path=output_tif,
        target_crs="EPSG:32619" # UTM Zone 19N
    )

original = "./data/output_tifs/mosaic_test.tif"
transformed = "./data/output_tifs/mosaic_test_32619.tif"

with rasterio.open(original) as src_orig, rasterio.open(transformed) as src_trans:
    print(f"File: {src_orig.name}")
    print(f"CRS: {src_orig.crs}")
    print(f"Width: {src_orig.width}, Height: {src_orig.height}")
    print(f"Transform: {src_orig.transform}")
    print(f"Band Count: {src_orig.count}")
    print(f"Band list: {[src_orig.descriptions[i] for i in range(src_orig.count)]}")
    
    print(f"File: {src_trans.name}")
    print(f"CRS: {src_trans.crs}")
    print(f"Width: {src_trans.width}, Height: {src_trans.height}")
    print(f"Transform: {src_trans.transform}")
    print(f"Band Count: {src_trans.count}")
    print(f"Band list: {[src_trans.descriptions[i] for i in range(src_trans.count)]}")
    
    # This is the critical number (Pixel Size)
    res_x = src_trans.transform[0]
    res_y = -src_trans.transform[4] # Usually negative
    print(f"Resolution: {res_x:.4f} x {res_y:.4f} (in units of the CRS)")