# src/phytospatial/db/models.py

import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Float, 
    DateTime, 
    ForeignKey, 
    CheckConstraint, 
    Index
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator, VARCHAR, UserDefinedType

# We need to first define the base declarative class and the JSONVariant type before we can define our models, 
# since they are used as base classes and column types respectively in the subsequent model definitions.
Base = declarative_base()

class NativeGeometry(UserDefinedType):
    """
    A custom SQLAlchemy type for defining spatial columns without external dependencies.
    
    This class bypasses ORM-level geometry serialization, falling back to standard 
    geometry declarations for databases like PostGIS and SpatiaLite. It relies on 
    the database engine to natively parse Extended Well-Known Binary (EWKB) hex strings.
    """

    def __init__(
            self, 
            geometry_type: str = 'GEOMETRY', 
            srid: int = 32619
            ) -> None:
        """
        Initializes the NativeGeometry type.

        Args:
            geometry_type (str): The specific geometry type ('POINT', 'POLYGON', etc.).
            srid (int): The spatial reference identifier.
        """
        self.geometry_type = geometry_type.upper()
        self.srid = srid

    def get_col_spec(
            self, 
            **kw: Any
            ) -> str:
        """
        Generates the column specification for DDL compilation.

        Args:
            **kw (Any): Additional keyword arguments passed by the SQLAlchemy compiler.

        Returns:
            str: The SQL column type definition.
        """
        return f"geometry({self.geometry_type}, {self.srid})"

    def bind_processor(
            self, 
            dialect: Any
            ) -> Any:
        """
        Processes the bound parameter before execution.

        Args:
            dialect (Any): The active database dialect.

        Returns:
            Any: A processor function that returns the value unmodified, relying on 
            native database EWKB hex casting.
        """
        def process(value: Optional[str]) -> Optional[str]:
            return value
        return process

    def result_processor(
            self, 
            dialect: Any, 
            coltype: Any
            ) -> Any:
        """
        Processes the result value retrieved from the database.

        Args:
            dialect (Any): The active database dialect.
            coltype (Any): The column type.

        Returns:
            Any: A processor function that returns the raw WKB/EWKB hex string.
        """
        def process(value: Optional[Any]) -> Optional[Any]:
            return value
        return process
    
class JSONVariant(TypeDecorator):
    """
    Dynamically abstracts JSON column typing to support both PostgreSQL JSONB and SQLite VARCHAR serialization.
    """
    impl = VARCHAR
    cache_ok = True

    def load_dialect_impl(
            self, 
            dialect: Any
            ) -> Any:
        """
        Provisions the appropriate SQL type descriptor based on the active database engine dialect.

        Args:
            dialect (Any): The active SQLAlchemy execution dialect.

        Returns:
            Any: The dialect-specific column type implementation.
        """
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(VARCHAR())

    def process_bind_param(
            self, 
            value: Dict[str, Any], 
            dialect: Any
            ) -> Any:
        """
        Serializes dictionary payloads into dialect-compatible formats during database insertion.

        Args:
            value (Dict[str, Any]): The target dictionary payload.
            dialect (Any): The active SQLAlchemy execution dialect.

        Returns:
            Any: The serialized payload ready for database insertion.
        """
        if value is None:
            return value
        if dialect.name == 'postgresql':
            return value
        import json
        return json.dumps(value)

    def process_result_value(
            self, 
            value: Any, 
            dialect: Any
            ) -> Any:
        """
        Deserializes dialect-specific strings or binaries back into Python dictionaries during retrieval.

        Args:
            value (Any): The raw data retrieved from the database.
            dialect (Any): The active SQLAlchemy execution dialect.

        Returns:
            Dict[str, Any]: The parsed dictionary payload.
        """
        if value is None:
            return None
        if dialect.name == 'postgresql':
            return value
        import json
        return json.loads(value)

class Tree(Base):
    """
    Represents the primary master tree anchor points in the spatial database.

    Attributes:
        objectid (int): Primary key, auto-incrementing integer identifier.
        tree_id (str): Unique, non-nullable string identifier for the tree.
        species (str): Botanical species classification of the tree.
        status (str): Current physiological or management status of the tree.
        geom (NativeGeometry): Custom spatial type for the tree's geometry, spatially indexed.
        created_at (datetime.datetime): Timestamp of record creation, defaults to current UTC time.

    Relationships:
        crowns (list[Crown]): Collection of delineated crown polygons associated with this tree. Cascade deletes orphans.
    """
    __tablename__ = 'trees'
    
    objectid = Column(Integer, primary_key=True, autoincrement=True)
    tree_id = Column(String(255), unique=True, nullable=False)
    species = Column(String(255))
    status = Column(String(20))
    geom = Column(NativeGeometry('POINT', 32619))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    crowns = relationship("Crown", back_populates="tree", cascade="all, delete-orphan")

