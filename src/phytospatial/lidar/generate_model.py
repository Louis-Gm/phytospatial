from enum import Enum
from typing import Union, Tuple
from pathlib import Path
import logging

import numpy as np
import scipy.ndimage as ndimage
from rasterio.crs import CRS
from rasterio.fill import fillnodata
from rasterio.transform import Affine
from numba import njit

from phytospatial.raster.layer import Raster

from phytospatial.lidar.layer import PointCloud
from phytospatial.lidar.io import iter_pc
from phytospatial.lidar.csf import simulate_cloth, simulate_cloth_chunked

log = logging.getLogger(__name__)

__all__ = [
    "TerrainType",
    "generate_dtm",
    "generate_dsm",
    "generate_chm"
]

NODATA_VAL = -9999.0

class TerrainType(Enum):
    """
    Categorical enumeration defining landscape complexities for ground filtering tolerances.
    """
    FLAT = 1
    RELIEF = 2
    HIGH_RELIEF = 3

def _get_filter_params(
    terrain: TerrainType
    ) -> dict:
    """
    Maps terrain complexity to optimal parameters for the physics-based cloth simulation.

    Args:
        terrain (TerrainType): The complexity of the landscape.

    Returns:
        dict: A mapping containing configurations for the cloth simulation filter.
    """
    if terrain == TerrainType.FLAT:
        return {"cell_size": 1.5, "iterations": 50, "time_step": 0.5, "rigidness": 0.1, "height_threshold": 0.3}
    elif terrain == TerrainType.RELIEF:
        return {"cell_size": 1.0, "iterations": 100, "time_step": 0.4, "rigidness": 0.5, "height_threshold": 0.5}
    elif terrain == TerrainType.HIGH_RELIEF:
        return {"cell_size": 1.0, "iterations": 150, "time_step": 0.3, "rigidness": 1.0, "height_threshold": 1.0}
    return {"cell_size": 1.0, "iterations": 100, "time_step": 0.4, "rigidness": 0.5, "height_threshold": 0.5}

def _create_affine_transform(min_x: float, max_y: float, resolution: float) -> Affine:
    """
    Generates affine coordinate reference transforms for empty grids.

    Args:
        min_x (float): Minimum absolute X coordinate of the target grid footprint.
        max_y (float): Maximum absolute Y coordinate of the target grid footprint.
        resolution (float): Spatial resolution defining geographic units per pixel.

    Returns:
        Affine: Instantiated affine transformation matrix for strict georeferencing.
    """
    return Affine.translation(min_x, max_y) * Affine.scale(resolution, -resolution)

@njit(cache=True, fastmath=True)
def _process_dual_chunk_fused(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    ground_mask: np.ndarray,
    dsm_grid: np.ndarray,
    dtm_grid: np.ndarray,
    min_x: float,
    max_y: float,
    resolution: float,
    height: int,
    width: int,
    compute_dtm: bool
    ) -> None:
    """
    Simultaneously populates the digital surface and terrain matrices within a single 
    compiled iteration block to eliminate redundant point evaluations.

    Args:
        x (np.ndarray): Horizontal point coordinates.
        y (np.ndarray): Vertical point coordinates.
        z (np.ndarray): Elevation point coordinates.
        ground_mask (np.ndarray): Boolean array isolating bare earth classifications.
        dsm_grid (np.ndarray): Target matrix for maximum elevations.
        dtm_grid (np.ndarray): Target matrix for minimum ground elevations.
        min_x (float): Absolute minimum X coordinate of the spatial envelope.
        max_y (float): Absolute maximum Y coordinate of the spatial envelope.
        resolution (float): Coordinate span per discrete grid cell.
        height (int): Row boundary dimension of the matrices.
        width (int): Column boundary dimension of the matrices.
        compute_dtm (bool): Flag to dynamically toggle ground evaluation logic.
    """
    for i in range(x.shape[0]):
        c = int((x[i] - min_x) / resolution)
        r = int((max_y - y[i]) / resolution)

        if 0 <= r < height and 0 <= c < width:
            if z[i] > dsm_grid[r, c]:
                dsm_grid[r, c] = z[i]
                
            if compute_dtm and ground_mask[i]:
                if z[i] < dtm_grid[r, c]:
                    dtm_grid[r, c] = z[i]

