# main_pipeline.py

import pandas as pd
from pathlib import Path
import logging

# Import our new modules
from phytospatial import preprocessing
from phytospatial import loaders
from phytospatial import spatial_tools
from phytospatial import spectral_extraction

# Configure logging to see progress
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def run_pipeline():
    # --- Configuration ---
    # RAW_HDR_DIR = "./data/input_hdrs"
    PROCESSED_TIF_DIR = "./data/output_tifs"
    CROWNS_SHP = "./data/crowns.shp"
    # POINTS_SHP = "./data/vectors/field_points.shp"
    OUTPUT_CSV = "./data/results/final_stats_aggregate.csv"
    TARGET_CRS = "EPSG:32619" # UTM Zone 19N
    
    # 1. Preprocessing (Batch Convert)
    # print("--- Step 1: Preprocessing HDRs ---")
    # preprocessing.convert_envi_to_geotiff(RAW_HDR_DIR, PROCESSED_TIF_DIR)
    
    # --- Step 1.5: Ensure Metric Projection (Reproject if needed) ---
    # This ensures we have 20cm pixels (Meters) instead of Degrees
    # print(f"--- Step 1.5: Ensuring projection is {TARGET_CRS} ---")
    # raw_tifs = list(Path(PROCESSED_TIF_DIR).glob("*.tif"))
    # for tif in raw_tifs:
    #     if "32198" not in tif.name:
    #         out_name = tif.with_name(f"{tif.stem}_32198.tif")
    #         if not out_name.exists():
    #             preprocessing.reproject_raster(
    #                 str(tif), 
    #                 str(out_name), 
    #                 target_crs=TARGET_CRS,
    #                 target_resolution=0.20 # Force 20cm resolution
    #             )

    # 2. Load & Label Vectors
    print("\n--- Step 2: Loading & Labeling Vectors ---")
    crowns = loaders.load_crowns(CROWNS_SHP, species_col="species")
    # Optional: Label crowns spatially
    # crowns = spatial_tools.label_crowns_spatially(crowns, POINTS_SHP, label_col="species")
    
    # 3. Extraction Loop
    tif_files = list(Path(PROCESSED_TIF_DIR).glob("*_32619.tif"))
    
    if not tif_files:
        print("Warning: No reprojected (*_32619.tif) files found. Falling back to all .tif files.")
        tif_files = list(Path(PROCESSED_TIF_DIR).glob("*.tif"))

    all_results = []
    
    print("\n--- Step 3: Extracting Spectra ---")
    for tif_path in tif_files:
        print(f"Processing raster: {tif_path.name}")
        
        extractor = spectral_extraction.BlockExtractor(
            str(tif_path), 
            band_names=["Red", "Green", "Blue"],
            return_raw_pixels=True
        )
        
        # Using the generator to get results
        for stats in extractor.process_crowns(crowns):
            all_results.append(stats)
            
        extractor.close()

    """   # 4. Save in excel-friendly format 
    print("\n--- Step 4: Saving Results ---")
    if all_results:
        df_results = pd.DataFrame(all_results)
        # Merge back with original crown info if needed, or save directly
        df_results.to_csv(OUTPUT_CSV, index=False, float_format='%.12f')
        print(f"Saved {len(df_results)} rows to {OUTPUT_CSV}")
    else:
        print("No results extracted.") """

    print("\n--- Step 4: Saving Results ---")
    if all_results:
        df_results = pd.DataFrame(all_results)
        
        # Define output filename
        # Parquet files usually have .parquet extension
        OUTPUT_PARQUET = "./data/results/final_spectral_data.parquet"

        df_results.to_parquet(OUTPUT_PARQUET, index=False, engine='pyarrow', compression='snappy')
        
        print(f"Saved {len(df_results)} trees to {OUTPUT_PARQUET}")

if __name__ == "__main__":
    run_pipeline()

