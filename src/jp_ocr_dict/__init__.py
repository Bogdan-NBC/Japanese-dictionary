"""
Japanese OCR Pop-up Dictionary
==============================

A high-performance, Yomichan/10ten-inspired desktop OCR overlay dictionary
designed for reading Japanese digital manga, light novels, and games.
"""

__version__ = "2.0.0"
__author__ = "Bogdan-NBC"

import sys
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

try:
    from .api import JishoAPIHandler  # noqa: E402
    from .db_dictionary import SQLiteDictionary  # noqa: E402
    from .settings_manager import SettingsManager, settings  # noqa: E402
except ImportError:
    from api import JishoAPIHandler  # noqa: E402
    from db_dictionary import SQLiteDictionary  # noqa: E402
    from settings_manager import SettingsManager, settings  # noqa: E402

__all__ = [
    "JishoAPIHandler",
    "SQLiteDictionary",
    "SettingsManager",
    "settings",
    "__version__",
]
