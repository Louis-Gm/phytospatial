# src/phytospatial/raster/engine.py

"""
This module manages interactions between other raster modules.

It serves as the core dispatch mechanism for raster processing.
"""

import logging
from pathlib import Path
from typing import Callable, Union, Optional, Any, Dict, Generator, Tuple, Iterable
from enum import Enum

from rasterio.windows import Window

from .layer import Raster
from .io import load
from .resources import ProcessingMode, determine_strategy
from .partition import iter_tiles, iter_blocks, iter_windows, TileStitcher

log = logging.getLogger(__name__)

__all__ = [
    "AggregationType",
    "DispatchConfig",
    "dispatch"
]

class AggregationType(Enum):
    """Strategies for combining results from chunked processing.
    
    Options:
        STITCH: Reassemble processed tiles into a single raster file.
        COLLECT: Return a list of results for each tile (no stitching).
        REDUCE: Accumulate results using a reducer function (e.g. sum, max).
        NONE: Discard individual results (useful for side-effect functions).
    """
    STITCH = "stitch"
    COLLECT = "collect"
    REDUCE = "reduce"
    NONE = "none"

class DispatchConfig:
    """Configuration object for the execution engine.
    
    Args:
        mode: ProcessingMode to enforce ('in_memory', 'tiled', 'blocked', 'auto').
        tile_size: Size of tiles/windows for streaming (in pixels). Default=512.
        overlap: Overlap between tiles/windows (in pixels). Default=0.
        output_path: Optional path to save output raster (required for STITCH).
        aggregation: AggregationType for combining results. Default=STITCH.
        reducer: Optional function for REDUCE aggregation.
    """
    def __init__(
        self,
        mode: Union[ProcessingMode, str] = "auto",
        tile_size: int = 512,
        overlap: int = 0,
        output_path: Optional[Union[str, Path]] = None,
        aggregation: AggregationType = AggregationType.STITCH,
        reducer: Optional[Callable[[Any, Any], Any]] = None
    ):
        self.mode = mode
        self.tile_size = tile_size
        self.overlap = overlap
        self.output_path = Path(output_path) if output_path else None
        self.aggregation = aggregation
        self.reducer = reducer

def _create_iterator(
    source: Union[str, Path, Raster], 
    mode: ProcessingMode, 
    config: DispatchConfig
) -> Generator[Tuple[Window, Raster], None, None]:
    """Helper to create the correct iterator from source and mode.
    
    Args:
        source: Raster source (file path or Raster object).
        mode: ProcessingMode to use.
        config: DispatchConfig with tiling parameters.
        
    Returns:
        Generator yielding (Window, Raster) tuples.
    """
    
    if isinstance(source, Raster):
        return iter_windows(source, tile_size=config.tile_size, overlap=config.overlap)
        
    if mode == ProcessingMode.BLOCKED:
        return iter_blocks(source)
    else:
        return iter_tiles(
            source, 
            tile_size=config.tile_size, 
            overlap=config.overlap
        )

def _synchronize_inputs(
    input_map: Dict[str, Union[str, Path, Raster]],
    mode: ProcessingMode,
    config: DispatchConfig
) -> Generator[Tuple[Window, Dict[str, Raster]], None, None]:
    """
    Helper to synchronize iterators for multiple inputs.
    
    Args:
        input_map: Dictionary mapping argument names to raster sources.
        mode: ProcessingMode to use.
        config: DispatchConfig with tiling parameters.

    Yields:
        Tuple[Window, Dict[arg_name, TileRaster]]
    """
    iterators = {}
    primary_key = next(iter(input_map.keys()))
    
    for name, source in input_map.items():
        iterators[name] = _create_iterator(source, mode, config)

    primary_iter = iterators[primary_key]

    for window, primary_tile in primary_iter:
        current_tiles = {primary_key: primary_tile}
        
        for name, it in iterators.items():
            if name == primary_key: 
                continue
                
            try:
                other_window, other_tile = next(it)
                if other_window != window:
                    raise RuntimeError(
                        f"Grid Mismatch! Input '{name}' is out of sync with '{primary_key}'.\n"
                        f"Expected Window: {window}\n"
                        f"Got Window:      {other_window}\n"
                        "Ensure all input rasters have identical dimensions/transforms."
                    )
                current_tiles[name] = other_tile
                
            except StopIteration:
                raise RuntimeError(f"Input '{name}' ended prematurely during synchronization.")
        
        yield window, current_tiles

