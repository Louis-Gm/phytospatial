# src/phytospatial/db/client.py

import datetime
import logging
import os
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv
from sqlalchemy import create_engine, insert, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.event import listen
from sqlalchemy.exc import SQLAlchemyError

from phytospatial.vector.layer import Vector
from phytospatial.vector.io import resolve_vector

from phytospatial.db.models import (
    Base, Tree, LidarAcquisition, ImageAcquisition, ImageBand, SpectralAttribute
)
from phytospatial.db.bulk_loader import PolarsLoader

log = logging.getLogger(__name__)

def _load_spatialite(
        dbapi_conn: Any, 
        connection_record: Any
        ) -> None:
    """
    Hooks into the SQLite connection lifecycle to enable and load the mod_spatialite extension.
    
    Args:
        dbapi_conn (Any): The underlying DBAPI connection object provided by SQLAlchemy.
        connection_record (Any): The connection record object associated with the pool.
        
    Raises:
        Exception: Captures and logs errors if the SpatiaLite binary is missing from the system path.
    """
    try:
        dbapi_conn.enable_load_extension(True)
        dbapi_conn.execute('SELECT load_extension("mod_spatialite")')
    except Exception as e:
        log.warning(f"Failed to load SpatiaLite extension. Spatial queries may fail. Error: {e}")

