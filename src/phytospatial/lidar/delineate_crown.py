# src/phytospatial/lidar/delineate_crown.py

"""
This module implements functions for delineating tree crowns from canopy height models and treetop locations.
"""

from typing import Tuple, Union, Generator, Dict, Any
from pathlib import Path
from dataclasses import dataclass
import logging

import numpy as np
import scipy.ndimage as ndimage
from numba import jit
from rasterio.features import shapes
from skimage.segmentation import watershed
from shapely.geometry import shape

from phytospatial.raster.layer import Raster
from phytospatial.raster.partition import iter_core_halo
from phytospatial.vector.layer import Vector
from phytospatial.vector.geom import to_crs

log = logging.getLogger(__name__)

__all__ = [
    "DelineationParams",
    "delineate_crowns"
]

@dataclass
class DelineationParams:
    """
    Parameters for tree crown delineation methods.

    Args:
        delineation_method: Method to use for delineation ("watershed" or "region_growing").
        pixel_size: Resolution of the input canopy height model in meters.
        min_height: Minimum height threshold for including pixels in crowns.
        watershed_sigma: Sigma value for Gaussian smoothing in watershed method.
        max_crown_radius: Maximum expected crown radius in meters for region growing method.
        apex_inclusion: Minimum relative height of pixels to be included in the crown compared to the apex height.
        crown_threshold: Minimum relative height of pixels to be included in the crown compared to the 
                        current average height of the crown during region growing.

    """
    delineation_method: str = "watershed"
    pixel_size: float = 0.25
    min_height: float = 3.0
    watershed_sigma: float = 0.5       
    max_crown_radius: float = 10.0
    apex_inclusion: float = 0.45   
    crown_threshold: float = 0.55  

def _run_watershed(
    chm: np.ndarray, 
    apex_ref: np.ndarray, 
    params: DelineationParams
    ) -> np.ndarray:
    """
    Delineate tree crowns using a watershed segmentation approach.

    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        apex_ref (np.ndarray): Array of shape (N, 2) containing the row and column indices of treetop locations.
        params (DelineationParams): Parameters for the watershed delineation method.
    
    Returns:
        np.ndarray: 2D array of integer labels representing the segmented tree crowns.
    """
    # Fill in gaps in the CHM through morphological closing to create a more continuous surface for watershed segmentation
    chm_closed = ndimage.grey_closing(chm, size=(3, 3))
    
    # Optionally apply Gaussian smoothing to the closed CHM to reduce noise and create smoother watershed basins
    chm_delin = ndimage.gaussian_filter(chm_closed, sigma=params.watershed_sigma) if params.watershed_sigma > 0 else chm_closed
    
    # We then perform the watershed segmentation using the negative of the prepared CHM as the input surface,
    # and the treetop locations as the markers for the watershed basins. 
    # We also apply a mask to restrict the watershed to areas above the minimum height threshold.
    markers = np.zeros(chm.shape, dtype=np.int32)
    for i, (r, c) in enumerate(apex_ref): 
        markers[r, c] = i + 1
    
    # The watershed function will segment the CHM into distinct regions (crowns) based on the local minima defined by 
    # the treetop markers and the topography of the CHM surface.
    return watershed(-chm_delin, markers, mask=(chm_delin >= params.min_height), watershed_line=True)

