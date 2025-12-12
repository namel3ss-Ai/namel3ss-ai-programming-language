from __future__ import annotations

import asyncio
from typing import Any

from ...memory.engine import MemoryEngine
from ...memory.models import MemorySpaceConfig, MemoryType
from ...runtime.eventlog import EventLogger
from ..graph import FlowRuntimeContext
from .context import get_user_context

__all__ = ["FlowEngineRuntimeMixin"]


class FlowEngineRuntimeMixin:
    def _build_runtime_context(self, context, stream_callback: Any = None) -> FlowRuntimeContext:
        mem_engine = context.memory_engine
        if mem_engine is None and self.program and self.program.memories:
            spaces = [
                MemorySpaceConfig(
                    name=mem.name,
                    type=MemoryType(mem.memory_type or MemoryType.CONVERSATION),
                    retention_policy=mem.retention,
                )
                for mem in self.program.memories.values()
            ]
            mem_engine = MemoryEngine(spaces=spaces)
        mem_stores = getattr(context, "memory_stores", None)
        user_context = get_user_context(getattr(context, "user_context", None))
        if getattr(context, "metadata", None) is not None and user_context.get("id") and "user_id" not in context.metadata:
            context.metadata["user_id"] = user_context.get("id")
        try:
            context.vectorstores = self.vector_registry
        except Exception:
            pass
        return FlowRuntimeContext(
            program=self.program,
            model_registry=self.model_registry,
            tool_registry=self.tool_registry,
            agent_runner=self.agent_runner,
            router=self.router,
            tracer=context.tracer,
            metrics=context.metrics or self.metrics,
            secrets=context.secrets or self.secrets,
            memory_engine=mem_engine,
            memory_stores=mem_stores,
            rag_engine=context.rag_engine,
            frames=self.frame_registry,
            vectorstores=self.vector_registry,
            rag_pipelines=getattr(self.program, "rag_pipelines", {}),
            graphs=getattr(self.program, "graphs", {}),
            graph_summaries=getattr(self.program, "graph_summaries", {}),
            graph_engine=self.graph_engine,
            records=getattr(self.program, "records", {}) if self.program else {},
            auth_config=getattr(self.program, "auth", None) if self.program else None,
            user_context=user_context,
            execution_context=context,
            max_parallel_tasks=self.max_parallel_tasks,
            parallel_semaphore=asyncio.Semaphore(self.max_parallel_tasks),
            variables=None,
            event_logger=EventLogger(
                self.frame_registry,
                session_id=context.metadata.get("session_id") if context.metadata else context.request_id,
            ),
            stream_callback=stream_callback or self.global_stream_callback,
            provider_cache=context.provider_cache or None,
        )
