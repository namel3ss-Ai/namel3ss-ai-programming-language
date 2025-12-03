"""
Plugin registry with discovery, load, unload, and install helpers.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..obs.tracer import Tracer
from .manifest import PluginManifest
from .models import PluginInfo
from .sdk import PluginSDK
from .versioning import CORE_VERSION


@dataclass
class _LoadedPlugin:
    info: PluginInfo
    manifest: PluginManifest


class PluginRegistry:
    def __init__(self, plugins_dir: Path, core_version: str = CORE_VERSION, tracer: Optional[Tracer] = None) -> None:
        self.plugins_dir = plugins_dir
        self.core_version = core_version
        self.tracer = tracer
        self._plugins: Dict[str, _LoadedPlugin] = {}
        self._discovered: Dict[str, PluginInfo] = {}

    def discover(self) -> List[PluginInfo]:
        self._discovered = {}
        if not self.plugins_dir.exists():
            return []
        for child in self.plugins_dir.iterdir():
            manifest_path = child / "plugin.toml"
            if not manifest_path.exists():
                continue
            try:
                manifest = PluginManifest.from_file(manifest_path)
                compatible = manifest.is_compatible_with(self.core_version)
                info = PluginInfo(
                    id=manifest.id,
                    name=manifest.name,
                    description=manifest.description,
                    version=manifest.version,
                    author=manifest.author,
                    compatible=compatible,
                    enabled=True,
                    path=str(child),
                    entrypoints=manifest.entrypoints,
                )
                self._discovered[manifest.id] = info
            except Exception as exc:  # pragma: no cover - invalid plugin path
                err = PluginInfo(
                    id=child.name,
                    name=child.name,
                    description="Invalid manifest",
                    compatible=False,
                    enabled=False,
                    loaded=False,
                    errors=[str(exc)],
                    path=str(child),
                )
                self._discovered[child.name] = err
        return list(self._discovered.values())

    def list_plugins(self) -> List[PluginInfo]:
        if not self._discovered:
            self.discover()
        return list(self._discovered.values())

    def load(self, plugin_id: str, sdk: PluginSDK) -> PluginInfo:
        if not self._discovered:
            self.discover()
        info = self._discovered.get(plugin_id)
        if not info:
            raise ValueError(f"Plugin '{plugin_id}' not found")
        if not info.compatible:
            info.errors.append("Incompatible with core version")
            return info
        if info.loaded:
            return info
        manifest_path = Path(info.path or "") / "plugin.toml"
        manifest = PluginManifest.from_file(manifest_path)
        # add plugin path to sys.path for imports
        plugin_root = Path(info.path or ".")
        sys.path.insert(0, str(plugin_root))
        src_path = plugin_root / "src"
        added_src = False
        if src_path.exists():
            sys.path.insert(0, str(src_path))
            added_src = True
        try:
            contributions: Dict[str, List[str]] = {}
            for group, target in manifest.entrypoints.items():
                module_name, func_name = target.split(":")
                module = importlib.import_module(module_name)
                func = getattr(module, func_name)
                # set default plugin id on sdk before invoking
                sdk.tools.default_plugin_id = plugin_id
                sdk.agents.default_plugin_id = plugin_id
                sdk.flows.default_plugin_id = plugin_id
                sdk.rag.default_plugin_id = plugin_id
                func(sdk)
                contributions.setdefault(group, []).append(target)
            info.loaded = True
            info.contributions = contributions
            self._plugins[plugin_id] = _LoadedPlugin(info=info, manifest=manifest)
            if self.tracer:
                self.tracer.record_flow_event(
                    "plugin.load", {"plugin_id": plugin_id, "version": manifest.version}
                )
        except Exception as exc:
            info.errors.append(str(exc))
            info.loaded = False
        finally:
            if str(plugin_root) in sys.path:
                sys.path.remove(str(plugin_root))
            if added_src and str(src_path) in sys.path:
                sys.path.remove(str(src_path))
        return info

    def unload(self, plugin_id: str, sdk: Optional[PluginSDK] = None) -> None:
        info = self._discovered.get(plugin_id)
        if not info:
            return
        info.loaded = False
        if sdk:
            sdk.tools.unregister_contributions(plugin_id)
            sdk.flows.unregister_contributions(plugin_id)
            sdk.agents.unregister_contributions(plugin_id)
            sdk.rag.unregister_contributions(plugin_id)
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]

    def install_from_path(self, source: Path) -> PluginInfo:
        dest = self.plugins_dir / source.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(source, dest)
        # refresh discovery
        plugins = self.discover()
        for p in plugins:
            if p.id == source.name or p.path == str(dest):
                return p
        raise ValueError("Failed to install plugin")
