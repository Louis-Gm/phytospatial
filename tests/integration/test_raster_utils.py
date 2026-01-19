# tests/test_raster_utils.py

import pytest
import math
import numpy as np

from phytospatial.raster import io, geom
from helpers import assert_raster_integrity, assert_grid_match

def test_raster_utils(tmp_path, source_envi_path):
    """
    Integration test validating the HDR -> GeoTIFF mechanism and subsequent processing.
    """
    
    # Load ENVI (Tests resolve_envi_path & ENVI driver)

    original_envi = io.load(source_envi_path)
    assert original_envi.count == 3
    assert original_envi.crs.to_epsg() == 4326
    
    geotiff_path = tmp_path / "converted_raw.tif"
    io.save(original_envi, geotiff_path)
    assert geotiff_path.exists()
    
    # Reload GeoTIFF and compare
    converted_tif = io.load(geotiff_path)
    assert_grid_match(original_envi, converted_tif)
    assert_raster_integrity(converted_tif, original_envi, tolerance=1e-6)

    working_raster = converted_tif

    # Split & Stacking checks
    bands = geom.split_bands(working_raster)
    stacked = geom.stack_bands(bands)
    assert np.array_equal(stacked.data, working_raster.data)

    # Reprojection check
    target_crs = "EPSG:3857"
    reprojected = geom.reproject(stacked, target_crs=target_crs)
    assert reprojected.crs.to_string() == target_crs
    assert_raster_integrity(reprojected, stacked)


    # Resampling check
    scale = 0.5
    resampled = geom.resample(reprojected, scale_factor=scale)
    
    expected_w = int(reprojected.width * scale)
    assert math.isclose(resampled.width, expected_w, abs_tol=1)
    assert_raster_integrity(resampled, reprojected)

    # Cropping check
    l, b, r, t = resampled.bounds
    w, h = (r - l), (t - b)
    crop_bounds = (l + w*0.25, b + h*0.25, r - w*0.25, t - h*0.25)
    
    cropped = geom.crop(resampled, bounds=crop_bounds)
    assert resampled.transform[0] == cropped.transform[0]

    # Alignment check
    rogue_raster = geom.reproject(cropped, target_crs="EPSG:4326")
    aligned_list = geom.align_rasters([cropped, rogue_raster], method='first')
    
    assert_grid_match(cropped, aligned_list[0])
    assert_grid_match(cropped, aligned_list[1])
    assert_raster_integrity(aligned_list[1], cropped, tolerance=0.05)

    # Final output
    final_path = tmp_path / "final_result.tif"
    io.save(cropped, final_path)
    assert final_path.exists()