def _generate_base_surfaces(
    source: Union[str, Path, PointCloud],
    resolution: float,
    terrain: TerrainType,
    chunk_size: int,
    force_csf: bool,
    compute_dtm: bool = True
    ) -> Tuple[np.ndarray, np.ndarray, Affine, float, float]:
    """
    Core execution engine responsible for loading, classifying, and mapping point geometries 
    into a unified multi-band tensor representing the extreme bounds of the surface profile.

    Args:
        source (Union[str, Path, PointCloud]): Target spatial object or active byte stream.
        resolution (float): Continuous surface resolution in discrete meter steps.
        terrain (TerrainType): Complexity definition mapped to physics simulations.
        chunk_size (int): Buffer limit strictly governing RAM allocation profiles.
        force_csf (bool): Command to override existing classifications with cloth simulation.
        compute_dtm (bool): Toggle to bypass physics computations for surface-only calls.

    Returns:
        Tuple[np.ndarray, np.ndarray, Affine, float, float]: The populated DSM matrix, DTM matrix, 
            affine orientation, and the search radii requirements for spatial gap filling.
    """
    is_classified = False
    
    if isinstance(source, PointCloud):
        min_x, max_x = source.min_x, source.max_x
        min_y, max_y = source.min_y, source.max_y
        if np.any(source.classification == 2):
            is_classified = True
    else:
        source_path = Path(source)
        first_chunk = next(iter_pc(source_path, chunk_size=chunk_size))
        min_x, max_x = first_chunk.min_x, first_chunk.max_x
        min_y, max_y = first_chunk.min_y, first_chunk.max_y
        
        for pc in iter_pc(source_path, chunk_size=chunk_size):
            if np.any(pc.classification == 2):
                is_classified = True
                break

    width = int((max_x - min_x) / resolution)
    height = int((max_y - min_y) / resolution)
    dsm_grid = np.full((height, width), -np.inf, dtype=np.float32)
    dtm_grid = np.full((height, width), np.inf, dtype=np.float32)
    transform = _create_affine_transform(min_x, max_y, resolution)

    if isinstance(source, PointCloud):
        if compute_dtm:
            if is_classified and not force_csf:
                ground_mask = source.classification == 2
            else:
                params = _get_filter_params(terrain)
                ground_mask = simulate_cloth(
                    pc=source,
                    cell_size=params["cell_size"],
                    iterations=params["iterations"],
                    time_step=params["time_step"],
                    rigidness=params["rigidness"],
                    height_threshold=params["height_threshold"]
                )
        else:
            ground_mask = np.zeros(source.x.shape[0], dtype=np.bool_)
            
        _process_dual_chunk_fused(
            x=source.x, y=source.y, z=source.z, ground_mask=ground_mask,
            dsm_grid=dsm_grid, dtm_grid=dtm_grid, min_x=min_x, max_y=max_y, 
            resolution=resolution, height=height, width=width, compute_dtm=compute_dtm
        )
    else:
        if compute_dtm:
            if is_classified and not force_csf:
                for pc in iter_pc(source_path, chunk_size=chunk_size):
                    ground_mask = pc.classification == 2
                    _process_dual_chunk_fused(
                        x=pc.x, y=pc.y, z=pc.z, ground_mask=ground_mask,
                        dsm_grid=dsm_grid, dtm_grid=dtm_grid, min_x=min_x, max_y=max_y, 
                        resolution=resolution, height=height, width=width, compute_dtm=True
                    )
            else:
                params = _get_filter_params(terrain)
                mask_generator = simulate_cloth_chunked(
                    source=source_path,
                    cell_size=params["cell_size"],
                    iterations=params["iterations"],
                    time_step=params["time_step"],
                    rigidness=params["rigidness"],
                    height_threshold=params["height_threshold"],
                    chunk_size=chunk_size
                )
                for pc, mask in zip(iter_pc(source_path, chunk_size=chunk_size), mask_generator):
                    _process_dual_chunk_fused(
                        x=pc.x, y=pc.y, z=pc.z, ground_mask=mask,
                        dsm_grid=dsm_grid, dtm_grid=dtm_grid, min_x=min_x, max_y=max_y, 
                        resolution=resolution, height=height, width=width, compute_dtm=True
                    )
        else:
            for pc in iter_pc(source_path, chunk_size=chunk_size):
                dummy_mask = np.zeros(pc.x.shape[0], dtype=np.bool_)
                _process_dual_chunk_fused(
                    x=pc.x, y=pc.y, z=pc.z, ground_mask=dummy_mask,
                    dsm_grid=dsm_grid, dtm_grid=dtm_grid, min_x=min_x, max_y=max_y, 
                    resolution=resolution, height=height, width=width, compute_dtm=False
                )

    d_search = max(10, int(20.0 / resolution))
    t_search = max(15, int(35.0 / resolution))
    
    return dsm_grid, dtm_grid, transform, d_search, t_search

def generate_dtm(
    source: Union[str, Path, PointCloud],
    resolution: float,
    crs: Union[str, CRS],
    terrain: TerrainType = TerrainType.RELIEF,
    chunk_size: int = 2_000_000,
    force_csf: bool = False
    ) -> Raster:
    """
    Extracts and interpolates the minimum bare earth elevation footprint from the unified spatial pipeline.

    Args:
        source (Union[str, Path, PointCloud]): Target geometric entity or byte file.
        resolution (float): Square dimension of discrete matrix cells in coordinate metrics.
        crs (Union[str, CRS]): Projection and datum specifications.
        terrain (TerrainType): Modifies internal simulation tension limits for complex landscapes.
        chunk_size (int): Execution point limit strictly scaling active RAM utilization.
        force_csf (bool): Circumvents explicit classifications to re-simulate ground masks.

    Returns:
        Raster: Interpolated and sealed continuous surface.
    """
    _, dtm_grid, transform, _, t_search = _generate_base_surfaces(
        source, resolution, terrain, chunk_size, force_csf, compute_dtm=True
    )
    
    dtm_grid[dtm_grid == np.inf] = np.nan
    valid_mask = ~np.isnan(dtm_grid)

    if np.any(valid_mask) and not np.all(valid_mask):
        dtm_grid = fillnodata(dtm_grid, mask=valid_mask.astype(np.uint8), max_search_distance=t_search)
    elif not np.any(valid_mask):
        dtm_grid[:] = NODATA_VAL

    dtm_grid[np.isnan(dtm_grid)] = NODATA_VAL

    return Raster(
        data=dtm_grid.astype(np.float32),
        transform=transform,
        crs=crs,
        nodata=NODATA_VAL
    )

