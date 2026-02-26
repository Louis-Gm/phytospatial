import argparse
import sys
import logging
import os
from pathlib import Path

def setup_logging(level: int = logging.INFO) -> None:
    """
    Configures the standard logging format and level for the command-line interface.

    Args:
        level (int): The logging threshold level.
    """
    logging.basicConfig(
        level=level, 
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def initialize_database(db_type: str, path: str, reset: bool = False) -> None:
    """
    Orchestrates the provisioning of the spatial database schema based on the user's dialect preference.

    Validates the presence of optional enterprise dependencies, resolves environment variables 
    if a PostgreSQL dialect is selected, and delegates the schema creation to the Data Access Layer.

    Args:
        db_type (str): The requested database dialect ('sqlite' or 'postgres').
        path (str): The designated file path for local SQLite deployments.
        reset (bool): Instructs the engine to delete an existing local database file before initialization.
    """
    try:
        from phytospatial.db import DB_Client
    except ImportError as e:
        logging.error(f"Database dependencies are missing. Run `pip install phytospatial[db]`. Details: {e}")
        sys.exit(1)

    if db_type == "sqlite":
        if reset and Path(path).exists():
            logging.warning(f"Reset flag detected. Removing existing GeoPackage at {path}.")
            os.remove(path)
            
        db_url = f"sqlite:///{path}"
        
    elif db_type == "postgres":
        try:
            from dotenv import load_dotenv, find_dotenv
            env_path = find_dotenv()
            if env_path:
                load_dotenv(env_path)
        except ImportError:
            logging.warning("python-dotenv not installed. Relying strictly on system environment variables.")
            
        db_user = os.getenv("DB_USER")
        db_pass = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME", "phytospatial")
        
        if not all([db_user, db_pass]):
            logging.error("Missing DB_USER or DB_PASSWORD in environment variables. Cannot connect to PostgreSQL.")
            sys.exit(1)
            
        db_url = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        
    else:
        logging.error(f"Unsupported database type: {db_type}")
        sys.exit(1)

    logging.info(f"Targeting database connection: {db_type.upper()}")
    
    try:
        client = DB_Client(connection_string=db_url)
        success = client.initialize_database()
        
        if success:
            logging.info("Database initialization sequence completed successfully.")
        else:
            logging.error("Database initialization encountered an error.")
            sys.exit(1)
            
    except Exception as e:
        logging.error(f"Failed to instantiate DB_Client or deploy schema: {e}")
        sys.exit(1)

def main() -> None:
    """
    Parses command-line arguments and routes execution to the appropriate administrative subroutines.
    """
    parser = argparse.ArgumentParser(
        prog="phytospatial", 
        description="Phytospatial Enterprise Administrative CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    db_parser = subparsers.add_parser(
        "init-db", 
        help="Provisions the target spatial database and deploys the relational schema."
    )
    db_parser.add_argument(
        "--type", 
        choices=["sqlite", "postgres"],
        default="sqlite",
        help="The database dialect to initialize. Defaults to sqlite."
    )
    db_parser.add_argument(
        "--path", 
        type=str,
        default="phytospatial_local.gpkg",
        help="The output file path for the SQLite GeoPackage."
    )
    db_parser.add_argument(
        "--reset", 
        action="store_true", 
        help="Forcefully deletes the existing local database file before recreation."
    )
    
    args = parser.parse_args()
    setup_logging()
    
    if args.command == "init-db":
        initialize_database(db_type=args.type, path=args.path, reset=args.reset)

if __name__ == "__main__":
    main()