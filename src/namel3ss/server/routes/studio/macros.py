from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException

from ...deps import Principal, Role, get_principal
from .... import lexer, parser
from ....macros import MacroExpander, MacroExpansionRecord, default_macro_ai_callback


def register_macro_routes(
    router: APIRouter,
    *,
    project_root: Callable[[], Path],
    iter_ai_files_fn: Callable[[Path], list[Path]],
) -> None:
    """Register macro inspection routes."""

    def _macro_id(record: MacroExpansionRecord, idx: int) -> str:
        path_label = Path(record.source_path).name if record.source_path else "unknown"
        line = record.span.line if record.span else 0
        col = record.span.column if record.span else 0
        return f"{record.macro_name}:{path_label}:{line}:{col}:{idx}"

    def _collect_macro_invocations() -> list[tuple[str, MacroExpansionRecord]]:
        invocations: list[tuple[str, MacroExpansionRecord]] = []
        base = project_root()
        for path in iter_ai_files_fn(base):
            try:
                source = path.read_text(encoding="utf-8")
                tokens = lexer.Lexer(source, filename=str(path)).tokenize()
                module = parser.Parser(tokens).parse_module()
                expander = MacroExpander(default_macro_ai_callback, capture_expansions=True)
                expander.expand_module(module, source_path=str(path))
                for rec in expander.expansion_records:
                    invocations.append((_macro_id(rec, len(invocations)), rec))
            except Exception:
                continue
        return invocations

    @router.get("/api/studio/macros")
    def api_studio_macros(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        invocations = _collect_macro_invocations()
        macros = []
        for macro_id, rec in invocations:
            counts = {k: len(v) for k, v in rec.artifacts.items()}
            macros.append(
                {
                    "id": macro_id,
                    "name": rec.macro_name,
                    "source": rec.source_path,
                    "line": rec.span.line if rec.span else None,
                    "column": rec.span.column if rec.span else None,
                    "artifact_counts": counts,
                }
            )
        return {"macros": macros}

    @router.get("/api/studio/macros/{macro_id}")
    def api_studio_macro_detail(macro_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if principal.role not in {Role.ADMIN, Role.DEVELOPER, Role.VIEWER}:
            raise HTTPException(status_code=403, detail="Forbidden")
        invocations = _collect_macro_invocations()
        match = next(((mid, rec) for mid, rec in invocations if mid == macro_id), None)
        if not match:
            raise HTTPException(status_code=404, detail="Macro not found")
        _, rec = match
        return {
            "macro": {
                "id": macro_id,
                "name": rec.macro_name,
                "source": rec.source_path,
                "line": rec.span.line if rec.span else None,
                "column": rec.span.column if rec.span else None,
                "artifacts": rec.artifacts,
            }
        }


__all__ = ["register_macro_routes"]
