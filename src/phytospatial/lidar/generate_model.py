# src/phytospatial/lidar/generate_model.py

"""
This module implements functions to generate various raster products from lidar point clouds.
"""

from enum import Enum
from typing import Union, Optional
from pathlib import Path
import logging

import numpy as np
import CSF
import scipy.ndimage as ndimage
from rasterio.crs import CRS
from rasterio.fill import fillnodata
from numba import jit

from phytospatial.raster.layer import Raster
from phytospatial.raster.engine import dispatch, DispatchConfig, AggregationType

from .layer import PointCloud
from .rasterize import points_to_grid, NODATA_VAL

log = logging.getLogger(__name__)

__all__ = [
    "TerrainType",
    "generate_dtm",
    "generate_dsm",
    "calculate_chm"
]

class TerrainType(Enum):
    """
    Defines terrain types used in topographical filtering parameterization.

    Options:
    FLAT: Represents areas with minimal elevation variation, such as plains or agricultural fields.
    RELIEF: Represents areas with moderate elevation variation, such as rolling hills or mixed terrain.
    HIGH_RELIEF: Represents areas with significant elevation variation, such as mountainous regions or deep valleys
    """
    FLAT = 1
    RELIEF = 2
    HIGH_RELIEF = 3

def _get_csf_params(
    terrain: TerrainType
    ) -> dict:
    """
    Extracts configuration parameters for the Cloth Simulation Filter framework.

    Args:
        terrain (TerrainType): Macro level topographical structure. See TerrainType enum for options.

    Returns:
        dict: Dictionary of parameters to configure the CSF algorithm based on terrain type.
    """
    if terrain == TerrainType.FLAT:
        return {"rigidness": 3, "slope_smoothing": False}
    elif terrain == TerrainType.RELIEF:
        return {"rigidness": 2, "slope_smoothing": True}
    elif terrain == TerrainType.HIGH_RELIEF:
        return {"rigidness": 1, "slope_smoothing": True}
    return {"rigidness": 2, "slope_smoothing": True}

def generate_dtm(
    pc: PointCloud,
    resolution: float,
    crs: Union[str, CRS],
    terrain: TerrainType = TerrainType.RELIEF
    ) -> Raster:
    """
    Classifies points and extracts the terrain plane using Cloth Simulation Filters and optimized GDAL filling.
    
    Args:
        pc (PointCloud): Fully loaded point cloud dependency.
        resolution (float): Output pixel dimension sizing.
        crs (Union[str, CRS]): Affine coordinate projection mapping.
        terrain (TerrainType): Macro level topographical structure.
        
    Returns:
        Raster: Filtered representation of the ground topography securely clipped to the original flight path.
    """
    # Initializes terrain parameters for the CSF algorithm based on the specified terrain type
    params = _get_csf_params(terrain)

    # Set up the CSF filter with the configured parameters and prepare the point cloud for processing
    csf = CSF.CSF()
    
    # Set a cloth resolution that is at least as large as the output raster resolution to balance detail and performance
    cloth_res = max(1.0, resolution)

    # Configure CSF parameters based on terrain type, 
    # which influences how the algorithm simulates the cloth draping over the point cloud to identify ground points
    csf.params.cloth_resolution = cloth_res
    csf.params.bSloopSmooth = params["slope_smoothing"]
    csf.params.time_step = 0.65
    csf.params.rigidness = params["rigidness"]
    
    # To optimize the CSF processing, we shift the point cloud to a local coordinate system starting at (0,0)
    # This avoids issues with large coordinate values
    shift_x = np.min(pc.x)
    shift_y = np.min(pc.y)    
    x_local = pc.x - shift_x
    y_local = pc.y - shift_y
    
    # We convert the local point coordinates into a format suitable for the CSF algorithm (2D array of points with X, Y, and Z values)
    # We then set this point cloud into the CSF filter for processing
    points = np.vstack((x_local, y_local, pc.z)).transpose()
    csf.setPointCloud(points)
    
    # We classify points using the CSF algorithm
    ground_idx = CSF.VecInt()
    off_ground_idx = CSF.VecInt()
    csf.do_filtering(ground_idx, off_ground_idx, False)
    
    g_idx = np.array(ground_idx)
    gx, gy, gz = pc.x[g_idx], pc.y[g_idx], pc.z[g_idx]
    
    # We assign the classified ground points to a new PointCloud object, which will be used to generate the DTM raster
    ground_pc = PointCloud(
        x=gx, y=gy, z=gz,
        classification=np.zeros_like(gx), return_number=np.zeros_like(gx),
        min_x=pc.min_x, max_x=pc.max_x, min_y=pc.min_y, max_y=pc.max_y, max_z=np.max(gz) if len(gz) > 0 else 0.0
    )

    # points_to_grid is used to rasterize the ground points into a DTM raster using the 'min' method
    dtm_raster = points_to_grid(ground_pc, resolution, crs, method='min', nodata=np.nan)
    dtm_grid = dtm_raster.data[0]
    
    # We create a mask of valid pixels in the DTM grid to identify areas that need filling
    valid_mask = ~np.isnan(dtm_grid)

    # We create a footprint of where we have data with the 'count' method.
    # This prevents the fillnodata function from extrapolating values far beyond the original point cloud coverage
    footprint_raster = points_to_grid(pc, resolution, crs, method='count')
    data_footprint = footprint_raster.data[0] > 0
    data_footprint = ndimage.binary_closing(data_footprint, structure=np.ones((5,5)))
    data_footprint = ndimage.binary_fill_holes(data_footprint)
    
    # Define a max search distance to prevent excessive searching in areas with sparse data
    max_search_px = max(15, int(35.0 / resolution))
    
    if np.any(valid_mask) and not np.all(valid_mask):
        dtm_grid = fillnodata(dtm_grid, mask=valid_mask.astype(np.uint8), max_search_distance=max_search_px)
    elif not np.any(valid_mask):
        dtm_grid[:] = NODATA_VAL

    # To smooth the DTM and reduce artifacts from the rasterization and filling process, we apply a Gaussian filter.
    blur_sigma = (cloth_res / resolution) * 0.5
    dtm_grid = ndimage.gaussian_filter(dtm_grid, sigma=blur_sigma)
    dtm_grid[~data_footprint] = NODATA_VAL
    dtm_grid[np.isnan(dtm_grid)] = NODATA_VAL

    return Raster(
            data=dtm_grid.astype(np.float32),
            transform=dtm_raster.transform,
            crs=crs,
            nodata=NODATA_VAL
            )

