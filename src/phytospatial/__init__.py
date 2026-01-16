# src/phytospatial/__init__.py
#
# Copyright (c) The phytospatial project contributors
# This software is distributed under the Apache-2.0 license.
# See the NOTICE file for more information

import logging

logger = logging.getLogger("phytospatial")
logger.addHandler(logging.NullHandler())# prevents errors if end user doesn't configure logging
