"""
Plugin registry and discovery.
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .manifest import ManifestError, PluginManifest, load_manifest
from .models import PluginInfo
from .versioning import is_compatible, CORE_VERSION


class PluginRegistry:
    def __init__(
        self,
        plugins_dir: Optional[Path] = None,
        builtins_dir: Optional[Path] = None,
        user_dir: Optional[Path] = None,
        core_version: Optional[str] = None,
        tracer: Any = None,
    ) -> None:
        # Support legacy single-argument constructor where the first argument is the user plugins directory.
        self.user_dir = user_dir or plugins_dir or Path("plugins")
        default_builtin = Path(__file__).resolve().parents[3] / "plugins"
        self.builtins_dir = builtins_dir or (default_builtin if default_builtin.exists() else Path(__file__).parent / "builtin")
        self.core_version = core_version or CORE_VERSION
        self.tracer = tracer
        self._manifests: dict[str, PluginManifest] = {}
        self._paths: dict[str, Path] = {}
        self._discover()

    def _register_manifest(self, manifest: PluginManifest, manifest_path: Path) -> None:
        plugin_id = manifest.id or manifest.name
        manifest.extra = manifest.extra or {}
        manifest.extra.setdefault("manifest_path", str(manifest_path))
        if manifest.entry_point and not manifest.entrypoints:
            manifest.entrypoints = {"main": manifest.entry_point}
        self._manifests[plugin_id] = manifest
        self._paths[plugin_id] = manifest_path.parent

    def _discover_dir(self, directory: Path) -> None:
        if not directory.exists():
            return
        for manifest_path in directory.rglob("plugin.toml"):
            try:
                manifest = PluginManifest.from_file(manifest_path)
            except Exception:
                continue
            self._register_manifest(manifest, manifest_path)
        for manifest_path in directory.rglob("plugin.json"):
            try:
                manifest = load_manifest(manifest_path)
            except ManifestError:
                continue
            self._register_manifest(manifest, manifest_path)

    def _discover(self) -> None:
        self._manifests.clear()
        self._paths.clear()
        self._discover_dir(self.builtins_dir)
        if self.user_dir != self.builtins_dir:
            self._discover_dir(self.user_dir)

    def _ensure_discovered(self) -> None:
        if not self._manifests:
            self._discover()

    def list_plugins(self) -> List[PluginManifest]:
        self._ensure_discovered()
        return list(self._manifests.values())

    def discover(self) -> List[PluginInfo]:
        self._discover()
        infos: List[PluginInfo] = []
        for plugin_id, manifest in self._manifests.items():
            entrypoints = manifest.entrypoints or ({"main": manifest.entry_point} if manifest.entry_point else {})
            compatible = True
            if manifest.n3_core_version:
                compatible = is_compatible(self.core_version, manifest.n3_core_version)
            info = PluginInfo(
                id=plugin_id,
                name=manifest.name,
                description=manifest.description,
                version=manifest.version,
                author=manifest.author,
                compatible=compatible,
                enabled=getattr(manifest, "enabled", True),
                loaded=False,
                path=str(self._paths.get(plugin_id, "")),
                entrypoints=entrypoints,
                contributions={},
            )
            infos.append(info)
        return infos

    def get_plugin(self, name: str) -> Optional[PluginManifest]:
        self._ensure_discovered()
        return self._manifests.get(name)

    def _call_entrypoint(self, plugin_id: str, target: str, sdk: Any) -> None:
        plugin_path = self._paths.get(plugin_id)
        if plugin_path:
            candidate_paths = [plugin_path / "src", plugin_path]
            for candidate in candidate_paths:
                if candidate.exists() and str(candidate) not in sys.path:
                    sys.path.insert(0, str(candidate))
        module_path, func_name = target.rsplit(":", 1)
        module = importlib.import_module(module_path)
        func = getattr(module, func_name)
        func(sdk)

    def load(self, plugin_id: str, sdk: Optional[Any] = None) -> PluginInfo:
        self._ensure_discovered()
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            raise ValueError(f"Unknown plugin '{plugin_id}'")
        info_list = [p for p in self.discover() if p.id == plugin_id]
        info = info_list[0] if info_list else PluginInfo(id=plugin_id, name=manifest.name, description=manifest.description, version=manifest.version, author=manifest.author, compatible=True, enabled=True, loaded=False, path=str(self._paths.get(plugin_id, "")), entrypoints=manifest.entrypoints, contributions={})
        entrypoints = manifest.entrypoints or ({"main": manifest.entry_point} if manifest.entry_point else {})
        if entrypoints:
            if sdk is None:
                raise ValueError("Plugin SDK is required to load plugin entrypoints")
            for target in entrypoints.values():
                self._call_entrypoint(plugin_id, target, sdk)
        elif manifest.entry_point:
            # Fallback for simple entry point modules that do not use the SDK.
            module_path, _ = manifest.entry_point.rsplit(":", 1)
            importlib.import_module(module_path)
        info.loaded = True
        if sdk:
            contributions: Dict[str, List[str]] = {}
            for key, attr in [
                ("tools", "tools"),
                ("agents", "agents"),
                ("flows", "flows"),
                ("rag", "rag"),
            ]:
                section = getattr(sdk, attr, None)
                if section and getattr(section, "contributions", None):
                    contrib = section.contributions.get(plugin_id, [])
                    if contrib:
                        contributions[key] = contrib
            info.contributions = contributions
        return info

    def unload(self, plugin_id: str, sdk: Optional[Any] = None) -> None:
        if sdk:
            for section in ["tools", "agents", "flows", "rag"]:
                part = getattr(sdk, section, None)
                if part and hasattr(part, "unregister_contributions"):
                    part.unregister_contributions(plugin_id)

    def install_from_path(self, path: Path) -> PluginInfo:
        target_dir = path
        if path.is_file():
            target_dir = path.parent
        manifest_path = None
        for candidate in ["plugin.toml", "plugin.json"]:
            candidate_path = target_dir / candidate
            if candidate_path.exists():
                manifest_path = candidate_path
                break
        if manifest_path is None:
            raise ValueError(f"No plugin manifest found in {path}")
        manifest = PluginManifest.from_file(manifest_path)
        plugin_id = manifest.id or manifest.name
        destination = self.user_dir / target_dir.name
        if not destination.exists():
            shutil.copytree(target_dir, destination)
        self._register_manifest(manifest, manifest_path)
        info_list = self.discover()
        for info in info_list:
            if info.id == plugin_id:
                return info
        return PluginInfo(
            id=plugin_id,
            name=manifest.name,
            description=manifest.description,
            version=manifest.version,
            author=manifest.author,
            compatible=True,
            enabled=True,
            loaded=False,
            path=str(destination),
            entrypoints=manifest.entrypoints,
            contributions={},
        )
