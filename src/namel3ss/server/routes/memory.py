"""Memory inspection and management routes."""

from __future__ import annotations

from typing import Any, Callable, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import Role, can_view_pages, get_principal, Principal
from ..schemas import MemoryClearRequest


def build_memory_router(
    project_program: Callable[[], Any],
    build_project_engine: Callable[[Any], Any],
    describe_memory_plan_fn,
    describe_memory_state_fn,
    short_term_store_name_fn: Callable[[Any], str],
    long_term_store_name_fn: Callable[[Any], str | None],
    profile_store_name_fn: Callable[[Any], str | None],
    long_term_key_fn: Callable[[str], str],
    profile_key_fn: Callable[[str], str],
    compute_scope_keys_fn,
    legacy_session_payload_fn,
    clear_recall_snapshot_fn,
    ir_module,
) -> APIRouter:
    """Build memory-related endpoints."""

    router = APIRouter()

    @router.get("/api/memory/ai/{ai_id}/plan")
    def api_memory_plan(ai_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        plan = describe_memory_plan_fn(ai_calls[ai_id])
        return plan

    @router.get("/api/memory/ai/{ai_id}/state")
    def api_memory_state(
        ai_id: str,
        session_id: str | None = Query(default=None),
        user_id: str | None = Query(default=None),
        limit: int = Query(default=25, ge=1, le=200),
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        if not session_id and not user_id:
            raise HTTPException(status_code=400, detail="Provide session_id or user_id to inspect memory.")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        engine = build_project_engine(program)
        try:
            state = describe_memory_state_fn(engine, ai_calls[ai_id], session_id=session_id, user_id=user_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return state

    @router.get("/api/memory/ai/{ai_id}/sessions")
    def api_memory_ai_sessions(ai_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        ai_call = ai_calls[ai_id]
        mem_cfg = getattr(ai_call, "memory", None)
        if not mem_cfg:
            return {"ai": ai_id, "sessions": []}
        engine = build_project_engine(program)
        store_name = short_term_store_name_fn(mem_cfg)
        backend = engine.memory_stores.get(store_name)
        if backend is None:
            raise HTTPException(status_code=404, detail=f"Memory store '{store_name}' unavailable")
        sessions = backend.list_sessions(ai_id)
        serialized = [
            {
                "id": entry.get("id"),
                "last_activity": entry.get("last_activity"),
                "turns": entry.get("turns", 0),
                "user_id": entry.get("user_id"),
            }
            for entry in sessions
        ]
        return {"ai": ai_id, "sessions": serialized}

    @router.get("/api/memory/ai/{ai_id}/sessions/{session_id}")
    def api_memory_session_detail(ai_id: str, session_id: str, principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        ai_call = ai_calls[ai_id]
        mem_cfg = getattr(ai_call, "memory", None)
        if not mem_cfg:
            return {"ai": ai_id, "session": session_id, "short_term": {"turns": []}}
        engine = build_project_engine(program)
        try:
            state = describe_memory_state_fn(engine, ai_call, session_id=session_id, limit=50)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return legacy_session_payload_fn(ai_id, session_id, state)

    @router.post("/api/memory/ai/{ai_id}/sessions/{session_id}/clear")
    def api_memory_session_clear(
        ai_id: str,
        session_id: str,
        payload: MemoryClearRequest,
        principal: Principal = Depends(get_principal),
    ) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {})
        if ai_id not in ai_calls:
            raise HTTPException(status_code=404, detail="AI not found")
        mem_cfg = getattr(ai_calls[ai_id], "memory", None)
        if not mem_cfg:
            return {"success": True}
        engine = build_project_engine(program)
        memory_stores = engine.memory_stores
        kinds = payload.kinds or ["short_term", "long_term", "profile"]
        short_cfg = getattr(mem_cfg, "short_term", None)
        if short_cfg is None and (getattr(mem_cfg, "kind", None) or getattr(mem_cfg, "window", None) or getattr(mem_cfg, "store", None)):
            short_cfg = ir_module.IRAiShortTermMemoryConfig(window=getattr(mem_cfg, "window", None), store=getattr(mem_cfg, "store", None))
        short_store_name = short_term_store_name_fn(mem_cfg)
        short_backend = memory_stores.get(short_store_name)
        session_user_id: str | None = None
        if short_backend and hasattr(short_backend, "get_session_user"):
            try:
                session_user_id = short_backend.get_session_user(ai_id, session_id)
            except Exception:
                session_user_id = None
        short_scope = compute_scope_keys_fn(
            "short_term",
            getattr(short_cfg, "scope", None) if short_cfg else None,
            ai_id,
            session_id,
            session_user_id,
        )
        if "short_term" in kinds and short_store_name in memory_stores:
            memory_stores[short_store_name].clear_session(short_scope["ai_key"], short_scope["session_key"])
        long_cfg = getattr(mem_cfg, "long_term", None)
        long_scope = (
            compute_scope_keys_fn("long_term", getattr(long_cfg, "scope", None), long_term_key_fn(ai_id), session_id, session_user_id)
            if long_cfg
            else None
        )
        long_store_name = long_term_store_name_fn(mem_cfg)
        if (
            "long_term" in kinds
            and long_scope
            and long_store_name
            and long_store_name in memory_stores
        ):
            memory_stores[long_store_name].clear_session(long_scope["ai_key"], long_scope["session_key"])
        profile_cfg = getattr(mem_cfg, "profile", None)
        profile_scope = (
            compute_scope_keys_fn("profile", getattr(profile_cfg, "scope", None), profile_key_fn(ai_id), session_id, session_user_id)
            if profile_cfg
            else None
        )
        profile_store_name = profile_store_name_fn(mem_cfg)
        if (
            "profile" in kinds
            and profile_scope
            and profile_store_name
            and profile_store_name in memory_stores
        ):
            memory_stores[profile_store_name].clear_session(profile_scope["ai_key"], profile_scope["session_key"])
        clear_recall_snapshot_fn(ai_id, session_id)
        return {"success": True}

    @router.get("/api/memory/ais")
    def api_memory_ai_list(principal: Principal = Depends(get_principal)) -> Dict[str, Any]:
        if not can_view_pages(principal.role):
            raise HTTPException(status_code=403, detail="Forbidden")
        program = project_program()
        ai_calls = getattr(program, "ai_calls", {}) or {}
        ais: list[dict[str, Any]] = []
        for name, ai_call in ai_calls.items():
            if getattr(ai_call, "memory", None) or getattr(ai_call, "memory_name", None):
                ais.append({"id": name, "name": name, "has_memory": True})
        return {"ais": ais}

    return router


__all__ = ["build_memory_router"]
