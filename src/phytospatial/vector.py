# src/phytospatial/spatial_tools.py

import logging
import geopandas as gpd

log = logging.getLogger(__name__)

def label_crowns(crowns_gdf: gpd.GeoDataFrame, points_path: str, 
                           label_col: str, max_dist: float = 2.0) -> gpd.GeoDataFrame:
    """
    Performs a spatial join to label crowns based on nearest points.
    Returns the modified GeoDataFrame.
    """
    try:
        points_gdf = gpd.read_file(points_path)
        log.info(f"Loaded {len(points_gdf)} labeling points from {points_path}")
    except Exception as e:
        raise IOError(f"Could not load points: {e}")

    # Ensure CRS match
    if crowns_gdf.crs != points_gdf.crs:
        log.info(f"CRS mismatch detected. Reprojecting points from {points_gdf.crs.name} to {crowns_gdf.crs.name}...")
        points_gdf = points_gdf.to_crs(crowns_gdf.crs)

    temp_label_col = "pts_label_temp"
    
    # Prepare the subset with the renamed column
    points_subset = points_gdf[[label_col, 'geometry']].rename(columns={label_col: temp_label_col})

    # Spatial Join Nearest using the SAFE subset
    joined = gpd.sjoin_nearest(
        crowns_gdf,
        points_subset,
        how='left',
        max_distance=max_dist,
        distance_col="dist"
    )
    
    # Deduplicate (keep closest/first if ties)
    joined = joined[~joined.index.duplicated(keep='first')]

    # Update species column using the temporary column name
    crowns_gdf['species'] = crowns_gdf['species'].combine_first(joined[temp_label_col])
    
    count = crowns_gdf['species'].notna().sum()
    
    log.info(f"Labeling complete. {count} crowns now have labels.")
    
    return crowns_gdf