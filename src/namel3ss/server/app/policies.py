"""Memory and policy helpers used by the FastAPI app."""

from __future__ import annotations

from typing import Any, Dict


def short_term_store_name(mem_cfg: Any) -> str:
    short_cfg = getattr(mem_cfg, "short_term", None)
    store = getattr(short_cfg, "store", None) if short_cfg else None
    if store:
        return store
    store = getattr(mem_cfg, "store", None)
    return store or "default_memory"


def long_term_store_name(mem_cfg: Any) -> str | None:
    long_cfg = getattr(mem_cfg, "long_term", None)
    return getattr(long_cfg, "store", None) if long_cfg else None


def profile_store_name(mem_cfg: Any) -> str | None:
    profile_cfg = getattr(mem_cfg, "profile", None)
    return getattr(profile_cfg, "store", None) if profile_cfg else None


def long_term_key(ai_id: str) -> str:
    return f"{ai_id}::long_term"


def profile_key(ai_id: str) -> str:
    return f"{ai_id}::profile"


def default_scope(kind: str, user_id: str | None) -> str:
    if kind == "short_term":
        return "per_session"
    if kind in {"long_term", "profile"}:
        return "per_user" if user_id else "per_session"
    return "per_session"


def compute_scope_keys(
    kind: str,
    cfg_scope: str | None,
    base_key: str,
    session_id: str,
    user_id: str | None,
) -> dict[str, Any]:
    default = default_scope(kind, user_id)
    scope = (cfg_scope or default) or "per_session"
    fallback = False
    if scope == "per_user":
        if user_id:
            session_key = f"user:{user_id}"
        else:
            session_key = session_id
            scope = "per_session"
            fallback = True
    elif scope == "shared":
        session_key = "shared"
    else:
        session_key = session_id
    return {
        "ai_key": base_key,
        "session_key": session_key,
        "scope": scope,
        "fallback": fallback,
        "requested": cfg_scope or default,
    }


def build_policy_info(
    kind: str,
    cfg: Any | None,
    scope_info: dict[str, Any] | None,
    user_id: str | None,
) -> dict[str, Any] | None:
    if cfg is None or scope_info is None:
        return None
    policy = {
        "scope": scope_info["scope"],
        "requested_scope": scope_info["requested"],
        "scope_fallback": scope_info["fallback"],
        "retention_days": getattr(cfg, "retention_days", None),
        "pii_policy": getattr(cfg, "pii_policy", None) or "none",
    }
    if scope_info["fallback"] and scope_info["requested"] == "per_user" and not user_id:
        policy["scope_note"] = "Using per_session fallback (no user identity)."
    return policy


def legacy_session_payload(ai_id: str, session_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    kinds = state.get("kinds", {})
    short_payload = kinds.get("short_term") or {}
    long_payload = kinds.get("long_term")
    profile_payload = kinds.get("profile")
    episodic_payload = kinds.get("episodic")
    semantic_payload = kinds.get("semantic")
    return {
        "ai": ai_id,
        "session": session_id,
        "user_id": state.get("user_id"),
        "short_term": {
            "window": short_payload.get("window"),
            "turns": short_payload.get("turns", []),
        },
        "long_term": (
            {"store": long_payload.get("store"), "items": long_payload.get("items", [])} if long_payload else None
        ),
        "profile": (
            {"store": profile_payload.get("store"), "facts": profile_payload.get("facts", [])}
            if profile_payload
            else None
        ),
        "episodic": episodic_payload,
        "semantic": semantic_payload,
        "policies": state.get("policies", {}),
        "last_recall_snapshot": state.get("recall_snapshot"),
        "kinds": kinds,
    }


__all__ = [
    "build_policy_info",
    "compute_scope_keys",
    "default_scope",
    "legacy_session_payload",
    "long_term_key",
    "long_term_store_name",
    "profile_key",
    "profile_store_name",
    "short_term_store_name",
]
