"""
Intermediate Representation (IR) for Namel3ss V3.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional, Union

from . import ast_nodes
from .config import load_config
from .errors import IRError
from .tools.builtin import BUILTIN_TOOL_NAMES


DEFAULT_SHORT_TERM_WINDOW = 20


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
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRModel:
    name: str
    provider: str | None = None


@dataclass
class IRAiCall:
    name: str
    model_name: str | None = None
    provider: str | None = None
    input_source: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    memory_name: str | None = None
    memory: "IRAiMemoryConfig | None" = None
    tools: list["IRAiToolBinding"] = field(default_factory=list)


@dataclass
class IRAiToolBinding:
    internal_name: str
    exposed_name: str


@dataclass
class IRAiShortTermMemoryConfig:
    window: int | None = None
    store: str | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None


@dataclass
class IRAiLongTermMemoryConfig:
    store: str | None = None
    pipeline: list["IRMemoryPipelineStep"] | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None


@dataclass
class IRAiProfileMemoryConfig:
    store: str | None = None
    extract_facts: bool | None = None
    pipeline: list["IRMemoryPipelineStep"] | None = None
    retention_days: int | None = None
    pii_policy: str | None = None
    scope: str | None = None


@dataclass
class IRMemoryPipelineStep:
    name: str
    type: str
    max_tokens: int | None = None


@dataclass
class IRAiRecallRule:
    source: str
    count: int | None = None
    top_k: int | None = None
    include: bool | None = None


@dataclass
class IRAiMemoryConfig:
    kind: str | None = None
    window: int | None = None
    store: str | None = None
    short_term: IRAiShortTermMemoryConfig | None = None
    long_term: IRAiLongTermMemoryConfig | None = None
    profile: IRAiProfileMemoryConfig | None = None
    recall: list[IRAiRecallRule] = field(default_factory=list)

    def referenced_store_names(self) -> list[str | None]:
        stores: list[str | None] = []
        if self.short_term:
            stores.append(self.short_term.store)
        else:
            stores.append(self.store)
        if self.long_term:
            stores.append(self.long_term.store)
        if self.profile:
            stores.append(self.profile.store)
        return stores


@dataclass
class IRAgent:
    name: str
    goal: str | None = None
    personality: str | None = None
    system_prompt: str | None = None
    memory_name: str | None = None
    conditional_branches: list["IRConditionalBranch"] | None = None


@dataclass
class IRMemory:
    name: str
    memory_type: str | None = None
    retention: str | None = None


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
    kind: Literal[
        "ai",
        "agent",
        "tool",
        "condition",
        "goto_flow",
        "script",
        "frame_insert",
        "frame_query",
        "frame_update",
        "frame_delete",
        "vector_index_frame",
        "vector_query",
        "db_create",
        "db_get",
        "db_update",
        "db_delete",
        "auth_register",
        "auth_login",
        "auth_logout",
    ]
    target: str
    message: str | None = None
    params: dict[str, object] = field(default_factory=dict)
    conditional_branches: list["IRConditionalBranch"] | None = None
    statements: list["IRStatement"] | None = None
    when_expr: ast_nodes.Expr | None = None
    streaming: bool = False
    stream_channel: str | None = None
    stream_role: str | None = None
    stream_label: str | None = None
    stream_mode: str | None = None
    tools_mode: str | None = None


@dataclass
class IRFlow:
    name: str
    description: str | None
    steps: List[Union["IRFlowStep", "IRFlowLoop"]] = field(default_factory=list)
    error_steps: List[IRFlowStep] = field(default_factory=list)


@dataclass
class IRFlowLoop:
    name: str
    var_name: str
    iterable: ast_nodes.Expr | None = None
    body: List[Union[IRFlowStep, "IRFlowLoop"]] = field(default_factory=list)


@dataclass
class IRAction:
    kind: Literal[
        "ai",
        "agent",
        "tool",
        "goto_flow",
        "flow",
        "goto_page",
        "frame_insert",
        "frame_query",
        "frame_update",
        "frame_delete",
        "vector_index_frame",
        "db_create",
        "db_get",
        "db_update",
        "db_delete",
    ]
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
class IRTryCatch:
    try_body: list["IRStatement"] = field(default_factory=list)
    error_name: str = "err"
    catch_body: list["IRStatement"] = field(default_factory=list)


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


IRStatement = IRAction | IRLet | IRSet | IRTryCatch | IRIf | IRForEach | IRRepeatUpTo | IRMatch | IRRetry | IRAskUser | IRForm | IRLog | IRNote | IRCheckpoint | IRReturn


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
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRHeading:
    text: str
    styles: List["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRText:
    text: str
    expr: ast_nodes.Expr | None = None
    styles: List["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRImage:
    url: str
    styles: List["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IREmbedForm:
    form_name: str
    styles: List["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRUIState:
    name: str
    initial: object = None


@dataclass
class IRUIInput:
    label: str
    var_name: str
    field_type: str | None = None
    validation: dict[str, object] | None = None
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRUIEventAction:
    kind: Literal["flow", "goto_page", "goto_flow", "navigate"]
    target: str | None = None
    target_path: str | None = None
    target_page: str | None = None
    args: dict[str, ast_nodes.Expr] = field(default_factory=dict)


@dataclass
class IRUIButton:
    label: str
    actions: list[IRUIEventAction] = field(default_factory=list)
    styles: list["IRUIStyle"] = field(default_factory=list)
    label_expr: ast_nodes.Expr | None = None
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


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
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRUIComponentCall:
    name: str
    args: list[ast_nodes.Expr] = field(default_factory=list)
    named_args: dict[str, list["IRStatement"]] = field(default_factory=dict)
    styles: list[IRUIStyle] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRCard:
    title: str | None = None
    layout: list["IRLayoutElement"] = field(default_factory=list)
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRRow:
    layout: list["IRLayoutElement"] = field(default_factory=list)
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRColumn:
    layout: list["IRLayoutElement"] = field(default_factory=list)
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRTextarea:
    label: str
    var_name: str | None = None
    validation: dict[str, object] | None = None
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRBadge:
    text: str
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)

@dataclass
class IRMessageList:
    layout: list["IRMessage"]
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


@dataclass
class IRMessage:
    name: str | None
    role: Expr | None
    text_expr: Expr | None
    styles: list["IRUIStyle"] = field(default_factory=list)
    class_name: str | None = None
    style: dict[str, str] = field(default_factory=dict)


IRLayoutElement = IRHeading | IRText | IRImage | IREmbedForm | IRSection | IRUIInput | IRUIButton | IRUIConditional | IRUIComponentCall | IRCard | IRRow | IRColumn | IRTextarea | IRBadge | IRMessageList | IRMessage


@dataclass
class IRFrame:
    name: str
    source_kind: str = "file"
    path: str | None = None
    backend: str | None = None
    table: str | None = None
    primary_key: str | None = None
    delimiter: str | None = None
    has_headers: bool = False
    select_cols: list[str] = field(default_factory=list)
    where: ast_nodes.Expr | None = None


@dataclass
class IRVectorStore:
    name: str
    backend: str
    frame: str
    text_column: str
    id_column: str
    embedding_model: str
    options: dict[str, str] = field(default_factory=dict)


@dataclass
class IRRecordField:
    name: str
    type: str
    primary_key: bool = False
    required: bool = False
    default: object | None = None


@dataclass
class IRRecord:
    name: str
    frame: str
    fields: dict[str, IRRecordField] = field(default_factory=dict)
    primary_key: str | None = None


@dataclass
class IRAuth:
    backend: str | None = None
    user_record: str | None = None
    id_field: str | None = None
    identifier_field: str | None = None
    password_hash_field: str | None = None


@dataclass
class IRProgram:
    apps: Dict[str, IRApp] = field(default_factory=dict)
    pages: Dict[str, IRPage] = field(default_factory=dict)
    models: Dict[str, IRModel] = field(default_factory=dict)
    ai_calls: Dict[str, IRAiCall] = field(default_factory=dict)
    agents: Dict[str, IRAgent] = field(default_factory=dict)
    memories: Dict[str, IRMemory] = field(default_factory=dict)
    frames: Dict[str, IRFrame] = field(default_factory=dict)
    records: Dict[str, IRRecord] = field(default_factory=dict)
    auth: IRAuth | None = None
    vector_stores: Dict[str, IRVectorStore] = field(default_factory=dict)
    flows: Dict[str, IRFlow] = field(default_factory=dict)
    plugins: Dict[str, "IRPlugin"] = field(default_factory=dict)
    rulegroups: Dict[str, Dict[str, ast_nodes.Expr]] = field(default_factory=dict)
    helpers: Dict[str, IRHelper] = field(default_factory=dict)
    imports: List[IRImport] = field(default_factory=list)
    settings: IRSettings | None = None
    ui_components: Dict[str, IRUIComponent] = field(default_factory=dict)
    tools: Dict[str, IRTool] = field(default_factory=dict)


@dataclass
class IRPlugin:
    name: str
    description: str | None = None


@dataclass
class IRTool:
    name: str
    kind: str | None = None
    method: str | None = None
    url_template: str | None = None
    url_expr: ast_nodes.Expr | None = None
    headers: Dict[str, Expr] = field(default_factory=dict)
    query_params: Dict[str, Expr] = field(default_factory=dict)
    body_fields: Dict[str, Expr] = field(default_factory=dict)
    body_template: Expr | None = None
    input_fields: list[str] = field(default_factory=list)


SUPPORTED_MEMORY_PIPELINE_TYPES = {"llm_summarizer", "llm_fact_extractor"}
SUPPORTED_PII_POLICIES = {"none", "strip-email-ip"}
SUPPORTED_MEMORY_SCOPES = {"per_session", "per_user", "shared"}
SUPPORTED_RECORD_FIELD_TYPES = {"string", "text", "int", "float", "bool", "uuid", "datetime"}


def _collect_input_refs(expr: ast_nodes.Expr | None) -> set[str]:
    refs: set[str] = set()

    def _visit(node: ast_nodes.Expr | ast_nodes.RecordField | None) -> None:
        if node is None:
            return
        if isinstance(node, ast_nodes.RecordFieldAccess):
            parts: list[str] = []
            current = node
            while isinstance(current, ast_nodes.RecordFieldAccess):
                parts.insert(0, current.field or "")
                current = current.target
            if isinstance(current, ast_nodes.Identifier) and (current.name or "") == "input" and parts:
                refs.add(".".join(parts))
                return
            _visit(current)
            return
        if isinstance(node, ast_nodes.Identifier):
            name = node.name or ""
            if name.startswith("input.") and len(name.split(".", 1)) == 2:
                refs.add(name.split(".", 1)[1])
            return
        if isinstance(node, ast_nodes.RecordField):
            _visit(node.value)
            return
        if isinstance(node, ast_nodes.RecordLiteral):
            for field in node.fields:
                _visit(field)
            return
        if not hasattr(node, "__dict__"):
            return
        for value in node.__dict__.values():
            if isinstance(value, ast_nodes.Expr):
                _visit(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, ast_nodes.Expr) or isinstance(item, ast_nodes.RecordField):
                        _visit(item)
            elif isinstance(value, ast_nodes.RecordField):
                _visit(value)

    _visit(expr)
    return refs


def _collect_input_refs_from_dict(exprs: dict[str, ast_nodes.Expr] | None) -> set[str]:
    refs: set[str] = set()
    if not exprs:
        return refs
    for value in exprs.values():
        refs.update(_collect_input_refs(value))
    return refs


def _lower_memory_pipeline_steps(
    steps: list[ast_nodes.AiMemoryPipelineStep] | None,
    ai_name: str,
    kind: str,
) -> list[IRMemoryPipelineStep] | None:
    if not steps:
        return None
    lowered: list[IRMemoryPipelineStep] = []
    for step in steps:
        step_name = (step.name or "").strip()
        step_type = (step.type or "").strip()
        if not step_name:
            raise IRError(
                f"N3L-1203: Memory pipeline step on '{ai_name}' ({kind}) requires a non-empty name.",
                step.span.line if step.span else None,
            )
        if step_type not in SUPPORTED_MEMORY_PIPELINE_TYPES:
            raise IRError(
                f"N3L-1203: Unknown memory pipeline type '{step_type}' on AI '{ai_name}' ({kind}). Supported types: 'llm_fact_extractor', 'llm_summarizer'.",
                step.span.line if step.span else None,
            )
        max_tokens = step.max_tokens
        if max_tokens is not None and max_tokens <= 0:
            raise IRError(
                f"N3L-1202: max_tokens must be positive on pipeline step '{step_name}' for AI '{ai_name}' ({kind}).",
                step.span.line if step.span else None,
            )
        lowered.append(
            IRMemoryPipelineStep(
                name=step_name,
                type=step_type,
                max_tokens=max_tokens,
            )
        )
    return lowered


def _extract_policy_fields(
    cfg: ast_nodes.AiShortTermMemoryConfig | ast_nodes.AiLongTermMemoryConfig | ast_nodes.AiProfileMemoryConfig,
    ai_name: str,
    kind: str,
) -> tuple[int | None, str | None, str | None]:
    retention = getattr(cfg, "retention_days", None)
    if retention is not None and retention <= 0:
        raise IRError(
            f"N3L-1202: retention_days must be a positive integer on AI '{ai_name}' kind '{kind}'.",
            cfg.span.line if cfg.span else None,
        )
    pii_policy = (getattr(cfg, "pii_policy", None) or "").strip() or None
    if pii_policy and pii_policy not in SUPPORTED_PII_POLICIES:
        supported = ", ".join(sorted(SUPPORTED_PII_POLICIES))
        raise IRError(
            f"N3L-1204: Unknown pii_policy '{pii_policy}' on AI '{ai_name}' kind '{kind}'. Supported: {supported}.",
            cfg.span.line if cfg.span else None,
        )
    scope = (getattr(cfg, "scope", None) or "").strip() or None
    if scope and scope not in SUPPORTED_MEMORY_SCOPES:
        supported = ", ".join(sorted(SUPPORTED_MEMORY_SCOPES))
        raise IRError(
            f"N3L-1205: Unknown memory scope '{scope}' on AI '{ai_name}' kind '{kind}'. Supported: {supported}.",
            cfg.span.line if cfg.span else None,
        )
    return retention, pii_policy, scope


def _lower_ai_memory_config(
    mem: ast_nodes.AiMemoryConfig,
    ai_name: str,
) -> tuple[IRAiMemoryConfig, list[str | None]]:
    short_term_ast = mem.short_term
    if short_term_ast is None and (mem.kind or mem.window or mem.store):
        short_term_ast = ast_nodes.AiShortTermMemoryConfig(window=mem.window, store=mem.store)
    short_term_cfg = None
    if short_term_ast:
        window = short_term_ast.window or mem.window or DEFAULT_SHORT_TERM_WINDOW
        if window is not None and window <= 0:
            raise IRError(
                f"N3L-1202: memory window must be a positive integer on AI '{ai_name}'.",
                mem.span.line if mem.span else None,
            )
        retention, pii_policy, scope = _extract_policy_fields(short_term_ast, ai_name, "short_term")
        short_term_cfg = IRAiShortTermMemoryConfig(
            window=window,
            store=short_term_ast.store or mem.store,
            retention_days=retention,
            pii_policy=pii_policy,
            scope=scope,
        )
    long_term_cfg = None
    if mem.long_term:
        retention, pii_policy, scope = _extract_policy_fields(mem.long_term, ai_name, "long_term")
        long_term_cfg = IRAiLongTermMemoryConfig(
            store=mem.long_term.store,
            pipeline=_lower_memory_pipeline_steps(mem.long_term.pipeline, ai_name, "long_term"),
            retention_days=retention,
            pii_policy=pii_policy,
            scope=scope,
        )
    profile_cfg = None
    if mem.profile:
        retention, pii_policy, scope = _extract_policy_fields(mem.profile, ai_name, "profile")
        profile_cfg = IRAiProfileMemoryConfig(
            store=mem.profile.store,
            extract_facts=mem.profile.extract_facts,
            pipeline=_lower_memory_pipeline_steps(mem.profile.pipeline, ai_name, "profile"),
            retention_days=retention,
            pii_policy=pii_policy,
            scope=scope,
        )
    recall_rules: list[IRAiRecallRule] = []
    for rule in mem.recall or []:
        source = (rule.source or "").strip()
        if source not in {"short_term", "long_term", "profile"}:
            raise IRError(
                f"N3L-1202: Recall rule source '{source}' on AI '{ai_name}' is invalid.",
                rule.span.line if rule.span else (mem.span.line if mem.span else None),
            )
        recall_rules.append(
            IRAiRecallRule(
                source=source,
                count=rule.count,
                top_k=rule.top_k,
                include=rule.include,
            )
        )
    if not recall_rules and short_term_cfg:
        recall_rules.append(IRAiRecallRule(source="short_term", count=short_term_cfg.window))
    defined_sources = {
        "short_term": bool(short_term_cfg),
        "long_term": bool(long_term_cfg),
        "profile": bool(profile_cfg),
    }
    for rule in recall_rules:
        if not defined_sources.get(rule.source):
            raise IRError(
                f"N3L-1202: Recall rule refers to memory source '{rule.source}' but no '{rule.source}' kind is defined on AI '{ai_name}'.",
                mem.span.line if mem.span else None,
            )
    ir_config = IRAiMemoryConfig(
        kind=mem.kind,
        window=mem.window,
        store=mem.store,
        short_term=short_term_cfg,
        long_term=long_term_cfg,
        profile=profile_cfg,
        recall=recall_rules,
    )
    return ir_config, ir_config.referenced_store_names()


def _evaluate_record_default(
    expr: ast_nodes.Expr | None,
    record_name: str,
    field_name: str,
    field_type: str,
) -> object | None:
    if expr is None:
        return None
    if isinstance(expr, ast_nodes.Literal):
        return expr.value
    if isinstance(expr, ast_nodes.Identifier):
        ident = (expr.name or "").strip()
        if ident == "now" and field_type == "datetime":
            return "now"
    raise IRError(
        f"N3L-1501: Default value for field '{field_name}' on record '{record_name}' must be a literal "
        f"(strings, numbers, booleans) or 'now' for datetime fields.",
        expr.span.line if expr.span else None,
    )


def ast_to_ir(module: ast_nodes.Module) -> IRProgram:
    program = IRProgram()
    page_names = {decl.name for decl in module.declarations if isinstance(decl, ast_nodes.PageDecl)}
    allowed_memory_types = {"conversation", "user", "global"}
    macro_defs: dict[str, ast_nodes.Expr] = {}
    rulegroups: dict[str, dict[str, ast_nodes.Expr]] = {}
    ai_memory_refs: list[tuple[str, str, int | None]] = []
    agent_memory_refs: list[tuple[str, str, int | None]] = []
    page_routes: dict[str, str] = {}
    memory_store_refs: list[tuple[str, str | None]] = []
    ai_tool_refs: list[tuple[str, str, int | None]] = []
    def lower_flow_item(step: ast_nodes.FlowStepDecl | ast_nodes.FlowLoopDecl) -> IRFlowStep | IRFlowLoop:
        if isinstance(step, ast_nodes.FlowLoopDecl):
            body_items = [lower_flow_item(s) for s in step.steps]
            flat_body: list[IRFlowStep | IRFlowLoop] = []
            for item in body_items:
                if isinstance(item, list):
                    flat_body.extend(item)
                else:
                    flat_body.append(item)
            return IRFlowLoop(name=step.name, var_name=step.var_name, iterable=step.iterable, body=flat_body)
        if step.statements:
            ir_statements = [lower_statement(stmt) for stmt in step.statements]
            return IRFlowStep(
                name=step.name,
                kind="script",
                target=step.target or step.name,
                message=getattr(step, "message", None),
                params=getattr(step, "params", {}) or {},
                statements=ir_statements,
                when_expr=getattr(step, "when_expr", None),
                streaming=getattr(step, "streaming", False),
                stream_channel=getattr(step, "stream_channel", None),
                stream_role=getattr(step, "stream_role", None),
                stream_label=getattr(step, "stream_label", None),
                stream_mode=getattr(step, "stream_mode", None),
                tools_mode=getattr(step, "tools_mode", None),
            )
        if step.conditional_branches:
            branches: list[IRConditionalBranch] = [lower_branch(br) for br in step.conditional_branches]
            return IRFlowStep(
                name=step.name,
                kind="condition",
                target=step.name,
                conditional_branches=branches,
                params=getattr(step, "params", {}) or {},
                when_expr=getattr(step, "when_expr", None),
                streaming=getattr(step, "streaming", False),
                stream_channel=getattr(step, "stream_channel", None),
                stream_role=getattr(step, "stream_role", None),
                stream_label=getattr(step, "stream_label", None),
                stream_mode=getattr(step, "stream_mode", None),
                tools_mode=getattr(step, "tools_mode", None),
            )
        if step.kind not in (
            "ai",
            "agent",
            "tool",
            "goto_flow",
            "frame_insert",
            "frame_query",
            "frame_update",
            "frame_delete",
            "vector_index_frame",
            "vector_query",
            "db_create",
            "db_get",
            "db_update",
            "db_delete",
            "auth_register",
            "auth_login",
            "auth_logout",
            "for_each",
        ):
            raise IRError(f"Unsupported step kind '{step.kind}'", step.span and step.span.line)
        if step.kind == "tool":
            if not step.target:
                raise IRError("N3L-963: Tool call step must specify a target tool.", step.span and step.span.line)
            if step.target not in program.tools and step.target not in BUILTIN_TOOL_NAMES:
                raise IRError(
                    f"N3L-1400: Tool '{step.target}' referenced in step '{step.name}' is not declared.",
                    step.span and step.span.line,
                )
        if step.kind in {"vector_index_frame", "vector_query"}:
            vector_store_name = (step.params or {}).get("vector_store") or step.target
            if not vector_store_name:
                raise IRError("N3L-930: vector step must specify a 'vector_store'.", step.span and step.span.line)
            if vector_store_name not in program.vector_stores:
                raise IRError(
                    f"N3L-931: Vector store '{vector_store_name}' is not declared.",
                    step.span and step.span.line,
                )
            if step.kind == "vector_query" and "query_text" not in (step.params or {}):
                raise IRError("N3L-941: vector_query step must define 'query_text'.", step.span and step.span.line)
        return IRFlowStep(
            name=step.name,
            kind=step.kind,
            target=step.target,
            message=getattr(step, "message", None),
            params=getattr(step, "params", {}) or {},
            when_expr=getattr(step, "when_expr", None),
            streaming=getattr(step, "streaming", False),
            stream_channel=getattr(step, "stream_channel", None),
            stream_role=getattr(step, "stream_role", None),
            stream_label=getattr(step, "stream_label", None),
            stream_mode=getattr(step, "stream_mode", None),
            tools_mode=getattr(step, "tools_mode", None),
        )

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
        if isinstance(expr, ast_nodes.VarRef):
            return expr, None
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
        if isinstance(stmt, ast_nodes.TryCatchStatement):
            try_body = [lower_statement(s) for s in stmt.try_block]
            catch_body = [lower_statement(s) for s in stmt.catch_block]
            return IRTryCatch(try_body=try_body, error_name=stmt.error_identifier, catch_body=catch_body)
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
        cond = None
        macro_origin = None
        if br.condition is not None:
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

    def lower_style_map(style: dict[str, str] | None) -> dict[str, str]:
        return dict(style or {})

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
            return IRHeading(
                text=el.text,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.TextNode):
            return IRText(
                text=el.text,
                expr=getattr(el, "expr", None),
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.ImageNode):
            return IRImage(
                url=el.url,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.EmbedFormNode):
            return IREmbedForm(
                form_name=el.form_name,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.SectionDecl):
            sec_children_raw = [lower_layout_element(child, collected_states) for child in el.layout]
            sec_children = [c for c in sec_children_raw if c is not None]
            return IRSection(
                name=el.name,
                components=[],
                layout=sec_children,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.UIInputNode):
            if el.field_type and el.field_type not in {"text", "number", "email", "secret", "long_text", "date"}:
                raise IRError("N3U-2101: invalid input type", getattr(el, "span", None) and getattr(el.span, "line", None))
            validation = None
            if getattr(el, "validation", None):
                v = el.validation
                validation = {
                    key: getattr(v, key)
                    for key in ["required", "min_length", "max_length", "pattern", "message"]
                    if getattr(v, key) is not None
                }
            return IRUIInput(
                label=el.label,
                var_name=el.var_name,
                field_type=el.field_type,
                validation=validation,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
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
                    elif act.kind == "navigate":
                        if not act.target_path and not act.target_page_name:
                            raise IRError("N3L-950: navigate action must specify a path or page.", getattr(act, "span", None) and getattr(act.span, "line", None))
                        if act.target_page_name and act.target_page_name not in page_names:
                            raise IRError(
                                f"N3L-1301: Page '{act.target_page_name}' referenced in navigate action does not exist.",
                                getattr(act, "span", None) and getattr(act.span, "line", None),
                            )
                        actions.append(
                            IRUIEventAction(
                                kind="navigate",
                                target=act.target_page_name or act.target_path,
                                target_path=act.target_path,
                                target_page=act.target_page_name,
                                args={},
                            )
                        )
                    else:
                        raise IRError("N3U-2202: invalid action in click handler", getattr(act, "span", None) and getattr(act.span, "line", None))
            return IRUIButton(
                label=el.label,
                label_expr=getattr(el, "label_expr", None),
                actions=actions,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.CardNode):
            children_raw = [lower_layout_element(child, collected_states) for child in el.children]
            children = [c for c in children_raw if c is not None]
            return IRCard(
                title=el.title or None,
                layout=children,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.RowNode):
            children_raw = [lower_layout_element(child, collected_states) for child in el.children]
            children = [c for c in children_raw if c is not None]
            return IRRow(
                layout=children,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.ColumnNode):
            children_raw = [lower_layout_element(child, collected_states) for child in el.children]
            children = [c for c in children_raw if c is not None]
            return IRColumn(
                layout=children,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.TextareaNode):
            validation = None
            if getattr(el, "validation", None):
                v = el.validation
                validation = {
                    key: getattr(v, key)
                    for key in ["required", "min_length", "max_length", "pattern", "message"]
                    if getattr(v, key) is not None
                }
            return IRTextarea(
                label=el.label,
                var_name=el.var_name,
                validation=validation,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.BadgeNode):
            return IRBadge(
                text=el.text,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.MessageListNode):
            children_raw = [lower_layout_element(child, collected_states) for child in el.children]
            children = [c for c in children_raw if c is not None]
            return IRMessageList(
                layout=children,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
        if isinstance(el, ast_nodes.MessageNode):
            return IRMessage(
                name=el.name,
                role=el.role,
                text_expr=el.text_expr,
                styles=lower_styles(el.styles),
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
            )
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
                class_name=getattr(el, "class_name", None),
                style=lower_style_map(getattr(el, "style", None)),
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
                class_name=getattr(decl, "class_name", None),
                style=lower_style_map(getattr(decl, "style", None)),
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
                        class_name=getattr(sec, "class_name", None),
                        style=lower_style_map(getattr(sec, "style", None)),
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
                class_name=getattr(decl, "class_name", None),
                style=lower_style_map(getattr(decl, "style", None)),
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
            mem_cfg = None
            if getattr(decl, "memory", None):
                mem_cfg, store_refs = _lower_ai_memory_config(decl.memory, decl.name)
                for store_name in store_refs:
                    memory_store_refs.append((decl.name, store_name))
            tool_bindings: list[IRAiToolBinding] = []
            seen_exposed: set[str] = set()
            for binding in getattr(decl, "tools", []) or []:
                internal_name = binding.internal_name or ""
                exposed_name = binding.exposed_name or internal_name
                if not internal_name:
                    continue
                if exposed_name in seen_exposed:
                    raise IRError(
                        f"N3L-1411: AI '{decl.name}' cannot expose tool name '{exposed_name}' more than once.",
                        binding.span and binding.span.line,
                    )
                seen_exposed.add(exposed_name)
                tool_bindings.append(
                    IRAiToolBinding(
                        internal_name=internal_name,
                        exposed_name=exposed_name,
                    )
                )
                ai_tool_refs.append((decl.name, internal_name, binding.span and binding.span.line))

            program.ai_calls[decl.name] = IRAiCall(
                name=decl.name,
                model_name=decl.model_name,
                provider=getattr(decl, "provider", None),
                input_source=decl.input_source,
                description=getattr(decl, "description", None),
                system_prompt=getattr(decl, "system_prompt", None),
                memory_name=getattr(decl, "memory_name", None),
                memory=mem_cfg,
                tools=tool_bindings,
            )
            if getattr(decl, "memory_name", None):
                ai_memory_refs.append((decl.name, decl.memory_name or "", decl.span and decl.span.line))
        elif isinstance(decl, ast_nodes.AgentDecl):
            if decl.name in program.agents:
                raise IRError(
                    f"Duplicate agent '{decl.name}'", decl.span and decl.span.line
                )

            agent_branches: list[IRConditionalBranch] | None = None
            if getattr(decl, "conditional_branches", None):
                agent_branches = [lower_branch(br) for br in decl.conditional_branches or []]
            program.agents[decl.name] = IRAgent(
                name=decl.name, goal=decl.goal, personality=decl.personality, conditional_branches=agent_branches, system_prompt=getattr(decl, "system_prompt", None), memory_name=getattr(decl, "memory_name", None)
            )
            if getattr(decl, "memory_name", None):
                agent_memory_refs.append((decl.name, decl.memory_name or "", decl.span and decl.span.line))
        elif isinstance(decl, ast_nodes.MemoryDecl):
            if decl.name in program.memories:
                raise IRError(
                    f"Duplicate memory '{decl.name}'", decl.span and decl.span.line
                )
            if not decl.memory_type:
                raise IRError(
                    f"Memory '{decl.name}' must specify a type.",
                    decl.span and decl.span.line,
                )
            if decl.memory_type and decl.memory_type not in allowed_memory_types:
                raise IRError(
                    f"Memory '{decl.name}' has unsupported type '{decl.memory_type}'",
                    decl.span and decl.span.line,
                )
            program.memories[decl.name] = IRMemory(
                name=decl.name, memory_type=decl.memory_type, retention=decl.retention
            )
        elif isinstance(decl, ast_nodes.FrameDecl):
            if decl.name in program.frames:
                raise IRError(
                    f"Duplicate frame '{decl.name}'", decl.span and decl.span.line
                )
            if not (decl.source_path or decl.backend):
                raise IRError("N3F-1000: frame source not specified", decl.span and decl.span.line)
            if decl.backend and decl.backend not in {"memory", "sqlite", "postgres"}:
                raise IRError(
                    f"Unsupported frame backend '{decl.backend}'", decl.span and decl.span.line
                )
            where_expr, _ = transform_expr(decl.where)
            program.frames[decl.name] = IRFrame(
                name=decl.name,
                source_kind=decl.source_kind or decl.backend or "file",
                path=decl.source_path,
                backend=decl.backend,
                table=decl.table,
                primary_key=decl.primary_key,
                delimiter=decl.delimiter,
                has_headers=decl.has_headers,
                select_cols=decl.select_cols or [],
                where=where_expr,
            )
        elif isinstance(decl, ast_nodes.RecordDecl):
            if decl.name in program.records:
                raise IRError(
                    f"Duplicate record '{decl.name}'", decl.span and decl.span.line
                )
            if not decl.frame:
                raise IRError(
                    f"N3L-1500: Record '{decl.name}' must reference a frame.",
                    decl.span and decl.span.line,
                )
            if decl.frame not in program.frames:
                raise IRError(
                    f"N3L-1500: Record '{decl.name}' references unknown frame '{decl.frame}'.",
                    decl.span and decl.span.line,
                )
            if not decl.fields:
                raise IRError(
                    f"Record '{decl.name}' must declare at least one field.",
                    decl.span and decl.span.line,
                )
            field_map: dict[str, IRRecordField] = {}
            primary_key_name: str | None = None
            for field in decl.fields:
                field_name = (field.name or "").strip()
                if not field_name:
                    raise IRError(
                        f"Record '{decl.name}' has a field with no name.",
                        field.span and field.span.line,
                    )
                if field_name in field_map:
                    raise IRError(
                        f"Record '{decl.name}' declares field '{field_name}' more than once.",
                        field.span and field.span.line,
                    )
                field_type = (field.type or "").strip().lower()
                if not field_type:
                    raise IRError(
                        f"N3L-1501: Field '{field_name}' on record '{decl.name}' is missing a type.",
                        field.span and field.span.line,
                    )
                if field_type not in SUPPORTED_RECORD_FIELD_TYPES:
                    raise IRError(
                        f"N3L-1501: Field '{field_name}' on record '{decl.name}' has unsupported type '{field_type}'. "
                        f"Supported types: {', '.join(sorted(SUPPORTED_RECORD_FIELD_TYPES))}.",
                        field.span and field.span.line,
                    )
                default_value = _evaluate_record_default(field.default_expr, decl.name, field_name, field_type) if getattr(field, "default_expr", None) else None
                if field.primary_key:
                    if primary_key_name and primary_key_name != field_name:
                        raise IRError(
                            f"Record '{decl.name}' may only declare one primary_key field.",
                            field.span and field.span.line,
                        )
                    primary_key_name = field_name
                field_map[field_name] = IRRecordField(
                    name=field_name,
                    type=field_type,
                    primary_key=bool(field.primary_key),
                    required=bool(field.required) or bool(field.primary_key),
                    default=default_value,
                )
            if not primary_key_name:
                raise IRError(
                    f"Record '{decl.name}' must declare a primary_key field.",
                    decl.span and decl.span.line,
                )
            program.records[decl.name] = IRRecord(
                name=decl.name,
                frame=decl.frame,
                fields=field_map,
                primary_key=primary_key_name,
            )
        elif isinstance(decl, ast_nodes.AuthDecl):
            if program.auth is not None:
                raise IRError("N3L-1600: Auth configuration already defined.", decl.span and decl.span.line)
            if not decl.user_record:
                raise IRError("N3L-1600: Auth configuration must specify user_record.", decl.span and decl.span.line)
            if decl.user_record not in program.records:
                raise IRError(
                    f"N3L-1600: Auth configuration references unknown user_record '{decl.user_record}'.",
                    decl.span and decl.span.line,
                )
            record = program.records[decl.user_record]
            id_field = decl.id_field or record.primary_key
            if not id_field or id_field not in record.fields:
                raise IRError(
                    "N3L-1600: Auth configuration id_field must reference an existing primary key field.",
                    decl.span and decl.span.line,
                )
            if record.primary_key and id_field != record.primary_key:
                raise IRError(
                    f"N3L-1600: Auth id_field '{id_field}' must match record primary key '{record.primary_key}'.",
                    decl.span and decl.span.line,
                )
            identifier_field = decl.identifier_field or ""
            password_hash_field = decl.password_hash_field or ""
            for fname, label in [
                (identifier_field, "identifier_field"),
                (password_hash_field, "password_hash_field"),
            ]:
                if not fname or fname not in record.fields:
                    raise IRError(
                        f"N3L-1600: Auth {label} '{fname or '?'}' does not exist on user_record '{record.name}'.",
                        decl.span and decl.span.line,
                    )
            program.auth = IRAuth(
                backend=decl.backend or "default_auth",
                user_record=decl.user_record,
                id_field=id_field,
                identifier_field=identifier_field,
                password_hash_field=password_hash_field,
            )
        elif isinstance(decl, ast_nodes.VectorStoreDecl):
            if decl.name in program.vector_stores:
                raise IRError(f"Duplicate vector_store '{decl.name}'", decl.span and decl.span.line)
            if not decl.backend:
                raise IRError(f"N3L-900: Vector store '{decl.name}' must specify a backend.", decl.span and decl.span.line)
            if not decl.frame:
                raise IRError(f"N3L-901: Vector store '{decl.name}' must reference a frame.", decl.span and decl.span.line)
            if decl.frame not in program.frames:
                raise IRError(
                    f"N3L-901: Vector store '{decl.name}' references unknown frame '{decl.frame}'.",
                    decl.span and decl.span.line,
                )
            if not decl.embedding_model:
                raise IRError(
                    f"N3L-902: Vector store '{decl.name}' must specify an embedding_model.", decl.span and decl.span.line
                )
            if not decl.text_column or not decl.id_column:
                raise IRError(
                    f"N3L-903: Vector store '{decl.name}' must specify text_column and id_column.",
                    decl.span and decl.span.line,
                )
            program.vector_stores[decl.name] = IRVectorStore(
                name=decl.name,
                backend=decl.backend,
                frame=decl.frame,
                text_column=decl.text_column,
                id_column=decl.id_column,
                embedding_model=decl.embedding_model,
                options=decl.options or {},
            )
        elif isinstance(decl, ast_nodes.ToolDeclaration):
            if decl.name in program.tools:
                raise IRError(f"Duplicate tool '{decl.name}'", decl.span and decl.span.line)
            if not decl.kind or decl.kind != "http_json":
                raise IRError(
                    f"N3L-960: Tool '{decl.name}' must specify kind 'http_json' (only 'http_json' is supported in this phase).",
                    decl.span and decl.span.line,
                )
            allowed_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
            if not decl.method or decl.method.upper() not in allowed_methods:
                raise IRError(
                    f"N3L-961: Tool '{decl.name}' must specify method among {sorted(allowed_methods)}.",
                    decl.span and decl.span.line,
                )
            if not decl.url_expr and not decl.url_template:
                raise IRError(
                    f"N3L-962: Tool '{decl.name}' must define a URL.",
                    decl.span and decl.span.line,
                )
            for key in decl.headers.keys():
                if not key:
                    raise IRError(
                        f"N3L-962: Tool '{decl.name}' has an empty header name.",
                        decl.span and decl.span.line,
                    )
            for key in decl.query_params.keys():
                if not key:
                    raise IRError(
                        f"N3L-962: Tool '{decl.name}' has an empty query parameter name.",
                        decl.span and decl.span.line,
                    )
            for key in decl.body_fields.keys():
                if not key:
                    raise IRError(
                        f"N3L-962: Tool '{decl.name}' has an empty body field name.",
                        decl.span and decl.span.line,
                    )
            input_refs = set()
            input_refs.update(_collect_input_refs(decl.url_expr))
            input_refs.update(_collect_input_refs_from_dict(decl.headers))
            input_refs.update(_collect_input_refs_from_dict(decl.query_params))
            input_refs.update(_collect_input_refs_from_dict(decl.body_fields))
            input_refs.update(_collect_input_refs(decl.body_template))
            program.tools[decl.name] = IRTool(
                name=decl.name,
                kind=decl.kind,
                method=decl.method.upper() if decl.method else None,
                url_template=decl.url_template,
                url_expr=decl.url_expr,
                headers=decl.headers or {},
                query_params=decl.query_params or {},
                body_fields=decl.body_fields or {},
                body_template=decl.body_template,
                input_fields=sorted(input_refs),
            )
        elif isinstance(decl, ast_nodes.FlowDecl):
            if decl.name in program.flows:
                raise IRError(
                    f"Duplicate flow '{decl.name}'", decl.span and decl.span.line
                )
            flow_steps: List[IRFlowStep | IRFlowLoop] = []
            for step in decl.steps:
                ir_item = lower_flow_item(step)
                flow_steps.append(ir_item)
            program.flows[decl.name] = IRFlow(
                name=decl.name,
                description=decl.description,
                steps=flow_steps,
                error_steps=[],  # placeholder, filled below
            )
            # Lower error handler steps if present
            error_steps_ir: List[IRFlowStep] = []
            for step in getattr(decl, "error_steps", []) or []:
                ir_item = lower_flow_item(step)
                if isinstance(ir_item, IRFlowLoop):
                    raise IRError("Loops are not allowed in error handlers", step.span and step.span.line)
                error_steps_ir.append(ir_item)
            program.flows[decl.name].error_steps = error_steps_ir
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
        for binding in getattr(ai_call, "tools", []) or []:
            tool_name = binding.internal_name
            if tool_name not in program.tools and tool_name not in BUILTIN_TOOL_NAMES:
                line = None
                for ai_name, internal, span_line in ai_tool_refs:
                    if ai_name == ai_call.name and internal == tool_name:
                        line = span_line
                        break
                raise IRError(
                    f"N3L-1410: Tool '{tool_name}' referenced on AI '{ai_call.name}' is not declared.",
                    line,
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

    # Validate memory references for ai and agents now that memories are collected.
    for ai_name, mem_name, line in ai_memory_refs:
        if mem_name not in program.memories:
            raise IRError(
                f"AI block '{ai_name}' references unknown memory '{mem_name}'.",
                line,
            )
    for agent_name, mem_name, line in agent_memory_refs:
        if mem_name not in program.memories:
            raise IRError(
                f"Agent '{agent_name}' references unknown memory '{mem_name}'.",
                line,
            )

    # Validate configured memory stores for AI memory configs.
    if memory_store_refs:
        cfg = load_config()
        configured_stores = set((cfg.memory_stores or {}).keys())
        if "default_memory" not in configured_stores:
            configured_stores.add("default_memory")
        for ai_name, store_name in memory_store_refs:
            resolved_store = store_name or "default_memory"
            if resolved_store not in configured_stores:
                raise IRError(
                    f"N3L-1201: Memory store '{resolved_store}' referenced on AI '{ai_name}' is not configured for this project.",
                    None,
                    )

    program.rulegroups = rulegroups
    providers_cfg = getattr(load_config(), "providers_config", None)
    provider_names = set((providers_cfg.providers if providers_cfg else {}).keys())
    default_provider = providers_cfg.default if providers_cfg else None
    for ai_name, ai_call in program.ai_calls.items():
        if getattr(ai_call, "provider", None):
            if ai_call.provider not in provider_names:
                raise IRError(
                    f"N3L-1800: AI '{ai_name}' references unknown provider '{ai_call.provider}'. Check your namel3ss config.",
                    getattr(ai_call, "span", None) and getattr(ai_call, "span", None).line,
                )
        elif not provider_names and default_provider is None:
            raise IRError(
                "N3L-1800: No default provider configured. Add a provider in namel3ss.config or set ai 'provider is \"...\"'.",
                getattr(ai_call, "span", None) and getattr(ai_call, "span", None).line,
            )

    for flow in program.flows.values():
        for step in flow.steps:
            if isinstance(step, IRFlowLoop):
                continue
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
                if step.target not in program.tools and step.target not in BUILTIN_TOOL_NAMES:
                    raise IRError(
                        f"Flow '{flow.name}' references missing tool '{step.target}'"
                    )
            elif step.kind in {"condition", "script"}:
                continue
            elif step.kind in {"frame_insert", "frame_query"}:
                if step.target not in program.frames:
                    raise IRError(
                        f"Flow '{flow.name}' references missing frame '{step.target}'",
                        None,
                    )
            elif step.kind in {"db_create", "db_get", "db_update", "db_delete"}:
                record = program.records.get(step.target)
                if not record:
                    raise IRError(
                        f"N3L-1500: Flow '{flow.name}' references missing record '{step.target}'.",
                        None,
                    )
                params = step.params or {}
                if step.kind == "db_create":
                    values = params.get("values")
                    if not isinstance(values, dict) or not values:
                        raise IRError(
                            f"Step '{step.name}' must define a non-empty 'values' block for record '{record.name}'.",
                            None,
                        )
                    missing_required = [
                        fname
                        for fname, field in record.fields.items()
                        if (field.required or field.primary_key)
                        and field.default is None
                        and fname not in values
                    ]
                    if missing_required:
                        raise IRError(
                            f"N3L-1502: Step '{step.name}' must provide field '{missing_required[0]}' when creating record '{record.name}'.",
                            None,
                        )
                elif step.kind == "db_update":
                    by_id = params.get("by_id") or {}
                    if record.primary_key and record.primary_key not in by_id:
                        raise IRError(
                            f"Step '{step.name}' must specify primary key '{record.primary_key}' inside 'by id' when updating record '{record.name}'.",
                            None,
                        )
                    set_block = params.get("set")
                    if not isinstance(set_block, dict) or not set_block:
                        raise IRError(
                            f"Step '{step.name}' must define a non-empty 'set' block when updating record '{record.name}'.",
                            None,
                        )
                elif step.kind == "db_delete":
                    by_id = params.get("by_id") or {}
                    if record.primary_key and record.primary_key not in by_id:
                        raise IRError(
                            f"Step '{step.name}' must specify primary key '{record.primary_key}' inside 'by id' when deleting record '{record.name}'.",
                            None,
                        )
                elif step.kind == "db_get":
                    by_id = params.get("by_id")
                    if by_id and record.primary_key and record.primary_key not in by_id:
                        raise IRError(
                            f"Step '{step.name}' must reference primary key '{record.primary_key}' inside 'by id' when querying record '{record.name}'.",
                            None,
                        )
            elif step.kind in {"auth_register", "auth_login", "auth_logout"}:
                if not program.auth:
                    raise IRError("N3L-1600: Auth configuration is not declared.", None)
                auth_record_name = program.auth.user_record
                if not auth_record_name or auth_record_name not in program.records:
                    raise IRError("N3L-1600: Auth configuration references unknown user_record.", None)
                if step.kind in {"auth_register", "auth_login"}:
                    input_block = (step.params or {}).get("input") or {}
                    if not isinstance(input_block, dict) or not input_block:
                        raise IRError(f"Step '{step.name}' must define an 'input' block.", None)
                    identifier_field = program.auth.identifier_field or ""
                    if identifier_field not in input_block:
                        raise IRError(
                            f"Step '{step.name}' must provide '{identifier_field}' inside 'input' for authentication.",
                            None,
                        )
                    if "password" not in input_block:
                        raise IRError(
                            f"Step '{step.name}' must provide 'password' inside 'input' for authentication.",
                            None,
                        )
            elif step.kind == "goto_flow":
                continue

    _validate_flow_scopes(program)

    return program


class _FlowScope:
    def __init__(self, locals: set[str] | None = None, active_loops: set[str] | None = None, all_loop_vars: set[str] | None = None):
        self.locals = set(locals or [])
        self.active_loops = set(active_loops or [])
        self.all_loop_vars = set(all_loop_vars or [])

    def copy(self) -> "_FlowScope":
        return _FlowScope(set(self.locals), set(self.active_loops), set(self.all_loop_vars))


def _validate_flow_scopes(program: IRProgram) -> None:
    if not program.flows:
        return

    def _collect_step_names(items: list[IRFlowStep | IRFlowLoop], names: set[str], loop_vars: set[str]) -> None:
        for item in items:
            if isinstance(item, IRFlowLoop):
                loop_vars.add(item.var_name)
                _collect_step_names(item.body, names, loop_vars)
            else:
                names.add(item.name)
                if item.statements:
                    _collect_statement_step_names(item.statements, names, loop_vars)

    def _collect_statement_step_names(stmts: list[IRStatement], names: set[str], loop_vars: set[str]) -> None:
        for stmt in stmts:
            if isinstance(stmt, IRForEach):
                loop_vars.add(stmt.var_name)
                _collect_statement_step_names(stmt.body, names, loop_vars)

    def _iter_exprs(obj: Any) -> list[ast_nodes.Expr]:
        exprs: list[ast_nodes.Expr] = []
        if isinstance(obj, ast_nodes.Expr):
            exprs.append(obj)
        elif isinstance(obj, dict):
            for val in obj.values():
                exprs.extend(_iter_exprs(val))
        elif isinstance(obj, list):
            for val in obj:
                exprs.extend(_iter_exprs(val))
        return exprs

    def _merge_record_access(expr: ast_nodes.RecordFieldAccess) -> ast_nodes.VarRef | None:
        if isinstance(expr.target, ast_nodes.VarRef):
            return ast_nodes.VarRef(
                name=f"{expr.target.root}.{'.'.join(expr.target.path + [expr.field])}",
                root=expr.target.root,
                path=list(expr.target.path) + [expr.field],
                kind=expr.target.kind,
                span=getattr(expr, "span", None),
            )
        return None

    def _validate_varref(
        varref: ast_nodes.VarRef,
        scope: _FlowScope,
        flow_name: str,
        all_steps: set[str],
        steps_seen: set[str],
    ) -> None:
        root = varref.root
        if root == "step":
            step_name = varref.path[0] if varref.path else ""
            if not step_name:
                raise IRError(
                    f"N3L-1702: Step reference is missing a name in flow '{flow_name}'.",
                    varref.span and varref.span.line,
                )
            if step_name not in all_steps:
                raise IRError(
                    f"N3L-1702: Step '{step_name}' is referenced but no step with that name exists in flow '{flow_name}'.",
                    varref.span and varref.span.line,
                )
            if step_name not in steps_seen:
                raise IRError(
                    f"N3L-1701: Step '{step_name}' is referenced before it is defined in flow '{flow_name}'.",
                    varref.span and varref.span.line,
                )
            varref.kind = ast_nodes.VarRefKind.STEP_OUTPUT
            return
        if root == "state":
            varref.kind = ast_nodes.VarRefKind.STATE
            return
        if root == "user":
            varref.kind = ast_nodes.VarRefKind.USER
            return
        if root == "secret":
            varref.kind = ast_nodes.VarRefKind.SECRET
            return
        if root == "input":
            varref.kind = ast_nodes.VarRefKind.INPUT
            return
        if root == "env":
            varref.kind = ast_nodes.VarRefKind.ENV
            return
        if root == "config":
            varref.kind = ast_nodes.VarRefKind.CONFIG
            return
        if root in scope.active_loops:
            varref.kind = ast_nodes.VarRefKind.LOOP_VAR
            return
        if root in scope.all_loop_vars:
            raise IRError(
                f"N3L-1703: Loop variable '{root}' is used outside of its loop in flow '{flow_name}'.",
                varref.span and varref.span.line,
            )
        if root in scope.locals:
            varref.kind = ast_nodes.VarRefKind.LOCAL
            return
        raise IRError(
            f"N3L-1700: Unknown variable '{root}' in flow '{flow_name}'. Did you mean 'state.{root}' or declare it with 'let {root} is ...'?",
            varref.span and varref.span.line,
        )

    def _walk_expr(expr: ast_nodes.Expr, scope: _FlowScope, flow_name: str, all_steps: set[str], steps_seen: set[str]) -> None:
        if isinstance(expr, ast_nodes.VarRef):
            _validate_varref(expr, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.Identifier):
            temp_varref = ast_nodes.VarRef(name=expr.name, root=expr.name, path=[], kind=ast_nodes.VarRefKind.UNKNOWN, span=expr.span)
            _validate_varref(temp_varref, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.RecordFieldAccess):
            merged = _merge_record_access(expr)
            if merged:
                _validate_varref(merged, scope, flow_name, all_steps, steps_seen)
                return
            if expr.target:
                _walk_expr(expr.target, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.BinaryOp):
            if expr.left:
                _walk_expr(expr.left, scope, flow_name, all_steps, steps_seen)
            if expr.right:
                _walk_expr(expr.right, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.UnaryOp):
            if expr.operand:
                _walk_expr(expr.operand, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.FunctionCall):
            for arg in expr.args:
                _walk_expr(arg, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.ListLiteral):
            for item in expr.items:
                _walk_expr(item, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.PatternExpr):
            _walk_expr(expr.subject, scope, flow_name, all_steps, steps_seen)
            for pair in expr.pairs:
                _walk_expr(pair.value, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.ListBuiltinCall):
            if expr.expr:
                _walk_expr(expr.expr, scope, flow_name, all_steps, steps_seen)
            return
        if isinstance(expr, ast_nodes.BuiltinCall):
            for arg in expr.args:
                _walk_expr(arg, scope, flow_name, all_steps, steps_seen)
            return

    def _walk_statements(stmts: list[IRStatement], scope: _FlowScope, flow_name: str, all_steps: set[str], steps_seen: set[str]) -> None:
        for stmt in stmts:
            if isinstance(stmt, IRLet):
                if stmt.expr:
                    _walk_expr(stmt.expr, scope, flow_name, all_steps, steps_seen)
                scope.locals.add(stmt.name)
            elif isinstance(stmt, IRSet):
                if stmt.expr:
                    _walk_expr(stmt.expr, scope, flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRAction):
                for expr in _iter_exprs(stmt.args):
                    _walk_expr(expr, scope, flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRIf):
                for br in stmt.branches:
                    if br.condition:
                        _walk_expr(br.condition, scope, flow_name, all_steps, steps_seen)
                    branch_scope = scope.copy()
                    _walk_statements(br.actions, branch_scope, flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRForEach):
                if stmt.iterable:
                    _walk_expr(stmt.iterable, scope, flow_name, all_steps, steps_seen)
                loop_scope = scope.copy()
                loop_scope.active_loops.add(stmt.var_name)
                loop_scope.all_loop_vars.add(stmt.var_name)
                _walk_statements(stmt.body, loop_scope, flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRRepeatUpTo):
                if stmt.count:
                    _walk_expr(stmt.count, scope, flow_name, all_steps, steps_seen)
                _walk_statements(stmt.body, scope.copy(), flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRMatch):
                if stmt.expr:
                    _walk_expr(stmt.expr, scope, flow_name, all_steps, steps_seen)
                for br in stmt.branches:
                    if br.expr:
                        _walk_expr(br.expr, scope, flow_name, all_steps, steps_seen)
                    _walk_statements(br.actions, scope.copy(), flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRRetry):
                _walk_statements(stmt.body, scope.copy(), flow_name, all_steps, steps_seen)
            elif isinstance(stmt, IRReturn):
                if stmt.expr:
                    _walk_expr(stmt.expr, scope, flow_name, all_steps, steps_seen)

    def _walk_flow_items(items: list[IRFlowStep | IRFlowLoop], scope: _FlowScope, flow_name: str, all_steps: set[str], steps_seen: set[str]) -> None:
        for item in items:
            if isinstance(item, IRFlowLoop):
                if item.iterable:
                    _walk_expr(item.iterable, scope, flow_name, all_steps, steps_seen)
                loop_scope = scope.copy()
                loop_scope.active_loops.add(item.var_name)
                loop_scope.all_loop_vars.add(item.var_name)
                _walk_flow_items(item.body, loop_scope, flow_name, all_steps, steps_seen)
            else:
                for expr in _iter_exprs(item.params):
                    _walk_expr(expr, scope, flow_name, all_steps, steps_seen)
                if item.when_expr:
                    _walk_expr(item.when_expr, scope, flow_name, all_steps, steps_seen)
                if item.statements:
                    _walk_statements(item.statements, scope.copy(), flow_name, all_steps, steps_seen)
                steps_seen.add(item.name)

    for flow in program.flows.values():
        all_steps: set[str] = set()
        loop_vars: set[str] = set()
        _collect_step_names(flow.steps, all_steps, loop_vars)
        scope = _FlowScope(locals=set(), active_loops=set(), all_loop_vars=loop_vars)
        steps_seen: set[str] = set()
        _walk_flow_items(flow.steps, scope, flow.name, all_steps, steps_seen)
