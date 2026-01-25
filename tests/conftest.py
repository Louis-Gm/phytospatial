# tests/conftest.py

import pytest
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS

@pytest.fixture
def source_envi_path(tmp_path):
    """
    Fixture: Creates a synthetic ENVI file (.hdr + binary) in a temp dir.
    This strictly simulates the 'RAW_HDR' input format.
    """
    p = tmp_path / "synthetic_raw"
    
    width, height = 100, 100
    transform = Affine.translation(0, 1) * Affine.scale(0.01, -0.01)
    crs = CRS.from_epsg(4326)
    
    data = np.zeros((3, height, width), dtype='float32')
    data[0] = np.linspace(0, 1, width * height).reshape(height, width) # Gradient
    data[1] = np.random.rand(height, width) # Noise
    data[2].fill(0.5)
    
    profile = {
        'driver': 'ENVI', 
        'height': height,
        'width': width,
        'count': 3,
        'dtype': 'float32',
        'crs': crs,
        'transform': transform
    }

    with rasterio.open(p, 'w', **profile) as dst:
        dst.write(data)
        
    return p.with_suffix(".hdr")