def generate_dsm(
    source: Union[str, Path, PointCloud],
    resolution: float,
    crs: Union[str, CRS]
) -> Raster:
    """
    Interpolates uppermost LiDAR returns into a continuous canopy surface mapping.
    
    Args:
        source (Union[str, Path, PointCloud]): Data object or streaming path reference.
        resolution (float): Output pixel dimension sizing.
        crs (Union[str, CRS]): Affine coordinate projection mapping.
        
    Returns:
        Raster: Array of interpolated point maxima securely clipped to the valid spatial bounds.
    """
    # The DSM is simpler to generate than the DTM, as we can directly rasterize the highest points using the 'max' method in points_to_grid.
    dsm_raster = points_to_grid(source, resolution, crs, method='max', nodata=np.nan)
    dsm_grid = dsm_raster.data[0]

    valid_mask = ~np.isnan(dsm_grid)

    # Note that the search distance for filling DSM gaps may need to be larger than for the DTM, 
    # especially in areas with sparse canopy coverage, to ensure we can fill in missing values without leaving large holes. 
    # However, we still want to limit this to prevent unrealistic interpolation across large gaps.
    max_search_px = max(10, int(20.0 / resolution))
    
    # We define a data footprint based on where we have valid DSM values, and we expand this footprint slightly to allow for filling small gaps
    # while preventing excessive extrapolation in areas with no data.
    data_footprint = valid_mask.copy()
    data_footprint = ndimage.binary_closing(data_footprint, structure=np.ones((5,5)))
    data_footprint = ndimage.binary_fill_holes(data_footprint)

    if np.any(valid_mask) and not np.all(valid_mask):
        dsm_grid = fillnodata(dsm_grid, mask=valid_mask.astype(np.uint8), max_search_distance=max_search_px)
    elif not np.any(valid_mask):
        dsm_grid[:] = NODATA_VAL

    dsm_grid[~data_footprint] = NODATA_VAL
    dsm_grid[np.isnan(dsm_grid)] = NODATA_VAL

    return Raster(
            data=dsm_grid.astype(np.float32),
            transform=dsm_raster.transform,
            crs=crs,
            nodata=NODATA_VAL
            )

