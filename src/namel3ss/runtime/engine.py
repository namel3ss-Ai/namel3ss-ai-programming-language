"""
Runtime engine for Namel3ss V3.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from .. import ir, lexer, parser
from ..agent.engine import AgentRunner
from ..agent.teams import AgentTeamRunner
from ..ai.config import default_global_ai_config
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..config import load_config
from ..distributed.queue import JobQueue, global_job_queue
from ..distributed.scheduler import JobScheduler
from ..errors import Namel3ssError
from ..flows.engine import FlowEngine
from ..flows.triggers import TriggerManager
from ..ir import IRProgram
from ..macros import MacroExpander, default_macro_ai_callback, expand_macros
from ..memory.engine import MemoryEngine, PersistentMemoryEngine, ShardedMemoryEngine
from ..memory.models import MemorySpaceConfig, MemoryType
from ..metrics.tracker import MetricsTracker
from ..obs.tracer import Tracer
from ..optimizer.apply import SuggestionApplier
from ..optimizer.engine import OptimizerEngine
from ..optimizer.overlays import OverlayStore
from ..optimizer.storage import OptimizerStorage
from ..plugins.registry import PluginRegistry
from ..rag.engine import RAGEngine
from ..secrets.manager import SecretsManager
from ..tools.builtin import register_builtin_tools
from ..tools.registry import ToolRegistry
from ..ui.renderer import UIRenderer
from .context import (
    ExecutionContext,
    execute_app,
    execute_page,
    load_memory,
)
from .graph import Graph, GraphEdge, GraphNode, NodeType


class Engine:
    def __init__(
        self,
        program: IRProgram,
        metrics_tracker: Optional[MetricsTracker] = None,
        trigger_manager: Optional[TriggerManager] = None,
        plugins_dir: Optional[Path] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> None:
        self.program = program
        self.secrets_manager = SecretsManager()
        self.config = load_config()
        from ..memory.registry import build_memory_store_registry
        self.memory_stores = build_memory_store_registry(self.secrets_manager)
        self.metrics_tracker = metrics_tracker or MetricsTracker()
        self.job_queue: JobQueue = global_job_queue
        self.scheduler = JobScheduler(self.job_queue)
        self.trigger_manager = trigger_manager or TriggerManager(
            job_queue=self.job_queue,
            secrets=self.secrets_manager,
            tracer=Tracer(),
            metrics=self.metrics_tracker,
        )
        self.plugins_dir = plugins_dir or Path(self.secrets_manager.get("N3_PLUGINS_DIR") or "plugins")
        self.plugin_registry = plugin_registry or PluginRegistry(self.plugins_dir)
        self.registry = self._build_registry(program)
        self.router = ModelRouter(self.registry, default_global_ai_config())
        self.memory_engine = self._build_memory_engine(program)
        if hasattr(self.memory_engine, "trigger_manager"):
            self.memory_engine.trigger_manager = self.trigger_manager
        self.rag_engine = self._build_rag_engine()
        self.tool_registry = self._build_tool_registry()
        self.agent_runner = AgentRunner(
            program=self.program,
            model_registry=self.registry,
            tool_registry=self.tool_registry,
            router=self.router,
        )
        self.team_runner = AgentTeamRunner(
            program=self.program,
            model_registry=self.registry,
            router=self.router,
            tool_registry=self.tool_registry,
        )
        self.flow_engine = FlowEngine(
            program=self.program,
            model_registry=self.registry,
            tool_registry=self.tool_registry,
            agent_runner=self.agent_runner,
            router=self.router,
            metrics=self.metrics_tracker,
            secrets=self.secrets_manager,
        )
        self.optimizer_storage = OptimizerStorage(Path(self.secrets_manager.get("N3_OPTIMIZER_DB") or "optimizer.db"))
        self.overlay_store = OverlayStore(Path(self.secrets_manager.get("N3_OPTIMIZER_OVERLAYS") or "optimizer_overlays.json"))
        self.optimizer_engine = OptimizerEngine(
            storage=self.optimizer_storage,
            metrics=self.metrics_tracker,
            memory_engine=self.memory_engine,
            tracer=Tracer(),
            router=self.router,
            secrets=self.secrets_manager,
        )
        self.suggestion_applier = SuggestionApplier(self.overlay_store, self.optimizer_storage, tracer=Tracer())
        self._load_plugins()
        self.ui_renderer = UIRenderer()
        self.graph = self.build_graph(program)
        self._validate_memory_stores()

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        metrics_tracker: Optional[MetricsTracker] = None,
        trigger_manager: Optional[TriggerManager] = None,
        plugins_dir: Optional[Path] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> "Engine":
        source_path = Path(path)
        source = source_path.read_text(encoding="utf-8")
        return cls(
            cls._load_program(source, filename=str(source_path)),
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugins_dir=plugins_dir,
            plugin_registry=plugin_registry,
        )

    @classmethod
    def from_source(
        cls,
        source: str,
        filename: str = "<string>",
        metrics_tracker: Optional[MetricsTracker] = None,
        trigger_manager: Optional[TriggerManager] = None,
        plugins_dir: Optional[Path] = None,
        plugin_registry: Optional[PluginRegistry] = None,
    ) -> "Engine":
        return cls(
            cls._load_program(source, filename=filename),
            metrics_tracker=metrics_tracker,
            trigger_manager=trigger_manager,
            plugins_dir=plugins_dir,
            plugin_registry=plugin_registry,
        )

    @staticmethod
    def _load_program(source: str, filename: str) -> IRProgram:
        tokens = lexer.Lexer(source, filename=filename).tokenize()
        module = parser.Parser(tokens).parse_module()
        module = expand_macros(module, default_macro_ai_callback)
        return ir.ast_to_ir(module)

    def build_graph(self, program: IRProgram) -> Graph:
        graph = Graph()

        for app in program.apps.values():
            graph.add_node(
                GraphNode(id=f"app:{app.name}", type=NodeType.APP, label=app.name)
            )
        for page in program.pages.values():
            graph.add_node(
                GraphNode(id=f"page:{page.name}", type=NodeType.PAGE, label=page.name)
            )
        for model in program.models.values():
            graph.add_node(
                GraphNode(
                    id=f"model:{model.name}", type=NodeType.MODEL, label=model.name
                )
            )
        for ai_call in program.ai_calls.values():
            graph.add_node(
                GraphNode(
                    id=f"ai:{ai_call.name}", type=NodeType.AI_CALL, label=ai_call.name
                )
            )
        for agent in program.agents.values():
            graph.add_node(
                GraphNode(
                    id=f"agent:{agent.name}", type=NodeType.AGENT, label=agent.name
                )
            )
        for memory in program.memories.values():
            graph.add_node(
                GraphNode(
                    id=f"memory:{memory.name}",
                    type=NodeType.MEMORY,
                    label=memory.name,
                )
            )
        for flow in program.flows.values():
            graph.add_node(
                GraphNode(id=f"flow:{flow.name}", type=NodeType.FLOW, label=flow.name)
            )
            for step in flow.steps:
                if step.kind == "ai" and f"ai:{step.target}" in graph.nodes:
                    graph.add_edge(
                        GraphEdge(
                            source=f"flow:{flow.name}",
                            target=f"ai:{step.target}",
                            label="flow_step",
                        )
                    )
                if step.kind == "agent" and f"agent:{step.target}" in graph.nodes:
                    graph.add_edge(
                        GraphEdge(
                            source=f"flow:{flow.name}",
                            target=f"agent:{step.target}",
                            label="flow_step",
                        )
                    )
                if step.kind == "tool":
                    tool_node_id = f"tool:{step.target}"
                    if tool_node_id not in graph.nodes:
                        graph.add_node(
                            GraphNode(
                                id=tool_node_id,
                                type=NodeType.TOOL,
                                label=step.target,
                            )
                        )
                    graph.add_edge(
                        GraphEdge(
                            source=f"flow:{flow.name}",
                            target=tool_node_id,
                            label="flow_step",
                        )
                    )

        for app in program.apps.values():
            if app.entry_page and f"page:{app.entry_page}" in graph.nodes:
                graph.add_edge(
                    GraphEdge(
                        source=f"app:{app.name}",
                        target=f"page:{app.entry_page}",
                        label="entry_page",
                    )
                )

        for ai_call in program.ai_calls.values():
            if ai_call.model_name and f"model:{ai_call.model_name}" in graph.nodes:
                graph.add_edge(
                    GraphEdge(
                        source=f"ai:{ai_call.name}",
                        target=f"model:{ai_call.model_name}",
                        label="uses_model",
                    )
                )

        for page in program.pages.values():
            for ai_call_name in page.ai_calls:
                ref_id = f"ai_ref:{page.name}:{ai_call_name}"
                graph.add_node(
                    GraphNode(
                        id=ref_id,
                        type=NodeType.AI_CALL_REF,
                        label=ai_call_name,
                        data={"page": page.name},
                    )
                )
                graph.add_edge(
                    GraphEdge(
                        source=f"page:{page.name}", target=ref_id, label="ai_call"
                    )
                )
                if f"ai:{ai_call_name}" in graph.nodes:
                    graph.add_edge(
                        GraphEdge(
                            source=ref_id, target=f"ai:{ai_call_name}", label="invokes"
                        )
                    )
            for agent_name in page.agents:
                if f"agent:{agent_name}" in graph.nodes:
                    graph.add_edge(
                        GraphEdge(
                            source=f"page:{page.name}",
                            target=f"agent:{agent_name}",
                            label="agent",
                        )
                    )
            for memory_name in page.memories:
                if f"memory:{memory_name}" in graph.nodes:
                    graph.add_edge(
                        GraphEdge(
                            source=f"page:{page.name}",
                            target=f"memory:{memory_name}",
                            label="memory",
                        )
                    )

        return graph

    def _build_registry(self, program: IRProgram) -> ModelRegistry:
        registry = ModelRegistry(secrets=self.secrets_manager, providers_config=self.config.providers_config)
        for model in program.models.values():
            registry.register_model(model.name, model.provider)
        # Ensure agents or other components may register providers later.
        return registry

    def _build_memory_engine(self, program: IRProgram) -> MemoryEngine:
        spaces = [
            MemorySpaceConfig(
                name=mem.name,
                type=MemoryType(mem.memory_type or MemoryType.CONVERSATION),
            )
            for mem in program.memories.values()
        ]
        if self.secrets_manager.is_enabled("N3_ENABLE_PERSISTENT_MEMORY"):
            db_path = self.secrets_manager.get("N3_MEMORY_DB_PATH") or "namel3ss_memory.db"
            return PersistentMemoryEngine(spaces, db_path=db_path)
        return ShardedMemoryEngine(spaces)

    def _build_rag_engine(self) -> RAGEngine:
        engine = RAGEngine(secrets=self.secrets_manager, metrics=self.metrics_tracker, tracer=Tracer(), memory_engine=self.memory_engine)
        engine.index_documents(
            "default",
            [
                "Welcome to Namel3ss studio.",
                "Namel3ss supports AI-native applications.",
                "Memory and RAG power contextual responses.",
            ],
        )
        return engine

    def _build_tool_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        register_builtin_tools(registry)
        return registry

    def _validate_memory_stores(self) -> None:
        available = set(self.memory_stores.keys())
        for ai_call in self.program.ai_calls.values():
            mem_cfg = getattr(ai_call, "memory", None)
            if mem_cfg:
                store_names = []
                if hasattr(mem_cfg, "referenced_store_names"):
                    store_names = mem_cfg.referenced_store_names()
                else:
                    store_names = [getattr(mem_cfg, "store", None)]
                for store_name in store_names:
                    resolved = store_name or "default_memory"
                    if resolved not in available:
                        raise Namel3ssError(
                            f"N3L-1201: Memory store '{resolved}' referenced on AI '{ai_call.name}' is not configured for this project."
                        )

    def _build_default_execution_context(self) -> ExecutionContext:
        return ExecutionContext(
            app_name="__ui__",
            request_id=str(uuid4()),
            memory_engine=self.memory_engine,
            memory_stores=self.memory_stores,
            rag_engine=self.rag_engine,
            tracer=Tracer(),
            tool_registry=self.tool_registry,
            metrics=self.metrics_tracker,
            secrets=self.secrets_manager,
            trigger_manager=self.trigger_manager,
        )

    def _load_plugins(self) -> None:
        from ..plugins.sdk import PluginSDK

        sdk = PluginSDK.from_engine(self)
        for info in self.plugin_registry.discover():
            if not info.enabled or not info.compatible:
                continue
            self.plugin_registry.load(info.id, sdk)

    def run_app(
        self,
        app_name: str,
        context: Optional[ExecutionContext] = None,
        include_trace: bool = False,
        principal_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        if app_name not in self.program.apps:
            raise Namel3ssError(f"Unknown app '{app_name}'")

        app = self.program.apps[app_name]
        if context is None:
            context = ExecutionContext(
                app_name=app_name,
                request_id=str(uuid4()),
                memory_engine=self.memory_engine,
                memory_stores=self.memory_stores,
                rag_engine=self.rag_engine,
                tracer=Tracer(),
                tool_registry=self.tool_registry,
                metrics=self.metrics_tracker,
                secrets=self.secrets_manager,
                trigger_manager=self.trigger_manager,
            )
        if context.tracer:
            context.tracer.start_app(app_name, role=principal_role)

        app_result = execute_app(app, context)
        agent_results: Dict[str, Any] = {}
        memory_results = {
            name: load_memory(memory, context)
            for name, memory in self.program.memories.items()
        }
        page_result = None
        if app.entry_page and app.entry_page in self.program.pages:
            page = self.program.pages[app.entry_page]
            page_result = execute_page(
                page,
                self.program,
                self.registry,
                self.router,
                context,
                renderer=self.ui_renderer,
            )
            page_agent_runs = []
            for agent_name in page.agents:
                result = self.agent_runner.run(
                    agent_name,
                    context,
                    page_ai_fallback=page.ai_calls[0] if page.ai_calls else None,
                )
                agent_results[agent_name] = asdict(result)
                page_agent_runs.append(asdict(result))
            page_result["agent_runs"] = page_agent_runs
        remaining_agents = set(self.program.agents.keys()) - set(agent_results.keys())
        for agent_name in remaining_agents:
            result = self.agent_runner.run(agent_name, context)
            agent_results[agent_name] = asdict(result)
        response: Dict[str, Any] = {
            "app": app_result,
            "agents": agent_results,
            "memories": memory_results,
            "entry_page": page_result,
            "graph": {
                "nodes": list(self.graph.nodes.keys()),
                "edges": [
                    {"source": edge.source, "target": edge.target, "label": edge.label}
                    for edge in self.graph.edges
                ],
            },
        }
        if include_trace and context.tracer and context.tracer.last_trace:
            response["trace"] = asdict(context.tracer.last_trace)
        return response

    def execute_agent(
        self, agent_name: str, context: Optional[ExecutionContext] = None
    ) -> Dict[str, Any]:
        if context is None:
            context = ExecutionContext(
                app_name="__agent__",
                request_id=str(uuid4()),
                memory_engine=self.memory_engine,
                memory_stores=self.memory_stores,
                rag_engine=self.rag_engine,
                tracer=Tracer(),
                tool_registry=self.tool_registry,
                secrets=self.secrets_manager,
                trigger_manager=self.trigger_manager,
            )
            if context.tracer:
                context.tracer.start_app("__agent__")
        result = self.agent_runner.run(agent_name, context)
        return asdict(result)

    def execute_page_public(self, page_name: str) -> Dict[str, Any]:
        if page_name not in self.program.pages:
            raise Namel3ssError(f"Unknown page '{page_name}'")
        page = self.program.pages[page_name]
        context = ExecutionContext(
            app_name="__page__",
            request_id=str(uuid4()),
            memory_engine=self.memory_engine,
            memory_stores=self.memory_stores,
            rag_engine=self.rag_engine,
            tracer=Tracer(),
            tool_registry=self.tool_registry,
            metrics=self.metrics_tracker,
            secrets=self.secrets_manager,
            trigger_manager=self.trigger_manager,
        )
        if context.tracer:
            context.tracer.start_app("__page__")
        page_result = execute_page(
            page,
            self.program,
            self.registry,
            self.router,
            context,
            renderer=self.ui_renderer,
        )
        return page_result

    def execute_flow(
        self,
        flow_name: str,
        context: Optional[ExecutionContext] = None,
        principal_role: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.a_execute_flow(
                flow_name,
                context=context,
                principal_role=principal_role,
                payload=payload,
            )
        )

    async def a_execute_flow(
        self,
        flow_name: str,
        context: Optional[ExecutionContext] = None,
        principal_role: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if flow_name not in self.program.flows:
            raise Namel3ssError(f"Unknown flow '{flow_name}'")
        if context is None:
            context = ExecutionContext(
                app_name="__flow__",
                request_id=str(uuid4()),
                memory_engine=self.memory_engine,
                memory_stores=self.memory_stores,
                rag_engine=self.rag_engine,
                tracer=Tracer(),
                tool_registry=self.tool_registry,
                metrics=self.metrics_tracker,
                secrets=self.secrets_manager,
                trigger_manager=self.trigger_manager,
            )
            if context.tracer:
                context.tracer.start_app("__flow__", role=principal_role)
        flow = self.program.flows[flow_name]
        initial_state = {}
        if payload:
            initial_state = payload.get("state") or payload.get("payload") or {}
            context.metadata.update(payload)
        result = await self.flow_engine.run_flow_async(flow, context, initial_state=initial_state)
        payload_out = result.to_dict() if hasattr(result, "to_dict") else asdict(result)
        if context.tracer and context.tracer.last_trace:
            payload_out["trace"] = asdict(context.tracer.last_trace)
        return payload_out

    async def execute_flow_async(self, flow_name: str) -> str:
        job = self.scheduler.schedule_flow(flow_name, {})
        return job.id

    async def execute_agent_async(self, agent_name: str) -> str:
        job = self.scheduler.schedule_agent(agent_name, {})
        return job.id

    async def execute_page_async(self, page_name: str) -> str:
        job = self.scheduler.schedule_page(page_name, {})
        return job.id


def load_graph_from_file(path: str | Path) -> Graph:
    engine = Engine.from_file(path)
    return engine.graph
    def execute_team(
        self, agent_names: list[str], task: str, context: Optional[ExecutionContext] = None
    ) -> Dict[str, Any]:
        if context is None:
            context = ExecutionContext(
                app_name="__team__",
                request_id=str(uuid4()),
                memory_engine=self.memory_engine,
                rag_engine=self.rag_engine,
                tracer=Tracer(),
                tool_registry=self.tool_registry,
                metrics=self.metrics_tracker,
                secrets=self.secrets_manager,
            )
            if context.tracer:
                context.tracer.start_app("__team__")
        result = self.team_runner.run_team(agent_names, task, context)
        return asdict(result)
