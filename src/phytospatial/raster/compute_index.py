# src/phytospatial/raster/compute_index.py

"""
This module provides functionality to generate spectral indices from raster data.
"""

import logging
from typing import Dict, Union
from pathlib import Path

import numexpr as ne
import numpy as np

from phytospatial.raster.layer import Raster
from phytospatial.raster.engine import dispatch, DispatchConfig, AggregationType
from phytospatial.raster.io import read_info
from phytospatial.raster.indices import IndexCatalog
from phytospatial.raster.utils import map_wavelengths

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
    """
    Calculate a spectral index for a block of raster data using a provided formula and band mapping.

    Args:
        raster (Raster): Input Raster object containing the spectral bands.
        formula (str): A string representing the mathematical formula for the index, 
                       using variable names corresponding to the band_mapping keys.
        band_mapping (Dict[str, int]): A dictionary mapping variable names in the formula 
                                       to 1-based band indices in the raster.
        
    Returns:
        Raster: A new Raster object containing the calculated index as a single band.
    """
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
    """
    Generates a specified vegetation index from an input orthomosaic raster and saves the result to disk.

    Args:
        input_path (Union[str, Path]): File path to the input orthomosaic raster containing the necessary spectral bands.
        output_path (Union[str, Path]): File path where the output index raster will be saved.
        index_name (str): The name of the vegetation index to compute.
        max_tolerance (float): Maximum tolerance for wavelength matching. Defaults to 20.0 nm.

    Returns:
        Path: The file path to the generated index raster.
    """
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