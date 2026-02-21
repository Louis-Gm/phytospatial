# src/phytospatial/raster/indices.py
"""
This module defines the SpectralIndex data structure and a registry of common spectral indices.
"""

from dataclasses import dataclass
import logging
from typing import Dict

log = logging.getLogger(__name__)

__all__ = [
    "SpectralIndex",
    "IndexCatalog"
]

@dataclass
class SpectralIndex:
    name: str
    formula: str
    wavelengths: Dict[str, float]

class IndexCatalog:
    def __init__(self):
        self._indices = {
            "NDVI": SpectralIndex("NDVI", "(nir - red) / (nir + red)", {"nir": 850.0, "red": 650.0}),
            "OTHER INDEX": SpectralIndex("OTHER INDEX", "SOME FORMULA", {"BANDNAME1": 700.0, "BANDNAME2": 500.0})
        }
    
    def get(self, name: str) -> SpectralIndex:
        return self._indices[name]
    
    def register(self, index: SpectralIndex):
        self._indices[index.name] = index