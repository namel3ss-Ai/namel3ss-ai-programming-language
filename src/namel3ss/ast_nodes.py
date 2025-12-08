"""
AST node definitions for the Namel3ss V3 language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


@dataclass
class Span:
    """Location span for diagnostics."""

    line: int
    column: int


@dataclass
class Module:
    """Top-level module comprising declarations."""

    declarations: List["Declaration"] = field(default_factory=list)


@dataclass
class UseImport:
    """use \"file.ai\""""

    path: str
    span: Optional[Span] = None


@dataclass
class AppDecl:
    """app \"name\": description and entry point."""

    name: str
    description: Optional[str] = None
    entry_page: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class PageDecl:
    """page \"name\": title and route."""

    name: str
    title: Optional[str] = None
    route: Optional[str] = None
    description: Optional[str] = None
    properties: List["PageProperty"] = field(default_factory=list)
    ai_calls: List["AICallRef"] = field(default_factory=list)
    agents: List["PageAgentRef"] = field(default_factory=list)
    memories: List["PageMemoryRef"] = field(default_factory=list)
    sections: List["SectionDecl"] = field(default_factory=list)
    layout: List["LayoutElement"] = field(default_factory=list)
    styles: List["UIStyle"] = field(default_factory=list)
    class_name: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class ModelDecl:
    """model \"name\": provider declaration."""

    name: str
    provider: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AiToolBinding:
    internal_name: str
    exposed_name: str
    span: Optional[Span] = None


@dataclass
class AICallDecl:
    """ai \"name\": AI call binding to a model."""

    name: str
    model_name: Optional[str] = None
    provider: Optional[str] = None
    input_source: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    memory_name: Optional[str] = None
    memory: Optional["AiMemoryConfig"] = None
    tools: List[AiToolBinding] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class AICallRef:
    """Reference to an AI call inside a page."""

    name: str
    span: Optional[Span] = None


@dataclass
class PageProperty:
    """Key-value property inside a page."""

    key: str
    value: str
    span: Optional[Span] = None


@dataclass
class PageAgentRef:
    """Reference to an agent inside a page."""

    name: str
    span: Optional[Span] = None


@dataclass
class PageMemoryRef:
    """Reference to a memory inside a page."""

    name: str
    span: Optional[Span] = None


@dataclass
class AgentDecl:
    """agent \"name\": goal and personality."""

    name: str
    goal: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    conditional_branches: Optional[List["ConditionalBranch"]] = None
    memory_name: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class MemoryDecl:
    """memory "name": memory type."""

    name: str
    memory_type: Optional[str] = None
    retention: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AiShortTermMemoryConfig:
    window: Optional[int] = None
    store: Optional[str] = None
    retention_days: Optional[int] = None
    pii_policy: Optional[str] = None
    scope: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AiLongTermMemoryConfig:
    store: Optional[str] = None
    pipeline: Optional[list["AiMemoryPipelineStep"]] = None
    retention_days: Optional[int] = None
    pii_policy: Optional[str] = None
    scope: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AiProfileMemoryConfig:
    store: Optional[str] = None
    extract_facts: Optional[bool] = None
    pipeline: Optional[list["AiMemoryPipelineStep"]] = None
    retention_days: Optional[int] = None
    pii_policy: Optional[str] = None
    scope: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AiMemoryPipelineStep:
    name: str = ""
    type: str = ""
    max_tokens: Optional[int] = None
    span: Optional[Span] = None


@dataclass
class AiRecallRule:
    source: str = ""
    count: Optional[int] = None
    top_k: Optional[int] = None
    include: Optional[bool] = None
    span: Optional[Span] = None


@dataclass
class AiMemoryConfig:
    kind: Optional[str] = None
    window: Optional[int] = None
    store: Optional[str] = None
    short_term: Optional[AiShortTermMemoryConfig] = None
    long_term: Optional[AiLongTermMemoryConfig] = None
    profile: Optional[AiProfileMemoryConfig] = None
    recall: List[AiRecallRule] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class FrameDecl:
    """frame \"name\": data source and query."""

    name: str
    backend: str | None = None
    table: str | None = None
    primary_key: str | None = None
    source_kind: str | None = None
    source_path: str | None = None
    delimiter: str | None = None
    has_headers: bool = False
    select_cols: List[str] = field(default_factory=list)
    where: Optional["Expr"] = None
    span: Optional[Span] = None


@dataclass
class RecordFieldDecl:
    name: str
    type: str
    primary_key: bool = False
    required: bool = False
    default_expr: "Expr" | None = None
    span: Optional[Span] = None


