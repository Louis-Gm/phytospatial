# spatial_tools.py

import geopandas as gpd

def label_crowns_spatially(crowns_gdf: gpd.GeoDataFrame, points_path: str, 
                           label_col: str, max_dist: float = 2.0) -> gpd.GeoDataFrame:
    """
    Performs a spatial join to label crowns based on nearest points.
    Returns the modified GeoDataFrame.
    """
    try:
        points_gdf = gpd.read_file(points_path)
    except Exception as e:
        raise IOError(f"Could not load points: {e}")

    # Ensure CRS match
    if crowns_gdf.crs != points_gdf.crs:
        print(f"Reprojecting points to {crowns_gdf.crs.name}...")
        points_gdf = points_gdf.to_crs(crowns_gdf.crs)

    # Spatial Join Nearest
    joined = gpd.sjoin_nearest(
        crowns_gdf,
        points_gdf[[label_col, 'geometry']],
        how='left',
        max_distance=max_dist,
        distance_col="dist"
    )

    # Deduplicate (keep closest/first if ties)
    joined = joined[~joined.index.duplicated(keep='first')]

    # Update species column using combine_first (fills NaNs in crowns with label from points)
    crowns_gdf['species'] = crowns_gdf['species'].combine_first(joined[label_col])
    
    count = crowns_gdf['species'].notna().sum()
    print(f"Labeling complete. {count} crowns now have labels.")
    
    return crowns_gdf