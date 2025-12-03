"""
Plugin subsystem.
"""

from .models import PluginInfo
from .registry import PluginRegistry

__all__ = ["PluginInfo", "PluginRegistry"]
