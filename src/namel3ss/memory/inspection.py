from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from typing import TYPE_CHECKING

from .. import ir
from ..runtime.context import (
    filter_items_by_retention,
    filter_turns_by_retention,
    get_last_recall_snapshot,
    list_recall_snapshots,
    _parse_timestamp,
    _serialize_time_decay,
)

if TYPE_CHECKING:  # pragma: no cover
    from .engine import MemoryEngine
    from ..runtime.engine import Engine

CANONICAL_KINDS = ("short_term", "long_term", "episodic", "semantic", "profile")
KIND_SUFFIXES = {
    "short_term": "",
    "long_term": "::long_term",
    "episodic": "::episodic",
    "semantic": "::semantic",
    "profile": "::profile",
}
DEFAULT_SCOPE_BY_KIND = {
    "short_term": ir.DEFAULT_SHORT_TERM_SCOPE,
    "long_term": ir.DEFAULT_LONG_TERM_SCOPE,
    "episodic": ir.DEFAULT_EPISODIC_SCOPE,
    "semantic": ir.DEFAULT_SEMANTIC_SCOPE,
    "profile": ir.DEFAULT_PROFILE_SCOPE,
}


def inspect_memory_state(
    session_id: str,
    ai_id: str | None = None,
    memory_engine: "MemoryEngine | None" = None,
    memory_name: str | None = None,
) -> Dict[str, Any]:
    """
    Legacy helper that returns recall snapshots plus optional conversation history.
    """

    if ai_id:
        snapshots = {ai_id: get_last_recall_snapshot(ai_id, session_id)}
    else:
        snapshots = list_recall_snapshots(session_id)
    result: Dict[str, Any] = {
        "session_id": session_id,
        "ai_id": ai_id,
        "recall_snapshots": snapshots,
    }
    if memory_engine and memory_name:
        try:
            result["conversation"] = memory_engine.load_conversation(memory_name, session_id=session_id)
        except Exception as exc:  # pragma: no cover
            result["conversation_error"] = str(exc)
    return result


def describe_memory_plan(ai_call: ir.IRAiCall) -> Dict[str, Any]:
    """
    Build a normalized plan for all canonical memory kinds on an AI.
    """

    mem_cfg = getattr(ai_call, "memory", None)
    plan: Dict[str, Any] = {"ai": ai_call.name, "kinds": [], "recall": []}
    if not mem_cfg:
        return plan

    short_cfg = _effective_short_term_config(mem_cfg)
    for kind in CANONICAL_KINDS:
        cfg = _kind_config_for_plan(mem_cfg, kind, short_cfg)
        entry: Dict[str, Any] = {"kind": kind, "enabled": cfg is not None}
        if cfg:
            entry.update(
                {
                    "scope": getattr(cfg, "scope", None),
                    "retention_days": getattr(cfg, "retention_days", None),
                    "pii_policy": getattr(cfg, "pii_policy", None) or "none",
                    "time_decay": _serialize_time_decay(getattr(cfg, "time_decay", None)),
                    "pipeline": _serialize_pipeline_steps(getattr(cfg, "pipeline", None)),
                }
            )
            if kind == "short_term":
                entry["window"] = getattr(cfg, "window", None) or ir.DEFAULT_SHORT_TERM_WINDOW
            if kind in {"long_term", "episodic", "semantic", "profile"}:
                entry["store"] = getattr(cfg, "store", None)
        plan["kinds"].append(entry)

    recall_plan = getattr(mem_cfg, "recall", []) or []
    plan["recall"] = [
        {
            "source": getattr(rule, "source", None),
            "count": getattr(rule, "count", None),
            "top_k": getattr(rule, "top_k", None),
            "include": getattr(rule, "include", None),
        }
        for rule in recall_plan
    ]
    return plan


