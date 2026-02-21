# src/phytospatial/raster/spectral_map.py
"""
This module provides functionality to generate spectral indices from raster data.
"""

import logging
from typing import Dict, Union
from pathlib import Path

import numexpr as ne
import numpy as np

from .layer import Raster
from .engine import dispatch, DispatchConfig, AggregationType
from .io import read_info
from .indices import IndexCatalog
from .utils import map_wavelengths

log = logging.getLogger(__name__)

__all__ = [
    "calculate_index_block",
    "generate_index"
]

def calculate_index_block(
    raster: Raster, 
    formula: str, 
    band_mapping: Dict[str, int]
) -> Raster:
    local_dict = {}
    for var_name, band_idx in band_mapping.items():
        local_dict[var_name] = raster.get_band(band_idx) 
        
    mask = None
    if raster.nodata is not None:
        mask = np.ones_like(list(local_dict.values())[0], dtype=bool)
        for arr in local_dict.values():
            mask &= (arr != raster.nodata)
            
        for var_name in local_dict:
            local_dict[var_name] = np.where(mask, local_dict[var_name], 1.0)
    
    result_array = ne.evaluate(formula, local_dict=local_dict)
    
    if raster.nodata is not None and mask is not None:
        result_array = np.where(mask, result_array, raster.nodata)
        
    return Raster(
        data=result_array, 
        transform=raster.transform,
        crs=raster.crs,
        nodata=raster.nodata,
        band_names={"index_name": 1}
    )

def generate_index(
    input_path: Union[str, Path], 
    output_path: Union[str, Path], 
    index_name: str,
    max_tolerance: float = 20.0
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    catalog = IndexCatalog()
    target_index = catalog.get(index_name)
    
    metadata = read_info(input_path)
    
    band_mapping = map_wavelengths(
        parsed_wavelengths=metadata.get('wavelengths_nm', {}),
        required_wavelengths=target_index.wavelengths,
        max_tolerance=max_tolerance
    )
    
    config = DispatchConfig(
        mode="auto", 
        output_path=output_path, 
        aggregation=AggregationType.STITCH 
    )
    
    dispatch(
        func=calculate_index_block,
        input_map={'raster': input_path},
        static_kwargs={
            'formula': target_index.formula,
            'band_mapping': band_mapping
        },
        config=config
    )
    
    return output_path