"""
Plugin subsystem.
"""

from .models import PluginInfo
from .registry import PluginRegistry
from .versioning import CORE_VERSION

__all__ = ["PluginInfo", "PluginRegistry", "CORE_VERSION"]
