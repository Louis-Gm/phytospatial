# src/phytospatial/vector.py

import logging
import geopandas as gpd

log = logging.getLogger(__name__)

def label_crowns(crowns_gdf: gpd.GeoDataFrame, points_gdf: gpd.GeoDataFrame, 
                 label_col: str, max_dist: float = 2.0) -> gpd.GeoDataFrame:
    """
    Performs a spatial join to label crowns based on the nearest point in the provided GeoDataFrame.
    
    Args:
        crowns_gdf (gpd.GeoDataFrame): The target crowns to be labeled.
        points_gdf (gpd.GeoDataFrame): The source points containing the labels.
        label_col (str): The column name in points_gdf to transfer to crowns.
        max_dist (float): Maximum distance (in CRS units) to search for a label.
    
    Returns:
        gpd.GeoDataFrame: The input crowns with a new/updated 'species' column.
    """
    if label_col not in points_gdf.columns:
        raise ValueError(f"Column '{label_col}' not found in points GeoDataFrame.")

    if crowns_gdf.crs != points_gdf.crs:
        log.info(f"CRS mismatch. Reprojecting points from {points_gdf.crs.name} to {crowns_gdf.crs.name}...")
        points_gdf = points_gdf.to_crs(crowns_gdf.crs)

    temp_label_col = "pts_label_temp"

    points_subset = points_gdf[[label_col, 'geometry']].rename(columns={label_col: temp_label_col})

    try:
        joined = gpd.sjoin_nearest(
            crowns_gdf,
            points_subset,
            how='left',
            max_distance=max_dist,
            distance_col="dist"
        )
    except NotImplementedError:
        raise ImportError("Geopandas 0.10+ is required for sjoin_nearest.")

    joined = joined[~joined.index.duplicated(keep='first')]
 
    if 'species' not in crowns_gdf.columns:
        crowns_gdf['species'] = None
    
    crowns_gdf['species'] = crowns_gdf['species'].combine_first(joined[temp_label_col])
    
    count = crowns_gdf['species'].notna().sum()
    log.info(f"Labeling complete. {count} crowns now have labels.")
    
    return crowns_gdf