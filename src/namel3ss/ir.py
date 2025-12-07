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
    layout: List["IRLayoutElement"] = field(default_factory=list)
    ui_states: List["IRUIState"] = field(default_factory=list)
    styles: List["IRUIStyle"] = field(default_factory=list)


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
class IRHelper:
    name: str
    identifier: str
    params: list[str] = field(default_factory=list)
    return_name: str | None = None
    body: list["IRStatement"] = field(default_factory=list)


@dataclass
class IRImport:
    module: str
    kind: str
    name: str
    alias: str | None = None


@dataclass
class IREnvConfig:
    name: str
    entries: dict[str, ast_nodes.Expr] = field(default_factory=dict)


@dataclass
class IRSettings:
    envs: dict[str, IREnvConfig] = field(default_factory=dict)
    theme: dict[str, str] = field(default_factory=dict)


@dataclass
class IRFlowStep:
    name: str
    kind: Literal["ai", "agent", "tool", "condition", "goto_flow", "script"]
    target: str
    message: str | None = None
    conditional_branches: list["IRConditionalBranch"] | None = None
    statements: list["IRStatement"] | None = None


@dataclass
class IRFlow:
    name: str
    description: str | None
    steps: List[IRFlowStep] = field(default_factory=list)


@dataclass
class IRAction:
    kind: Literal["ai", "agent", "tool", "goto_flow", "flow", "goto_page"]
    target: str
    message: str | None = None
    args: dict[str, ast_nodes.Expr] = field(default_factory=dict)


@dataclass
class IRLet:
    name: str
    expr: ast_nodes.Expr | None = None


@dataclass
class IRSet:
    name: str
    expr: ast_nodes.Expr | None = None


@dataclass
class IRIf:
    branches: list["IRConditionalBranch"] = field(default_factory=list)


@dataclass
class IRForEach:
    var_name: str
    iterable: ast_nodes.Expr | None = None
    body: list["IRStatement"] = field(default_factory=list)


@dataclass
class IRRepeatUpTo:
    count: ast_nodes.Expr | None = None
    body: list["IRStatement"] = field(default_factory=list)


@dataclass
class IRAskUser:
    label: str
    var_name: str
    validation: ast_nodes.InputValidation | None = None


@dataclass
class IRFormField:
    label: str
    name: str
    validation: ast_nodes.InputValidation | None = None


@dataclass
class IRForm:
    label: str
    name: str
    fields: list[IRFormField] = field(default_factory=list)


@dataclass
class IRLog:
    level: str
    message: str
    metadata: ast_nodes.Expr | None = None


@dataclass
class IRNote:
    message: str


@dataclass
class IRCheckpoint:
    label: str


@dataclass
class IRReturn:
    expr: ast_nodes.Expr | None = None


@dataclass
class IRMatchBranch:
    pattern: ast_nodes.Expr | ast_nodes.SuccessPattern | ast_nodes.ErrorPattern | None = None
    binding: str | None = None
    actions: list["IRStatement"] = field(default_factory=list)
    label: str | None = None


@dataclass
class IRMatch:
    target: ast_nodes.Expr | None = None
    branches: list[IRMatchBranch] = field(default_factory=list)


@dataclass
class IRRetry:
    count: ast_nodes.Expr | None = None
    with_backoff: bool = False
    body: list["IRStatement"] = field(default_factory=list)


IRStatement = IRAction | IRLet | IRSet | IRIf | IRForEach | IRRepeatUpTo | IRMatch | IRRetry | IRAskUser | IRForm | IRLog | IRNote | IRCheckpoint | IRReturn


@dataclass
class IRConditionalBranch:
    condition: ast_nodes.Expr | None
    actions: List[IRStatement] = field(default_factory=list)
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
    layout: List["IRLayoutElement"] = field(default_factory=list)
    styles: List["IRUIStyle"] = field(default_factory=list)


@dataclass
class IRHeading:
    text: str
    styles: List["IRUIStyle"] = field(default_factory=list)


@dataclass
class IRText:
    text: str
    expr: ast_nodes.Expr | None = None
    styles: List["IRUIStyle"] = field(default_factory=list)


@dataclass
class IRImage:
    url: str
    styles: List["IRUIStyle"] = field(default_factory=list)


@dataclass
class IREmbedForm:
    form_name: str
    styles: List["IRUIStyle"] = field(default_factory=list)


@dataclass
class IRUIState:
    name: str
    initial: object = None


