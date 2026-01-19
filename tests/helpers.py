# tests/helpers.py

import numpy as np
from phytospatial.raster.layer import Raster

def assert_raster_integrity(current: Raster, reference: Raster, tolerance: float = 0.01):
    """Check that pixel values haven't drifted significantly."""
    curr_mean = np.nanmean(current.data)
    ref_mean = np.nanmean(reference.data)
    diff = abs(curr_mean - ref_mean)
    assert diff < tolerance, f"Mean drift too high: {diff:.6f} (Tol: {tolerance})"

def assert_grid_match(r1: Raster, r2: Raster):
    """Strictly verify two rasters share the exact same grid."""
    assert r1.crs == r2.crs, \
        f"CRS mismatch: {r1.crs} != {r2.crs}"
        
    assert r1.shape == r2.shape, \
        f"Shape mismatch: {r1.shape} != {r2.shape}"
        
    assert np.allclose(np.array(r1.transform), np.array(r2.transform), atol=1e-9), \
        "Transform mismatch (Pixel alignment error)"