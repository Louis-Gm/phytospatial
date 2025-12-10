# loaders.py
import logging
import geopandas as gpd

def load_crowns(path: str, id_col: str = None, species_col: str = None) -> gpd.GeoDataFrame:
    """
    Loads crown geometries, logs row numbers of invalid geometries, and filters them out.

    Args:
        path (str): Path to the crowns shapefile.
        id_col (str): Optional field name to use as crown ID. If None, uses the row index.
        species_col (str): Optional field name for species labels. If None, no species labels are assigned.

    Returns:
        GeoDataFrame: Loaded and cleaned crowns with 'crown_id' and optional 'species' fields.
    """
    try:
        gdf = gpd.read_file(path)
    except Exception as e:
        raise IOError(f"Could not load crowns from {path}: {e}")

    # Geometry Validation
    if not gdf.is_valid.all():
        # Identify invalid row indices
        invalid_rows = gdf[~gdf.is_valid]

        invalid_indices = invalid_rows.index.tolist()
        
        logging.warning(
            f"Found {len(invalid_indices)} invalid geometries. "
            f"Skipping the following row indices: {invalid_indices}"
        )

        # Keep only valid geometries
        gdf = gdf[gdf.is_valid].copy()

    # Check if the requested ID field actually exists
    if id_col not in gdf.columns:
        logging.warning(f"ID field '{id_col}' not found. Using row index as ID.")
        
        temp_id = 'crown_id'
        gdf[temp_id] = gdf.index
        id_col = temp_id 

    # Rename whichever field we are using to 'crown_id'
    gdf = gdf.rename(columns={id_col: 'crown_id'})

    # Standardize 'species' field (if exists)
    if species_col and species_col in gdf.columns:
        gdf = gdf.rename(columns={species_col: 'species'})
    elif 'species' not in gdf.columns:
        gdf['species'] = None

    # Final Cleanup
    gdf.set_index('crown_id', drop=False, inplace=True)
    
    return gdf
