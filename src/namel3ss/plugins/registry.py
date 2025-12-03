"""
Plugin registry.
"""

from __future__ import annotations

from typing import Dict, List

from .models import PluginInfo


class PluginRegistry:
    def __init__(self, plugins: List[PluginInfo] | None = None) -> None:
        self._plugins: Dict[str, PluginInfo] = {}
        for plugin in plugins or []:
            self._plugins[plugin.name] = plugin

    def is_enabled(self, name: str) -> bool:
        plugin = self._plugins.get(name)
        return bool(plugin and plugin.enabled)

    def list_plugins(self) -> List[PluginInfo]:
        return list(self._plugins.values())
