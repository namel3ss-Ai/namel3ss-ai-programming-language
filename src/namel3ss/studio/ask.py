"""
Helpers to power the Ask Studio endpoint.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..ai.config import default_global_ai_config
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..ai.models import ModelResponse
from ..errors import Namel3ssError


def _call_model(messages: List[Dict[str, str]], model: str | None = None, router: ModelRouter | None = None) -> ModelResponse:
    """
    Thin wrapper so tests can monkeypatch model invocations.
    """
    active_router = router or ModelRouter(ModelRegistry(), default_global_ai_config())
    return active_router.generate(messages=messages, model=model)


def _summarize_entity(kind: str, entity: Dict[str, Any] | None) -> str:
    if not entity:
        return ""
    lines = [f"{kind}: {entity.get('name') or ''}"]
    for key, val in entity.items():
        if key in {"kind", "name", "id"}:
            continue
        if val is None or val == [] or val == {}:
            continue
        try:
            lines.append(f"- {key}: {val}")
        except Exception:
            continue
    return "\n".join(lines)


def _summarize_logs(logs: List[Dict[str, Any]], limit: int = 10) -> str:
    if not logs:
        return "No recent logs."
    entries = logs[-limit:]
    parts = []
    for entry in entries:
        level = entry.get("level") or "info"
        event = entry.get("event") or "event"
        msg = entry.get("details") or entry.get("message") or ""
        parts.append(f"[{level}] {event} {msg}".strip())
    return "\n".join(parts)


def _summarize_status(status: Dict[str, Any] | None) -> str:
    if not status:
        return ""
    ir_status = status.get("ir_status")
    ir_err = status.get("ir_error") or {}
    err_line = ""
    if ir_status == "error":
        loc = [ir_err.get("file"), ir_err.get("line"), ir_err.get("column")]
        loc_txt = ":".join([str(x) for x in loc if x is not None])
        err_line = f"IR error: {ir_err.get('message','')} {loc_txt}".strip()
    return "\n".join(
        [
            f"IR status: {ir_status}",
            err_line,
            f"AI files: {status.get('ai_files')}",
            f"Watcher: {'active' if status.get('watcher_active') else 'inactive'}",
        ]
    )


def _mode_instructions(mode: str) -> str:
    if mode == "generate_flow":
        return (
            "Task: generate a Namel3ss flow snippet.\n"
            '- Use English-first headers like: flow is "checkout".\n'
            "- Include steps with ai/tool/memory usage as needed.\n"
            "- No braces {}; indent blocks."
        )
    if mode == "generate_page":
        return (
            "Task: generate a Namel3ss page snippet.\n"
            '- Use: page is "home" at "/".\n'
            "- Include UI sections/components and bindings to flows or ai calls.\n"
            "- No braces {}; indent blocks."
        )
    if mode == "generate_tool":
        return (
            "Task: generate a Namel3ss tool snippet.\n"
            '- Use: tool is "charge_card": method/url/auth/body/fields.\n'
            "- Keep payloads as JSON if needed.\n"
            "- No braces {}; indent blocks."
        )
    if mode == "generate_agent":
        return (
            "Task: generate an agent snippet.\n"
            '- Use: agent is "helper": goal/tools/memory/model.\n'
            "- No braces {}; indent blocks."
        )
    if mode == "generate_rag":
        return (
            "Task: generate a RAG pipeline snippet.\n"
            '- Use: rag pipeline is "support_rag": stages like rewrite, vector_retrieve, rerank, answer.\n'
            "- Describe indexes/stores/models clearly.\n"
            "- No braces {}; indent blocks."
        )
    return (
        "Task: explain or suggest fixes. Provide concise guidance.\n"
        "If you include DSL, follow English-first headers and avoid braces {}."
    )


def build_prompt(
    question: str,
    *,
    status: Dict[str, Any] | None = None,
    entity: Dict[str, Any] | None = None,
    logs: List[Dict[str, Any]] | None = None,
    flow_run: Dict[str, Any] | None = None,
    memory: Dict[str, Any] | None = None,
    memory_state: Dict[str, Any] | None = None,
    mode: str = "explain",
) -> str:
    """
    Compose a single prompt that includes DSL reminders, program context, and the user's question.
    """
    sections: list[str] = []
    sections.append(
        "You are Ask Studio, an assistant for the Namel3ss AI programming language and Studio.\n"
        "Language rules:\n"
        '- English-first DSL headers like: app is "name", page is "home" at "/".\n'
        '- Do NOT suggest legacy syntax like app \"x\": or db_get.\n'
        '- No braces {} in DSL snippets; use indentation.\n'
        "Return explanations and suggested DSL snippets, but do NOT modify files.\n"
        + _mode_instructions(mode)
    )
    if status:
        sections.append("Project status:\n" + _summarize_status(status))
    if entity:
        sections.append("Entity context:\n" + _summarize_entity(entity.get("kind", "entity"), entity))
    if flow_run:
        sections.append("Flow run:\n" + str(flow_run))
    if memory:
        sections.append("Memory plan:\n" + str(memory))
    if memory_state:
        sections.append("Memory state:\n" + str(memory_state))
    if logs:
        sections.append("Recent logs:\n" + _summarize_logs(logs))
    sections.append("Question:\n" + question)
    sections.append(f"Mode: {mode}")
    return "\n\n".join([s for s in sections if s])


def _infer_kind(code: str) -> str:
    first_line = ""
    for line in code.splitlines():
        if line.strip():
            first_line = line.strip().lower()
            break
    if first_line.startswith("flow is"):
        return "flow"
    if first_line.startswith("page is"):
        return "page"
    if first_line.startswith("tool is"):
        return "tool"
    if first_line.startswith("agent is"):
        return "agent"
    if first_line.startswith("rag pipeline is"):
        return "rag"
    if first_line.startswith("memory is") or first_line.startswith("memory \"") or first_line.startswith("memory "):
        return "memory"
    if first_line.startswith("app is"):
        return "app"
    return "other"


def extract_snippets(text: str) -> List[Dict[str, str]]:
    """
    Heuristic extraction of fenced code blocks as suggested snippets.
    """
    snippets: List[Dict[str, str]] = []
    if not text:
        return snippets
    parts = text.split("```")
    for idx in range(1, len(parts), 2):
        code = parts[idx].strip()
        if not code:
            continue
        before = parts[idx - 1] if idx - 1 >= 0 else ""
        after = parts[idx + 1] if idx + 1 < len(parts) else ""
        title: str | None = None
        note: str | None = None
        before_lines = [ln.strip() for ln in before.splitlines() if ln.strip()]
        if before_lines:
            possible_title = before_lines[-1]
            if 3 <= len(possible_title) <= 120:
                title = possible_title
        after_lines = [ln.strip() for ln in after.splitlines() if ln.strip()]
        if after_lines:
            note = after_lines[0]
        snippets.append(
            {
                "title": title or "Suggested snippet",
                "dsl": code,
                "kind": _infer_kind(code),
                "notes": note,
            }
        )
    return snippets


def ask_studio(
    question: str,
    *,
    status: Dict[str, Any] | None = None,
    entity: Dict[str, Any] | None = None,
    logs: List[Dict[str, Any]] | None = None,
    flow_run: Dict[str, Any] | None = None,
    memory: Dict[str, Any] | None = None,
    memory_state: Dict[str, Any] | None = None,
    model: str | None = None,
    router: ModelRouter | None = None,
    mode: str = "explain",
) -> Dict[str, Any]:
    prompt = build_prompt(
        question,
        status=status,
        entity=entity,
        logs=logs,
        flow_run=flow_run,
        memory=memory,
        memory_state=memory_state,
        mode=mode,
    )
    try:
        response = _call_model(
            messages=[
                {
                    "role": "system",
                    "content": "You are Ask Studio, a helpful assistant for Namel3ss developers. "
                    "Always return clear explanations and, when asked to generate, produce valid Namel3ss DSL using English-first headers. "
                    "Do not include braces {} unless inside JSON payloads.",
                },
                {"role": "user", "content": prompt},
            ],
            model=model,
            router=router,
        )
    except Namel3ssError as exc:
        raise
    except Exception as exc:
        raise Namel3ssError(f"Ask Studio failed: {exc}") from exc
    answer = getattr(response, "text", None) or response.get("result") if isinstance(response, dict) else None
    if not answer and hasattr(response, "to_dict"):
        answer = response.to_dict().get("result")
    snippets = extract_snippets(answer or "")
    return {"answer": answer or "", "suggested_snippets": snippets, "mode": mode}