@dataclass
class RecordDecl:
    name: str
    frame: str
    fields: List[RecordFieldDecl] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class AuthDecl:
    backend: str | None = None
    user_record: str | None = None
    id_field: str | None = None
    identifier_field: str | None = None
    password_hash_field: str | None = None
    span: Optional[Span] = None


@dataclass
class VectorStoreDecl:
    """vector_store \"name\": semantic index definition."""

    name: str
    backend: str | None = None
    frame: str | None = None
    text_column: str | None = None
    id_column: str | None = None
    embedding_model: str | None = None
    options: Dict[str, Any] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class MacroDecl:
    """macro \"name\" using ai \"model\": description/sample/parameters."""

    name: str
    ai_model: str
    description: str | None = None
    sample: str | None = None
    parameters: List[str] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class MacroUse:
    """use macro \"name\" with arguments."""

    macro_name: str
    args: Dict[str, Expr] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class HelperDecl:
    """define helper \"name\": reusable helper."""

    name: str
    identifier: str
    params: List[str] = field(default_factory=list)
    return_name: Optional[str] = None
    body: List["Statement | FlowAction"] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class ModuleUse:
    module: str
    span: Optional[Span] = None


@dataclass
class ImportDecl:
    module: str
    kind: str
    name: str
    alias: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class SettingEntry:
    key: str
    expr: Expr


@dataclass
class EnvConfig:
    name: str
    entries: List[SettingEntry] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class ThemeEntry:
    key: str
    value: str
    span: Optional[Span] = None


@dataclass
class SettingsDecl:
    envs: List[EnvConfig] = field(default_factory=list)
    theme: List[ThemeEntry] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class PluginDecl:
    """plugin \"name\": description."""

    name: str
    description: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class ComponentDecl:
    """component \"type\" with key/value props."""

    type: str
    props: List["PageProperty"] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class SectionDecl:
    """section grouping components on a page."""

    name: str
    components: List[ComponentDecl] = field(default_factory=list)
    layout: List["LayoutElement"] = field(default_factory=list)
    styles: List["UIStyle"] = field(default_factory=list)
    class_name: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class FlowStepDecl:
    """step \"name\" within a flow."""

    name: str
    kind: str
    target: str
    message: Optional[str] = None
    params: Dict[str, Expr] = field(default_factory=dict)
    statements: List["Statement | FlowAction"] = field(default_factory=list)
    conditional_branches: Optional[list["ConditionalBranch"]] = None
    when_expr: Optional[Expr] = None
    streaming: bool = False
    stream_channel: Optional[str] = None
    stream_role: Optional[str] = None
    stream_label: Optional[str] = None
    stream_mode: Optional[str] = None
    tools_mode: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class FlowLoopDecl:
    """for each loop within a flow."""

    name: str
    var_name: str
    iterable: Expr
    steps: List[FlowStepDecl | "FlowLoopDecl"] = field(default_factory=list)
    span: Optional[Span] = None


@dataclass
class FlowDecl:
    """flow \"name\": collection of steps."""

    name: str
    description: Optional[str] = None
    steps: List[FlowStepDecl | FlowLoopDecl] = field(default_factory=list)
    error_steps: List[FlowStepDecl] = field(default_factory=list)
    span: Optional[Span] = None


# Expressions for conditions
@dataclass
class Expr:
    span: Optional[Span] = None


@dataclass
class Identifier(Expr):
    name: str = ""


@dataclass
class Literal(Expr):
    value: object = None


@dataclass
class FunctionCall(Expr):
    name: str = ""
    args: List[Expr] = field(default_factory=list)


@dataclass
class UnaryOp(Expr):
    op: str = ""
    operand: Expr | None = None


@dataclass
class BinaryOp(Expr):
    left: Expr | None = None
    op: str = ""
    right: Expr | None = None


@dataclass
class PatternPair:
    key: str
    value: Expr


@dataclass
class PatternExpr(Expr):
    subject: Identifier = field(default_factory=Identifier)
    pairs: List[PatternPair] = field(default_factory=list)


class VarRefKind(str, Enum):
    UNKNOWN = "unknown"
    STATE = "state"
    USER = "user"
    STEP_OUTPUT = "step_output"
    LOCAL = "local"
    LOOP_VAR = "loop_var"
    INPUT = "input"
    SECRET = "secret"
    ENV = "env"
    CONFIG = "config"


@dataclass
class VarRef(Expr):
    name: str = ""
    root: str = ""
    path: List[str] = field(default_factory=list)
    kind: VarRefKind = VarRefKind.UNKNOWN