def describe_memory_state(
    engine: "Engine",
    ai_call: ir.IRAiCall,
    *,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 25,
) -> Dict[str, Any]:
    """
    Collect a scrubbed snapshot of stored memory for the requested AI/user/session.
    """

    mem_cfg = getattr(ai_call, "memory", None)
    if not mem_cfg:
        return {"ai": ai_call.name, "session_id": session_id, "user_id": user_id, "kinds": {}, "policies": {}}

    short_cfg = _effective_short_term_config(mem_cfg)
    memory_stores = getattr(engine, "memory_stores", {}) or {}

    resolved_user_id = user_id or _lookup_user_id(short_cfg, mem_cfg, engine, ai_call.name, session_id)
    kinds_payload: Dict[str, Any] = {}
    policies: Dict[str, Any] = {}

    for kind in CANONICAL_KINDS:
        if kind == "short_term" and session_id is None:
            # Short-term memory is strictly per-session; skip when no session id is provided.
            continue
        cfg = _kind_config_for_plan(mem_cfg, kind, short_cfg)
        store_name = _store_name_for_kind(mem_cfg, kind)
        if not cfg or not store_name:
            continue
        backend = memory_stores.get(store_name)
        if backend is None:
            continue
        base_key = ai_call.name + KIND_SUFFIXES[kind]
        scope = _resolve_scope(
            kind,
            getattr(cfg, "scope", None),
            base_key,
            session_id,
            resolved_user_id,
            default_scope=DEFAULT_SCOPE_BY_KIND[kind],
        )
        policy = _build_policy_info(cfg, scope, resolved_user_id)
        data = _collect_kind_entries(
            kind,
            cfg,
            backend,
            scope,
            limit=limit,
        )
        if data is None:
            continue
        kinds_payload[kind] = data
        policies[kind] = policy

    snapshot = get_last_recall_snapshot(ai_call.name, session_id or "")
    return {
        "ai": ai_call.name,
        "session_id": session_id,
        "user_id": resolved_user_id,
        "kinds": kinds_payload,
        "policies": policies,
        "recall_snapshot": snapshot,
    }


def _effective_short_term_config(mem_cfg: ir.IRAiMemoryConfig | None) -> ir.IRAiShortTermMemoryConfig | None:
    if mem_cfg is None:
        return None
    cfg = getattr(mem_cfg, "short_term", None)
    if cfg is not None:
        return cfg
    if mem_cfg.kind or mem_cfg.window or mem_cfg.store:
        return ir.IRAiShortTermMemoryConfig(
            window=mem_cfg.window or ir.DEFAULT_SHORT_TERM_WINDOW,
            store=mem_cfg.store,
            retention_days=None,
            pii_policy=None,
            scope=ir.DEFAULT_SHORT_TERM_SCOPE,
        )
    return None


def _kind_config_for_plan(
    mem_cfg: ir.IRAiMemoryConfig,
    kind: str,
    short_cfg: ir.IRAiShortTermMemoryConfig | None,
) -> Any | None:
    if kind == "short_term":
        return short_cfg
    return getattr(mem_cfg, kind, None)


def _serialize_pipeline_steps(steps: Optional[List[ir.IRMemoryPipelineStep]]) -> List[Dict[str, Any]]:
    if not steps:
        return []
    return [
        {
            "name": step.name,
            "type": step.type,
            "target_kind": step.target_kind,
            "max_tokens": step.max_tokens,
            "embedding_model": step.embedding_model,
        }
        for step in steps
    ]


def _lookup_user_id(
    short_cfg: ir.IRAiShortTermMemoryConfig | None,
    mem_cfg: ir.IRAiMemoryConfig,
    engine: "Engine",
    ai_id: str,
    session_id: Optional[str],
) -> Optional[str]:
    if not session_id:
        return None
    short_store = _store_name_for_kind(mem_cfg, "short_term")
    backend = engine.memory_stores.get(short_store) if short_store else None
    if backend and hasattr(backend, "get_session_user"):
        try:
            return backend.get_session_user(ai_id, session_id)
        except Exception:
            return None
    return None


def _store_name_for_kind(mem_cfg: ir.IRAiMemoryConfig, kind: str) -> Optional[str]:
    if kind == "short_term":
        short_cfg = getattr(mem_cfg, "short_term", None)
        if short_cfg and getattr(short_cfg, "store", None):
            return short_cfg.store
        return getattr(mem_cfg, "store", None) or "default_memory"
    cfg = getattr(mem_cfg, kind, None)
    if cfg is None:
        return None
    return getattr(cfg, "store", None)