@dataclass
class IRUIInput:
    label: str
    var_name: str
    field_type: str | None = None
    styles: list["IRUIStyle"] = field(default_factory=list)


@dataclass
class IRUIEventAction:
    kind: Literal["flow", "goto_page", "goto_flow"]
    target: str
    args: dict[str, ast_nodes.Expr] = field(default_factory=dict)


@dataclass
class IRUIButton:
    label: str
    actions: list[IRUIEventAction] = field(default_factory=list)
    styles: list["IRUIStyle"] = field(default_factory=list)
    label_expr: ast_nodes.Expr | None = None


@dataclass
class IRUIShowBlock:
    layout: list["IRLayoutElement"] = field(default_factory=list)


@dataclass
class IRUIConditional:
    condition: ast_nodes.Expr | None = None
    when_block: IRUIShowBlock | None = None
    otherwise_block: IRUIShowBlock | None = None


@dataclass
class IRUIStyle:
    kind: str
    value: object


@dataclass
class IRUIComponent:
    name: str
    params: list[str] = field(default_factory=list)
    render: list["IRLayoutElement"] = field(default_factory=list)
    styles: list[IRUIStyle] = field(default_factory=list)


@dataclass
class IRUIComponentCall:
    name: str
    args: list[ast_nodes.Expr] = field(default_factory=list)
    named_args: dict[str, list["IRStatement"]] = field(default_factory=dict)
    styles: list[IRUIStyle] = field(default_factory=list)


IRLayoutElement = IRHeading | IRText | IRImage | IREmbedForm | IRSection | IRUIInput | IRUIButton | IRUIConditional | IRUIComponentCall


@dataclass
class IRFrame:
    name: str
    source_kind: str = "file"
    path: str | None = None
    delimiter: str | None = None
    has_headers: bool = False
    select_cols: list[str] = field(default_factory=list)
    where: ast_nodes.Expr | None = None


@dataclass
class IRProgram:
    apps: Dict[str, IRApp] = field(default_factory=dict)
    pages: Dict[str, IRPage] = field(default_factory=dict)
    models: Dict[str, IRModel] = field(default_factory=dict)
    ai_calls: Dict[str, IRAiCall] = field(default_factory=dict)
    agents: Dict[str, IRAgent] = field(default_factory=dict)
    memories: Dict[str, IRMemory] = field(default_factory=dict)
    frames: Dict[str, IRFrame] = field(default_factory=dict)
    flows: Dict[str, IRFlow] = field(default_factory=dict)
    plugins: Dict[str, "IRPlugin"] = field(default_factory=dict)
    rulegroups: Dict[str, Dict[str, ast_nodes.Expr]] = field(default_factory=dict)
    helpers: Dict[str, IRHelper] = field(default_factory=dict)
    imports: List[IRImport] = field(default_factory=list)
    settings: IRSettings | None = None
    ui_components: Dict[str, IRUIComponent] = field(default_factory=dict)


@dataclass
class IRPlugin:
    name: str
    description: str | None = None