@dataclass
class ListLiteral(Expr):
    items: List[Expr] = field(default_factory=list)


@dataclass
class IndexExpr(Expr):
    seq: Expr | None = None
    index: Expr | None = None


@dataclass
class SliceExpr(Expr):
    seq: Expr | None = None
    start: Expr | None = None
    end: Expr | None = None


@dataclass
class RecordField:
    key: str
    value: Expr


@dataclass
class RecordLiteral(Expr):
    fields: List[RecordField] = field(default_factory=list)


@dataclass
class RecordFieldAccess(Expr):
    target: Expr | None = None
    field: str = ""


@dataclass
class ListBuiltinCall(Expr):
    name: str = ""
    expr: Expr | None = None
    predicate: Expr | None = None
    mapper: Expr | None = None
    var_name: str = "item"


@dataclass
class FilterExpression(Expr):
    source: Expr | None = None
    var_name: str = "item"
    predicate: Expr | None = None


@dataclass
class MapExpression(Expr):
    source: Expr | None = None
    var_name: str = "item"
    mapper: Expr | None = None


@dataclass
class BuiltinCall(Expr):
    name: str = ""
    args: List[Expr] = field(default_factory=list)


@dataclass
class AnyExpression(Expr):
    source: Expr | None = None
    var_name: str = "item"
    predicate: Expr | None = None


@dataclass
class AllExpression(Expr):
    source: Expr | None = None
    var_name: str = "item"
    predicate: Expr | None = None


@dataclass
class Statement:
    span: Optional[Span] = None


@dataclass
class LetStatement(Statement):
    name: str = ""
    expr: Expr | None = None
    uses_equals: bool = False


@dataclass
class SetStatement(Statement):
    name: str = ""
    expr: Expr | None = None


@dataclass
class ForEachLoop(Statement):
    var_name: str = "item"
    iterable: Expr | None = None
    body: List["Statement | FlowAction"] = field(default_factory=list)


@dataclass
class RepeatUpToLoop(Statement):
    count: Expr | None = None
    body: List["Statement | FlowAction"] = field(default_factory=list)


@dataclass
class InputValidation:
    field_type: str | None = None
    min_expr: Expr | None = None
    max_expr: Expr | None = None


@dataclass
class AskUserStatement(Statement):
    label: str = ""
    var_name: str = ""
    validation: InputValidation | None = None


@dataclass
class FormField:
    label: str = ""
    name: str = ""
    validation: InputValidation | None = None


@dataclass
class FormStatement(Statement):
    label: str = ""
    name: str = ""
    fields: List[FormField] = field(default_factory=list)


@dataclass
class LogStatement(Statement):
    level: str = "info"
    message: str = ""
    metadata: Expr | None = None


@dataclass
class NoteStatement(Statement):
    message: str = ""


@dataclass
class CheckpointStatement(Statement):
    label: str = ""


@dataclass
class ReturnStatement(Statement):
    expr: Expr | None = None


@dataclass
class SuccessPattern:
    binding: str | None = None


@dataclass
class ErrorPattern:
    binding: str | None = None


@dataclass
class MatchBranch:
    pattern: Expr | SuccessPattern | ErrorPattern | None = None
    actions: List["Statement | FlowAction"] = field(default_factory=list)
    binding: str | None = None
    label: str | None = None


@dataclass
class MatchStatement(Statement):
    target: Expr | None = None
    branches: List[MatchBranch] = field(default_factory=list)


@dataclass
class RetryStatement(Statement):
    count: Expr | None = None
    with_backoff: bool = False
    body: List["Statement | FlowAction"] = field(default_factory=list)


@dataclass
class TryCatchStatement(Statement):
    try_block: List["Statement | FlowAction"] = field(default_factory=list)
    error_identifier: str = ""
    catch_block: List["Statement | FlowAction"] = field(default_factory=list)


@dataclass
class RuleGroupRefExpr(Expr):
    group_name: str = ""
    condition_name: Optional[str] = None


@dataclass
class FlowAction:
    kind: str
    target: str
    message: Optional[str] = None
    args: Dict[str, Expr] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class NavigateAction:
    kind: str = "navigate"
    target_path: str | None = None
    target_page_name: str | None = None
    span: Optional[Span] = None


ClickAction = Union[FlowAction, NavigateAction]


@dataclass
class ConditionalBranch:
    condition: Optional[Expr]
    actions: List[Statement | FlowAction] = field(default_factory=list)
    label: Optional[str] = None
    binding: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class IfStatement(Statement):
    branches: List[ConditionalBranch] = field(default_factory=list)


