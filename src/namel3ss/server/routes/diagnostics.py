"""Diagnostics, bundling, and provider status/meta routes."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException

from ..deps import API_KEY_HEADER, Principal, Role, get_principal
from ..schemas import BundleRequest, DiagnosticsRequest


def build_diagnostics_router(
    parse_source_to_ir: Callable[[str], Any],
    collect_diagnostics_fn: Callable[..., Any],
    collect_lint_fn: Callable[..., Any],
    iter_ai_files_fn: Callable[..., Any],
    lint_config_loader: Callable[[Any], Any],
    bundler_factory: Callable[[], Any],
    make_server_bundle_fn: Callable[[Any], Any],
    make_worker_bundle_fn: Callable[[Any], Any],
    load_config_fn: Callable[[], Any],
    providers_config_cls,
    model_registry_cls,
    project_root: Callable[[], Any],
    engine_factory: Callable[[str], Any],
) -> APIRouter:
    """Build diagnostics/bundle/provider/meta router."""

    router = APIRouter()

    @router.post("/api/diagnostics")
    def api_diagnostics(payload: DiagnosticsRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            paths = [project_root() / p for p in payload.paths]
            ai_files = iter_ai_files_fn(paths)
            diags, summary = collect_diagnostics_fn(ai_files, payload.strict)
            lint_results: list[dict[str, Any]] = []
            if payload.lint:
                lint_results = [d.to_dict() for d in collect_lint_fn(ai_files, config=lint_config_loader(project_root()))]
            success = summary["errors"] == 0
            return {
                "success": success,
                "diagnostics": [] if payload.summary_only else [d.to_dict() for d in diags],
                "lint": [] if payload.summary_only else lint_results,
                "summary": summary,
            }
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/bundle")
    def api_bundle(payload: BundleRequest, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        try:
            ir_program = parse_source_to_ir(payload.code)
            bundler = bundler_factory()
            bundle = bundler.from_ir(ir_program)
            target = (payload.target or "server").lower()
            if target == "worker":
                return {"bundle": make_worker_bundle_fn(bundle)}
            return {"bundle": make_server_bundle_fn(bundle)}
        except Exception as exc:  # pragma: no cover - defensive
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/api/providers/status")
    def api_providers_status(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        cfg = load_config_fn()
        providers_cfg = cfg.providers_config or providers_config_cls()
        providers: list[dict[str, Any]] = []
        for name, pcfg in (providers_cfg.providers or {}).items():
            env_key = pcfg.api_key_env
            resolved = pcfg.api_key or (env_key and os.environ.get(env_key))
            if not resolved and pcfg.type == "openai":
                resolved = os.environ.get("N3_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
            if not resolved and pcfg.type == "gemini":
                resolved = os.environ.get("N3_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
            if not resolved and pcfg.type == "anthropic":
                resolved = os.environ.get("N3_ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
            has_key = bool(resolved)
            status = model_registry_cls.last_status.get(name, "ok" if has_key else "missing_key")
            providers.append(
                {
                    "name": name,
                    "type": pcfg.type,
                    "has_key": has_key,
                    "last_check_status": status,
                }
            )
        return {"default": providers_cfg.default, "providers": providers}

    @router.get("/api/meta")
    def api_meta(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        engine = engine_factory("")
        return {
            "ai": {
                "models": list(engine.registry.models.keys()),
                "providers": list(engine.registry.providers.keys()),
                "config": engine.router.config.__dict__,
            },
            "plugins": [
                {"name": p.name, "enabled": p.enabled, "description": p.description}
                for p in engine.plugin_registry.list_plugins()
            ],
            "security": {
                "roles": [r.value for r in Role],
                "auth": f"{API_KEY_HEADER} header required",
            },
        }

    return router


__all__ = ["build_diagnostics_router"]
