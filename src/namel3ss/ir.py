"""
Intermediate Representation (IR) for Namel3ss V3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal

from . import ast_nodes
from .errors import IRError
from .tools.builtin import BUILTIN_TOOL_NAMES


@dataclass
class IRApp:
    name: str
    description: str | None = None
    entry_page: str | None = None


@dataclass
class IRPage:
    name: str
    title: str | None = None
    route: str | None = None
    description: str | None = None
    properties: Dict[str, str] = field(default_factory=dict)
    ai_calls: List[str] = field(default_factory=list)
    agents: List[str] = field(default_factory=list)
    memories: List[str] = field(default_factory=list)
    sections: List["IRSection"] = field(default_factory=list)


@dataclass
class IRModel:
    name: str
    provider: str | None = None


@dataclass
class IRAiCall:
    name: str
    model_name: str | None = None
    input_source: str | None = None
    description: str | None = None


@dataclass
class IRAgent:
    name: str
    goal: str | None = None
    personality: str | None = None


@dataclass
class IRMemory:
    name: str
    memory_type: str | None = None


@dataclass
class IRFlowStep:
    name: str
    kind: Literal["ai", "agent", "tool"]
    target: str
    message: str | None = None


@dataclass
class IRFlow:
    name: str
    description: str | None
    steps: List[IRFlowStep] = field(default_factory=list)


@dataclass
class IRComponent:
    type: str
    props: Dict[str, str] = field(default_factory=dict)


@dataclass
class IRSection:
    name: str
    components: List[IRComponent] = field(default_factory=list)


@dataclass
class IRProgram:
    apps: Dict[str, IRApp] = field(default_factory=dict)
    pages: Dict[str, IRPage] = field(default_factory=dict)
    models: Dict[str, IRModel] = field(default_factory=dict)
    ai_calls: Dict[str, IRAiCall] = field(default_factory=dict)
    agents: Dict[str, IRAgent] = field(default_factory=dict)
    memories: Dict[str, IRMemory] = field(default_factory=dict)
    flows: Dict[str, IRFlow] = field(default_factory=dict)
    plugins: Dict[str, "IRPlugin"] = field(default_factory=dict)


@dataclass
class IRPlugin:
    name: str
    description: str | None = None


def ast_to_ir(module: ast_nodes.Module) -> IRProgram:
    program = IRProgram()
    allowed_memory_types = {"conversation", "user", "global"}
    for decl in module.declarations:
        if isinstance(decl, ast_nodes.AppDecl):
            if decl.name in program.apps:
                raise IRError(
                    f"Duplicate app '{decl.name}'", decl.span and decl.span.line
                )
            program.apps[decl.name] = IRApp(
                name=decl.name,
                description=decl.description,
                entry_page=decl.entry_page,
            )
        elif isinstance(decl, ast_nodes.PageDecl):
            if decl.name in program.pages:
                raise IRError(
                    f"Duplicate page '{decl.name}'", decl.span and decl.span.line
                )
            sections = [
                IRSection(
                    name=sec.name,
                    components=[
                        IRComponent(
                            type=comp.type,
                            props={prop.key: prop.value for prop in comp.props},
                        )
                        for comp in sec.components
                    ],
                )
                for sec in decl.sections
            ]
            # validate duplicate section names
            section_names = [s.name for s in sections]
            if len(section_names) != len(set(section_names)):
                raise IRError(
                    f"Duplicate section name in page '{decl.name}'",
                    decl.span and decl.span.line,
                )
            program.pages[decl.name] = IRPage(
                name=decl.name,
                title=decl.title,
                route=decl.route,
                description=decl.description,
                properties={prop.key: prop.value for prop in decl.properties},
                ai_calls=[ref.name for ref in decl.ai_calls],
                agents=[ref.name for ref in decl.agents],
                memories=[ref.name for ref in decl.memories],
                sections=sections,
            )
        elif isinstance(decl, ast_nodes.ModelDecl):
            if decl.name in program.models:
                raise IRError(
                    f"Duplicate model '{decl.name}'", decl.span and decl.span.line
                )
            program.models[decl.name] = IRModel(name=decl.name, provider=decl.provider)
        elif isinstance(decl, ast_nodes.AICallDecl):
            if decl.name in program.ai_calls:
                raise IRError(
                    f"Duplicate ai call '{decl.name}'", decl.span and decl.span.line
                )
            program.ai_calls[decl.name] = IRAiCall(
                name=decl.name,
                model_name=decl.model_name,
                input_source=decl.input_source,
                description=getattr(decl, "description", None),
            )
        elif isinstance(decl, ast_nodes.AgentDecl):
            if decl.name in program.agents:
                raise IRError(
                    f"Duplicate agent '{decl.name}'", decl.span and decl.span.line
                )
            program.agents[decl.name] = IRAgent(
                name=decl.name, goal=decl.goal, personality=decl.personality
            )
        elif isinstance(decl, ast_nodes.MemoryDecl):
            if decl.name in program.memories:
                raise IRError(
                    f"Duplicate memory '{decl.name}'", decl.span and decl.span.line
                )
            if decl.memory_type and decl.memory_type not in allowed_memory_types:
                raise IRError(
                    f"Memory '{decl.name}' has unsupported type '{decl.memory_type}'",
                    decl.span and decl.span.line,
                )
            program.memories[decl.name] = IRMemory(
                name=decl.name, memory_type=decl.memory_type
            )
        elif isinstance(decl, ast_nodes.FlowDecl):
            if decl.name in program.flows:
                raise IRError(
                    f"Duplicate flow '{decl.name}'", decl.span and decl.span.line
                )
            flow_steps: List[IRFlowStep] = []
            for step in decl.steps:
                if step.kind not in ("ai", "agent", "tool"):
                    raise IRError(
                        f"Unsupported step kind '{step.kind}'", step.span and step.span.line
                    )
                flow_steps.append(
                    IRFlowStep(
                        name=step.name,
                        kind=step.kind,
                        target=step.target,
                        message=getattr(step, "message", None),
                    )
                )
            program.flows[decl.name] = IRFlow(
                name=decl.name, description=decl.description, steps=flow_steps
            )
        elif isinstance(decl, ast_nodes.PluginDecl):
            if decl.name in program.plugins:
                raise IRError(
                    f"Duplicate plugin '{decl.name}'", decl.span and decl.span.line
                )
            program.plugins[decl.name] = IRPlugin(
                name=decl.name, description=decl.description
            )
        elif isinstance(decl, ast_nodes.UseImport):
            # Imports are acknowledged but not expanded in this minimal slice.
            continue
        else:  # pragma: no cover - defensive
            raise IRError(f"Unknown declaration type {type(decl).__name__}")

    for app in program.apps.values():
        if app.entry_page and app.entry_page not in program.pages:
            raise IRError(
                f"App '{app.name}' references missing page '{app.entry_page}'"
            )

    for ai_call in program.ai_calls.values():
        if ai_call.model_name and ai_call.model_name not in program.models:
            raise IRError(
                f"AI call '{ai_call.name}' references missing model '{ai_call.model_name}'"
            )

    for page in program.pages.values():
        for ai_call_name in page.ai_calls:
            if ai_call_name not in program.ai_calls:
                raise IRError(
                    f"Page '{page.name}' references missing ai_call '{ai_call_name}'"
                )
        for agent_name in page.agents:
            if agent_name not in program.agents:
                raise IRError(
                    f"Page '{page.name}' references missing agent '{agent_name}'"
                )
        for memory_name in page.memories:
            if memory_name not in program.memories:
                raise IRError(
                    f"Page '{page.name}' references missing memory '{memory_name}'"
                )

    for flow in program.flows.values():
        for step in flow.steps:
            if step.kind == "ai":
                if step.target not in program.ai_calls:
                    raise IRError(
                        f"Flow '{flow.name}' references missing ai_call '{step.target}'"
                    )
            elif step.kind == "agent":
                if step.target not in program.agents:
                    raise IRError(
                        f"Flow '{flow.name}' references missing agent '{step.target}'"
                    )
            elif step.kind == "tool":
                if step.target not in BUILTIN_TOOL_NAMES:
                    raise IRError(
                        f"Flow '{flow.name}' references missing tool '{step.target}'"
                    )

    return program
