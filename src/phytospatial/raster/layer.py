# src/phytospatial/raster/layer.py

"""
This module defines the Raster data structure. It is the core
unit of raster data in phytospatial.

It synchronizes pixel data (NumPy array) with geospatial context (CRS, Transform).
"""

import logging
from typing import Union, Optional, Dict, Any, Tuple
import copy

import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS

log = logging.getLogger(__name__)

__all__ = ["Raster"]

class Raster:
    """
    In-memory raster data container with geospatial metadata.
    
    A Raster synchronizes:
    1. Pixel Data: A NumPy array in (Bands, Height, Width) format
    2. Geospatial Context: CRS, Affine Transform, NoData value
    
    Unlike a rasterio dataset, this object holds data in RAM, enabling
    high-performance operation chaining without disk I/O.
    
    Attributes:
        data (np.ndarray): Pixel array in (Bands, Height, Width) format
        transform (Affine): Affine transform matrix (pixel → coordinates)
        crs (CRS): Coordinate Reference System
        nodata (float | int | None): Value representing missing data
        band_names (Dict[str, int]): Mapping of semantic names to 1-based band indices
    """

    def __init__(
        self, 
        data: np.ndarray, 
        transform: Affine, 
        crs: Union[str, CRS], 
        nodata: Optional[Union[float, int]] = None,
        band_names: Optional[Dict[str, int]] = None
    ):
        """
        Initialize a Raster object.

        Args:
            data: Pixel array. Must be 2D (Height, Width) or 3D (Bands, Height, Width).
                  2D arrays are automatically promoted to 3D (1, Height, Width).
            transform: Geospatial transform (maps pixel coords to CRS coords)
            crs: Coordinate Reference System (EPSG code, proj string, or CRS object)
            nodata: Value indicating missing/invalid data
            band_names: Optional mapping of semantic names to 1-based band indices
                        Format:{"red": 1, "green": 2, "blue": 3}
        
        Raises:
            TypeError: If data or transform have wrong types
            ValueError: If data dimensions are invalid
        """
        self._validate_inputs(data, transform, crs)
        if isinstance(crs, str):
            crs = CRS.from_string(crs)

        if data.ndim == 2:
            data = data[np.newaxis, :, :]

        self._data = data
        self.transform = transform
        self.crs = crs
        self.nodata = nodata
        self.band_names = band_names or {}

    def _validate_inputs(self, data: np.ndarray, transform: Affine, crs: Union[str, CRS]):
        """
        Helper to validate constructor inputs.
        
        Args:
            data: Input array
            transform: Affine transform
            crs: Coordinate reference system
            
        Raises:
            TypeError: If types are incorrect
            ValueError: If dimensions are invalid
        """
        if not isinstance(data, np.ndarray):
            raise TypeError(f"Data must be numpy.ndarray, got {type(data)}")
        
        if data.ndim not in (2, 3):
            raise ValueError(f"Data must be 2D or 3D, got shape {data.shape}")
        
        if not isinstance(transform, Affine):
            raise TypeError(f"Transform must be rasterio.Affine, got {type(transform)}")
        
        if not isinstance(crs, (str, CRS)):
            raise TypeError(f"CRS must be string or rasterio.CRS, got {type(crs)}")

    @property
    def data(self) -> np.ndarray:
        """
        Access the raw pixel data.
        
        Returns:
            np.ndarray: 3D array in (Bands, Height, Width) format
        """
        return self._data

    @data.setter
    def data(self, new_data: np.ndarray):
        """
        Update pixel data.

        Args:
            new_data: New pixel array (2D or 3D). 2D arrays are promoted to 3D.
        
        Raises:
            ValueError: If new_data is not 2D or 3D
        """
        if new_data.ndim == 2:
            new_data = new_data[np.newaxis, :, :]
        
        if new_data.ndim != 3:
            raise ValueError(f"New data must be 2D or 3D, got {new_data.ndim}D")
            
        self._data = new_data

    @property
    def width(self) -> int:
        """Raster width in pixels."""
        return self._data.shape[2]

    @property
    def height(self) -> int:
        """Raster height in pixels."""
        return self._data.shape[1]

    @property
    def count(self) -> int:
        """Number of bands."""
        return self._data.shape[0]

    @property
    def shape(self) -> Tuple[int, int, int]:
        """
        Raster dimensions.
        
        Returns:
            Tuple[int, int, int]: (Bands, Height, Width)
        """
        return self._data.shape

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """
        Bounding box in CRS coordinates.
        
        Returns:
            Tuple[float, float, float, float]: (left, bottom, right, top)
        """
        return rasterio.transform.array_bounds(self.height, self.width, self.transform)

    @property
    def profile(self) -> Dict[str, Any]:
        """
        Generate a rasterio-compliant profile for saving.
        
        This profile can be used with rasterio.open() to write the raster to disk.
        NOTE: Can override specific keys (compress='deflate') when saving using
        the **profile_kwargs in the save() function.
        
        Returns:
            Dict[str, Any]: Rasterio profile dictionary
        """
        return {
            'driver': 'GTiff',
            'dtype': self._data.dtype,
            'nodata': self.nodata,
            'width': self.width,
            'height': self.height,
            'count': self.count,
            'crs': self.crs,
            'transform': self.transform,
            'compress': 'lzw',
            'tiled': True
        }
    
    @property
    def memory_size(self) -> int:
        """
        Estimate memory size in bytes.
        
        Returns:
            int: Memory size in bytes
        """
        return self._data.nbytes * 3  # Rough estimate including overhead
    
    def get_band(self, identifier: Union[int, str]) -> np.ndarray:
        """
        Retrieve a specific band by index or name.
        
        Args:
            identifier: Either a 1-based band index (int) or semantic name (str)
        
        Returns:
            np.ndarray: 2D array of the requested band
            
        Raises:
            KeyError: If band name not found
            IndexError: If band index out of range
        """
        if isinstance(identifier, str):
            if identifier not in self.band_names:
                raise KeyError(
                    f"Band name '{identifier}' not found. "
                    f"Available names: {list(self.band_names.keys())}"
                )
            idx = self.band_names[identifier]
        else:
            idx = identifier

        if not (1 <= idx <= self.count):
            raise IndexError(f"Band index {idx} out of range (1-{self.count})")
        
        return self._data[idx - 1]

    def copy(self) -> 'Raster':
        """
        Create a deep copy of the Raster.
        
        Returns:
            Raster: Independent copy with duplicated data and metadata
        """
        return Raster(
            data=self._data.copy(),
            transform=copy.deepcopy(self.transform),
            crs=self.crs,  # CRS is immutable, no need to copy
            nodata=self.nodata,
            band_names=self.band_names.copy()
        )

    def __repr__(self) -> str:
        """
        String representation for debugging.
        
        Returns:
            str: Human-readable description of the Raster
        """
        return (
            f"<Raster shape={self.shape} dtype={self._data.dtype} "
            f"crs={self.crs} bounds={self.bounds}>"
        )

    def __eq__(self, other: object) -> bool:
        """
        Check equality based on metadata and pixel data.
        
        Args:
            other: Object to compare with
            
        Returns:
            bool: True if rasters are identical
        """
        if not isinstance(other, Raster):
            return NotImplemented
        
        # Check metadata first (cheap)
        meta_equal = (
            self.transform == other.transform and
            self.crs == other.crs and
            self.nodata == other.nodata and
            self.shape == other.shape
        )
        
        if not meta_equal: # no need to check data if metadata differs
            return False
            
        # Check data only if metadata matches (expensive)
        return np.array_equal(self._data, other._data, equal_nan=True)

    def __array__(self) -> np.ndarray:
        """
        NumPy array interface.
        Allows direct use in NumPy functions:
            
        Returns:
            np.ndarray: The underlying data array
        """
        return self._data