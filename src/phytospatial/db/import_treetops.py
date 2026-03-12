import os
import sys
import logging
from pathlib import Path

import geopandas as gpd
from dotenv import load_dotenv, find_dotenv

from phytospatial.db.client import DB_Client
from phytospatial.vector.layer import Vector

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def get_database_url() -> str:
    """
    Resolves the target database connection string from system environment variables.

    Returns:
        str: A fully qualified SQLAlchemy connection URL.
    """
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "phytospatial")
    
    if db_user and db_pass:
        return f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    return "sqlite:///phytospatial_local.sqlite"

def main(crowns: Path) -> None:
    """
    Executes the primary tree ingestion pipeline.

    Raises:
        SystemExit: If the input file cannot be located, if mandatory schema columns 
            are missing post-mapping, or if the database ingestion transaction fails.
    """
    INPUT_FILE = crowns
    
    COLUMN_MAPPING = {
        "OBJECTID_F": "tree_id",
        "Species": "species"
    }

    env_path = find_dotenv()
    if env_path:
        load_dotenv(env_path)

    db_url = get_database_url()
    client = DB_Client(connection_string=db_url)

    if not INPUT_FILE.exists():
        log.error(f"Could not find the input file: {INPUT_FILE}")
        sys.exit(1)

    log.info(f"Loading existing treetops from {INPUT_FILE.name}...")
    try:
        gdf = gpd.read_file(INPUT_FILE)
    except Exception as e:
        log.error(f"Failed to read input file: {e}")
        sys.exit(1)

    gdf = gdf.rename(columns=COLUMN_MAPPING)

    missing_cols = [col for col in ["tree_id", "species"] if col not in gdf.columns]
    if missing_cols:
        log.error(f"Missing required columns after mapping: {missing_cols}. Please check COLUMN_MAPPING.")
        sys.exit(1)

    db_gdf = gdf[["tree_id", "species", "geometry"]].copy()
    db_gdf["tree_id"] = db_gdf["tree_id"].astype(str)
    db_gdf["status"] = "Alive"
    
    if not db_gdf.geometry.has_z.all():
        log.info("Promoting 2D geometries to 3D PointZ...")
        db_gdf.geometry = gpd.GeoSeries.from_wkb(db_gdf.geometry.to_wkb(output_dimension=3))

    db_gdf = db_gdf.rename(columns={"geometry": "geom"})
    db_gdf = db_gdf.set_geometry("geom")

    target_srid = int(os.getenv("PROJECT_SRID", "32619"))
    if db_gdf.crs and db_gdf.crs.to_epsg() != target_srid:
        log.info(f"Reprojecting geometries from {db_gdf.crs.to_epsg()} to EPSG:{target_srid}...")
        db_gdf = db_gdf.to_crs(epsg=target_srid)

    trees_vector = Vector(db_gdf)

    log.info(f"Appending {len(db_gdf)} tree points directly into the database...")
    try:
        inserted_count = client.upload_trees(trees_vector=trees_vector, srid=target_srid)
        log.info(f"✓ Success! {inserted_count} master trees are now locked into the database.")
    except Exception as e:
        log.error(f"Database insertion failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()