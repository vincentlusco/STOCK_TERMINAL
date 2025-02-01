"""
Bloomberg Lite Application Package
"""

import logging

# Set up logging
logger = logging.getLogger(__name__)
logger.info("Initializing Bloomberg Lite package")

__version__ = "0.1.0"

# Note: We don't import settings here to avoid circular imports 