def ast_to_ir(module: ast_nodes.Module) -> IRProgram:
    program = IRProgram()
    allowed_memory_types = {"conversation", "user", "global"}
    macro_defs: dict[str, ast_nodes.Expr] = {}
    rulegroups: dict[str, dict[str, ast_nodes.Expr]] = {}
    page_routes: dict[str, str] = {}
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
        if isinstance(expr, ast_nodes.RecordFieldAccess):
            if isinstance(expr.target, ast_nodes.Identifier) and expr.target.name in rulegroups:
                group = expr.target.name
                cond_name = expr.field
                if cond_name not in rulegroups[group]:
                    raise IRError(
                        f"Condition '{cond_name}' does not exist in rulegroup '{group}'.",
                        expr.span and expr.span.line,
                    )
                return ast_nodes.RuleGroupRefExpr(group_name=group, condition_name=cond_name), None
            return expr, None
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
        if isinstance(expr, ast_nodes.BuiltinCall):
            new_args: list[ast_nodes.Expr] = []
            for arg in expr.args:
                new_arg, _ = transform_expr(arg)
                new_args.append(new_arg or arg)
            return ast_nodes.BuiltinCall(name=expr.name, args=new_args), None
        if isinstance(expr, ast_nodes.FunctionCall):
            new_args: list[ast_nodes.Expr] = []
            for arg in expr.args:
                new_arg, _ = transform_expr(arg)
                new_args.append(new_arg or arg)
            return ast_nodes.FunctionCall(name=expr.name, args=new_args, span=expr.span), None
        if isinstance(expr, ast_nodes.ListBuiltinCall):
            inner, _ = transform_expr(expr.expr) if expr.expr is not None else (None, None)
            return ast_nodes.ListBuiltinCall(name=expr.name, expr=inner or expr.expr), None
        return expr, None

    def lower_statement(stmt: ast_nodes.Statement | ast_nodes.FlowAction) -> IRStatement:
        if isinstance(stmt, ast_nodes.FlowAction):
            return IRAction(kind=stmt.kind, target=stmt.target, message=stmt.message, args=stmt.args)
        if isinstance(stmt, ast_nodes.LetStatement):
            return IRLet(name=stmt.name, expr=stmt.expr)
        if isinstance(stmt, ast_nodes.SetStatement):
            return IRSet(name=stmt.name, expr=stmt.expr)
        if isinstance(stmt, ast_nodes.IfStatement):
            branches = [lower_branch(br) for br in stmt.branches]
            return IRIf(branches=branches)
        if isinstance(stmt, ast_nodes.ForEachLoop):
            body = [lower_statement(s) for s in stmt.body]
            return IRForEach(var_name=stmt.var_name, iterable=stmt.iterable, body=body)
        if isinstance(stmt, ast_nodes.RepeatUpToLoop):
            body = [lower_statement(s) for s in stmt.body]
            return IRRepeatUpTo(count=stmt.count, body=body)
        if isinstance(stmt, ast_nodes.MatchStatement):
            ir_branches: list[IRMatchBranch] = []
            for br in stmt.branches:
                actions = [lower_statement(a) for a in br.actions]
                ir_branches.append(IRMatchBranch(pattern=br.pattern, binding=br.binding, actions=actions, label=br.label))
            return IRMatch(target=stmt.target, branches=ir_branches)
        if isinstance(stmt, ast_nodes.RetryStatement):
            body = [lower_statement(s) for s in stmt.body]
            return IRRetry(count=stmt.count, with_backoff=stmt.with_backoff, body=body)
        if isinstance(stmt, ast_nodes.AskUserStatement):
            return IRAskUser(label=stmt.label, var_name=stmt.var_name, validation=stmt.validation)
        if isinstance(stmt, ast_nodes.FormStatement):
            fields = [
                IRFormField(label=f.label, name=f.name, validation=f.validation)
                for f in stmt.fields
            ]
            return IRForm(label=stmt.label, name=stmt.name, fields=fields)
        if isinstance(stmt, ast_nodes.LogStatement):
            return IRLog(level=stmt.level, message=stmt.message, metadata=stmt.metadata)
        if isinstance(stmt, ast_nodes.NoteStatement):
            return IRNote(message=stmt.message)
        if isinstance(stmt, ast_nodes.CheckpointStatement):
            return IRCheckpoint(label=stmt.label)
        if isinstance(stmt, ast_nodes.ReturnStatement):
            return IRReturn(expr=stmt.expr)
        raise IRError(f"Unsupported statement type '{type(stmt).__name__}'", getattr(stmt, "span", None) and getattr(stmt.span, "line", None))

    def lower_branch(br: ast_nodes.ConditionalBranch) -> IRConditionalBranch:
        cond, macro_origin = transform_expr(br.condition)
        if macro_origin is None and isinstance(br.condition, ast_nodes.Identifier) and br.condition.name in macro_defs:
            macro_origin = br.condition.name
        if br.binding and br.binding in macro_defs:
            raise IRError(
                f"Binding name '{br.binding}' conflicts with condition macro.",
                br.span and br.span.line,
            )
        actions = [lower_statement(act) for act in br.actions]
        return IRConditionalBranch(
            condition=cond,
            actions=actions,
            label=br.label,
            binding=br.binding,
            macro_origin=macro_origin,
        )

    def lower_styles(styles: list[ast_nodes.UIStyle]) -> list[IRUIStyle]:
        return [IRUIStyle(kind=s.kind, value=s.value) for s in styles]

    def lower_layout_element(
        el: ast_nodes.LayoutElement,
        collected_states: list[IRUIState] | None = None,
    ) -> IRLayoutElement | None:
        if isinstance(el, ast_nodes.UIStateDecl):
            if collected_states is None:
                return None
            val = None
            if isinstance(el.expr, ast_nodes.Literal):
                val = el.expr.value
                if not isinstance(val, (str, int, float, bool)) and val is not None:
                    raise IRError("N3U-2002: invalid state initializer", getattr(el, "span", None) and getattr(el.span, "line", None))
            else:
                raise IRError("N3U-2002: invalid state initializer", getattr(el, "span", None) and getattr(el.span, "line", None))
            collected_states.append(IRUIState(name=el.name, initial=val))
            return None
        if isinstance(el, ast_nodes.HeadingNode):
            return IRHeading(text=el.text, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.TextNode):
            return IRText(text=el.text, expr=getattr(el, "expr", None), styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.ImageNode):
            return IRImage(url=el.url, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.EmbedFormNode):
            return IREmbedForm(form_name=el.form_name, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.SectionDecl):
            sec_children_raw = [lower_layout_element(child, collected_states) for child in el.layout]
            sec_children = [c for c in sec_children_raw if c is not None]
            return IRSection(name=el.name, components=[], layout=sec_children, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.UIInputNode):
            if el.field_type and el.field_type not in {"text", "number", "email", "secret", "long_text", "date"}:
                raise IRError("N3U-2101: invalid input type", getattr(el, "span", None) and getattr(el.span, "line", None))
            return IRUIInput(label=el.label, var_name=el.var_name, field_type=el.field_type, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.UIButtonNode):
            actions: list[IRUIEventAction] = []
            if el.handler:
                for act in el.handler.actions:
                    if act.kind == "flow":
                        actions.append(IRUIEventAction(kind="flow", target=act.target, args=act.args))
                    elif act.kind == "goto_page":
                        actions.append(IRUIEventAction(kind="goto_page", target=act.target, args=act.args))
                    elif act.kind == "goto_flow":
                        actions.append(IRUIEventAction(kind="goto_flow", target=act.target, args=act.args))
                    else:
                        raise IRError("N3U-2202: invalid action in click handler", getattr(act, "span", None) and getattr(act.span, "line", None))
            return IRUIButton(label=el.label, label_expr=getattr(el, "label_expr", None), actions=actions, styles=lower_styles(el.styles))
        if isinstance(el, ast_nodes.UIConditional):
            when_children_raw = [lower_layout_element(child, collected_states) for child in el.when_children]
            otherwise_children_raw = [lower_layout_element(child, collected_states) for child in el.otherwise_children]
            when_block = IRUIShowBlock(layout=[c for c in when_children_raw if c is not None])
            otherwise_block = None
            if el.otherwise_children:
                otherwise_block = IRUIShowBlock(layout=[c for c in otherwise_children_raw if c is not None])
            return IRUIConditional(condition=el.condition, when_block=when_block, otherwise_block=otherwise_block)
        if isinstance(el, ast_nodes.UIComponentCall):
            return IRUIComponentCall(
                name=el.name,
                args=list(el.args),
                named_args={
                    key: [lower_statement(a) if isinstance(a, ast_nodes.FlowAction) else lower_statement(a) for a in actions]
                    for key, actions in el.named_args.items()
                },
                styles=lower_styles(el.styles),
            )
        raise IRError("Unsupported layout element", getattr(el, "span", None) and getattr(el.span, "line", None))

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
        elif isinstance(decl, ast_nodes.UIComponentDecl):
            if decl.name in program.ui_components:
                raise IRError("N3U-3500: component name conflicts", decl.span and decl.span.line)
            comp_layout_raw = [lower_layout_element(el, None) for el in decl.render]
            comp_layout = [c for c in comp_layout_raw if c is not None]
            program.ui_components[decl.name] = IRUIComponent(
                name=decl.name,
                params=list(decl.params),
                render=comp_layout,
                styles=lower_styles(decl.styles),
            )
        elif isinstance(decl, ast_nodes.PageDecl):
            if decl.name in program.pages:
                raise IRError(
                    f"N3U-1002: duplicate page '{decl.name}'", decl.span and decl.span.line
                )
            if decl.route:
                if decl.route in page_routes:
                    raise IRError(
                        f"N3U-1003: duplicate route '{decl.route}'", decl.span and decl.span.line
                    )
                page_routes[decl.route] = decl.name

            collected_states: list[IRUIState] = []

            sections: list[IRSection] = []
            for sec in decl.sections:
                sec_children_raw = [lower_layout_element(child, collected_states) for child in sec.layout]
                sec_children = [c for c in sec_children_raw if c is not None]
                sections.append(
                    IRSection(
                        name=sec.name,
                        components=[
                            IRComponent(
                                type=comp.type,
                                props={prop.key: prop.value for prop in comp.props},
                            )
                            for comp in sec.components
                        ],
                        layout=sec_children,
                        styles=lower_styles(sec.styles),
                    )
                )
            # validate duplicate section names
            section_names = [s.name for s in sections] + [el.name for el in decl.layout if isinstance(el, ast_nodes.SectionDecl)]
            if len(section_names) != len(set(section_names)):
                raise IRError(
                    f"N3U-1100: duplicate section name in page '{decl.name}'",
                    decl.span and decl.span.line,
                )
            layout_nodes_raw: list[IRLayoutElement | None] = [lower_layout_element(el, collected_states) for el in decl.layout]
            layout_nodes = [ln for ln in layout_nodes_raw if ln is not None]
            # deduplicate states by name
            state_names = [s.name for s in collected_states]
            if len(state_names) != len(set(state_names)):
                raise IRError("N3U-2001: duplicate state name", decl.span and decl.span.line)
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
                layout=layout_nodes,
                ui_states=collected_states,
                styles=lower_styles(decl.styles),
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
                agent_branches = [lower_branch(br) for br in decl.conditional_branches or []]
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
        elif isinstance(decl, ast_nodes.FrameDecl):
            if decl.name in program.frames:
                raise IRError(
                    f"Duplicate frame '{decl.name}'", decl.span and decl.span.line
                )
            if not decl.source_path:
                raise IRError("N3F-1000: frame source not specified", decl.span and decl.span.line)
            where_expr, _ = transform_expr(decl.where)
            program.frames[decl.name] = IRFrame(
                name=decl.name,
                source_kind=decl.source_kind or "file",
                path=decl.source_path,
                delimiter=decl.delimiter,
                has_headers=decl.has_headers,
                select_cols=decl.select_cols or [],
                where=where_expr,
            )
        elif isinstance(decl, ast_nodes.FlowDecl):
            if decl.name in program.flows:
                raise IRError(
                    f"Duplicate flow '{decl.name}'", decl.span and decl.span.line
                )
            flow_steps: List[IRFlowStep] = []
            for step in decl.steps:
                if step.statements:
                    ir_statements = [lower_statement(stmt) for stmt in step.statements]
                    flow_steps.append(
                        IRFlowStep(
                            name=step.name,
                            kind="script",
                            target=step.target or step.name,
                            message=getattr(step, "message", None),
                            statements=ir_statements,
                        )
                    )
                elif step.conditional_branches:
                    branches: list[IRConditionalBranch] = [lower_branch(br) for br in step.conditional_branches]
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
        elif isinstance(decl, ast_nodes.HelperDecl):
            if decl.identifier in program.helpers:
                raise IRError("N3-6003: duplicate helper identifier", decl.span and decl.span.line)
            body = [lower_statement(stmt) for stmt in decl.body]
            program.helpers[decl.identifier] = IRHelper(
                name=decl.name,
                identifier=decl.identifier,
                params=list(decl.params),
                return_name=decl.return_name,
                body=body,
            )
        elif isinstance(decl, ast_nodes.ImportDecl):
            program.imports.append(IRImport(module=decl.module, kind=decl.kind, name=decl.name, alias=decl.alias))
        elif isinstance(decl, ast_nodes.ModuleUse):
            program.imports.append(IRImport(module=decl.module, kind="module", name=decl.module))
        elif isinstance(decl, ast_nodes.SettingsDecl):
            if program.settings is not None:
                raise IRError("N3-6200: settings defined more than once", decl.span and decl.span.line)
            env_map: dict[str, IREnvConfig] = {}
            for env in decl.envs:
                if env.name in env_map:
                    raise IRError(f"N3-6200: duplicate env definition '{env.name}'", env.span and env.span.line)
                entry_map: dict[str, ast_nodes.Expr] = {}
                for entry in env.entries:
                    if entry.key in entry_map:
                        raise IRError(f"N3-6201: duplicate key '{entry.key}' in env '{env.name}'", env.span and env.span.line)
                    entry_map[entry.key] = entry.expr
                env_map[env.name] = IREnvConfig(name=env.name, entries=entry_map)
            theme_map: dict[str, str] = {}
            for entry in decl.theme:
                if entry.key in theme_map:
                    raise IRError("N3U-3002: duplicate theme key", entry.span and entry.span.line)
                theme_map[entry.key] = entry.value
            program.settings = IRSettings(envs=env_map, theme=theme_map)
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
            elif step.kind in {"condition", "script"}:
                continue
            elif step.kind == "goto_flow":
                # Flow redirection target validated at runtime; keep IR flexible.
                continue

    return program
