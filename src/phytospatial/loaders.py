# src/phytospatial/loaders.py

import logging
from typing import Optional

from phytospatial.vector import Vector, resolve_vector

log = logging.getLogger(__name__)

__all__ = [
    "load_crowns"
]

@resolve_vector
def load_crowns(
    vector: Vector, 
    id_col: Optional[str] = None, 
    species_col: Optional[str] = None,
    validate: bool = True,
    fix_invalid: bool = True
) -> Vector:
    """
    Loads crown geometries and enforces specific naming conventions.
    Returns a clean Vector object with standardized columns.
    
    This function handles:
    1. Geometry validation (if enabled)
    2. ID column standardization → 'crown_id'
    3. Species column standardization → 'species'
    4. Index setup for efficient lookups
    
    Args:
        vector: The input Vector object. 
                (If a path string is passed, @resolve_vector converts it 
                 to a Vector object before this function runs).
        id_col: Name of the column containing tree IDs.
                If None, uses the DataFrame index.
                Will be renamed to 'crown_id'.
        species_col: Name of the column containing species information.
                     If None or not found, creates 'species' column with None.
                     Will be renamed to 'species'.
        validate: If True, runs geometry validation to remove/fix invalid features.
        fix_invalid: If validate=True, attempts to fix invalid geometries before dropping.
    
    Returns:
        Vector: Cleaned and standardized Vector object with:
                - 'crown_id' column (integer index)
                - 'species' column (string or None)
                - Valid geometries only (if validate=True)
                - Index set to crown_id for fast lookups
    
    Raises:
        ValueError: If critical issues prevent loading
    """
    
    if validate:
        log.info("Validating crown geometries...")
        vector = vector.validate(fix_invalid=fix_invalid, drop_invalid=True)
        if len(vector) == 0:
            raise ValueError("No valid geometries remaining after validation!")
    
    crowns = vector.copy()
    gdf = crowns.data

    if id_col:
        if id_col not in gdf.columns:
            log.warning(
                f"ID field '{id_col}' not found in shapefile. "
                f"Available columns: {gdf.columns.tolist()}\n"
                f"Using index as ID instead."
            )
            gdf['crown_id'] = gdf.index
        else:
            if id_col != 'crown_id':
                gdf = gdf.rename(columns={id_col: 'crown_id'})
            
            if gdf['crown_id'].duplicated().any():
                dup_count = gdf['crown_id'].duplicated().sum()
                log.warning(
                    f"Found {dup_count} duplicate IDs in '{id_col}'. "
                    f"Creating new unique IDs from index."
                )
                gdf['crown_id'] = gdf.index
    else:
        log.info("No ID column specified. Creating 'crown_id' from index.")
        gdf['crown_id'] = gdf.index

    try:
        gdf['crown_id'] = gdf['crown_id'].astype(int)
    except (ValueError, TypeError) as e:
        log.warning(f"Could not convert crown_id to integer: {e}. Using original values.")

    if species_col:
        if species_col in gdf.columns:
            if species_col != 'species':
                gdf = gdf.rename(columns={species_col: 'species'})
            
            missing_species = gdf['species'].isna().sum()
            if missing_species > 0:
                log.warning(f"{missing_species} features have missing species values")
        else:
            log.warning(
                f"Species field '{species_col}' not found. "
                f"Available columns: {gdf.columns.tolist()}\n"
                f"Setting all species to None."
            )
            gdf['species'] = None
    else:
        if 'species' not in gdf.columns:
            log.info("No species column specified. Creating 'species' with None values.")
            gdf['species'] = None

    gdf.index = gdf['crown_id']
    gdf.index.name = None
    
    crowns._data = gdf
    
    log.info(
        f"Loaded {len(crowns)} crowns with standardized columns: "
        f"crown_id, species, geometry"
    )
    
    return crowns