@jit(nopython=True, cache=True)
def _compute_raw_chm(
    dsm_arr: np.ndarray, 
    dtm_arr: np.ndarray, 
    has_d_nodata: bool, 
    d_nodata: float, 
    has_t_nodata: bool, 
    t_nodata: float, 
    out_nodata: float
    ):
    """
    Naive CHM computation with explicit loops for numba optimization.

    Args:
        dsm_arr: 2D array of DSM values.
        dtm_arr: 2D array of DTM values.
        has_d_nodata: Whether DSM has a nodata value.
        d_nodata: The nodata value for DSM.
        has_t_nodata: Whether DTM has a nodata value.
        t_nodata: The nodata value for DTM.
        out_nodata: The nodata value to use for the output CHM.

    Returns:
        Tuple of (chm_arr, valid_mask) where chm_arr is the computed CHM and valid_mask indicates valid pixels.
    """
    rows, cols = dsm_arr.shape
    chm_arr = np.empty((rows, cols), dtype=np.float32)
    valid_mask = np.empty((rows, cols), dtype=np.bool_)
    
    # We iterate through each pixel in the DSM and DTM arrays to compute the CHM value as the difference between DSM and DTM.
    # We also check for nodata values in both DSM and DTM to ensure we only compute valid CHM values where we have valid input data.
    for i in range(rows):
        for j in range(cols):
            d_val = dsm_arr[i, j]
            t_val = dtm_arr[i, j]
            
            is_valid = True
            if has_d_nodata and d_val == d_nodata:
                is_valid = False
            if has_t_nodata and t_val == t_nodata:
                is_valid = False
                
            if not is_valid:
                chm_arr[i, j] = out_nodata
                valid_mask[i, j] = False
            else:
                diff = d_val - t_val
                if diff < 0.0:
                    diff = 0.0
                chm_arr[i, j] = diff
                valid_mask[i, j] = True
                
    return chm_arr, valid_mask

def _chm_block(
    dsm: Raster, 
    dtm: Raster, 
    filter_size: int
    ) -> Raster:
    """
    Helper function to compute CHM for a block of DSM and DTM rasters. Designed for use with the dispatch framework.

    Args:
        dsm: Raster object representing the Digital Surface Model for the block.
        dtm: Raster object representing the Digital Terrain Model for the block.
        filter_size: Size of the median filter to apply to the CHM.

    Returns:
        Raster: The computed CHM raster for the block.
    """
    d_nodata = dsm.nodata
    t_nodata = dtm.nodata
    
    dsm_arr = dsm.get_band(1)
    dtm_arr = dtm.get_band(1)
    
    has_d_nodata = d_nodata is not None
    d_nodata_val = float(d_nodata) if has_d_nodata else 0.0
    has_t_nodata = t_nodata is not None
    t_nodata_val = float(t_nodata) if has_t_nodata else 0.0
    
    out_nodata_val = float(d_nodata) if has_d_nodata else float(NODATA_VAL)
    
    # We compute the raw CHM values using the helper function, which handles nodata values and computes the difference between DSM and DTM.
    chm_arr, valid_mask = _compute_raw_chm(
        dsm_arr, 
        dtm_arr, 
        has_d_nodata, 
        d_nodata_val, 
        has_t_nodata, 
        t_nodata_val, 
        out_nodata_val
    )
    
    # To reduce noise and create a smoother canopy surface, we apply a median filter to the CHM values.
    if filter_size > 0:
        temp_chm = np.copy(chm_arr)
        temp_chm[~valid_mask] = 0.0
        smoothed_chm = ndimage.median_filter(temp_chm, size=filter_size)
        chm_arr = np.where(valid_mask, smoothed_chm, out_nodata_val)
        
    return Raster(
        data=chm_arr,
        transform=dsm.transform,
        crs=dsm.crs,
        nodata=out_nodata_val,
        band_names={"CHM": 1} # we set a band name for clarity if the output is stacked in the future
    )

def calculate_chm(
    dsm: Union[str, Path, Raster],
    dtm: Union[str, Path, Raster],
    output_path: Optional[Union[str, Path]] = None,
    filter_size: int = 3,
    tile_mode: str = "auto"
    ) -> Union[Raster, Path]:
    """
    Calculates the Canopy Height Model (CHM) from DSM and DTM rasters.

    Args:
        dsm: Digital Surface Model raster or path.
        dtm: Digital Terrain Model raster or path.
        output_path: Optional output path for the CHM.
        filter_size: Size of the median filter to apply to the CHM.
        tile_mode: Mode for tiling operations (e.g., "auto").

    Returns:
        The computed CHM raster or the path to the output file if `output_path` is provided.
    """

    # We set up a dispatch configuration to compute the CHM in blocks, 
    # which allows us to handle larger rasters that may not fit into memory all at once.
    # See the dispatch framework for more details on how this works, but essentially it will call the _chm_block function
    # on manageable chunks of the input rasters and then aggregate the results.
    config = DispatchConfig(
        mode=tile_mode,
        output_path=output_path,
        aggregation=AggregationType.STITCH if output_path else AggregationType.COLLECT
    )

    result = dispatch(
        func=_chm_block,
        input_map={'dsm': dsm, 'dtm': dtm},
        static_kwargs={'filter_size': filter_size},
        config=config
    )
    
    if output_path:
        # We allow polymorphic return types here:
        # if an output path is provided, we return the path to the saved CHM raster.
        # Otherwise, we return the Raster object directly.
        return Path(output_path)
    return result[0] if isinstance(result, list) else result