# src/phytospatial/raster_layer.py

import logging
from pathlib import Path
from typing import Union, Optional, Dict, Any, Tuple, List, Callable, Iterator

import copy
import psutil
from functools import wraps
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
from rasterio.windows import Window
from rasterio.windows import transform as compute_window_transform

from unfinished.exceptions import RasterError, RasterIOError, RasterValidationError

log = logging.getLogger(__name__)

__all__ = ["Raster", "resolve_raster"]

class Raster:
    """
    The fundamental unit of the phytospatial pipeline.

    A Raster is an in-memory "Envelope" that synchronizes:
    1. The 'Heavy' Data: A NumPy array of pixels.
    2. The 'Light' Context: Geospatial metadata (CRS, Transform).

    Unlike a raw Rasterio dataset, this object holds data in RAM. This allows
    for high-performance chaining of operations without constant disk I/O.
    
    Attributes:
        data (np.ndarray): The pixel array in (Bands, Height, Width) format.
        transform (Affine): The affine transform matrix.
        crs (CRS): The Coordinate Reference System.
        nodata (float | int | None): The value representing missing data.
        band_names (Dict[str, int]): Mapping of semantic names to 1-based band indices.
    """

    def __init__(
        self, 
        data: np.ndarray, 
        transform: Affine, 
        crs: CRS, 
        nodata: Optional[Union[float, int]] = None,
        band_names: Optional[Dict[str, int]] = None
    ):
        """
        Initialize a Raster object.

        Args:
            data: Input array. Must be 2D (Height, Width) or 3D (Bands, Height, Width).
                  2D arrays are automatically promoted to 3D (1, Height, Width).
            transform: Geospatial transform (maps pixels to coordinates).
            crs: Coordinate Reference System.
            nodata: Value indicating no data.
            band_names: Optional mapping of names to band indices ('Red': 1).
        
        Raises:
            RasterValidationError: If dimensions mismatch or types are incorrect.
        """
        self.validate_inputs(data, transform, crs)

        # Enforce 3D structure (Bands, Height, Width)
        if data.ndim == 2:
            data = data[np.newaxis, :, :]
        
        self._data = data
        self.transform = transform
        self.crs = crs
        self.nodata = nodata
        self.band_names = band_names or {}

    def validate_inputs(self, data: np.ndarray, transform: Affine, crs: CRS):
        """Internal validation logic."""
        if not isinstance(data, np.ndarray):
            raise TypeError(f"Data must be numpy.ndarray, got {type(data)}")
        
        if data.ndim not in (2, 3):
            raise RasterValidationError(f"Data must be 2D or 3D, got shape {data.shape}")
        
        if not isinstance(transform, Affine):
            raise TypeError(f"Transform must be rasterio.Affine, got {type(transform)}")

    @staticmethod
    def resolve_envi_path(path: Path) -> Path:
        """
        Helper: Handles ENVI header/binary confusion.
        
        If a user provides 'image.hdr' but the actual data is in 'image' (binary),
        this returns the path to the binary.
        """
        # If path ends in .hdr and the stripped path exists, switch to the binary.
        if path.suffix.lower() == '.hdr':
            binary_path = path.with_suffix('')
            if binary_path.exists():
                log.debug(f"Redirecting {path.name} to binary file {binary_path.name}")
                return binary_path
        return path

    @staticmethod
    def check_memory_safety(path: Union[str, Path], safety_factor: float = 2) -> Tuple[bool, str]:
        """
        Estimates if loading the file at 'path' is safe for available system RAM.

        This method calculates the uncompressed size of the raster (Count * Height * Width * dtype)
        and compares it against currently available memory.

        Args:
            path: Path to the raster file.
            safety_factor: Multiplier for overhead. Python and NumPy require significantly
                           more memory than the raw data size to perform operations.
                           Defaults to 2 (safe for heavy processing).

        Returns:
            Tuple[bool, str]: 
                - bool: True if safe to load, False if dangerous.
                - str: A human-readable message explaining the memory math.
        """
        path = Raster.resolve_envi_path(Path(path))
        
        try:
            # Open in read mode just to check metadata (does not load pixels)
            with rasterio.open(path) as src:
                # Calculate Raw Uncompressed Size (Bands * Height * Width)
                total_pixels = src.count * src.height * src.width
                
                # Get bytes per pixel based on dtype (float32 = 4 bytes, uint8 = 1 byte)
                # NOTE: We assume the first band is representative of all.
                bytes_per_pixel = np.dtype(src.dtypes[0]).itemsize
                
                raw_bytes = total_pixels * bytes_per_pixel
                estimated_ram_usage = raw_bytes * safety_factor
                
                # Check RAM availability
                available_ram = psutil.virtual_memory().available
                
                # Convert to GB for readable messaging
                req_gb = estimated_ram_usage / (1024**3)
                avail_gb = available_ram / (1024**3)

                if estimated_ram_usage > available_ram:
                    msg = (
                        f"Insufficient Memory: File requires ~{req_gb:.2f} GB RAM "
                        f"(Raw: {raw_bytes/(1024**3):.2f} GB * Factor: {safety_factor}), "
                        f"but only {avail_gb:.2f} GB is available."
                    )
                    return False, msg
                else:
                    msg = (
                        f"Memory Check Passed: Requires ~{req_gb:.2f} GB "
                        f"(Available: {avail_gb:.2f} GB)."
                    )
                    return True, msg

        except Exception as e:
            # If we can't check, we default to False/Warning to be safe.
            return False, f"Could not verify memory safety: {e}"

    @classmethod
    def process_smart(
        cls, 
        path: Union[str, Path], 
        func: Callable[['Raster'], Any], 
        safety_factor: float = 2
    ):
        """
        Smart Executor: Automatically chooses between in-memory or tiled processing 
        based on available RAM.
        
        Args:
            path: File path.
            func: A function that takes a single Raster object as input.
        """
        path = cls.resolve_envi_path(Path(path))
        
        # Check Safety
        is_safe, msg = cls.check_memory_safety(path, safety_factor=safety_factor)
        
        if is_safe:
            log.info(f"Memory Safe. Loading full raster: {msg}")
            # Strategy A: Load once, run once
            full_raster = cls.from_file(path, check_memory=False)
            yield func(full_raster)
        else:
            log.warning(f"Memory Unsafe. Switching to tiled stream: {msg}")
            # Strategy B: Stream tiles, run many times
            for window, tile_raster in cls.iter_tiles(path):
                yield func(tile_raster)

    @classmethod
    def from_file(
        cls, 
        path: Union[str, Path], 
        bands: Optional[Union[int, List[int]]] = None,
        driver: str = None,
        window: Optional[Window] = None,
        check_memory: bool = True
    ) -> 'Raster':
        """
        Load a Raster from disk into memory.

        Can load a full image or a specific window (tile).

        Args:
            path: Path to the raster file.
            bands: Specific band index (int) or list of indices to load (1-based).
                   If None, loads all bands.
            driver: Optional GDAL driver name. 
                    If None, lets rasterio auto-detect.
            window: Optional rasterio Window object to load only a specific subset 
                    of the raster.
            check_memory: If True (default), estimates required RAM before loading.
                          Raises MemoryError if the file is too large for the system.
                          Ignored if 'window' is provided (as windows are assumed small).

        Returns:
            Raster: A new Raster instance.
        
        Raises:
            MemoryError: If check_memory is True and the file is too large.
            RasterIOError: If the file cannot be read.
        """
        path = Path(path)
        path = cls.resolve_envi_path(Path(path))

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # We only check memory if we are loading the WHOLE file.
        # If the user asks for a specific window, we assume they know it fits.
        if check_memory and window is None:
            is_safe, msg = cls.check_memory_safety(path)
            if not is_safe:
                log.error(msg)
                raise MemoryError(
                    f"{msg}\n"
                    "Tip: Use Raster.iter_tiles() or Raster.process_smart()"
                )
            else:
                log.debug(msg)

        log.debug(f"Loading Raster from: {path.name}")
        
        try:
            with rasterio.open(path, driver=driver) as src:
                # Handle band selection and windowed reading
                if bands is None:
                    # Read all bands (in window if provided)
                    indexes = src.indexes
                    data = src.read(window=window)
                elif isinstance(bands, int):
                    # Read single band, keep it 3D
                    indexes = [bands]
                    data = src.read([bands], window=window)
                else:
                    # Read specific list
                    indexes = bands
                    data = src.read(bands, window=window)

                # Attempt to extract band names from metadata tags
                band_names = {}
                for i, idx in enumerate(indexes):
                    desc = src.descriptions[idx - 1]
                    if desc:
                        band_names[desc] = i + 1

                # If a window was used, the transform must be updated to reflect the new origin
                if window is not None:
                    current_transform = src.window_transform(window)
                else:
                    current_transform = src.transform

                return cls(
                    data=data,
                    transform=current_transform,
                    crs=src.crs,
                    nodata=src.nodata,
                    band_names=band_names
                )
        except rasterio.RasterioIOError as e:
            raise RasterIOError(f"Failed to read {path}: {e}") from e

    @classmethod
    def iter_tiles(
        cls, 
        path: Union[str, Path], 
        bands: Optional[Union[int, List[int]]] = None
    ) -> Iterator[Tuple[Window, 'Raster']]:
        """
        Generator that yields small Raster objects (tiles) from a large file.
        
        This enables memory-safe processing of hyperspectral or massive images
        by iterating over internal blocks without loading the whole file.
        
        Args:
            path: Path to large raster.
            bands: Optional bands to load.
            
        Yields:
            (Window, Raster): A tuple containing the spatial window definition 
                              and the corresponding Raster object for that tile.
        """
        path = Path(path)
        
        path = cls.resolve_envi_path(path)

        log.debug(f"Streaming tiles from: {path.name}")

        try:
            with rasterio.open(path) as src:
                log.info(f"Streaming tiles from {path.name} ({src.width}x{src.height})")
                
                # Use internal block windows for optimal IO performance 
                # but compromise in processing speed
                for ji, window in src.block_windows(1):
                    # We yield a fully valid Raster object for this specific tile.
                    tile_raster = cls.from_file(path, bands=bands, window=window)
                    yield window, tile_raster
        except Exception as e:
             raise RasterIOError(f"Failed to iterate tiles for {path}: {e}") from e

    def iter_windows(
        self, 
        tile_width: int = 512, 
        tile_height: int = 512,
        overlap: int = 0
    ) -> Iterator[Tuple[Window, 'Raster']]:
        """
        Generates small Raster tiles from this in-memory object by slicing.
        Allows for custom tile sizes and overlaps for efficient processing.

        Args:
            tile_width: Width of each tile in pixels.
            tile_height: Height of each tile in pixels.
            overlap: Amount of pixel overlap between tiles (useful for convolutions).
                     Note: The yielded Window tracks the valid data area.
        
        Yields:
            (Window, Raster): A tuple containing the spatial window definition 
                              and the new Raster object for that specific slice.
        """
        # Iterate over the grid
        # We step by the tile size minus overlap to create the sliding effect
        step_w = tile_width - overlap
        step_h = tile_height - overlap

        for row_off in range(0, self.height, step_h):
            for col_off in range(0, self.width, step_w):
                
                # Calculate actual dimensions (handle edge cases at right/bottom)
                width = min(tile_width, self.width - col_off)
                height = min(tile_height, self.height - row_off)
                
                # Define the window
                window = Window(col_off=col_off, row_off=row_off, width=width, height=height)
                
                # Slice the Data
                # NOTE: Rasterio windows use (col, row), Numpy uses (row, col),
                # but our data format is (Bands, Height, Width)
                window_data = self._data[
                    :, 
                    row_off : row_off + height, 
                    col_off : col_off + width
                ].copy()  # Copy to ensure independence
                
                # We shift the origin (top-left) to the new window location.
                window_transform = compute_window_transform(window, self.transform)
                
                # 3. Create the Child Raster
                tile_raster = Raster(
                    data=window_data,
                    transform=window_transform,
                    crs=self.crs,
                    nodata=self.nodata,
                    band_names=self.band_names
                )
                
                yield window, tile_raster

    # Dynamic metadata properties

    @property
    def data(self) -> np.ndarray:
        """Access the raw pixel data."""
        return self._data

    @data.setter
    def data(self, new_data: np.ndarray):
        """
        Update pixel data.

        Args:
            new_data: New pixel array (2D or 3D). 
            2D arrays are automatically promoted to 3D via the initializer.
        
        Note: We allow the shape to change (crop, transform, etc.), but the user must 
        be aware that they should update self.transform manually if the spatial 
        extent changes.
        """
        if new_data.ndim == 2:
            new_data = new_data[np.newaxis, :, :]
        
        if new_data.ndim != 3:
            raise RasterValidationError(f"New data must be 2D or 3D, got {new_data.ndim}D")
            
        self._data = new_data

    @property
    def width(self) -> int:
        return self._data.shape[2]

    @property
    def height(self) -> int:
        return self._data.shape[1]

    @property
    def count(self) -> int:
        return self._data.shape[0]

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Returns (Bands, Height, Width)."""
        return self._data.shape

    @property
    def bounds(self) -> Tuple[float, float, float, float]:
        """Returns (left, bottom, right, top) in CRS units."""
        return rasterio.transform.array_bounds(self.height, self.width, self.transform)

    @property
    def profile(self) -> Dict[str, Any]:
        """
        Generates a Rasterio-compliant profile based on current state.
        Properties like compression and tiling can be overridden in kwargs by passing
        rasterio profile parameters.
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
            'compress': 'lzw', # Sensible default
            'tiled': True
        }

    def get_band(self, identifier: Union[int, str]) -> np.ndarray:
        """
        Retrieve a specific band by 1-based index or semantic name.
        
        Returns:
            np.ndarray: 2D array of the band.
        """
        if isinstance(identifier, str):
            if identifier not in self.band_names:
                raise KeyError(f"Band name '{identifier}' not found in {list(self.band_names.keys())}")
            idx = self.band_names[identifier]
        else:
            idx = identifier

        if not (1 <= idx <= self.count):
            raise IndexError(f"Band index {idx} out of range (1-{self.count})")
        
        return self._data[idx - 1]

    def save(self, path: Union[str, Path], **kwargs):
        """
        Write the Raster to disk.

        Args:
            path: Output file path.
            **kwargs: Overrides for rasterio profile (e.g. compress='deflate').
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Merge dynamic profile with user overrides
        out_profile = self.profile.copy()
        out_profile.update(kwargs)

        log.info(f"Saving Raster ({self.shape}) to {path}")
        
        try:
            with rasterio.open(path, 'w', **out_profile) as dst:
                dst.write(self._data)
                
                # Write band tags
                if self.band_names:
                    for name, idx in self.band_names.items():
                        # Safety check if index is still valid
                        if idx <= self.count:
                            dst.set_band_description(idx, name)
        except Exception as e:
            raise RasterIOError(f"Failed to save {path}: {e}") from e

    def write_window(self, path: Union[str, Path], window: Window, indexes: Optional[List[int]] = None):
        """
        Writes the current Raster data into a specific window of an EXISTING file on disk.
        
        Useful for stitching processed tiles back into a large mosaic.
        
        Args:
            path: Path to the existing target file (must be opened in read/write mode).
            window: The window in the target file where data should be placed.
            indexes: Specific band indices in the target file to write to.
        """
        if not Path(path).exists():
            raise FileNotFoundError(f"Target file for window write does not exist: {path}")

        try:
            # Open in read/write mode
            with rasterio.open(path, 'r+') as dst:
                if indexes:
                    dst.write(self._data, window=window, indexes=indexes)
                else:
                    # Write all bands
                    dst.write(self._data, window=window)
        except Exception as e:
             raise RasterIOError(f"Failed to write window to {path}: {e}") from e

    def copy(self) -> 'Raster':
        """Returns a deep copy of the Raster."""
        return Raster(
            data=self._data.copy(),
            transform=copy.deepcopy(self.transform),
            crs=copy.deepcopy(self.crs),
            nodata=self.nodata,
            band_names=self.band_names.copy()
        )

    def __repr__(self) -> str:
        """Returns a string representation of the Raster object based on its metadata."""
        return (f"<Raster shape={self.shape} dtype={self._data.dtype} "
                f"crs={self.crs} bounds={self.bounds}>")

    def __eq__(self, other: object) -> bool:
        """Checks equality based on metadata and pixel data."""
        if not isinstance(other, Raster):
            return NotImplemented
        
        # Check metadata first (cheap)
        meta_eq = (
            self.transform == other.transform and
            self.crs == other.crs and
            self.nodata == other.nodata and
            self.shape == other.shape
        )
        if not meta_eq:
            return False
            
        # Check data only if necessary (expensive)
        return np.array_equal(self._data, other.data)

    def __array__(self) -> np.ndarray:
        """Allows np.array(raster_obj) to work directly."""
        return self._data

# Resolve decorator to handle polymorphic inputs

def resolve_raster(func: Callable):
    """
    Decorator: Resolves polymorphic inputs for pipeline functions.

    Ensures that the first argument of the decorated function is always a 
    Raster object, regardless of whether the user passed a file path or 
    an existing Raster object.

    Behavior:
    1. Input is path (str/Path) -> Calls Raster.from_file() (Cold Start).
    2. Input is Raster object -> Passes through (Warm Start).
    3. Input is None -> Passes None (for optional arguments).

    Usage:
        @resolve_raster
        def calculate_something(input_raster: Raster, factor: int):
            # 'input_raster' is now guaranteed to be a Raster instance
            return input_raster.data * factor
    """
    @wraps(func)
    def wrapper(input_obj: Union[str, Path, Raster, None], *args, **kwargs):
        if input_obj is None:
            return func(None, *args, **kwargs)

        raster = None

        # Resolve input raster as either path or Raster object
        if isinstance(input_obj, (str, Path)):
            try:
                # NOTE: We let from_file handle memory checks internally.
                # If a user wants to bypass, they should call from_file directly
                # rather than relying on the decorator.
                raster = Raster.from_file(input_obj)
            except Exception as e:
                log.error(f"Auto-loading failed for {input_obj}")
                raise e
        elif isinstance(input_obj, Raster):
            raster = input_obj
        else:
            raise TypeError(
                f"Function {func.__name__} expects a file path or Raster object, "
                f"got {type(input_obj).__name__}"
            )

        # If we made it here, we have a valid Raster and we call the function
        try:
            return func(raster, *args, **kwargs)
        except Exception as e:
            # Provide context on which function failed
            log.error(f"Pipeline error in {func.__name__}: {e}")
            raise

    return wrapper