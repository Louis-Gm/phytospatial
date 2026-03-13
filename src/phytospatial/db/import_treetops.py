# src/phytospatial/db/import_treetops.py

import logging
from pathlib import Path
from typing import Dict, Union

import geopandas as gpd

from phytospatial.db.client import DB_Client
from phytospatial.vector.layer import Vector

log = logging.getLogger(__name__)

__all__ = [
    "import_treetops"
]

def import_treetops(
    client: DB_Client,
    input_path: Union[str, Path],
    column_mapping: Dict[str, str],
    target_srid: int = 32619
    ) -> int:
    """
    Ingests a spatial vector dataset of master tree locations into the persistent storage layer.

    Args:
        client (DB_Client): An instantiated and fully configured database access client.
        input_path (Union[str, Path]): The absolute or relative system path resolving to the vector file.
        column_mapping (Dict[str, str]): A translation dictionary bridging the native shapefile 
            attributes to the required Phytospatial relational schema columns. Must map attributes 
            to 'tree_id' and 'species'.
        target_srid (int, optional): The Spatial Reference System Identifier enforced on the 
            destination schema. Defaults to 32619.

    Returns:
        int: The aggregate total of successfully committed tree anchor records.

    Raises:
        FileNotFoundError: If the designated input vector path cannot be resolved.

        KeyError: If the underlying spatial dataset lacks the required schema fields 
            after the translation mapping is applied.

        RuntimeError: If vector decoding fails during memory staging or if the 
            subsequent relational transaction is rejected by the database engine.
    """
    input_file = Path(input_path)

    if not input_file.exists():
        log.error(f"Could not find the input file: {input_file}")
        raise FileNotFoundError(f"Input file not found: {input_file}")

    log.info(f"Loading existing treetops from {input_file.name}...")
    try:
        gdf = gpd.read_file(input_file)
    except Exception as e:
        log.error(f"Failed to read input file: {e}")
        raise RuntimeError(f"Failed to read vector data: {e}") from e

    gdf = gdf.rename(columns=column_mapping)

    required_columns = ["tree_id", "species"]
    missing_cols = [col for col in required_columns if col not in gdf.columns]
    
    if missing_cols:
        error_msg = f"Missing required columns after mapping: {missing_cols}."
        log.error(error_msg)
        raise KeyError(error_msg)

    db_gdf = gdf[["tree_id", "species", "geometry"]].copy()
    db_gdf["tree_id"] = db_gdf["tree_id"].astype(str)
    db_gdf["status"] = "Alive"

    if not db_gdf.geometry.has_z.all():
        log.info("Promoting 2D geometries to 3D PointZ...")
        db_gdf.geometry = gpd.GeoSeries.from_wkb(db_gdf.geometry.to_wkb(output_dimension=3))

    db_gdf = db_gdf.rename(columns={"geometry": "geom"})
    db_gdf = db_gdf.set_geometry("geom")

    if db_gdf.crs and db_gdf.crs.to_epsg() != target_srid:
        log.info(f"Reprojecting geometries from {db_gdf.crs.to_epsg()} to EPSG:{target_srid}...")
        db_gdf = db_gdf.to_crs(epsg=target_srid)

    trees_vector = Vector(db_gdf)

    log.info(f"Appending {len(db_gdf)} tree points directly into the database...")
    try:
        inserted_count = client.upload_trees(trees_vector=trees_vector, srid=target_srid)
        log.info(f"Successfully inserted {inserted_count} tree records.")
        return inserted_count
    except Exception as e:
        log.error(f"Database insertion failed: {e}")
        raise RuntimeError(f"Failed to upload records to database: {e}") from e