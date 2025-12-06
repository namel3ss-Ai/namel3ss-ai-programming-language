"""
AST node definitions for the Namel3ss V3 language.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Union


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
    span: Optional[Span] = None


@dataclass
class ModelDecl:
    """model \"name\": provider declaration."""

    name: str
    provider: Optional[str] = None
    span: Optional[Span] = None


@dataclass
class AICallDecl:
    """ai \"name\": AI call binding to a model."""

    name: str
    model_name: Optional[str] = None
    input_source: Optional[str] = None
    description: Optional[str] = None
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
    conditional_branches: Optional[List["ConditionalBranch"]] = None
    span: Optional[Span] = None


@dataclass
class MemoryDecl:
    """memory \"name\": memory type."""

    name: str
    memory_type: Optional[str] = None
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
    span: Optional[Span] = None


@dataclass
class FlowStepDecl:
    """step \"name\" within a flow."""

    name: str
    kind: str
    target: str
    message: Optional[str] = None
    statements: List["Statement | FlowAction"] = field(default_factory=list)
    conditional_branches: Optional[list["ConditionalBranch"]] = None
    span: Optional[Span] = None


@dataclass
class FlowDecl:
    """flow \"name\": collection of steps."""

    name: str
    description: Optional[str] = None
    steps: List[FlowStepDecl] = field(default_factory=list)
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


@dataclass
class Statement:
    span: Optional[Span] = None


@dataclass
class LetStatement(Statement):
    name: str = ""
    expr: Expr | None = None


@dataclass
class SetStatement(Statement):
    name: str = ""
    expr: Expr | None = None


@dataclass
class RuleGroupRefExpr(Expr):
    group_name: str = ""
    condition_name: Optional[str] = None


@dataclass
class FlowAction:
    kind: str
    target: str
    message: Optional[str] = None
    span: Optional[Span] = None


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


Declaration = Union[
    UseImport,
    AppDecl,
    PageDecl,
    ModelDecl,
    AICallDecl,
    AgentDecl,
    MemoryDecl,
    FlowDecl,
    PluginDecl,
    ConditionMacroDecl,
    RuleGroupDecl,
]
