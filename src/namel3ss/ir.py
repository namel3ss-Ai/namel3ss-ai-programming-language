"""
Intermediate Representation (IR) for Namel3ss V3.
"""

from __future__ import annotations

import copy
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
    conditional_branches: list["IRConditionalBranch"] | None = None


@dataclass
class IRMemory:
    name: str
    memory_type: str | None = None


@dataclass
class IRFlowStep:
    name: str
    kind: Literal["ai", "agent", "tool", "condition", "goto_flow"]
    target: str
    message: str | None = None
    conditional_branches: list["IRConditionalBranch"] | None = None


@dataclass
class IRFlow:
    name: str
    description: str | None
    steps: List[IRFlowStep] = field(default_factory=list)


@dataclass
class IRAction:
    kind: Literal["ai", "agent", "tool", "goto_flow"]
    target: str
    message: str | None = None


@dataclass
class IRConditionalBranch:
    condition: ast_nodes.Expr | None
    actions: List[IRAction] = field(default_factory=list)
    label: str | None = None
    binding: str | None = None
    macro_origin: str | None = None


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
    rulegroups: Dict[str, Dict[str, ast_nodes.Expr]] = field(default_factory=dict)


@dataclass
class IRPlugin:
    name: str
    description: str | None = None


def ast_to_ir(module: ast_nodes.Module) -> IRProgram:
    program = IRProgram()
    allowed_memory_types = {"conversation", "user", "global"}
    macro_defs: dict[str, ast_nodes.Expr] = {}
    rulegroups: dict[str, dict[str, ast_nodes.Expr]] = {}
    for decl in module.declarations:
        if isinstance(decl, ast_nodes.ConditionMacroDecl):
            if decl.name in macro_defs:
                raise IRError(f"Duplicate condition macro '{decl.name}'", decl.span and decl.span.line)
            if decl.expr is None:
                raise IRError(f"Condition macro '{decl.name}' must have a body.", decl.span and decl.span.line)
            macro_defs[decl.name] = decl.expr
        if isinstance(decl, ast_nodes.RuleGroupDecl):
            if decl.name in rulegroups:
                raise IRError(f"Rulegroup '{decl.name}' is defined more than once.", decl.span and decl.span.line)
            group_map: dict[str, ast_nodes.Expr] = {}
            for cond in decl.conditions:
                if cond.name in group_map:
                    raise IRError(
                        f"Condition '{cond.name}' is defined more than once in rulegroup '{decl.name}'.",
                        cond.span and cond.span.line,
                    )
                group_map[cond.name] = cond.expr
            rulegroups[decl.name] = group_map
    def transform_expr(expr: ast_nodes.Expr | None) -> tuple[ast_nodes.Expr | None, str | None]:
        if expr is None:
            return None, None
        if isinstance(expr, ast_nodes.Identifier):
            name = expr.name
            if name in macro_defs:
                return copy.deepcopy(macro_defs[name]), name
            if name in rulegroups:
                return ast_nodes.RuleGroupRefExpr(group_name=name), None
            if "." in name:
                group, _, cond_name = name.partition(".")
                if group in rulegroups:
                    if cond_name not in rulegroups[group]:
                        raise IRError(
                            f"Condition '{cond_name}' does not exist in rulegroup '{group}'.",
                            expr.span and expr.span.line,
                        )
                    return ast_nodes.RuleGroupRefExpr(group_name=group, condition_name=cond_name), None
        if isinstance(expr, ast_nodes.PatternExpr):
            updated_pairs: list[ast_nodes.PatternPair] = []
            for pair in expr.pairs:
                if pair.key in rulegroups or pair.key in macro_defs:
                    raise IRError(
                        "Rulegroups or condition macros cannot be used as pattern keys; use them as values instead.",
                        expr.span and expr.span.line,
                    )
                val_expr, _ = transform_expr(pair.value)
                updated_pairs.append(ast_nodes.PatternPair(key=pair.key, value=val_expr or pair.value))
            return ast_nodes.PatternExpr(subject=expr.subject, pairs=updated_pairs, span=expr.span), None
        return expr, None

    for decl in module.declarations:
        if isinstance(decl, ast_nodes.ConditionMacroDecl):
            continue
        if isinstance(decl, ast_nodes.RuleGroupDecl):
            continue
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

            agent_branches: list[IRConditionalBranch] | None = None
            if getattr(decl, "conditional_branches", None):
                agent_branches = []
                for br in decl.conditional_branches or []:
                    actions = [
                        IRAction(kind=act.kind, target=act.target, message=act.message)
                        for act in br.actions
                    ]
                    cond, macro_origin = transform_expr(br.condition)
                    if macro_origin is None and isinstance(br.condition, ast_nodes.Identifier) and br.condition.name in macro_defs:
                        macro_origin = br.condition.name
                    if br.binding and br.binding in macro_defs:
                        raise IRError(
                            f"Binding name '{br.binding}' conflicts with condition macro.",
                            br.span and br.span.line,
                        )
                    agent_branches.append(
                        IRConditionalBranch(
                            condition=cond,
                            actions=actions,
                            label=br.label,
                            binding=br.binding,
                            macro_origin=macro_origin,
                        )
                    )
            program.agents[decl.name] = IRAgent(
                name=decl.name, goal=decl.goal, personality=decl.personality, conditional_branches=agent_branches
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
                if step.conditional_branches:
                    branches: list[IRConditionalBranch] = []
                    for br in step.conditional_branches:
                        actions = [
                            IRAction(kind=act.kind, target=act.target, message=act.message)
                            for act in br.actions
                        ]
                        cond, macro_origin = transform_expr(br.condition)
                        if macro_origin is None and isinstance(br.condition, ast_nodes.Identifier) and br.condition.name in macro_defs:
                            macro_origin = br.condition.name
                        if br.binding and br.binding in macro_defs:
                            raise IRError(
                                f"Binding name '{br.binding}' conflicts with condition macro.",
                                br.span and br.span.line,
                            )
                        branches.append(
                            IRConditionalBranch(
                                condition=cond,
                                actions=actions,
                                label=br.label,
                                binding=br.binding,
                                macro_origin=macro_origin,
                            )
                        )
                    flow_steps.append(
                        IRFlowStep(
                            name=step.name,
                            kind="condition",
                            target=step.name,
                            conditional_branches=branches,
                        )
                    )
                else:
                    if step.kind not in ("ai", "agent", "tool", "goto_flow"):
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

    program.rulegroups = rulegroups

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
            elif step.kind == "goto_flow":
                # Flow redirection target validated at runtime; keep IR flexible.
                continue

    return program