def _aggregate_stitch(
    results_gen: Iterable[Tuple[Window, Raster]],
    template_source: Union[str, Path, Raster],
    output_path: Path
) -> Path:
    """
    Helper to handle STITCH aggregation using TileStitcher.

    Args:
        results_gen: Generator yielding (Window, Raster) tuples.
        template_source: Source raster to derive profile from.
        output_path: Path to save the stitched output.
    
    Returns:
        Path to the stitched output raster.
    """
    if isinstance(template_source, (str, Path)):
        import rasterio
        with rasterio.open(template_source) as src:
            profile = src.profile
    else:
        profile = template_source.profile

    with TileStitcher(output_path, profile, tiled=True) as stitcher:
        for window, result_tile in results_gen:
            stitcher.add_tile(window, result_tile)
            
    return output_path

def dispatch(
    func: Callable,
    input_map: Dict[str, Union[str, Path, Raster]],
    static_args: Tuple = (),
    static_kwargs: Dict = None,
    config: DispatchConfig = None
) -> Any:
    """
    Execute a function over raster inputs using the optimal strategy.
    
    Args:
        func: The function to execute. Must accept raster objects as arguments.
        input_map: Dictionary mapping argument names to raster sources.
                   {'raster_a': 'file1.tif', 'raster_b': 'file2.tif'}
        static_args: Positional arguments to pass to func (passed through).
        static_kwargs: Keyword arguments to pass to func (passed through).
        config: Execution configuration (Mode, Tiling, Aggregation).
        
    Returns:
        The result of the processing (Path, List, or Value).
    """
    if not input_map:
        raise ValueError("Cannot dispatch engine without at least one raster input.")
        
    static_kwargs = static_kwargs or {}
    config = config or DispatchConfig()
    
    primary_input = next(iter(input_map.values()))

    if isinstance(primary_input, Raster):
        mode = ProcessingMode.IN_MEMORY
        log.info(f"Engine dispatching {func.__name__} in IN_MEMORY mode (Object Input)")
    else:
        user_mode = config.mode if config.mode != "auto" else "auto"
        report = determine_strategy(Path(primary_input), user_mode=user_mode)
        mode = report.mode

        log.info(f"Engine dispatching {func.__name__} in {mode.value} mode")
        log.debug(f"Strategy Report: {report.reason}")

    if mode == ProcessingMode.IN_MEMORY:
        loaded_inputs = {}
        for name, source in input_map.items():
            loaded_inputs[name] = source if isinstance(source, Raster) else load(source)
        return func(*static_args, **{**static_kwargs, **loaded_inputs})

    else:
        if config.aggregation == AggregationType.STITCH and not config.output_path:
            raise ValueError("AggregationType.STITCH requires 'output_path' in config.")

        def execution_stream():
            # Process tiles/blocks and yield results
            for window, tiles in _synchronize_inputs(input_map, mode, config):
                yield window, func(*static_args, **{**static_kwargs, **tiles})

        if config.aggregation == AggregationType.STITCH:
            return _aggregate_stitch(execution_stream(), primary_input, config.output_path)
        elif config.aggregation == AggregationType.COLLECT:
            return [res for _, res in execution_stream()]
        elif config.aggregation == AggregationType.REDUCE:
            if not config.reducer: raise ValueError("REDUCE requires 'reducer' function.")
            acc = None
            for _, res in execution_stream():
                acc = res if acc is None else config.reducer(acc, res)
            return acc
        else:
            for _ in execution_stream(): pass
            return None