def _calculate_expansion_rings(
    max_spread: int
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pre-calculates the relative positions of neighboring pixels in concentric rings around a central pixel
    up to a specified maximum spread distance. This is used for efficient region growing in the region growing method.

    Args:
        max_spread: Maximum distance in pixels to consider for expanding the crown from the apex.

    Returns:
        Tuple of arrays containing the relative row and column offsets for neighboring pixels, 
        as well as the indices that define the boundaries of each ring of neighbors.
    """
    # We create a grid of relative pixel offsets within a square bounding box defined by the maximum spread distance.
    # We then calculate the radial distance of each offset from the center pixel and filter out those that are beyond the maximum spread.
    grid_range = np.arange(-max_spread, max_spread + 1)
    grid_y, grid_x = np.meshgrid(grid_range, grid_range)
    radial_dist = (grid_y**2 + grid_x**2).flatten()
    
    # We flatten the grid of offsets and filter them to include only those within the maximum spread distance.
    y_flat, x_flat = grid_y.flatten(), grid_x.flatten()
    valid_mask = (radial_dist > 0) & (radial_dist <= max_spread**2)
    
    # We sort the valid offsets by their radial distance from the center pixel, which allows us to expand the crown in concentric rings.
    y_valid, x_valid, dist_valid = y_flat[valid_mask], x_flat[valid_mask], radial_dist[valid_mask]
    sort_indices = np.argsort(dist_valid)

    # Finally, we calculate the boundaries of each ring of neighbors based on the unique radial distances, 
    # which will be used to control the expansion process in the region growing method.
    y_sorted, x_sorted, dist_sorted = y_valid[sort_indices], x_valid[sort_indices], dist_valid[sort_indices]
    
    # We use np.unique to find the indices where the radial distance changes, which gives us the boundaries of each ring of neighbors.
    _, ring_boundaries = np.unique(dist_sorted, return_index=True)
    return y_sorted, x_sorted, np.append(ring_boundaries, [len(dist_sorted)]).astype(np.int32)

@jit(nopython=True, nogil=True, cache=True)
def _expand_canopy(
    surface_grid: np.ndarray, 
    ownership_grid: np.ndarray, 
    apex_p: np.ndarray, 
    step_y: np.ndarray, 
    step_x: np.ndarray, 
    expansion_rings: np.ndarray, 
    apex_inclusion: float, 
    core_inclusion: float, 
    min_height: float
    ):
    """
    This function performs the actual region growing for the region growing delineation method.
    
    It iteratively expands from the apex pixels outwards, checking the canopy adhesion criteria at each step 
    to determine if neighboring pixels should be included in the crown.
    
    Args:
        surface_grid: 2D array representing the canopy height model with padding.
        ownership_grid: 2D array of the same shape as surface_grid that keeps track of which tree (if any) owns each pixel.
        apex_p: Array of shape (N, 2) containing the row and column indices of the apex pixels (treetop locations) with padding.
        step_y: Array of relative row offsets for neighboring pixels in concentric rings around the apex.
        step_x: Array of relative column offsets for neighboring pixels in concentric rings around the apex.
        expansion_rings: Array of indices that define the boundaries of each ring of neighbors in step_y and step_x.
        apex_inclusion: Minimum relative height of pixels to be included in the crown compared to the apex height.
        core_inclusion: Minimum relative height of pixels to be included in the crown compared to the average height of the crown during region growing.
        min_height: Minimum height threshold for including pixels in crowns.

    Returns:
        None: The function modifies the ownership_grid in place to assign pixels to tree crowns.        
    """
    # We initialize the ownership grid with zeros (unassigned pixels) 
    # and assign unique tree IDs to the apex pixels based on their positions in the apex_p array.
    num_trees = apex_p.shape[0]
    
    # We store metrics for each tree to check our inclusion criteria during expansion. 
    # This includes the cumulative height of the pixels in the crown and the count of pixels,
    canopy_metrics = np.zeros((num_trees + 1, 2), dtype=np.float32)
    apex_heights = np.zeros(num_trees + 1, dtype=np.float32)
    active_trees = np.arange(num_trees, dtype=np.int32)
    
    trees_growing = num_trees
    
    for i in range(num_trees):
        # For each apex pixel, we assign it a unique tree ID in the ownership grid 
        # and initialize its metrics based on its height in the surface grid.
        r, c = apex_p[i]
        tree_id = i + 1
        z = surface_grid[r, c]
        apex_heights[tree_id] = z
        canopy_metrics[tree_id, 0] = z
        canopy_metrics[tree_id, 1] = 1.0 

    for ring_idx in range(len(expansion_rings) - 1):
        # We loop through each ring of neighboring pixels defined by the expansion_rings array,
        if trees_growing == 0: 
            break
            
        ring_start = expansion_rings[ring_idx]
        ring_end = expansion_rings[ring_idx+1]
        next_active_count = 0
        
        for i in range(trees_growing):
            # For each active tree (those that have pixels in the previous ring), 
            # we attempt to expand its crown by checking the neighboring pixels in the current ring.
            active_idx = active_trees[i]
            tree_id = active_idx + 1
            center_r, center_c = apex_p[active_idx]
            
            # We check the canopy adhesion criteria for each neighboring pixel 
            # to determine if it should be included in the crown.
            h_apex = apex_heights[tree_id]
            cumulative_height = canopy_metrics[tree_id, 0]
            pixel_count = canopy_metrics[tree_id, 1]
            
            min_apex_h = h_apex * apex_inclusion
            max_vertical_gain = h_apex + 0.5
            
            expanded_ring = False
            
            for k in range(ring_start, ring_end):
                # We calculate the row and column indices of the neighboring pixel based on the current ring's relative offsets.
                test_r = center_r + step_y[k]
                test_c = center_c + step_x[k]
                
                # We check if the neighboring pixel is already owned by another tree. 
                # If it is, we skip it since a pixel cannot belong to multiple crowns.
                if ownership_grid[test_r, test_c] != 0: 
                    continue
                    
                h_test = surface_grid[test_r, test_c]
                
                # We apply the canopy adhesion criteria to determine if this neighboring pixel should be included in the crown.
                if h_test <= min_height:
                    continue
                if h_test > max_vertical_gain:
                    continue
                if h_test <= min_apex_h:
                    continue
                    
                if (h_test * pixel_count) <= (cumulative_height * core_inclusion):
                    continue

                # If the pixel meets the criteria, we assign it to the current tree in the ownership grid 
                # and update the canopy metrics for that tree.    
                if (ownership_grid[test_r-1, test_c] == tree_id or 
                    ownership_grid[test_r+1, test_c] == tree_id or 
                    ownership_grid[test_r, test_c-1] == tree_id or 
                    ownership_grid[test_r, test_c+1] == tree_id):
                    
                    ownership_grid[test_r, test_c] = tree_id
                    canopy_metrics[tree_id, 0] += h_test
                    canopy_metrics[tree_id, 1] += 1.0
                    expanded_ring = True
                    
            if expanded_ring:
                active_trees[next_active_count] = active_idx
                next_active_count += 1
                
        trees_growing = next_active_count # update the count of active trees for the next ring expansion

def _run_region_growing(
    chm: np.ndarray,
    apex_p: np.ndarray,
    params: DelineationParams
    ) -> np.ndarray:
    """
    Delineate tree crowns using a region growing approach based on canopy adhesion.  
    Based on Dalponte and Coomes (2016) and adapted for our specific use case.
    
    Args:
        chm (np.ndarray): 2D array representing the canopy height model.
        apex_p (np.ndarray): Array of shape (N, 2) containing the row and column indices of treetop locations.
        params (DelineationParams): Parameters for the region growing delineation method.

    Returns:
        np.ndarray: 2D array of integer labels representing the segmented tree crowns.
    """
    # We first prepare the CHM by applying a morphological closing to fill small gaps 
    # and then optionally applying Gaussian smoothing to reduce noise before region growing.
    chm_prep = ndimage.grey_closing(chm, size=(3, 3))
    if params.smoothing_sigma > 0:
        chm_prep = ndimage.gaussian_filter(chm_prep, sigma=params.smoothing_sigma)
    
    # We calculate the relative height threshold for including pixels in the crown 
    # based on the apex height and the specified inclusion parameters.
    labels = np.zeros(chm_prep.shape, dtype=np.int32)
    for i, (r, c) in enumerate(apex_p): 
        labels[r, c] = i + 1
    
    # We then perform the region growing by iteratively expanding from the apex pixels outwards,
    # checking the canopy adhesion criteria at each step to determine if neighboring pixels should be included in the crown.
    radius_px = int(params.max_canopy_spread / params.pixel_size)
    pad = radius_px + 1
    
    # We apply a padding to the CHM and labels to handle edge cases during region growing without running into index errors.
    chm_pad = np.pad(chm_prep, pad, mode='constant', constant_values=0)
    labels_pad = np.pad(labels, pad, mode='constant', constant_values=0)
    
    # We calculate the relative positions of the neighboring pixels in concentric rings
    # around the apex points, which allows us to efficiently expand the crowns in a structured manner.
    step_y, step_x, boundaries = _calculate_expansion_rings(radius_px)
    
    # Finally, we call the _expand_canopy function which performs the actual region growing based on predefined paramters
    _expand_canopy(
        surface_grid=chm_pad, 
        ownership_grid=labels_pad, 
        apex_p=apex_p + pad, 
        step_y=step_y, 
        step_x=step_x, 
        expansion_rings=boundaries, 
        apex_inclusion=params.apex_inclusion, 
        core_inclusion=params.core_inclusion, 
        min_height=params.min_height
    )

    # After the expansion is complete, we remove the padding and return the final labeled array representing the delineated tree crowns.            
    return labels_pad[pad:-pad, pad:-pad]

def delineate_crowns(
    chm_input: Union[str, Path, Raster], 
    treetops: Vector, 
    params: DelineationParams = DelineationParams(),
    tile_mode: str = "auto",
    tile_size: int = 1024,
    overlap: int = 64
    ) -> Generator[Dict[str, Any], None, None]:
    """
    Delineates tree crowns from a canopy height model (CHM) and treetop locations using specified parameters and processing strategy.
    
    Args:
        chm_input: Input canopy height model, either as a file path or a Raster object.
        treetops: Vector layer containing the treetop locations as Point geometries.
        params: DelineationParams object containing parameters for the delineation methods.
        tile_mode: Tiling strategy for processing large rasters ('auto', 'in_memory', 'blocked', 'tiled').
        tile_size: Size of tiles to use if tiling is necessary.
        overlap: Number of pixels to overlap between tiles to avoid edge effects.

    Yields:
        Dict[str, Any]: A dictionary containing the tree ID, height, delineation method used, and geometry of each detected tree crown as a Polygon.
    """
    # We first check the coordinate reference system (CRS) of the input CHM and treetop vector layer. 
    # If they differ, we reproject the treetop geometries to match the CHM's CRS to ensure spatial alignment during processing.
    raster_crs = chm_input.crs if isinstance(chm_input, Raster) else None
    
    # We extract the treetop geometries (points) and their associated attributes into a GeoDataFrame
    tt_gdf = treetops.data
    if tt_gdf.empty:
        return

    # If the treetops and raster have different CRSs, we reproject the treetop geometries to match the raster's CRS.
    # This is much more efficient than reprojecting the raster.
    if raster_crs and treetops.crs != raster_crs:
        tt_gdf = to_crs(treetops, raster_crs, inplace=False).data
    
    sindex = tt_gdf.sindex

    # We use the iter_core_halo function to process the CHM in manageable tiles, 
    # which allows us to handle larger rasters that may not fit into memory all at once.
    for chm, transform, core_box, read_box in iter_core_halo(chm_input, tile_mode, tile_size, overlap):
        
        # We compare the spatial index of the treetop points with the current tile's bounding box 
        # to quickly identify which treetops fall within the tile (including the halo).
        if sindex is not None and read_box is not None:
            possible_matches_index = list(sindex.intersection(read_box.bounds))
            local_trees = tt_gdf.iloc[possible_matches_index]
            local_trees = local_trees[local_trees.intersects(read_box)]
        else:
            local_trees = tt_gdf
            
        if local_trees.empty:
            continue # pass if no treetops in this tile

        # We then convert the spatial coordinates of the local treetops to row and column indices relative to the current tile using the affine transform.
        x_coords = local_trees.geometry.x.values
        y_coords = local_trees.geometry.y.values
        cols, rows = (~transform) * (x_coords, y_coords)
        
        # We filter out any treetops that fall outside the bounds of the current tile (including the halo)
        valid_mask = (rows >= 0) & (rows < chm.shape[0]) & (cols >= 0) & (cols < chm.shape[1])
        if not np.any(valid_mask):
            continue

        valid_rows = rows[valid_mask].astype(int)
        valid_cols = cols[valid_mask].astype(int)
        apex_p = np.column_stack((valid_rows, valid_cols))
        
        # We also extract the tree IDs and geometries for the valid treetops to associate them with the delineated crowns later on.
        tree_ids = local_trees['tree_id'].values[valid_mask] if 'tree_id' in local_trees.columns else local_trees.index.values[valid_mask]
        apex_geoms = local_trees.geometry.values[valid_mask]

        # Finally, we call the appropriate delineation method (watershed or region growing)
        if params.delineation_method == "watershed":
            final_labels = _run_watershed(chm, apex_p, params)
        elif params.delineation_method == "region_growing":
            final_labels = _run_region_growing(chm, apex_p, params)
        else: 
            raise ValueError(f"Unknown delineation method: {params.delineation_method}")

        # We use the shapes function from rasterio to convert the labeled array of delineated crowns into vector geometries (Polygons),
        # and we associate each polygon with the corresponding tree ID and height information for output.
        for geometry, value in shapes(final_labels, mask=final_labels > 0, transform=transform):
            idx = int(value) - 1
            apex_geom = apex_geoms[idx]
            
            if core_box is not None and not core_box.contains(apex_geom):
                continue

            region_mask = (final_labels == value)
            
            # We yield a metadata dictionary for each delineated crown containing the tree ID, height, delineation method and  geometry of the crown (Polygon).
            # the height of the tree can be approximated as the maximum CHM value within the delineated crown region,
            # which gives us an estimate of the tree's height.
            yield {
                "tree_id": int(tree_ids[idx]), 
                "height": float(chm[region_mask].max()),
                "del_method": params.delineation_method,
                "geometry": shape(geometry)
            }