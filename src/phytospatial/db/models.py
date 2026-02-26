import datetime
from typing import Any, Dict

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import TypeDecorator, VARCHAR
from geoalchemy2 import Geometry

Base = declarative_base()

class JSONVariant(TypeDecorator):
    """
    Dynamically abstracts JSON column typing to support both PostgreSQL JSONB and SQLite VARCHAR serialization.
    """
    impl = VARCHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
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

    def process_bind_param(self, value: Dict[str, Any], dialect: Any) -> Any:
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

    def process_result_value(self, value: Any, dialect: Any) -> Dict[str, Any]:
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
    """
    __tablename__ = 'trees'

    objectid = Column(Integer, primary_key=True, autoincrement=True)
    tree_id = Column(String(255), unique=True, nullable=False)
    species = Column(String(255))
    status = Column(String(50))
    geom = Column(Geometry('POINT', spatial_index=True, management=True))
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    crowns = relationship("Crown", back_populates="tree", cascade="all, delete-orphan")

class LidarAcquisition(Base):
    """
    Registers foundational metadata for raw LiDAR point cloud acquisitions.
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
    """
    __tablename__ = 'crowns'

    objectid = Column(Integer, primary_key=True, autoincrement=True)
    crown_id = Column(String(255), unique=True, nullable=False)
    tree_id = Column(String(255), ForeignKey('trees.tree_id', ondelete='CASCADE'), nullable=False)
    crown_category = Column(String(50), nullable=False)
    generation_method = Column(String(255))
    source_lidar_id = Column(Integer, ForeignKey('lidar_acquisitions.id', ondelete='SET NULL'))
    source_image_id = Column(Integer, ForeignKey('image_acquisitions.id', ondelete='SET NULL'))
    geom = Column(Geometry('POLYGON', spatial_index=True, management=True))
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