class DB_Client:
    """
    A dialect-agnostic Data Access Layer managing connections, schema deployments, 
    and routing data to high-performance bulk loaders without external ORM spatial dependencies.

    Attributes:
        engine (sqlalchemy.engine.Engine): The active database engine.
        SessionLocal (sqlalchemy.orm.sessionmaker): The session factory for transactions.
    """

    def __init__(
            self, 
            connection_string: str = "sqlite:///phytospatial_local.gpkg"
            ) -> None:
        """
        Initializes the database client and configures spatial extensions if necessary.

        Args:
            connection_string (str): The database connection URI.
        """
        self.engine = create_engine(connection_string, echo=False)
        if connection_string.startswith("sqlite"):
            listen(self.engine, 'connect', _load_spatialite)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    @classmethod
    def from_env(
        cls,
        db_type: str = "postgres",
        env_path: Optional[Union[str, Path]] = None,
        sqlite_path: str = "phytospatial_local.gpkg"
        ) -> "DB_Client":
        """
        Constructs a DB_Client instance using environment variables.

        Args:
            db_type (str): The target database dialect ('postgres' or 'sqlite').
            env_path (Optional[Union[str, Path]]): Filepath to a specific .env file.
            sqlite_path (str): Filepath for local SQLite/GeoPackage databases.

        Returns:
            DB_Client: A fully configured database client instance.

        Raises:
            ValueError: If PostgreSQL credentials are required but missing from the environment.
        """
        if env_path:
            load_dotenv(env_path)

        if db_type == "sqlite":
            return cls(connection_string=f"sqlite:///{sqlite_path}")

        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "phytospatial")

        if not all([db_user, db_pass]):
            raise ValueError("Missing DB_USER or DB_PASSWORD in environment variables. Cannot connect to PostgreSQL.")

        db_url = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        return cls(connection_string=db_url)

    def deploy_schema(self) -> bool:
        """
        Deploys the complete relational schema to the connected database target.
        
        Returns:
            bool: True if the schema deployment was successful, False otherwise.
        """
        try:
            if self.engine.name == 'sqlite':
                with self.engine.connect() as conn:
                    conn.execute("SELECT InitSpatialMetaData(1);")
            Base.metadata.create_all(bind=self.engine)
            log.info(f"Schema successfully deployed to {self.engine.name}.")
            return True
        except SQLAlchemyError as e:
            log.error(f"Failed to initialize database schema: {e}")
            return False

    def fetch_trees(
            self, 
            crs: str = "EPSG:32619"
            ) -> Vector:
        """
        Retrieves all master anchor trees from the database into a unified Vector object.
        
        Args:
            crs (str): The coordinate reference system string to enforce on the output geometry.
            
        Returns:
            Vector: A Phytospatial Vector object encapsulating the retrieved spatial records.
        """
        with self.SessionLocal() as session:
            trees = session.execute(select(Tree.tree_id, Tree.species, Tree.status, Tree.geom)).all()
            
        if not trees:
            return Vector(gpd.GeoDataFrame(columns=["tree_id", "species", "status", "geometry"], crs=crs))
            
        data = [
            {
                "tree_id": t.tree_id,
                "species": t.species,
                "status": t.status,
                "geometry": to_shape(t.geom)
            } for t in trees
        ]
        
        gdf = gpd.GeoDataFrame(data, geometry="geometry", crs=crs)
        return Vector(gdf)

    def register_lidar_acquisition(
        self,
        sensor_type: str,
        acquisition_time: datetime.datetime,
        point_density: Optional[float] = None,
        returns: Optional[int] = None
        ) -> int:
        """
        Persists a new LiDAR acquisition record into the acquisition registry.
        
        Args:
            sensor_type (str): The nomenclature identifier of the sensor.
            acquisition_time (datetime.datetime): The timestamp the data was captured.
            point_density (Optional[float]): Points per square meter metric.
            returns (Optional[int]): Total discrete return capacity of the sensor.
            
        Returns:
            int: The primary key ID of the newly generated LiDAR record.
        """
        with self.SessionLocal() as session:
            acquisition = LidarAcquisition(
                acquisition_datetime=acquisition_time,
                sensor_type=sensor_type,
                point_density_m2=point_density,
                number_of_returns=returns
            )
            session.add(acquisition)
            session.commit()
            return acquisition.id

    def register_image_acquisition(
        self,
        sensor_type: str,
        acquisition_time: datetime.datetime,
        gsd_cm: Optional[float] = None,
        bands: Optional[List[Dict[str, Any]]] = None
        ) -> int:
        """
        Persists a new Image acquisition record, including sequential spectral band specifications.
        
        Args:
            sensor_type (str): The nomenclature identifier of the sensor.
            acquisition_time (datetime.datetime): The timestamp the data was captured.
            gsd_cm (Optional[float]): Ground Sample Distance resolution in centimeters.
            bands (Optional[List[Dict[str, Any]]]): List of dictionaries specifying band metadata parameters.
            
        Returns:
            int: The primary key ID of the newly generated Image record.
        """
        with self.SessionLocal() as session:
            acquisition = ImageAcquisition(
                acquisition_datetime=acquisition_time,
                sensor_type=sensor_type,
                gsd_cm=gsd_cm
            )
            session.add(acquisition)
            session.flush()
            
            if bands:
                band_objects = [
                    ImageBand(
                        image_acquisition_id=acquisition.id,
                        band_index=b.get("band_index"),
                        wavelength_nm=b.get("wavelength_nm"),
                        band_name=b.get("band_name")
                    ) for b in bands
                ]
                session.add_all(band_objects)
            session.commit()
            return acquisition.id

    @resolve_vector
    def upload_trees(
        self,
        trees_input: Union[str, Path, Vector],
        column_mapping: Optional[Dict[str, str]] = None,
        target_srid: int = 32619,
        batch_size: int = 15000
        ) -> int:
        """
        Routes the vector input to the PolarsLoader for high-performance insertion 
        of tree geometries.

        Args:
            trees_input (Union[str, Path, Vector]): The input vector data or filepath.
            column_mapping (Optional[Dict[str, str]]): Schema alignment dictionary.
            target_srid (int): The target spatial reference identifier.
            batch_size (int): Transaction block size for bulk insertions.

        Returns:
            int: The total number of trees successfully inserted.
        """
        with self.SessionLocal() as session:
            loader = PolarsLoader(session)
            return loader.load_trees(
                vector=trees_input,
                column_mapping=column_mapping,
                target_srid=target_srid,
                batch_size=batch_size
            )

    @resolve_vector
    def upload_crowns(
        self,
        crowns_input: Union[str, Path, Vector],
        crown_category: str = "Automated",
        generation_method: Optional[str] = None,
        trees_reference: Optional[Vector] = None,
        lidar_id: Optional[int] = None,
        image_id: Optional[int] = None,
        srid: int = 32619,
        batch_size: int = 5000
        ) -> int:
        """
        Routes the vector input to the PolarsLoader for high-performance insertion 
        of delineated crown polygons.

        Args:
            crowns_input (Union[str, Path, Vector]): The input vector data or filepath.
            crown_category (str): Defines the delineation source.
            generation_method (Optional[str]): Defines the algorithmic generation method.
            trees_reference (Optional[Vector]): A reference Vector of tree points for spatial reconciliation.
            lidar_id (Optional[int]): Source LiDAR record ID.
            image_id (Optional[int]): Source Image record ID.
            srid (int): The target spatial reference identifier.
            batch_size (int): Transaction block size for bulk insertions.

        Returns:
            int: The total number of crowns successfully inserted.
        """
        with self.SessionLocal() as session:
            loader = PolarsLoader(session)
            return loader.load_crowns(
                vector=crowns_input,
                crown_category=crown_category,
                generation_method=generation_method,
                trees_reference=trees_reference,
                lidar_id=lidar_id,
                image_id=image_id,
                target_srid=srid,
                batch_size=batch_size
            )

    def _batch_insert_spectral(
            self, 
            records: List[Dict[str, Any]]
            ) -> None:
        """
        Commits an explicit payload of parsed spectral JSON dicts into the relation persistence layer.
        
        Args:
            records (List[Dict[str, Any]]): Sequential records structured according to ORM metadata requirements.
        """
        if not records:
            return
        with self.SessionLocal() as session:
            session.execute(insert(SpectralAttribute), records)
            session.commit()

    def stream_spectral_extraction(
        self,
        raster_input: Union[str, Path, Any],
        vector_input: Vector,
        image_id: int,
        batch_size: int = 5000,
        **kwargs: Any
        ) -> int:
        """
        Orchestrates an extraction pipeline, routing generated scalar JSON payloads directly into SQL storage.
        
        Args:
            raster_input (Union[str, Path, Any]): Dimensional imagery source targeting metrics compilation.
            vector_input (Vector): Extraction mask topologies dictating operational boundaries.
            image_id (int): Primary key reference pointing backward to a validated catalog acquisition.
            batch_size (int): Numerical constraint dictating maximum pending records prior to transactional commit.
            **kwargs (Any): Auxiliary configuration flags relayed securely to the underlying extraction matrix.
            
        Raises:
            ValueError: If `return_raw` flags are enabled, blocking heavy data arrays from violating JSON bounds.
            
        Returns:
            int: Comprehensive integer representing total rows effectively inserted into the relational schema.
        """
        if kwargs.get("return_raw") is True:
            raise ValueError("Cannot extract raw pixel arrays directly to a relational database JSON payload. Use extract_to_dataframe for raw ML matrices.")

        from phytospatial.extract import extract_features
        results_gen = extract_features(
            raster_input=raster_input,
            vector_input=vector_input,
            return_raw=False,
            **kwargs
        )
        
        total_inserted = 0
        batch_records = []

        for feature in results_gen:
            f_copy = feature.copy()
            crown_id = str(f_copy.pop('crown_id'))
            f_copy.pop('raster_source', None)
            f_copy.pop('species', None)
            
            batch_records.append({
                "crown_id": crown_id,
                "source_image_id": image_id,
                "metrics": f_copy
            })
            
            if len(batch_records) >= batch_size:
                self._batch_insert_spectral(batch_records)
                total_inserted += len(batch_records)
                batch_records.clear()
                
        if batch_records:
            self._batch_insert_spectral(batch_records)
            total_inserted += len(batch_records)
            
        log.info(f"Successfully streamed {total_inserted} records into the database via ORM bulk insert.")
        return total_inserted