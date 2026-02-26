"""
Initializes the database sub-package and validates the presence of optional ORM dependencies.
"""

from typing import Tuple

def _check_db_dependencies() -> Tuple[bool, str]:
    """
    Evaluates the current Python environment for required database ORM packages.

    Returns:
        Tuple[bool, str]: A boolean indicating whether the core ORM packages are accessible, 
            accompanied by an appropriate error message if validation fails.
    """
    try:
        import sqlalchemy
        import geoalchemy2 
        # Note: psycopg is intentionally excluded here. It will be imported dynamically 
        # by SQLAlchemy only if the user specifies a postgresql:// connection string.
        return True, ""
    except ImportError as e:
        missing_module = str(e).split("'")[1] if "'" in str(e) else str(e)
        return False, (
            f"Phytospatial database features require optional dependencies. "
            f"Missing module: {missing_module}. "
            f"Please install via: pip install phytospatial[db]"
        )

_has_deps, _dep_error = _check_db_dependencies()

if not _has_deps:
    class MissingDependencyDummy:
        """
        Acts as a fail-safe placeholder class for environments lacking database dependencies.
        """
        def __init__(self, *args, **kwargs):
            """
            Intercepts instantiation attempts and raises an informative error.
            """
            raise ImportError(_dep_error)

    DB_Client = MissingDependencyDummy

else:
    from .client import DB_Client


__all__ = [
    "DB_Client"
]