class LidarAcquisition(Base):
    """
    Registers foundational metadata for raw LiDAR point cloud acquisitions.

    Attributes:
        id (int): Primary key, auto-incrementing integer identifier.
        acquisition_datetime (datetime.datetime): Non-nullable timestamp of when the LiDAR data was acquired.
        sensor_type (str): Specifications or model of the LiDAR sensor used.
        point_density_m2 (float): Average points per square meter captured during the flight.
        number_of_returns (int): Maximum number of returns recorded per pulse.

    Relationships:
        structural_attributes (list[StructuralAttribute]): Collection of structural metrics derived from this LiDAR acquisition.
        crowns (list[Crown]): Collection of crown polygons generated or validated using this LiDAR acquisition.
    """
    __tablename__ = 'lidar_acquisitions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    acquisition_datetime = Column(DateTime(timezone=True), nullable=False)
    sensor_type = Column(String(255))
    point_density_m2 = Column(Float)
    number_of_returns = Column(Integer)

    structural_attributes = relationship("StructuralAttribute", back_populates="lidar_acquisition")
    crowns = relationship("Crown", back_populates="lidar_acquisition")

class ImageAcquisition(Base):
    """
    Registers foundational metadata for multispectral and hyperspectral raster acquisitions.

    Attributes:
        id (int): Primary key, auto-incrementing integer identifier.
        acquisition_datetime (datetime.datetime): Non-nullable timestamp of when the imagery was acquired.
        sensor_type (str): Specifications or model of the imaging sensor used.
        gsd_cm (float): Ground Sample Distance represented in centimeters per pixel.

    Relationships:
        bands (list[ImageBand]): Collection of specific spectral bands recorded during this acquisition. Cascade deletes orphans.
        spectral_attributes (list[SpectralAttribute]): Collection of spectral metrics extracted from this image acquisition.
        crowns (list[Crown]): Collection of crown polygons generated or validated using this image acquisition.
    """
    __tablename__ = 'image_acquisitions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    acquisition_datetime = Column(DateTime(timezone=True), nullable=False)
    sensor_type = Column(String(255))
    gsd_cm = Column(Float)

    bands = relationship("ImageBand", back_populates="image_acquisition", cascade="all, delete-orphan")
    spectral_attributes = relationship("SpectralAttribute", back_populates="image_acquisition")
    crowns = relationship("Crown", back_populates="image_acquisition")

class ImageBand(Base):
    """
    Defines individual spectral bands associated with specific image acquisitions.

    Attributes:
        id (int): Primary key, auto-incrementing integer identifier.
        image_acquisition_id (int): Foreign key linking to the parent ImageAcquisition. Non-nullable, cascades on delete.
        band_index (int): The sequential index or channel number of the band within the raster dataset. Non-nullable.
        wavelength_nm (float): The central wavelength of the band measured in nanometers. Non-nullable.
        band_name (str): The common name or designation of the band.

    Relationships:
        image_acquisition (ImageAcquisition): The parent multispectral or hyperspectral acquisition event.
    """
    __tablename__ = 'image_bands'

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_acquisition_id = Column(Integer, ForeignKey('image_acquisitions.id', ondelete='CASCADE'), nullable=False)
    band_index = Column(Integer, nullable=False)
    wavelength_nm = Column(Float, nullable=False)
    band_name = Column(String(255))

    image_acquisition = relationship("ImageAcquisition", back_populates="bands")