def _resolve_scope(
    kind: str,
    requested_scope: Optional[str],
    base_ai_key: str,
    session_id: Optional[str],
    user_id: Optional[str],
    *,
    default_scope: str,
) -> Dict[str, Any]:
    scope = (requested_scope or default_scope) or "per_session"
    requested = scope
    fallback = False
    if scope == "per_user":
        if user_id:
            session_key = f"user:{user_id}"
        else:
            if not session_id:
                raise ValueError(f"Session id required to inspect per_session view of kind '{kind}'.")
            scope = "per_session"
            session_key = session_id
            fallback = True
    elif scope == "shared":
        session_key = "shared"
    else:
        if not session_id:
            raise ValueError(f"Session id required to inspect '{kind}' memory.")
        session_key = session_id
    return {
        "ai_key": base_ai_key,
        "session_key": session_key,
        "scope": scope,
        "requested": requested,
        "fallback": fallback,
    }


def _build_policy_info(cfg: Any, scope_info: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
    policy = {
        "scope": scope_info["scope"],
        "requested_scope": scope_info["requested"],
        "scope_fallback": scope_info["fallback"],
        "retention_days": getattr(cfg, "retention_days", None),
        "pii_policy": getattr(cfg, "pii_policy", None) or "none",
        "time_decay": _serialize_time_decay(getattr(cfg, "time_decay", None)),
    }
    if scope_info["fallback"] and scope_info["requested"] == "per_user" and not user_id:
        policy["scope_note"] = "Falling back to per_session because no user id was provided."
    return policy


def _collect_kind_entries(
    kind: str,
    cfg: Any,
    backend: Any,
    scope: Dict[str, Any],
    *,
    limit: int,
) -> Optional[Dict[str, Any]]:
    ai_key = scope["ai_key"]
    session_key = scope["session_key"]
    if kind == "short_term":
        if not hasattr(backend, "get_full_history"):
            return None
        history = backend.get_full_history(ai_key, session_key)
        history = filter_turns_by_retention(history, getattr(cfg, "retention_days", None))
        return {
            "turns": history[-limit:] if limit else history,
            "window": getattr(cfg, "window", None) or ir.DEFAULT_SHORT_TERM_WINDOW,
            "scope": scope["scope"],
        }
    if kind in {"long_term", "episodic", "semantic"}:
        if not hasattr(backend, "list_items"):
            return None
        items = backend.list_items(ai_key, session_key)
        items = filter_items_by_retention(items, getattr(cfg, "retention_days", None))
        items = items[-limit:] if limit else items
        enriched = []
        for entry in items:
            enriched_entry = dict(entry)
            score = _compute_decay_score(entry.get("created_at"), getattr(cfg, "time_decay", None))
            if score is not None:
                enriched_entry["decay_score"] = score
            enriched.append(enriched_entry)
        return {
            "items": enriched,
            "store": getattr(cfg, "store", None),
            "scope": scope["scope"],
        }
    if kind == "profile":
        if not hasattr(backend, "get_full_history"):
            return None
        turns = backend.get_full_history(ai_key, session_key)
        turns = filter_turns_by_retention(turns, getattr(cfg, "retention_days", None))
        facts = [
            turn.get("content", "")
            for turn in turns
            if (turn.get("role") or "").lower() == "system" and turn.get("content")
        ]
        return {
            "facts": facts,
            "store": getattr(cfg, "store", None),
            "scope": scope["scope"],
        }
    return None


def _compute_decay_score(timestamp: Optional[str], time_decay_cfg: Any | None) -> Optional[float]:
    if not time_decay_cfg:
        return None
    half_life = getattr(time_decay_cfg, "half_life_days", None)
    if not half_life or half_life <= 0:
        return None
    ts = _parse_timestamp(timestamp)
    if ts is None:
        return None
    age_days = max(0.0, (datetime.now(timezone.utc) - ts).total_seconds() / 86400.0)
    score = math.exp(-age_days / half_life)
    return round(score, 4)
