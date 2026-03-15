# src/phytospatial/db/bulk_loader.py

import logging
from typing import Dict, Union

import polars as pl
import shapely
from sqlalchemy.orm import Session
from sqlalchemy import insert

from phytospatial.vector.layer import Vector
from phytospatial.vector.geom import to_crs, force_Z
from phytospatial.vector.spatial_operations import prepare_treetop_vectors

from phytospatial.db.models import Tree, Crown

log = logging.getLogger(__name__)

class PolarsLoader:
    """
    An optimized loader which usese Polars and Shapely's C-API to generate 
    native database Extended Well Known Binary (EWKB) hex strings for bulk insertions.

    Attributes:
        session (Session): An active SQLAlchemy database session.
    """
    def __init__(
            self, 
            session: Session
            ) -> None:
        """
        Initializes the PolarsLoader with an active database session.

        Args:
            session (Session): The active SQLAlchemy session to execute bulk operations.
        """
        self.session = session

    def load_trees(
        self,
        vector: Vector,
        column_mapping: Union[Dict[str, str], None] = None,
        target_srid: int = 32619,
        batch_size: int = 15000
        ) -> int:
        """
        Transforms and loads tree point geometries into the relational database.

        Args:
            vector (Vector): The input Vector object containing tree features.
            column_mapping (Union[Dict[str, str], None]): Optional schema mapping dictionary.
            target_srid (int): The target spatial reference system identifier.
            batch_size (int): The number of records to commit per transaction block.

        Returns:
            int: The total number of tree records successfully inserted.
        """
        prepared_vector = prepare_treetop_vectors(
            vector=vector,
            column_mapping=column_mapping
        )

        if prepared_vector.crs and prepared_vector.crs.to_epsg() != target_srid:
            prepared_vector = to_crs(
                vector=prepared_vector,
                target_crs=f"EPSG:{target_srid}",
                inplace=True
            )

        prepared_vector = force_Z(
            vector=prepared_vector,
            dimensionality=3,
            inplace=True
        )

        gdf = prepared_vector.data
        if gdf.empty:
            return 0

        geoms_with_srid = shapely.set_srid(gdf.geometry.values, target_srid)
        ewkb_hex = shapely.to_wkb(geoms_with_srid, hex=True, include_srid=True)

        df = pl.DataFrame({
            "tree_id": gdf["tree_id"].astype(str).values,
            "species": gdf["species"].values,
            "status": gdf.get("status", "Alive").values,
            "geom": ewkb_hex
        })

        records = df.to_dicts()
        total_inserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.session.execute(insert(Tree), batch)
            self.session.commit()
            total_inserted += len(batch)

        return total_inserted

    def load_crowns(
        self,
        vector: Vector,
        crown_category: str = "Automated",
        generation_method: Union[str, None] = None,
        lidar_id: Union[int, None] = None,
        image_id: Union[int, None] = None,
        target_srid: int = 32619,
        batch_size: int = 15000
        ) -> int:
        """
        Transforms and loads tree crown polygons into the relational database.

        Args:
            vector (Vector): The input Vector object containing crown polygon features.
            crown_category (str): Classification of the crown generation.
            generation_method (Union[str, None]): The algorithm used if category is 'Automated'.
            lidar_id (Union[int, None]): Foreign key referencing the source LiDAR acquisition.
            image_id (Union[int, None]): Foreign key referencing the source Image acquisition.
            target_srid (int): The target spatial reference system identifier.
            batch_size (int): The number of records to commit per transaction block.

        Returns:
            int: The total number of crown records successfully inserted.

        Raises:
            ValueError: If an invalid category or missing method configuration is provided.
        """
        if vector.data.empty:
            return 0

        if crown_category not in ("Manual", "Automated"):
            raise ValueError(f"Invalid crown_category: {crown_category}. Must be 'Manual' or 'Automated'.")

        if crown_category == "Automated" and not generation_method:
            raise ValueError("generation_method must be provided when crown_category is 'Automated'.")

        if "tree_id" not in vector.data.columns:
            raise KeyError("Vector payload must contain a 'tree_id' mapping prior to reaching the bulk loader.")

        vector.data["tree_id"] = vector.data["tree_id"].astype(str)
        prefix = crown_category[:3].upper()
        vector.data["crown_id"] = vector.data["tree_id"] + f"_{prefix}"
        
        is_polygon = vector.data.geometry.geom_type == 'Polygon'
        if not is_polygon.all():
            dropped_gdf = vector.data[~is_polygon]
            for _, row in dropped_gdf.iterrows():
                log.warning(
                    f"Dropping crown_id '{row['crown_id']}' (tree_id: '{row['tree_id']}'). "
                    f"Expected 'Polygon', found '{row.geometry.geom_type}'."
                )
            vector.data = vector.data[is_polygon].copy()

        if vector.data.empty:
            return 0

        flat_vector = force_Z(
            vector=vector,
            dimensionality=2,
            inplace=False
        )
        
        gdf = flat_vector.data
        
        geoms_with_srid = shapely.set_srid(gdf.geometry.values, target_srid)
        ewkb_hex = shapely.to_wkb(geoms_with_srid, hex=True, include_srid=True)
        
        df = pl.DataFrame({
            "crown_id": gdf["crown_id"].values,
            "tree_id": gdf["tree_id"].values,
            "geom": ewkb_hex
        })
        
        df = df.with_columns([
            pl.lit(crown_category).alias("crown_category"),
            pl.lit(generation_method).alias("generation_method"),
            pl.lit(lidar_id).alias("source_lidar_id"),
            pl.lit(image_id).alias("source_image_id")
        ])

        records = df.to_dicts()
        total_inserted = 0

        for i in range(0, len(records), batch_size):
            batch = records[i:i + batch_size]
            self.session.execute(insert(Crown), batch)
            self.session.commit()
            total_inserted += len(batch)

        return total_inserted