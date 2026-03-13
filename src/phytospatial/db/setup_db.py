# src/phytospatial/db/setup_db.py

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union

from sqlalchemy import text

log = logging.getLogger(__name__)

__all__ = [
    "initialize_database"
]

def initialize_database(
    db_type: str, 
    path: Optional[str] = None, 
    reset: bool = False,
    env_path: Optional[Union[str, Path]] = None
) -> None:
    """
    Orchestrates the provisioning of the spatial database schema based on the dialect preference.

    Args:
        db_type (str): The requested database dialect ('sqlite' or 'postgres').
        path (Optional[str]): Optional file path for local SQLite deployments. Defaults to 'phytospatial_local.gpkg'.
        reset (bool): Instructs the engine to delete an existing local database file or drop all tables.
        env_path (Optional[Union[str, Path]]): Filepath to a .env configuration file containing database credentials.

    Raises:
        SystemExit: If database dependencies are missing or the schema deployment fails.
    """
    try:
        from phytospatial.db.client import DB_Client
        from phytospatial.db.models import Base
    except ImportError as e:
        log.error(f"Database dependencies are missing. Run `pip install phytospatial[db]`. Details: {e}")
        sys.exit(1)

    sqlite_path = path or "phytospatial_local.gpkg"
    
    if reset and db_type == "sqlite" and Path(sqlite_path).exists():
        log.warning(f"Reset flag detected. Removing existing GeoPackage at {sqlite_path}.")
        os.remove(sqlite_path)

    log.info(f"Targeting database connection: {db_type.upper()}")

    try:
        client = DB_Client.from_env(db_type=db_type, env_path=env_path, sqlite_path=sqlite_path)
        
        if reset and db_type == "postgres":
            log.warning("Reset flag detected for PostgreSQL. Dropping all existing tables with CASCADE.")
            with client.engine.begin() as conn:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(text(f"DROP TABLE IF EXISTS {table.name} CASCADE"))
                    
        success = client.deploy_schema()
        
        if success:
            log.info("Database initialization sequence completed successfully.")
        else:
            log.error("Database initialization encountered an error.")
            sys.exit(1)
            
    except Exception as e:
        log.error(f"Failed to instantiate DB_Client or deploy schema: {e}")
        sys.exit(1)