class Crown(Base):
    """
    Represents the delineated polygon boundaries associated with specific tree anchors.

    Attributes:
        objectid (int): Primary key, auto-incrementing integer identifier.
        crown_id (str): Unique, non-nullable string identifier for the crown polygon.
        tree_id (str): Foreign key linking to the parent Tree's tree_id. Non-nullable, cascades on delete.
        crown_category (str): Categorical designation of the crown generation approach ('Manual' or 'Automated'). Non-nullable.
        generation_method (str): Algorithm or methodology used for automated delineation (if applicable).
        source_lidar_id (int): Foreign key linking to the originating LidarAcquisition. Sets to NULL on delete.
        source_image_id (int): Foreign key linking to the originating ImageAcquisition. Sets to NULL on delete.
        geom (NativeGeometry): Custom spatial type for the crown polygon geometry, spatially indexed.
        created_at (datetime.datetime): Timestamp of record creation, defaults to current UTC time.

    Constraints:
        chk_crown_category: Ensures `crown_category` is strictly either 'Manual' or 'Automated'.
        chk_automated_method: Ensures `generation_method` is populated if `crown_category` is 'Automated'.
        chk_source_exists: Ensures that manual crowns do not require a source, but automated or generated crowns must link to at least one LiDAR or image source.

    Relationships:
        tree (Tree): The master tree anchor point associated with this crown boundary.
        lidar_acquisition (LidarAcquisition): The LiDAR dataset used to delineate or inform this crown polygon.
        image_acquisition (ImageAcquisition): The imagery dataset used to delineate or inform this crown polygon.
        spectral_attributes (list[SpectralAttribute]): Associated spectral metrics. Cascade deletes orphans.
        structural_attributes (list[StructuralAttribute]): Associated geometric metrics. Cascade deletes orphans.
    """
    __tablename__ = 'crowns'
    
    objectid = Column(Integer, primary_key=True, autoincrement=True)
    crown_id = Column(String(255), unique=True, nullable=False)
    tree_id = Column(String(255), ForeignKey('trees.tree_id', ondelete='CASCADE'), nullable=False)
    crown_category = Column(String(50), nullable=False)
    generation_method = Column(String(255))
    source_lidar_id = Column(Integer, ForeignKey('lidar_acquisitions.id', ondelete='SET NULL'))
    source_image_id = Column(Integer, ForeignKey('image_acquisitions.id', ondelete='SET NULL'))
    geom = Column(NativeGeometry('POLYGON', 32619))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint(
            "crown_category IN ('Manual', 'Automated')",
            name='chk_crown_category'
        ),
        CheckConstraint(
            "(crown_category = 'Manual') OR (crown_category = 'Automated' AND generation_method IS NOT NULL)",
            name='chk_automated_method'
        ),
        CheckConstraint(
            "(crown_category = 'Manual') OR (source_lidar_id IS NOT NULL OR source_image_id IS NOT NULL)",
            name='chk_source_exists'
        ),
    )
    
    tree = relationship("Tree", back_populates="crowns")
    lidar_acquisition = relationship("LidarAcquisition", back_populates="crowns")
    image_acquisition = relationship("ImageAcquisition", back_populates="crowns")
    spectral_attributes = relationship("SpectralAttribute", back_populates="crown", cascade="all, delete-orphan")
    structural_attributes = relationship("StructuralAttribute", back_populates="crown", cascade="all, delete-orphan")

class SpectralAttribute(Base):
    """
    Stores analytical metrics extracted from raster overlays mapped to specific crowns.

    Attributes:
        objectid (int): Primary key, auto-incrementing integer identifier.
        crown_id (str): Foreign key linking to the mapped Crown. Non-nullable, cascades on delete.
        source_image_id (int): Foreign key linking to the source ImageAcquisition. Sets to NULL on delete.
        metrics (JSONVariant): Flexible JSON payload containing extracted index values and statistics. Non-nullable.
        extracted_at (datetime.datetime): Timestamp marking when the metrics were computed, defaults to current UTC time.

    Indexes:
        ix_spectral_metrics_gin: GIN index deployed on the `metrics` column for rapid JSON querying in PostgreSQL environments.

    Relationships:
        crown (Crown): The spatial crown polygon these metrics correspond to.
        image_acquisition (ImageAcquisition): The raster dataset from which these spectral values were extracted.
    """
    __tablename__ = 'spectral_attributes'

    objectid = Column(Integer, primary_key=True, autoincrement=True)
    crown_id = Column(String(255), ForeignKey('crowns.crown_id', ondelete='CASCADE'), nullable=False)
    source_image_id = Column(Integer, ForeignKey('image_acquisitions.id', ondelete='SET NULL'))
    metrics = Column(JSONVariant, nullable=False)
    extracted_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('ix_spectral_metrics_gin', 'metrics', postgresql_using='gin'),
    )

    crown = relationship("Crown", back_populates="spectral_attributes")
    image_acquisition = relationship("ImageAcquisition", back_populates="spectral_attributes")

class StructuralAttribute(Base):
    """
    Stores geometric and structural metrics extracted from point clouds mapped to specific crowns.

    Attributes:
        objectid (int): Primary key, auto-incrementing integer identifier.
        crown_id (str): Foreign key linking to the mapped Crown. Non-nullable, cascades on delete.
        source_lidar_id (int): Foreign key linking to the source LidarAcquisition. Sets to NULL on delete.
        metrics (JSONVariant): Flexible JSON payload containing computed structural statistics. Non-nullable.
        extracted_at (datetime.datetime): Timestamp marking when the metrics were computed, defaults to current UTC time.

    Indexes:
        ix_structural_metrics_gin: GIN index deployed on the `metrics` column for rapid JSON querying in PostgreSQL environments.

    Relationships:
        crown (Crown): The spatial crown polygon these structural traits correspond to.
        lidar_acquisition (LidarAcquisition): The point cloud dataset from which these physical dimensions were calculated.
    """
    __tablename__ = 'structural_attributes'

    objectid = Column(Integer, primary_key=True, autoincrement=True)
    crown_id = Column(String(255), ForeignKey('crowns.crown_id', ondelete='CASCADE'), nullable=False)
    source_lidar_id = Column(Integer, ForeignKey('lidar_acquisitions.id', ondelete='SET NULL'))
    metrics = Column(JSONVariant, nullable=False)
    extracted_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    __table_args__ = (
        Index('ix_structural_metrics_gin', 'metrics', postgresql_using='gin'),
    )

    crown = relationship("Crown", back_populates="structural_attributes")
    lidar_acquisition = relationship("LidarAcquisition", back_populates="structural_attributes")