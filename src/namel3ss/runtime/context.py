"""
Execution context and stubbed executors for the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..ir import IRAgent, IRAiCall, IRApp, IRMemory, IRPage, IRProgram
from ..memory.engine import MemoryEngine
from ..metrics.tracker import MetricsTracker
from ..errors import Namel3ssError
from ..obs.tracer import Tracer
from ..rag.engine import RAGEngine
from ..secrets.manager import SecretsManager
from ..tools.registry import ToolRegistry
from ..tools.registry import build_ai_tool_specs
import json
import urllib.error
import urllib.request


@dataclass
class ExecutionContext:
    app_name: str
    request_id: str
    user_input: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    memory_engine: Optional[MemoryEngine] = None
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


def execute_ai_call_with_registry(
    ai_call: IRAiCall,
    registry: ModelRegistry,
    router: ModelRouter,
    context: ExecutionContext,
) -> Dict[str, Any]:
    """Execute an AI call through the model registry."""

    selection = router.select_model(logical_name=ai_call.model_name)
    cfg = registry.get_model_config(selection.model_name)
    provider = registry.get_provider_for_model(selection.model_name)
    messages: list[Dict[str, str]] = []

    session_id = context.metadata.get("session_id") if context.metadata else None
    session_id = session_id or context.request_id or "default"

    if getattr(ai_call, "system_prompt", None):
        messages.append({"role": "system", "content": ai_call.system_prompt or ""})

    # Load conversation history if memory is attached and available
    history: list[dict] = []
    if getattr(ai_call, "memory_name", None) and context.memory_engine:
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

    provider_model = cfg.model or selection.model_name

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
        # Allow tests to supply mocked tool results via context.metadata
        mock_tools = (context.metadata or {}).get("mock_tool_results") if context.metadata else None
        if isinstance(mock_tools, dict) and tool_name in mock_tools:
            return mock_tools[tool_name]
        headers = {}
        for hk, hv in (tool_cfg.headers or {}).items():
            headers[hk] = str(hv) if not isinstance(hv, dict) else json.dumps(hv)
        method = (tool_cfg.method or "GET").upper()
        try:
            url = tool_cfg.url_template.format(**{k: str(v) for k, v in args.items()})
        except KeyError as exc:
            missing = str(exc).strip("'\"")
            raise Namel3ssError(f"N3F-965: Missing arg '{missing}' for tool '{tool_cfg.name}' url_template.")
        body_bytes: bytes | None = None
        if tool_cfg.body_template is not None:
            body_val = tool_cfg.body_template
            if isinstance(body_val, (dict, list)):
                body_bytes = json.dumps(body_val).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body_val, str):
                body_bytes = body_val.encode("utf-8")
        try:
            return _http_json_request(method, url, headers, body_bytes)
        except urllib.error.HTTPError as exc:  # pragma: no cover - fallback
            raise Namel3ssError(f"N3F-963: Tool '{tool_cfg.name}' failed with HTTP {exc.code}")
        except urllib.error.URLError as exc:  # pragma: no cover - fallback
            raise Namel3ssError(f"N3F-963: Tool '{tool_cfg.name}' failed with HTTP error: {exc}")

    tools_payload = None
    if getattr(ai_call, "tools", None):
        if not context.tool_registry:
            raise Namel3ssError(f"N3F-965: Tools unavailable for AI '{ai_call.name}' (no registry).")
        specs = build_ai_tool_specs(ai_call.tools, context.tool_registry)
        tools_payload = [
            {"type": "function", "function": {"name": spec.name, "description": spec.description, "parameters": spec.parameters}}
            for spec in specs
        ]

    max_tool_calls = 3
    tool_calls_used = 0
    while True:
        invocation = provider.invoke(messages=messages, model=provider_model, tools=tools_payload)
        raw = invocation.raw if hasattr(invocation, "raw") else {}
        tool_calls = []
        if isinstance(raw, dict):
            tool_calls = raw.get("tool_calls") or raw.get("function_calls") or []
        if not tool_calls:
            result = execute_ai_call(ai_call, context)
            result.update(
                {
                    "provider_result": invocation.to_dict() if hasattr(invocation, "to_dict") else invocation,
                    "resolved_model": selection.model_name,
                    "provider_name": selection.provider_name,
                }
            )
            # Append conversation history if memory configured
            if getattr(ai_call, "memory_name", None) and context.memory_engine:
                try:
                    assistant_content = invocation.text if hasattr(invocation, "text") else str(invocation)
                    context.memory_engine.append_conversation(
                        ai_call.memory_name or "",
                        messages=[
                            user_message,
                            {"role": "assistant", "content": assistant_content},
                        ],
                        session_id=session_id,
                    )
                except Exception:
                    pass
            return result

        tool_calls_used += 1
        if tool_calls_used > max_tool_calls:
            raise Namel3ssError(f"N3F-971: Max tool call depth exceeded for AI '{ai_call.name}'.")
        tool_call = tool_calls[0]
        tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name") if isinstance(tool_call, dict) else None
        tool_args = tool_call.get("arguments") or tool_call.get("args") or {}
        tool_result = _execute_tool_by_name(tool_name, tool_args or {})
        # Append tool result message
        messages.append(
            {
                "role": "tool",
                "name": tool_name,
                "content": json.dumps(tool_result),
            }
        )

    # Append conversation history if memory configured
    if getattr(ai_call, "memory_name", None) and context.memory_engine:
        try:
            assistant_content = (
                invocation.get("result", None) if hasattr(invocation, "get") else None
            ) or (getattr(invocation, "text", None) if hasattr(invocation, "text") else None) or str(invocation)
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
            response_preview=str(invocation.get("result", "") if hasattr(invocation, "get") else ""),
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