def generate_dsm(
    source: Union[str, Path, PointCloud],
    resolution: float,
    crs: Union[str, CRS],
    chunk_size: int = 2_000_000
    ) -> Raster:
    """
    Extracts and filters the maximum vegetation footprint from the unified spatial pipeline.

    Args:
        source (Union[str, Path, PointCloud]): Target geometric entity or byte file.
        resolution (float): Square dimension of discrete matrix cells in coordinate metrics.
        crs (Union[str, CRS]): Projection and datum specifications.
        chunk_size (int): Execution point limit strictly scaling active RAM utilization.

    Returns:
        Raster: Sealed and hole-filled contiguous surface footprint.
    """
    dsm_grid, _, transform, d_search, _ = _generate_base_surfaces(
        source, resolution, TerrainType.FLAT, chunk_size, force_csf=False, compute_dtm=False
    )
    
    dsm_grid[dsm_grid == -np.inf] = np.nan
    valid_mask = ~np.isnan(dsm_grid)
    
    data_footprint = valid_mask.copy()
    data_footprint = ndimage.binary_closing(data_footprint, structure=np.ones((5, 5)))
    data_footprint = ndimage.binary_fill_holes(data_footprint)
    
    if np.any(valid_mask) and not np.all(valid_mask):
        dsm_grid = fillnodata(dsm_grid, mask=valid_mask.astype(np.uint8), max_search_distance=d_search)
    elif not np.any(valid_mask):
        dsm_grid[:] = NODATA_VAL
        
    dsm_grid[~data_footprint] = NODATA_VAL
    dsm_grid[np.isnan(dsm_grid)] = NODATA_VAL
    
    return Raster(
        data=dsm_grid.astype(np.float32),
        transform=transform,
        crs=crs,
        nodata=NODATA_VAL
    )

def generate_chm(
    source: Union[str, Path, PointCloud],
    resolution: float,
    crs: Union[str, CRS],
    terrain: TerrainType = TerrainType.RELIEF,
    chunk_size: int = 2_000_000,
    force_csf: bool = False,
    filter_size: int = 3
    ) -> Raster:
    """
    Constructs a finalized Canopy Height Model entirely in-memory using a fused single-pass map execution, 
    eliminating redundant disk streaming and intermediate layer serializations.

    Args:
        source (Union[str, Path, PointCloud]): Source coordinate spatial tensor.
        resolution (float): Matrix subdivision granularity.
        crs (Union[str, CRS]): Defined projection system.
        terrain (TerrainType): Modifies physics bounds for cloth drop.
        chunk_size (int): Stream slicing bounds for RAM safety limits.
        force_csf (bool): Bypass existing structural classification checks.
        filter_size (int): Matrix kernel mapping for salt-and-pepper noise dampening.

    Returns:
        Raster: Cleaned, height-normalized canopy architecture model.
    """
    dsm_grid, dtm_grid, transform, d_search, t_search = _generate_base_surfaces(
        source, resolution, terrain, chunk_size, force_csf, compute_dtm=True
    )
    
    dsm_grid[dsm_grid == -np.inf] = np.nan
    dtm_grid[dtm_grid == np.inf] = np.nan
    
    dsm_valid = ~np.isnan(dsm_grid)
    dtm_valid = ~np.isnan(dtm_grid)
    
    data_footprint = dsm_valid.copy()
    data_footprint = ndimage.binary_closing(data_footprint, structure=np.ones((5, 5)))
    data_footprint = ndimage.binary_fill_holes(data_footprint)
    
    if np.any(dtm_valid) and not np.all(dtm_valid):
        dtm_grid = fillnodata(dtm_grid, mask=dtm_valid.astype(np.uint8), max_search_distance=t_search)
        
    if np.any(dsm_valid) and not np.all(dsm_valid):
        dsm_grid = fillnodata(dsm_grid, mask=dsm_valid.astype(np.uint8), max_search_distance=d_search)
        
    chm_arr = dsm_grid - dtm_grid
    chm_arr[chm_arr < 0.0] = 0.0
    
    if filter_size > 0:
        chm_arr = np.where(data_footprint, ndimage.median_filter(chm_arr, size=filter_size), np.nan)
        
    chm_arr[~data_footprint] = NODATA_VAL
    chm_arr[np.isnan(chm_arr)] = NODATA_VAL
    
    return Raster(
        data=chm_arr.astype(np.float32),
        transform=transform,
        crs=crs,
        nodata=NODATA_VAL,
        band_names={"CHM": 1}
    )