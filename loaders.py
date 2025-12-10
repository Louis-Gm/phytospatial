# loaders.py
import logging
import geopandas as gpd

def load_crowns(path: str, id_col: str = None, species_col: str = None) -> gpd.GeoDataFrame:
    """
    Loads crown geometries, logs row numbers of invalid geometries, and filters them out.
    """
    try:
        # Note: RuntimeWarnings from the driver (GDAL/OSGeo) may still appear here
        gdf = gpd.read_file(path)
    except Exception as e:
        raise IOError(f"Could not load crowns from {path}: {e}")

    # --- Geometry Validation ---
    if not gdf.is_valid.all():
        # Identify invalid rows
        invalid_rows = gdf[~gdf.is_valid]
        
        # Get the row numbers (indices)
        invalid_indices = invalid_rows.index.tolist()
        
        logging.warning(
            f"Found {len(invalid_indices)} invalid geometries. "
            f"Skipping the following row indices: {invalid_indices}"
        )

        # Keep only valid geometries
        gdf = gdf[gdf.is_valid].copy()

    # --- Standardize ID ---
    # 1. Check if the requested ID column actually exists
    if id_col not in gdf.columns:
        logging.warning(f"ID column '{id_col}' not found. Using row index as ID.")
        
        temp_id = 'crown_id'
        gdf[temp_id] = gdf.index
        id_col = temp_id 

    # 2. Rename whichever column we are using to 'crown_id'
    gdf = gdf.rename(columns={id_col: 'crown_id'})

    # --- Standardize Species (if exists) ---
    if species_col and species_col in gdf.columns:
        gdf = gdf.rename(columns={species_col: 'species'})
    elif 'species' not in gdf.columns:
        gdf['species'] = None

    # --- Final Cleanup ---
    gdf.set_index('crown_id', drop=False, inplace=True)
    
    return gdf