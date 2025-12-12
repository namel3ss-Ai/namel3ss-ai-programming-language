"""Plugin-related API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import Principal, Role, get_principal
from ..schemas import PluginInstallRequest, PluginMetadata


def build_plugins_router(
    plugin_registry,
    engine_factory: Callable[[str], Any],
) -> APIRouter:
    """Build the plugins router."""

    router = APIRouter()

    @router.get("/api/plugins")
    def api_plugins(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        manifests = {m.id or m.name: m for m in plugin_registry.list_plugins()}
        plugins: list[PluginMetadata] = []
        for info in plugin_registry.discover():
            manifest = manifests.get(info.id)
            tags = manifest.tags if manifest else []
            plugins.append(
                PluginMetadata(
                    id=info.id,
                    name=info.name,
                    version=info.version,
                    description=info.description,
                    author=info.author,
                    compatible=info.compatible,
                    enabled=info.enabled,
                    loaded=info.loaded,
                    errors=info.errors,
                    path=info.path,
                    entrypoints=info.entrypoints,
                    contributions=info.contributions,
                    tags=tags or [],
                )
            )
        return {"plugins": [p.model_dump() for p in plugins]}

    @router.post("/api/plugins/{plugin_id}/load")
    def api_plugin_load(plugin_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = engine_factory("")
        from ...plugins.sdk import PluginSDK

        sdk = PluginSDK.from_engine(engine)
        info = plugin_registry.load(plugin_id, sdk)
        return {"plugin": info.__dict__}

    @router.post("/api/plugins/{plugin_id}/unload")
    def api_plugin_unload(plugin_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = engine_factory("")
        from ...plugins.sdk import PluginSDK

        sdk = PluginSDK.from_engine(engine)
        plugin_registry.unload(plugin_id, sdk)
        return {"status": "ok"}

    @router.post("/api/plugins/install")
    def api_plugin_install(
        payload: PluginInstallRequest, principal: Principal = Depends(get_principal)
    ) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        path = Path(payload.path)
        info = plugin_registry.install_from_path(path)
        return {"plugin": info.__dict__}

    return router


__all__ = ["build_plugins_router"]
