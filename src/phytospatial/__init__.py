# src/phytospatial/__init__.py

import logging

logger = logging.getLogger("phytospatial")
logger.addHandler(logging.NullHandler())# prevents errors if end user doesn't configure logging
