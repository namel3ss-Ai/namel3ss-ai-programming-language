"""
Plugin SDK for contributing tools, agents, flows, UI components, RAG indexes, and memory strategies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from ..agent.engine import AgentRunner
from ..ir import IRAgent, IRFlow
from ..memory.engine import MemoryEngine
from ..rag.engine import RAGEngine
from ..tools.registry import ToolRegistry

if TYPE_CHECKING:  # pragma: no cover
    from ..runtime.engine import Engine


class _DynamicTool:
    def __init__(self, name: str, func: Callable[..., Any], description: str = "") -> None:
        self.name = name
        self.func = func
        self.description = description

    def run(self, **kwargs: Any) -> Any:
        return self.func(**kwargs)


@dataclass
class ToolSDK:
    registry: ToolRegistry
    contributions: Dict[str, List[str]] = field(default_factory=dict)
    default_plugin_id: Optional[str] = None

    def register_tool(self, name: str, func: Callable[..., Any], description: str = "", plugin_id: Optional[str] = None) -> None:
        tool = _DynamicTool(name=name, func=func, description=description)
        self.registry.register(tool)
        pid = plugin_id or self.default_plugin_id
        if pid:
            self.contributions.setdefault(pid, []).append(name)

    def unregister_contributions(self, plugin_id: str) -> None:
        for name in self.contributions.get(plugin_id, []):
            self.registry.unregister(name)
        self.contributions.pop(plugin_id, None)


@dataclass
class AgentSDK:
    agent_runner: AgentRunner
    contributions: Dict[str, List[str]] = field(default_factory=dict)
    default_plugin_id: Optional[str] = None

    def register_agent(self, agent: IRAgent, plugin_id: Optional[str] = None) -> None:
        self.agent_runner.program.agents[agent.name] = agent
        pid = plugin_id or self.default_plugin_id
        if pid:
            self.contributions.setdefault(pid, []).append(agent.name)

    def unregister_contributions(self, plugin_id: str) -> None:
        for name in self.contributions.get(plugin_id, []):
            self.agent_runner.program.agents.pop(name, None)
        self.contributions.pop(plugin_id, None)


@dataclass
class FlowSDK:
    engine: Engine
    contributions: Dict[str, List[str]] = field(default_factory=dict)
    default_plugin_id: Optional[str] = None

    def register_flow(self, flow: IRFlow, plugin_id: Optional[str] = None) -> None:
        self.engine.program.flows[flow.name] = flow
        pid = plugin_id or self.default_plugin_id
        if pid:
            self.contributions.setdefault(pid, []).append(flow.name)

    def unregister_contributions(self, plugin_id: str) -> None:
        for name in self.contributions.get(plugin_id, []):
            self.engine.program.flows.pop(name, None)
        self.contributions.pop(plugin_id, None)


@dataclass
class RagSDK:
    rag_engine: RAGEngine
    contributions: Dict[str, List[str]] = field(default_factory=dict)
    default_plugin_id: Optional[str] = None

    def register_index(self, name: str, plugin_id: Optional[str] = None) -> None:
        if name not in self.rag_engine.index_registry:
            from ..rag.index_config import RAGIndexConfig

            self.rag_engine.index_registry[name] = RAGIndexConfig(name=name, backend="memory", collection=name)
        self.rag_engine._get_store(self.rag_engine.index_registry[name])
        pid = plugin_id or self.default_plugin_id
        if pid:
            self.contributions.setdefault(pid, []).append(name)

    def unregister_contributions(self, plugin_id: str) -> None:
        self.contributions.pop(plugin_id, None)


@dataclass
class PluginSDK:
    tools: ToolSDK
    agents: AgentSDK
    flows: FlowSDK
    rag: RagSDK
    memory_engine: Optional[MemoryEngine] = None

    @classmethod
    def from_engine(cls, engine: "Engine", plugin_id: Optional[str] = None) -> "PluginSDK":
        tools = ToolSDK(engine.tool_registry, default_plugin_id=plugin_id)
        agents = AgentSDK(engine.agent_runner, default_plugin_id=plugin_id)
        flows = FlowSDK(engine, default_plugin_id=plugin_id)
        rag = RagSDK(engine.rag_engine, default_plugin_id=plugin_id)
        return cls(tools=tools, agents=agents, flows=flows, rag=rag, memory_engine=engine.memory_engine)
