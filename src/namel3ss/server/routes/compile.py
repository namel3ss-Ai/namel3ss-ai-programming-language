"""Compilation/formatting related API routes."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, HTTPException

from ..errors import ParseError
from ..schemas import (
    FmtPreviewRequest,
    FmtPreviewResponse,
    NamingMigrationRequest,
    NamingMigrationResponse,
    NamingMigrationSummary,
    ParseRequest,
)


def build_compile_router(
    parse_source_to_ast: Callable[[str], Any],
    format_source_fn: Callable[[str], str],
    migrate_source_to_naming_standard,
    naming_migration_summary_cls: type[NamingMigrationSummary] = NamingMigrationSummary,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/parse")
    def api_parse(payload: ParseRequest) -> dict[str, Any]:
        try:
            return {"ast": parse_source_to_ast(payload.source)}
        except Exception as exc:  # pragma: no cover - FastAPI handles tracebacks
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/api/fmt/preview", response_model=FmtPreviewResponse)
    def api_fmt_preview(payload: FmtPreviewRequest) -> FmtPreviewResponse:
        if payload.source == "":
            return FmtPreviewResponse(formatted="", changes_made=False)
        try:
            formatted = format_source_fn(payload.source)
        except ParseError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FmtPreviewResponse(formatted=formatted, changes_made=formatted != payload.source)

    @router.post("/api/migrate/naming-standard", response_model=NamingMigrationResponse)
    def api_migrate_naming_standard(payload: NamingMigrationRequest) -> NamingMigrationResponse:
        try:
            migrated, result, summary = migrate_source_to_naming_standard(
                payload.source, apply_name_fixes=payload.fix_names
            )
        except Exception as exc:  # pragma: no cover - FastAPI handles tracebacks
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        renamed = summary.get("names_renamed") or []
        suggested = summary.get("suggested_names") or []
        return NamingMigrationResponse(
            source=migrated,
            changes_summary=naming_migration_summary_cls(
                headers_rewritten=summary.get("headers_rewritten", 0),
                let_rewritten=summary.get("let_rewritten", 0),
                set_rewritten=summary.get("set_rewritten", 0),
                names_renamed=[{"from": entry["from"], "to": entry["to"]} for entry in renamed],
                suggested_names=[{"from": entry["from"], "to": entry["to"]} for entry in suggested],
                changed=summary.get("changed", False),
            ),
        )

    return router


__all__ = ["build_compile_router"]
