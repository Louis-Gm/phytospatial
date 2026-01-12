# tests/unit/test_raster.py

import rasterio
import numpy as np
from rasterio.enums import Resampling
from pathlib import Path
from phytospatial import raster

def test_convert_envi_to_geotiff(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    input_dir.mkdir()
    
    header_file = input_dir / "test_image.hdr"
    header_content = (
        "ENVI\n"
        "samples = 10\n"
        "lines   = 10\n"
        "bands   = 1\n"
        "header offset = 0\n"
        "file type = ENVI Standard\n"
        "data type = 1\n"
        "interleave = bsq\n"
        "byte order = 0"
    )
    header_file.write_text(header_content)
    
    binary_file = input_dir / "test_image"
    binary_data = np.zeros((10, 10), dtype=np.uint8).tobytes()
    binary_file.write_bytes(binary_data)
    
    raster.convert_envi_to_geotiff(str(input_dir), str(output_dir))
    
    output_file = output_dir / "test_image.tif"
    assert output_file.exists()
    
    with rasterio.open(output_file) as src:
        assert src.driver == "GTiff"
        assert src.width == 10
        assert src.height == 10
        assert src.count == 1

def test_convert_envi_handles_compression(tmp_path):
    input_dir = tmp_path / "input_comp"
    output_dir = tmp_path / "output_comp"
    input_dir.mkdir()
    
    header_file = input_dir / "test_comp.hdr"
    header_file.write_text("ENVI\nsamples=10\nlines=10\nbands=1\ndata type=1\ninterleave=bsq\n")
    binary_file = input_dir / "test_comp"
    binary_file.write_bytes(np.zeros((10, 10), dtype=np.uint8).tobytes())
    
    raster.convert_envi_to_geotiff(str(input_dir), str(output_dir), compression="lzw")
    
    output_file = output_dir / "test_comp.tif"
    with rasterio.open(output_file) as src:
        assert src.profile['compress'] == 'lzw'

def test_reproject_raster_basic(tmp_path, mock_raster_factory):
    input_path = mock_raster_factory("input.tif", crs="EPSG:4326")
    output_path = tmp_path / "output.tif"
    
    raster.reproject_raster(input_path, str(output_path), target_crs="EPSG:3857")
    
    assert output_path.exists()
    with rasterio.open(output_path) as src:
        assert src.crs.to_string() == "EPSG:3857"

def test_reproject_raster_resampling(tmp_path, mock_raster_factory):
    input_path = mock_raster_factory("input_res.tif", crs="EPSG:32619", width=100, height=100)
    output_path = tmp_path / "output_res.tif"
    
    raster.reproject_raster(
        input_path, 
        str(output_path), 
        target_crs="EPSG:32619", 
        target_resolution=10.0,
        resampling_method=Resampling.nearest
    )
    
    with rasterio.open(output_path) as src:
        assert src.transform[0] == 10.0 
        assert src.transform[4] == -10.0 

def test_split_raster_indices(tmp_path, mock_raster_factory):
    input_path = mock_raster_factory("multiband.tif", count=3)
    output_dir = tmp_path / "split"
    
    raster.split_raster(input_path, str(output_dir))
    
    assert (output_dir / "multiband_band_1.tif").exists()
    assert (output_dir / "multiband_band_2.tif").exists()
    assert (output_dir / "multiband_band_3.tif").exists()
    
    with rasterio.open(output_dir / "multiband_band_1.tif") as src:
        assert src.count == 1

def test_split_raster_descriptions(tmp_path, mock_raster_factory):
    input_path = mock_raster_factory("desc.tif", count=2, descriptions=("Red", "NIR"))
    output_dir = tmp_path / "split_desc"
    
    raster.split_raster(input_path, str(output_dir))
    
    assert (output_dir / "desc_Red.tif").exists()
    assert (output_dir / "desc_NIR.tif").exists()

def test_stack_rasters(tmp_path, mock_raster_factory):
    input_files = []
    for i in range(3):
        p = mock_raster_factory(f"band_{i}.tif", count=1)
        input_files.append(p)
    
    output_path = tmp_path / "stacked.tif"
    raster.stack_rasters(input_files, str(output_path))
    
    assert output_path.exists()
    with rasterio.open(output_path) as src:
        assert src.count == 3
        assert src.width == 10
        assert src.height == 10