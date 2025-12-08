"""
Execution context and stubbed executors for the runtime.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, TypedDict
import re
from types import SimpleNamespace

from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..ir import IRAgent, IRAiCall, IRAiShortTermMemoryConfig, IRApp, IRMemory, IRPage, IRProgram
from ..memory.engine import MemoryEngine
from ..metrics.tracker import MetricsTracker
from ..errors import Namel3ssError, ProviderAuthError, ProviderConfigError
from ..obs.tracer import Tracer
from ..rag.engine import RAGEngine
from ..secrets.manager import SecretsManager
from ..tools.registry import ToolRegistry
from ..tools.registry import build_ai_tool_specs
from .. import ast_nodes
from .expressions import ExpressionEvaluator, VariableEnvironment
import json
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_SHORT_TERM_WINDOW = 20
DEFAULT_LONG_TERM_TOP_K = 5
PROFILE_HISTORY_WINDOW = 50
DEFAULT_SHORT_TERM_SCOPE = "per_session"
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)
IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


class _SecretProxy:
    def __init__(self, manager: SecretsManager | None) -> None:
        self._manager = manager

    def __getattr__(self, name: str) -> Any:
        if not self._manager:
            raise AttributeError(name)
        value = self._manager.get(name)
        if value is None:
            raise AttributeError(name)
        return value


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _retention_cutoff_iso(retention_days: int | None) -> str | None:
    if not retention_days:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    return cutoff.isoformat().replace("+00:00", "Z")


def _default_scope_for_kind(kind: str, user_id: str | None) -> str:
    if kind == "short_term":
        return DEFAULT_SHORT_TERM_SCOPE
    if kind in {"long_term", "profile"}:
        return "per_user" if user_id else "per_session"
    return "per_session"


def _compute_scope_keys(
    base_ai_key: str,
    requested_scope: str | None,
    default_scope: str,
    session_id: str,
    user_id: str | None,
) -> tuple[str, str, str, bool]:
    scope = (requested_scope or default_scope) or "per_session"
    fallback = False
    if scope == "per_user":
        if user_id:
            session_key = f"user:{user_id}"
        else:
            scope = "per_session"
            session_key = session_id
            fallback = True
    elif scope == "shared":
        session_key = "shared"
    else:
        session_key = session_id
    return base_ai_key, session_key, scope, fallback


def filter_turns_by_retention(turns: list[Dict[str, str]], retention_days: int | None) -> list[Dict[str, str]]:
    if not retention_days:
        return list(turns)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
    filtered: list[Dict[str, str]] = []
    for turn in turns:
        ts = _parse_timestamp(turn.get("created_at"))
        if ts is None or ts >= cutoff_dt:
            filtered.append(turn)
    return filtered


def filter_items_by_retention(items: list[Dict[str, Any]], retention_days: int | None) -> list[Dict[str, Any]]:
    if not retention_days:
        return list(items)
    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
    filtered: list[Dict[str, Any]] = []
    for item in items:
        ts = _parse_timestamp(item.get("created_at"))
        if ts is None or ts >= cutoff_dt:
            filtered.append(item)
    return filtered


def _apply_pii_policy_to_text(text: str, policy: str | None) -> str:
    if not text:
        return text
    if not policy or policy == "none":
        return text
    cleaned = EMAIL_PATTERN.sub("[email]", text)
    cleaned = IP_PATTERN.sub("[ip]", cleaned)
    return cleaned


def _apply_pii_policy_to_turns(turns: list[Dict[str, str]], policy: str | None) -> list[Dict[str, str]]:
    if not policy or policy == "none":
        return turns
    sanitized: list[Dict[str, str]] = []
    for turn in turns:
        new_turn = dict(turn)
        new_turn["content"] = _apply_pii_policy_to_text(turn.get("content", ""), policy)
        sanitized.append(new_turn)
    return sanitized


def _apply_pii_policy_to_list(values: list[str], policy: str | None) -> list[str]:
    if not policy or policy == "none":
        return values
    return [_apply_pii_policy_to_text(value, policy) for value in values]


def _cleanup_state_retention(state: Dict[str, Any]) -> None:
    retention_days = state.get("retention_days")
    backend = state.get("backend")
    if not retention_days or not backend:
        return
    cutoff_iso = _retention_cutoff_iso(retention_days)
    if not cutoff_iso:
        return
    if hasattr(backend, "cleanup_retention"):
        backend.cleanup_retention(state.get("ai_key"), state.get("session_key"), cutoff_iso)


def _normalize_user_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


@dataclass
class ExecutionContext:
    app_name: str
    request_id: str
    user_input: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    user_context: Dict[str, Any] = field(default_factory=lambda: {"id": None, "is_authenticated": False, "record": None})
    memory_engine: Optional[MemoryEngine] = None
    memory_stores: Optional[Dict[str, Any]] = None
    rag_engine: Optional[RAGEngine] = None
    tracer: Optional[Tracer] = None
    tool_registry: Optional[ToolRegistry] = None
    metrics: Optional[MetricsTracker] = None
    secrets: Optional[SecretsManager] = None
    trigger_manager: Optional[Any] = None
    optimizer_engine: Optional[Any] = None


def execute_app(app: IRApp, context: ExecutionContext) -> Dict[str, Any]:
    """
    Placeholder executor for an app. Returns a simple summary payload.
    """

    return {
        "app": app.name,
        "entry_page": app.entry_page,
        "request_id": context.request_id,
        "status": "ok",
    }


def execute_ai_call(ai_call: IRAiCall, context: ExecutionContext) -> Dict[str, Any]:
    """
    Placeholder executor for an AI call. No model invocation yet.
    """

    return {
        "ai_call": ai_call.name,
        "model": ai_call.model_name,
        "input": ai_call.input_source,
        "request_id": context.request_id,
        "status": "stubbed",
    }


def execute_agent(agent: IRAgent, context: ExecutionContext) -> Dict[str, Any]:
    """Placeholder executor for an agent."""

    return {
        "agent": agent.name,
        "goal": agent.goal,
        "personality": agent.personality,
        "request_id": context.request_id,
        "status": "ok",
    }


def load_memory(memory: IRMemory, context: ExecutionContext) -> Dict[str, Any]:
    """Placeholder loader for a memory block."""

    return {
        "memory": memory.name,
        "type": memory.memory_type,
        "request_id": context.request_id,
        "loaded": True,
    }


class MemoryPipelineContext(TypedDict):
    ai_id: str
    session_id: str
    user_id: str | None
    user_text: str
    assistant_text: str
    short_term_history: List[Dict[str, str]]


_RECALL_SNAPSHOTS: Dict[tuple[str, str], Dict[str, Any]] = {}


def record_recall_snapshot(
    ai_id: str,
    session_id: str,
    rules: List[Any] | None,
    messages: List[Dict[str, Any]],
) -> None:
    if not ai_id or not session_id:
        return
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rules": [_serialize_recall_rule(rule) for rule in (rules or [])],
        "messages": copy.deepcopy(messages),
    }
    _RECALL_SNAPSHOTS[(ai_id, session_id)] = snapshot


def get_last_recall_snapshot(ai_id: str, session_id: str) -> Dict[str, Any] | None:
    snap = _RECALL_SNAPSHOTS.get((ai_id, session_id))
    if not snap:
        return None
    return copy.deepcopy(snap)


def clear_recall_snapshot(ai_id: str, session_id: str) -> None:
    _RECALL_SNAPSHOTS.pop((ai_id, session_id), None)


def _serialize_recall_rule(rule: Any) -> Dict[str, Any]:
    return {
        "source": getattr(rule, "source", None),
        "count": getattr(rule, "count", None),
        "top_k": getattr(rule, "top_k", None),
        "include": getattr(rule, "include", None),
    }


def build_memory_messages(
    ai_call: IRAiCall,
    context: ExecutionContext,
    session_id: str,
    user_id: str | None,
) -> tuple[Dict[str, Any] | None, list[Dict[str, str]]]:
    mem_cfg = getattr(ai_call, "memory", None)
    memory_stores = getattr(context, "memory_stores", None)
    if not mem_cfg or not memory_stores:
        return None, []
    short_term_cfg = getattr(mem_cfg, "short_term", None)
    if short_term_cfg is None and (getattr(mem_cfg, "kind", None) or getattr(mem_cfg, "window", None) or getattr(mem_cfg, "store", None)):
        short_term_cfg = IRAiShortTermMemoryConfig(
            window=getattr(mem_cfg, "window", None),
            store=getattr(mem_cfg, "store", None),
        )
    recall_plan = list(getattr(mem_cfg, "recall", []) or [])
    memory_state: Dict[str, Any] = {
        "plan": mem_cfg,
        "short_term": None,
        "long_term": None,
        "profile": None,
        "user_id": _normalize_user_id(user_id),
    }
    recall_messages: list[Dict[str, str]] = []
    resolved_user_id = memory_state["user_id"]
    if resolved_user_id is None and context.metadata:
        resolved_user_id = _normalize_user_id(context.metadata.get("user_id"))
        memory_state["user_id"] = resolved_user_id

    def _require_backend(store_name: str | None) -> tuple[Any, str]:
        resolved = store_name or "default_memory"
        backend = memory_stores.get(resolved)
        if backend is None:
            raise Namel3ssError(
                f"N3L-1201: Memory store '{resolved}' referenced on AI '{ai_call.name}' is not configured for this project."
            )
        return backend, resolved

    short_state = None
    if short_term_cfg:
        window = getattr(short_term_cfg, "window", None) or getattr(mem_cfg, "window", None) or DEFAULT_SHORT_TERM_WINDOW
        store_name = getattr(short_term_cfg, "store", None) or getattr(mem_cfg, "store", None)
        backend, resolved = _require_backend(store_name)
        short_rules = [rule for rule in recall_plan if getattr(rule, "source", "") == "short_term"]
        needed = window
        if short_rules:
            needed = max(needed, max((getattr(rule, "count", None) or window) for rule in short_rules))
        history = []
        if short_rules or window:
            try:
                ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                    ai_call.name,
                    getattr(short_term_cfg, "scope", None),
                    _default_scope_for_kind("short_term", resolved_user_id),
                    session_id,
                    resolved_user_id,
                )
                history = backend.load_history(ai_key, session_key, needed)
                history = filter_turns_by_retention(history, getattr(short_term_cfg, "retention_days", None))
            except Exception as exc:
                raise Namel3ssError(f"Failed to load conversation history for AI '{ai_call.name}': {exc}")
        else:
            ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                ai_call.name,
                getattr(short_term_cfg, "scope", None),
                _default_scope_for_kind("short_term", resolved_user_id),
                session_id,
                resolved_user_id,
            )
        short_state = {
            "backend": backend,
            "store": resolved,
            "history": history,
            "window": window,
            "ai_key": ai_key,
            "session_key": session_key,
            "scope": resolved_scope,
            "scope_fallback": scope_fallback,
            "retention_days": getattr(short_term_cfg, "retention_days", None),
            "pii_policy": getattr(short_term_cfg, "pii_policy", None),
        }
        memory_state["short_term"] = short_state

    long_state = None
    long_term_cfg = getattr(mem_cfg, "long_term", None)
    if long_term_cfg:
        backend, resolved = _require_backend(getattr(long_term_cfg, "store", None))
        long_rules = [rule for rule in recall_plan if getattr(rule, "source", "") == "long_term"]
        needed = DEFAULT_LONG_TERM_TOP_K
        if long_rules:
            needed = max(DEFAULT_LONG_TERM_TOP_K, max((getattr(rule, "top_k", None) or DEFAULT_LONG_TERM_TOP_K) for rule in long_rules))
        history = []
        base_key = f"{ai_call.name}::long_term"
        if long_rules:
            try:
                ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                    base_key,
                    getattr(long_term_cfg, "scope", None),
                    _default_scope_for_kind("long_term", resolved_user_id),
                    session_id,
                    resolved_user_id,
                )
                history = backend.load_history(ai_key, session_key, needed)
                history = filter_turns_by_retention(history, getattr(long_term_cfg, "retention_days", None))
            except Exception as exc:
                raise Namel3ssError(f"Failed to load long_term memory for AI '{ai_call.name}': {exc}")
        else:
            base_key = f"{ai_call.name}::long_term"
            ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                base_key,
                getattr(long_term_cfg, "scope", None),
                _default_scope_for_kind("long_term", resolved_user_id),
                session_id,
                resolved_user_id,
            )
        long_state = {
            "backend": backend,
            "store": resolved,
            "history": history,
            "ai_key": ai_key,
            "session_key": session_key,
            "scope": resolved_scope,
            "scope_fallback": scope_fallback,
            "retention_days": getattr(long_term_cfg, "retention_days", None),
            "pii_policy": getattr(long_term_cfg, "pii_policy", None),
        }
        memory_state["long_term"] = long_state

    profile_state = None
    profile_cfg = getattr(mem_cfg, "profile", None)
    if profile_cfg:
        backend, resolved = _require_backend(getattr(profile_cfg, "store", None))
        history = []
        profile_rules = [rule for rule in recall_plan if getattr(rule, "source", "") == "profile"]
        if profile_rules:
            try:
                base_key = f"{ai_call.name}::profile"
                ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                    base_key,
                    getattr(profile_cfg, "scope", None),
                    _default_scope_for_kind("profile", resolved_user_id),
                    session_id,
                    resolved_user_id,
                )
                history = backend.load_history(ai_key, session_key, PROFILE_HISTORY_WINDOW)
                history = filter_turns_by_retention(history, getattr(profile_cfg, "retention_days", None))
            except Exception as exc:
                raise Namel3ssError(f"Failed to load profile memory for AI '{ai_call.name}': {exc}")
        else:
            base_key = f"{ai_call.name}::profile"
            ai_key, session_key, resolved_scope, scope_fallback = _compute_scope_keys(
                base_key,
                getattr(profile_cfg, "scope", None),
                _default_scope_for_kind("profile", resolved_user_id),
                session_id,
                resolved_user_id,
            )
        profile_state = {
            "backend": backend,
            "store": resolved,
            "history": history,
            "ai_key": ai_key,
            "session_key": session_key,
            "scope": resolved_scope,
            "scope_fallback": scope_fallback,
            "extract_facts": getattr(profile_cfg, "extract_facts", None),
            "retention_days": getattr(profile_cfg, "retention_days", None),
            "pii_policy": getattr(profile_cfg, "pii_policy", None),
        }
        memory_state["profile"] = profile_state

    for rule in recall_plan:
        source = getattr(rule, "source", "")
        if source == "short_term" and short_state:
            count = getattr(rule, "count", None) or short_state["window"] or DEFAULT_SHORT_TERM_WINDOW
            recall_messages.extend(_turns_to_messages(short_state.get("history", [])[-count:]))
        elif source == "long_term" and long_state:
            top_k = getattr(rule, "top_k", None) or DEFAULT_LONG_TERM_TOP_K
            recall_messages.extend(_turns_to_messages(long_state.get("history", [])[-top_k:]))
        elif source == "profile" and profile_state:
            include = getattr(rule, "include", None)
            include = True if include is None else include
            if include:
                profile_text = _profile_text_from_history(profile_state.get("history", []))
                if profile_text:
                    recall_messages.append({"role": "system", "content": profile_text})

    return memory_state, recall_messages


def persist_memory_state(
    memory_state: Dict[str, Any] | None,
    ai_call: IRAiCall,
    session_id: str,
    user_content: str,
    assistant_content: str,
    user_id: str | None,
) -> None:
    if not memory_state:
        return
    resolved_user_id = memory_state.get("user_id") or _normalize_user_id(user_id)
    short_state = memory_state.get("short_term")
    long_state = memory_state.get("long_term")
    profile_state = memory_state.get("profile")
    turns = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": assistant_content},
    ]
    if short_state and short_state.get("backend"):
        try:
            short_state["backend"].append_turns(
                short_state["ai_key"],
                short_state["session_key"],
                turns,
                resolved_user_id,
            )
            history = short_state.setdefault("history", [])
            if isinstance(history, list):
                history.extend(turns)
            _cleanup_state_retention(short_state)
        except Exception:
            pass
    if long_state and long_state.get("backend"):
        try:
            sanitized = _apply_pii_policy_to_turns(turns, long_state.get("pii_policy"))
            long_state["backend"].append_turns(long_state["ai_key"], long_state["session_key"], sanitized)
            history = long_state.setdefault("history", [])
            if isinstance(history, list):
                history.extend(sanitized)
            _cleanup_state_retention(long_state)
        except Exception:
            pass
    if profile_state and profile_state.get("backend") and profile_state.get("extract_facts"):
        try:
            sanitized_facts = _apply_pii_policy_to_turns(
                [{"role": "user", "content": user_content}],
                profile_state.get("pii_policy"),
            )
            profile_state["backend"].append_turns(
                profile_state["ai_key"],
                profile_state["session_key"],
                sanitized_facts,
            )
            history = profile_state.setdefault("history", [])
            if isinstance(history, list):
                history.extend(sanitized_facts)
            _cleanup_state_retention(profile_state)
        except Exception:
            pass


def run_memory_pipelines(
    ai_call: IRAiCall,
    memory_state: Dict[str, Any] | None,
    session_id: str,
    user_content: str,
    assistant_content: str,
    user_id: str | None,
    provider: Any,
    provider_model: str | None,
) -> None:
    if not memory_state or not getattr(ai_call, "memory", None):
        return
    mem_cfg = ai_call.memory
    short_history = (memory_state.get("short_term") or {}).get("history", []) if memory_state else []
    pipeline_ctx: MemoryPipelineContext = {
        "ai_id": ai_call.name,
        "session_id": session_id,
        "user_id": user_id,
        "user_text": user_content,
        "assistant_text": assistant_content,
        "short_term_history": list(short_history or []),
    }
    long_state = memory_state.get("long_term") if memory_state else None
    if getattr(mem_cfg, "long_term", None) and getattr(mem_cfg.long_term, "pipeline", None) and long_state:
        for step in mem_cfg.long_term.pipeline or []:
            _execute_memory_pipeline_step("long_term", step, long_state, pipeline_ctx, provider, provider_model)
    profile_state = memory_state.get("profile") if memory_state else None
    if getattr(mem_cfg, "profile", None) and getattr(mem_cfg.profile, "pipeline", None) and profile_state:
        for step in mem_cfg.profile.pipeline or []:
            _execute_memory_pipeline_step("profile", step, profile_state, pipeline_ctx, provider, provider_model)


def _execute_memory_pipeline_step(
    kind: str,
    step: Any,
    state: Dict[str, Any],
    pipeline_ctx: MemoryPipelineContext,
    provider: Any,
    provider_model: str | None,
) -> None:
    step_type = getattr(step, "type", None)
    if step_type == "llm_summarizer":
        _run_llm_summarizer_step(step, state, pipeline_ctx, provider, provider_model, state.get("pii_policy"))
    elif step_type == "llm_fact_extractor":
        _run_llm_fact_extractor_step(step, state, pipeline_ctx, provider, provider_model, state.get("pii_policy"))


def _run_llm_summarizer_step(
    step: Any,
    state: Dict[str, Any],
    pipeline_ctx: MemoryPipelineContext,
    provider: Any,
    provider_model: str | None,
    pii_policy: str | None,
) -> None:
    backend = state.get("backend")
    ai_key = state.get("ai_key") or state.get("key")
    session_key = state.get("session_key") or pipeline_ctx.get("session_id")
    if not backend or not ai_key or not session_key:
        return
    transcript = _format_turns_for_pipeline(
        pipeline_ctx.get("short_term_history", []),
        pipeline_ctx.get("user_text", ""),
        pipeline_ctx.get("assistant_text", ""),
    )
    if not transcript.strip():
        return
    max_tokens = getattr(step, "max_tokens", None)
    system_prompt = "You summarize recent conversations for long-term memory."
    user_prompt_lines = [
        "Summarize the following conversation so it can be stored as long-term memory.",
        "Focus on key decisions, commitments, and facts.",
    ]
    if max_tokens:
        user_prompt_lines.append(f"Limit the summary to roughly {max_tokens} tokens.")
    user_prompt_lines.append("")
    user_prompt_lines.append(transcript)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "\n".join(user_prompt_lines).strip()},
    ]
    summary = _invoke_pipeline_model(provider, provider_model, messages).strip()
    if not summary:
        return
    summary = _apply_pii_policy_to_text(summary, pii_policy)
    entry = _append_summary_entry(backend, ai_key, session_key, summary)
    if entry:
        history = state.setdefault("history", [])
        if isinstance(history, list):
            history.append(entry)


def _run_llm_fact_extractor_step(
    step: Any,
    state: Dict[str, Any],
    pipeline_ctx: MemoryPipelineContext,
    provider: Any,
    provider_model: str | None,
    pii_policy: str | None,
) -> None:
    backend = state.get("backend")
    ai_key = state.get("ai_key") or state.get("key")
    session_key = state.get("session_key") or pipeline_ctx.get("session_id")
    if not backend or not ai_key or not session_key:
        return
    transcript = _format_turns_for_pipeline(
        pipeline_ctx.get("short_term_history", []),
        pipeline_ctx.get("user_text", ""),
        pipeline_ctx.get("assistant_text", ""),
    )
    if not transcript.strip():
        return
    instructions = (
        "Extract concise, durable facts about the user from this conversation. "
        "Return each fact as a separate bullet without commentary."
    )
    messages = [
        {"role": "system", "content": "You extract long-lived user profile facts from chats."},
        {"role": "user", "content": f"{instructions}\n\nConversation:\n{transcript}"},
    ]
    facts_text = _invoke_pipeline_model(provider, provider_model, messages).strip()
    facts = _normalize_facts_from_text(facts_text)
    facts = _apply_pii_policy_to_list(facts, pii_policy)
    if not facts:
        return
    entries = _append_fact_entries(backend, ai_key, session_key, facts)
    if entries:
        history = state.setdefault("history", [])
        if isinstance(history, list):
            history.extend(entries)


def _invoke_pipeline_model(provider: Any, model_name: str | None, messages: List[Dict[str, str]]) -> str:
    if provider is None:
        return ""
    try:
        response = provider.invoke(messages=messages, model=model_name)
    except Exception:
        return ""
    if hasattr(response, "text"):
        return response.text or ""
    if isinstance(response, dict):
        return response.get("text") or ""
    return str(response)


def _format_turns_for_pipeline(
    history: List[Dict[str, str]],
    user_text: str,
    assistant_text: str,
) -> str:
    lines: list[str] = []
    for turn in history or []:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        role = (turn.get("role") or "user").lower()
        lines.append(f"{role}: {content}")
    if user_text:
        lines.append(f"user: {user_text.strip()}")
    if assistant_text:
        lines.append(f"assistant: {assistant_text.strip()}")
    return "\n".join(lines)


def _append_summary_entry(backend: Any, key: str, session_id: str, summary: str) -> Dict[str, str] | None:
    if not summary.strip():
        return None
    entry = {"role": "system", "content": summary.strip()}
    try:
        if hasattr(backend, "append_summary"):
            backend.append_summary(key, session_id, summary.strip())
        else:
            backend.append_turns(key, session_id, [entry])
    except Exception:
        return None
    return entry


def _append_fact_entries(backend: Any, key: str, session_id: str, facts: List[str]) -> List[Dict[str, str]]:
    cleaned = [fact.strip() for fact in facts if fact and fact.strip()]
    if not cleaned:
        return []
    entries = [{"role": "system", "content": fact} for fact in cleaned]
    try:
        if hasattr(backend, "append_facts"):
            backend.append_facts(key, session_id, cleaned)
        else:
            backend.append_turns(key, session_id, entries)
    except Exception:
        return []
    return entries


def _normalize_facts_from_text(text: str) -> List[str]:
    if not text:
        return []
    lines = [line.strip() for line in text.replace("\r", "").split("\n")]
    facts: list[str] = []
    for line in lines:
        if not line:
            continue
        trimmed = line.lstrip("-*• ").strip()
        if trimmed:
            facts.append(trimmed)
    if not facts:
        facts = [text.strip()]
    return facts


def _turns_to_messages(turns: list[Dict[str, str]]) -> list[Dict[str, str]]:
    messages: list[Dict[str, str]] = []
    for turn in turns:
        content = (turn.get("content") or "").strip()
        if not content:
            continue
        role = turn.get("role") or "user"
        messages.append({"role": role, "content": content})
    return messages


def _profile_text_from_history(turns: list[Dict[str, str]]) -> str:
    lines = [(turn.get("content") or "").strip() for turn in turns]
    lines = [line for line in lines if line]
    if not lines:
        return ""
    return "User profile:\n" + "\n".join(lines)


def execute_ai_call_with_registry(
    ai_call: IRAiCall,
    registry: ModelRegistry,
    router: ModelRouter,
    context: ExecutionContext,
    tools_mode: str | None = None,
) -> Dict[str, Any]:
    """Execute an AI call through the model registry."""

    provider, provider_model, provider_name = registry.resolve_provider_for_ai(ai_call)
    provider_model = provider_model or getattr(provider, "default_model", None) or getattr(ai_call, "model_name", None)
    selection = SimpleNamespace(provider_name=provider_name, model_name=provider_model or provider_name)
    messages: list[Dict[str, str]] = []

    session_id = context.metadata.get("session_id") if context.metadata else None
    session_id = session_id or context.request_id or "default"
    metadata_user_id = context.metadata.get("user_id") if context.metadata else None
    user_id = _normalize_user_id(metadata_user_id)

    if getattr(ai_call, "system_prompt", None):
        messages.append({"role": "system", "content": ai_call.system_prompt or ""})

    # Load conversation history if memory is attached and available
    history: list[dict] = []
    memory_cfg = getattr(ai_call, "memory", None)
    memory_state: Dict[str, Any] | None = None
    if memory_cfg and getattr(context, "memory_stores", None):
        memory_state, memory_messages = build_memory_messages(ai_call, context, session_id, user_id)
        messages.extend(memory_messages)
    elif getattr(ai_call, "memory_name", None) and context.memory_engine:
        try:
            history = context.memory_engine.load_conversation(ai_call.memory_name or "", session_id=session_id)
            messages.extend(history)
        except Exception:
            raise Namel3ssError(
                f"Failed to load conversation history for memory '{ai_call.memory_name}'."
            )

    user_content = ai_call.input_source or (context.user_input or "")
    user_message = {"role": "user", "content": user_content}
    messages.append(user_message)
    if memory_state and memory_cfg:
        record_recall_snapshot(
            ai_call.name,
            session_id,
            list(getattr(memory_cfg, "recall", []) or []),
            messages,
        )

    def _http_json_request(method: str, url: str, headers: dict[str, str], body: bytes | None) -> dict:
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:  # pragma: no cover - live calls
            text = resp.read().decode("utf-8")
            return json.loads(text)

    def _execute_tool_by_name(tool_name: str, args: dict[str, Any]) -> Any:
        if not context.tool_registry:
            raise Namel3ssError(f"N3F-965: Tool '{tool_name}' unavailable (no registry).")
        tool_cfg = context.tool_registry.get(tool_name)
        if not tool_cfg:
            raise Namel3ssError(f"N3F-965: Tool '{tool_name}' unavailable.")
        if not hasattr(tool_cfg, "url_expr") and not hasattr(tool_cfg, "url_template"):
            if callable(getattr(tool_cfg, "execute", None)):
                return tool_cfg.execute(args)
            if callable(tool_cfg):
                return tool_cfg(args)
            return {"result": args}
        # Allow tests to supply mocked tool results via context.metadata
        mock_tools = (context.metadata or {}).get("mock_tool_results") if context.metadata else None
        if isinstance(mock_tools, dict) and tool_name in mock_tools:
            return mock_tools[tool_name]

        required_inputs = list(getattr(tool_cfg, "input_fields", []) or [])
        missing_inputs = [field for field in required_inputs if field not in (args or {})]
        if missing_inputs:
            raise Namel3ssError(
                f"N3F-965: Missing arg '{missing_inputs[0]}' for tool '{tool_cfg.name}'."
            )

        input_values = args or {}
        env = VariableEnvironment()
        env.declare("input", input_values)
        env.declare("secret", _SecretProxy(context.secrets or SecretsManager()))

        def _resolver(name: str) -> tuple[bool, Any]:
            if env.has(name):
                return True, env.resolve(name)
            return False, None

        evaluator = ExpressionEvaluator(env, resolver=_resolver)

        def _eval(expr: Any) -> Any:
            if isinstance(expr, ast_nodes.Expr):
                return evaluator.evaluate(expr)
            return expr

        method = (getattr(tool_cfg, "method", "GET") or "GET").upper()
        url_value: Any = None
        if getattr(tool_cfg, "url_expr", None) is not None:
            url_value = _eval(tool_cfg.url_expr)
        else:
            url_template = getattr(tool_cfg, "url_template", None)
            if url_template:
                try:
                    url_value = url_template.format(**{k: "" if v is None else str(v) for k, v in input_values.items()})
                except KeyError as exc:
                    missing = str(exc).strip("'\"")
                    raise Namel3ssError(
                        f"N3F-965: Missing arg '{missing}' for tool '{tool_cfg.name}' url."
                    )
        if not url_value:
            raise Namel3ssError(f"N3F-965: Tool '{tool_cfg.name}' is missing a resolved URL.")
        url_str = str(url_value)

        headers = {}
        for hk, hv in (getattr(tool_cfg, "headers", {}) or {}).items():
            value = _eval(hv)
            if value is None:
                continue
            headers[hk] = "" if value is None else str(value)

        query_exprs = getattr(tool_cfg, "query_params", {}) or {}
        if query_exprs:
            parsed = urllib.parse.urlparse(url_str)
            query_items = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
            for qk, q_expr in query_exprs.items():
                val = _eval(q_expr)
                if val is None:
                    continue
                if isinstance(val, list):
                    for item in val:
                        query_items.append((qk, "" if item is None else str(item)))
                else:
                    query_items.append((qk, "" if val is None else str(val)))
            url_str = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query_items, doseq=True)))

        body_payload: Any = None
        body_fields = getattr(tool_cfg, "body_fields", {}) or {}
        if body_fields:
            body_payload = {}
            for bk, b_expr in body_fields.items():
                body_payload[bk] = _eval(b_expr)
        elif getattr(tool_cfg, "body_template", None) is not None:
            body_payload = _eval(tool_cfg.body_template)

        body_bytes: bytes | None = None
        if body_payload is not None:
            if isinstance(body_payload, (dict, list)):
                body_bytes = json.dumps(body_payload).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body_payload, str):
                body_bytes = body_payload.encode("utf-8")
            else:
                body_bytes = json.dumps(body_payload).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
        try:
            return _http_json_request(method, url_str, headers, body_bytes)
        except urllib.error.HTTPError as exc:  # pragma: no cover - fallback
            raise Namel3ssError(f"N3F-963: Tool '{tool_cfg.name}' failed with HTTP {exc.code}")
        except urllib.error.URLError as exc:  # pragma: no cover - fallback
            raise Namel3ssError(f"N3F-963: Tool '{tool_cfg.name}' failed with HTTP error: {exc}")

    tool_bindings = list(getattr(ai_call, "tools", []) or [])
    requested_mode = (tools_mode or "auto").lower()
    tools_enabled = requested_mode != "none" and bool(tool_bindings)
    tool_alias_map: dict[str, str] = {}
    tool_schemas: list[dict[str, Any]] = []
    if tools_enabled:
        if not context.tool_registry:
            raise Namel3ssError(f"N3F-965: Tools unavailable for AI '{ai_call.name}' (no registry).")
        specs = build_ai_tool_specs(tool_bindings, context.tool_registry)
        tool_alias_map = {}
        for binding in tool_bindings:
            tool_alias_map[binding.exposed_name] = binding.internal_name
            tool_alias_map.setdefault(binding.internal_name, binding.internal_name)
        tool_schemas = [
            {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
            for spec in specs
        ]

    assistant_content = ""
    provider_payload: dict[str, Any] | None = None

    def _build_provider_payload(raw_payload: Any, finish_reason: str | None) -> dict[str, Any]:
        return {
            "provider": selection.provider_name,
            "model": provider_model,
            "messages": list(messages),
            "result": assistant_content,
            "raw": raw_payload,
            "usage": None,
            "finish_reason": finish_reason,
            "cost": None,
            "json": None,
        }

    invocation = None
    if tools_enabled and tool_schemas:
        try:
            chat_response = provider.chat_with_tools(
                messages=messages,
                tools=tool_schemas,
                tool_choice="auto",
                model=provider_model,
            )
            registry.provider_status[provider_name] = "ok"
            ModelRegistry.last_status[provider_name] = "ok"
        except urllib.error.HTTPError as exc:  # pragma: no cover - live calls
            if exc.code in {401, 403}:
                registry.provider_status[provider_name] = "unauthorized"
                ModelRegistry.last_status[provider_name] = "unauthorized"
                raise ProviderAuthError(
                    f"Provider '{provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                ) from exc
            raise
        tool_calls = list(chat_response.tool_calls or [])
        assistant_content = chat_response.final_text or ""
        provider_payload = _build_provider_payload(chat_response.raw, chat_response.finish_reason)

        if tool_calls:
            def _normalize_tool_args(args_payload: Any) -> dict[str, Any]:
                if isinstance(args_payload, dict):
                    return args_payload
                if isinstance(args_payload, str):
                    try:
                        parsed = json.loads(args_payload)
                        return parsed if isinstance(parsed, dict) else {"value": parsed}
                    except json.JSONDecodeError:
                        return {"__raw__": args_payload}
                return {}

            for call in tool_calls:
                alias_name = call.get("name")
                if not alias_name:
                    continue
                internal_name = tool_alias_map.get(alias_name)
                if not internal_name:
                    raise Namel3ssError(
                        f"N3F-972: AI '{ai_call.name}' referenced unknown tool '{alias_name}'."
                    )
                arguments = _normalize_tool_args(call.get("arguments"))
                tool_result = _execute_tool_by_name(internal_name, arguments or {})
                messages.append(
                    {
                        "role": "tool",
                        "name": alias_name,
                        "content": json.dumps(tool_result),
                    }
                )
            try:
                follow_up = provider.chat_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="none",
                    model=provider_model,
                )
                registry.provider_status[provider_name] = "ok"
                ModelRegistry.last_status[provider_name] = "ok"
            except urllib.error.HTTPError as exc:  # pragma: no cover - live calls
                if exc.code in {401, 403}:
                    registry.provider_status[provider_name] = "unauthorized"
                    ModelRegistry.last_status[provider_name] = "unauthorized"
                    raise ProviderAuthError(
                        f"Provider '{provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                        code="N3P-1802",
                    ) from exc
                raise
            assistant_content = follow_up.final_text or ""
            provider_payload = _build_provider_payload(follow_up.raw, follow_up.finish_reason)
    else:
        try:
            invocation = provider.generate(messages=messages, model=provider_model)
            registry.provider_status[provider_name] = "ok"
            ModelRegistry.last_status[provider_name] = "ok"
        except urllib.error.HTTPError as exc:  # pragma: no cover - live calls
            if exc.code in {401, 403}:
                registry.provider_status[provider_name] = "unauthorized"
                ModelRegistry.last_status[provider_name] = "unauthorized"
                raise ProviderAuthError(
                    f"Provider '{provider_name}' rejected the API key (unauthorized). Check your key and account permissions.",
                    code="N3P-1802",
                ) from exc
            raise
        assistant_content = invocation.text if hasattr(invocation, "text") else str(invocation)
        provider_payload = invocation.to_dict() if hasattr(invocation, "to_dict") else {
            "provider": selection.provider_name,
            "model": provider_model,
            "messages": list(messages),
            "result": assistant_content,
            "raw": getattr(invocation, "raw", None),
            "usage": None,
            "finish_reason": getattr(invocation, "finish_reason", None),
            "cost": None,
            "json": None,
        }
        provider_payload["messages"] = list(messages)

    result = execute_ai_call(ai_call, context)
    result.update(
        {
            "provider_result": provider_payload,
            "resolved_model": selection.model_name,
            "provider_name": selection.provider_name,
        }
    )

    # Append conversation history if memory configured
    if memory_state:
        persist_memory_state(memory_state, ai_call, session_id, user_content, assistant_content, user_id)
        run_memory_pipelines(
            ai_call,
            memory_state,
            session_id,
            user_content,
            assistant_content,
            user_id,
            provider,
            provider_model,
        )
    elif getattr(ai_call, "memory_name", None) and context.memory_engine:
        try:
            context.memory_engine.append_conversation(
                ai_call.memory_name or "",
                session_id=session_id,
                messages=[user_message, {"role": "assistant", "content": assistant_content}],
            )
        except Exception:
            # Memory failures should surface clearly without breaking core call
            raise Namel3ssError(
                f"Failed to append conversation history for memory '{ai_call.memory_name}'."
            )

    if context.metrics:
        context.metrics.record_ai_call(
            provider=selection.provider_name,
            tokens_in=1,
            tokens_out=1,
            cost=0.001,
        )
    if context.tracer:
        context.tracer.record_ai(
            model_name=ai_call.model_name or "unknown",
            prompt=user_content,
            response_preview=str(assistant_content)[:200],
            provider_name=selection.provider_name,
            logical_model_name=ai_call.model_name,
        )
    return result


def execute_page(
    page: IRPage,
    program: IRProgram,
    registry: ModelRegistry,
    router: ModelRouter,
    context: ExecutionContext,
    renderer=None,
) -> Dict[str, Any]:
    """Execute a page: resolve ai calls, agents, and memory references."""

    if context.tracer:
        context.tracer.start_page(page.name)

    ai_results = [
        execute_ai_call_with_registry(program.ai_calls[ai_name], registry, router, context)
        for ai_name in page.ai_calls
        if ai_name in program.ai_calls
    ]
    agent_results = [
        execute_agent(program.agents[agent_name], context)
        for agent_name in page.agents
        if agent_name in program.agents
    ]
    memory_results = [
        load_memory(program.memories[memory_name], context)
        for memory_name in page.memories
        if memory_name in program.memories
    ]
    memory_snapshots: Dict[str, Any] = {}
    if context.memory_engine:
        for memory_name in page.memories:
            context.memory_engine.record_conversation(
                memory_name, f"Visited page {page.name}", role="system"
            )
            memory_snapshots[memory_name] = [
                item.__dict__ for item in context.memory_engine.get_recent(memory_name, limit=5)
            ]

    ui_repr = None
    if renderer:
        ui_repr = renderer.from_ir_page(page)
        if context.tracer and ui_repr:
            context.tracer.record_ui_sections(len(ui_repr.sections))

    return {
        "page": page.name,
        "route": page.route,
        "title": page.title,
        "ai_calls": ai_results,
        "agents": agent_results,
        "memories": memory_results,
        "memory_items": memory_snapshots,
        "ui": ui_repr.__dict__ if ui_repr else None,
        "status": "ok",
    }