@dataclass
class ConditionMacroDecl:
    """define condition "name" as: <expr>"""

    name: str
    expr: Expr
    span: Optional[Span] = None


@dataclass
class RuleGroupCondition:
    name: str
    expr: Expr
    span: Optional[Span] = None


@dataclass
class RuleGroupDecl:
    """define rulegroup "name": group of named conditions."""

    name: str
    conditions: List[RuleGroupCondition] = field(default_factory=list)
    span: Optional[Span] = None


# Layout elements (UI-1)
@dataclass
class LayoutElement:
    span: Optional[Span] = None
    styles: List["UIStyle"] = field(default_factory=list)
    class_name: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)


@dataclass
class HeadingNode(LayoutElement):
    text: str = ""


@dataclass
class TextNode(LayoutElement):
    text: str = ""
    expr: Expr | None = None


@dataclass
class ImageNode(LayoutElement):
    url: str = ""


@dataclass
class EmbedFormNode(LayoutElement):
    form_name: str = ""


@dataclass
class CardNode(LayoutElement):
    title: str = ""
    children: List["LayoutElement"] = field(default_factory=list)


@dataclass
class RowNode(LayoutElement):
    children: List["LayoutElement"] = field(default_factory=list)


@dataclass
class ColumnNode(LayoutElement):
    children: List["LayoutElement"] = field(default_factory=list)


@dataclass
class TextareaNode(LayoutElement):
    label: str = ""
    var_name: str | None = None
    validation: UIValidationRules | None = None


@dataclass
class BadgeNode(LayoutElement):
    text: str = ""


@dataclass
class MessageListNode(LayoutElement):
    children: List["MessageNode"] = field(default_factory=list)


@dataclass
class MessageNode(LayoutElement):
    name: str | None = None
    role: Expr | None = None
    text_expr: Expr | None = None


@dataclass
class UIStyle:
    kind: str
    value: object
    span: Optional[Span] = None


@dataclass
class UIValidationRules:
    required: bool | None = None
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None
    message: str | None = None


@dataclass
class UIComponentDecl:
    name: str
    params: List[str] = field(default_factory=list)
    render: List["LayoutElement"] = field(default_factory=list)
    styles: List[UIStyle] = field(default_factory=list)
    class_name: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)
    span: Optional[Span] = None


@dataclass
class UIComponentCall(LayoutElement):
    name: str = ""
    args: List[Expr] = field(default_factory=list)
    named_args: Dict[str, List["Statement | FlowAction"]] = field(default_factory=dict)
    class_name: Optional[str] = None
    style: Dict[str, str] = field(default_factory=dict)


@dataclass
class UIStateDecl(LayoutElement):
    name: str = ""
    expr: Expr | None = None


@dataclass
class UIInputNode(LayoutElement):
    label: str = ""
    var_name: str = ""
    field_type: str | None = None
    validation: UIValidationRules | None = None


@dataclass
class UIClickHandler(LayoutElement):
    actions: List[ClickAction] = field(default_factory=list)


@dataclass
class UIButtonNode(LayoutElement):
    label: str = ""
    label_expr: Expr | None = None
    handler: Optional[UIClickHandler] = None


@dataclass
class UIConditional(LayoutElement):
    condition: Expr | None = None
    when_children: List["LayoutElement"] = field(default_factory=list)
    otherwise_children: List["LayoutElement"] = field(default_factory=list)


@dataclass
class ToolDeclaration:
    name: str
    kind: str | None = None
    method: str | None = None
    url_template: str | None = None  # legacy placeholder-based templates
    url_expr: Expr | None = None
    headers: Dict[str, Expr] = field(default_factory=dict)
    query_params: Dict[str, Expr] = field(default_factory=dict)
    body_fields: Dict[str, Expr] = field(default_factory=dict)
    body_template: Expr | None = None  # legacy body expression
    span: Optional[Span] = None


Declaration = Union[
    UseImport,
    AppDecl,
    PageDecl,
    ModelDecl,
    AICallDecl,
    AgentDecl,
    MemoryDecl,
    FrameDecl,
    RecordDecl,
    AuthDecl,
    VectorStoreDecl,
    MacroDecl,
    MacroUse,
    HelperDecl,
    ModuleUse,
    ImportDecl,
    SettingsDecl,
    FlowDecl,
    PluginDecl,
    ConditionMacroDecl,
    RuleGroupDecl,
    UIComponentDecl,
    ToolDeclaration,
]
