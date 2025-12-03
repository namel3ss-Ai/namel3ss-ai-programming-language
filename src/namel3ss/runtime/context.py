"""
Execution context and stubbed executors for the runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..metrics.tracker import MetricsTracker
from ..secrets.manager import SecretsManager
from ..ir import IRApp, IRAgent, IRAiCall, IRMemory, IRPage, IRProgram
from ..tools.registry import ToolRegistry
from ..memory.engine import MemoryEngine
from ..obs.tracer import Tracer
from ..rag.engine import RAGEngine


@dataclass
class ExecutionContext:
    app_name: str
    request_id: str
    user_input: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
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
    messages = [{"role": "user", "content": ai_call.input_source or (context.user_input or "")}]
    provider_model = cfg.model or selection.model_name
    invocation = provider.invoke(messages=messages, model=provider_model)
    result = execute_ai_call(ai_call, context)
    result.update(
        {
            "provider_result": invocation,
            "resolved_model": selection.model_name,
            "provider_name": selection.provider_name,
        }
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
            prompt=ai_call.input_source or "",
            response_preview=str(invocation.get("result", "")),
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
