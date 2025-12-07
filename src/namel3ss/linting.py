from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

try:  # Python 3.11+
    import tomllib
except Exception:  # pragma: no cover - platform fallback
    tomllib = None

from . import ast_nodes
from .diagnostics.structured import Diagnostic as StructuredDiagnostic
from .parser import parse_source


@dataclass
class LintFinding:
    rule_id: str
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    span: Optional[object] = None

    def to_diagnostic(self) -> StructuredDiagnostic:
        return StructuredDiagnostic(
            code=self.rule_id,
            category="lint",
            severity=self.severity,
            message=self.message,
            hint=None,
            file=self.file,
            line=self.line,
            column=self.column,
        )


@dataclass
class LintConfig:
    """Simple lint configuration loaded from toml if available."""

    rule_levels: Dict[str, str] = field(default_factory=dict)

    def severity_for(self, rule_id: str, default: str) -> Optional[str]:
        level = self.rule_levels.get(rule_id, default).lower()
        if level in {"off", "none"}:
            return None
        return level

    @classmethod
    def load(cls, project_root: Optional[Path]) -> "LintConfig":
        if project_root is None:
            return cls()
        cfg_path: Optional[Path] = None
        for candidate in ("namel3ss.toml", "n3.config"):
            p = project_root / candidate
            if p.exists():
                cfg_path = p
                break
        if not cfg_path or not tomllib:
            return cls()
        try:
            data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:  # pragma: no cover - fallback on invalid config
            return cls()
        lint_section = data.get("lint", {}) if isinstance(data, dict) else {}
        alias_map = {
            "unused_bindings": "N3-L001",
            "unused_helper": "N3-L002",
            "match_unreachable": "N3-L003",
            "loop_bound": "N3-L004",
            "shadowed_vars": "N3-L005",
            "prefer_english_let": "N3-L006",
        }
        levels: Dict[str, str] = {}
        for key, val in lint_section.items():
            if not isinstance(val, str):
                continue
            rule_id = alias_map.get(key, key)
            levels[rule_id] = val.lower()
        return cls(rule_levels=levels)


def lint_source(source: str, file: Optional[str] = None, config: Optional[LintConfig] = None) -> List[LintFinding]:
    module = parse_source(source)
    return lint_module(module, file=file, config=config)


def lint_module(module: ast_nodes.Module, file: Optional[str] = None, config: Optional[LintConfig] = None) -> List[LintFinding]:
    config = config or LintConfig()
    findings: list[LintFinding] = []
    helper_names: set[str] = set()
    helper_calls: set[str] = set()

    for decl in module.declarations:
        if isinstance(decl, ast_nodes.HelperDecl):
            helper_names.add(decl.identifier)
            helper_calls |= _collect_helper_calls(decl.body)
    for decl in module.declarations:
        if isinstance(decl, ast_nodes.FlowDecl):
            used_all = _collect_identifiers_in_steps(decl.steps)
            for step in decl.steps:
                findings.extend(
                    _lint_statements(
                        (step.statements or []) + _actions_from_conditional(step.conditional_branches),
                        helper_calls,
                        file=file,
                        external_used=used_all,
                        config=config,
                    )
                )
        if isinstance(decl, ast_nodes.HelperDecl):
            initial_scope = set(decl.params or [])
            findings.extend(_lint_statements(decl.body, helper_calls, file=file, config=config, initial_scope=initial_scope))
        if isinstance(decl, ast_nodes.SettingsDecl):
            for env in decl.envs:
                for entry in env.entries:
                    if isinstance(entry.expr, ast_nodes.Literal) and entry.expr.value is None:
                        finding = _make("N3-6202", "warning", "Settings entry should have a value", file, entry.expr.span, config)
                        if finding:
                            findings.append(finding)

    unused_helpers = helper_names - helper_calls
    for name in sorted(unused_helpers):
        finding = _make("N3-L002", "warning", f"Helper '{name}' is never called", file, None, config)
        if finding:
            findings.append(finding)
    return findings


def _collect_helper_calls(statements: list[ast_nodes.Statement | ast_nodes.FlowAction]) -> set[str]:
    calls: set[str] = set()
    for stmt in statements:
        calls |= _collect_calls_in_statement(stmt)
    return calls


def _collect_calls_in_statement(stmt: ast_nodes.Statement | ast_nodes.FlowAction) -> set[str]:
    calls: set[str] = set()

    def walk_expr(expr: ast_nodes.Expr | None):
        if expr is None:
            return
        if isinstance(expr, ast_nodes.FunctionCall):
            calls.add(expr.name)
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, ast_nodes.BinaryOp):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, ast_nodes.UnaryOp):
            walk_expr(expr.operand)
        elif isinstance(expr, ast_nodes.PatternExpr):
            for p in expr.pairs:
                walk_expr(p.value)
        elif isinstance(expr, ast_nodes.FilterExpression):
            walk_expr(expr.source)
            walk_expr(expr.predicate)
        elif isinstance(expr, ast_nodes.MapExpression):
            walk_expr(expr.source)
            walk_expr(expr.mapper)
        elif isinstance(expr, ast_nodes.RecordFieldAccess):
            walk_expr(expr.target)
        elif isinstance(expr, ast_nodes.RecordLiteral):
            for f in expr.fields:
                walk_expr(f.value)
        elif isinstance(expr, ast_nodes.ListLiteral):
            for item in expr.items:
                walk_expr(item)
        elif isinstance(expr, ast_nodes.ListBuiltinCall):
            walk_expr(expr.expr)
        elif isinstance(expr, ast_nodes.BuiltinCall):
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, (ast_nodes.IndexExpr, ast_nodes.SliceExpr)):
            walk_expr(expr.seq)
            if hasattr(expr, "index"):
                walk_expr(expr.index)
            if hasattr(expr, "start"):
                walk_expr(expr.start)
            if hasattr(expr, "end"):
                walk_expr(expr.end)

    if isinstance(stmt, (ast_nodes.LetStatement, ast_nodes.SetStatement)):
        walk_expr(stmt.expr)
    elif isinstance(stmt, ast_nodes.LogStatement):
        walk_expr(stmt.metadata)
    elif isinstance(stmt, ast_nodes.IfStatement):
        for br in stmt.branches:
            walk_expr(br.condition)
            for a in br.actions:
                calls |= _collect_calls_in_statement(a)
    elif isinstance(stmt, ast_nodes.MatchStatement):
        walk_expr(stmt.target)
        for br in stmt.branches:
            walk_expr(br.pattern if isinstance(br.pattern, ast_nodes.Expr) else None)
            for a in br.actions:
                calls |= _collect_calls_in_statement(a)
    elif isinstance(stmt, ast_nodes.ForEachLoop):
        walk_expr(stmt.iterable)
        for a in stmt.body:
            calls |= _collect_calls_in_statement(a)
    elif isinstance(stmt, ast_nodes.RepeatUpToLoop):
        walk_expr(stmt.count)
        for a in stmt.body:
            calls |= _collect_calls_in_statement(a)
    elif isinstance(stmt, ast_nodes.RetryStatement):
        walk_expr(stmt.count)
        for a in stmt.body:
            calls |= _collect_calls_in_statement(a)
    elif isinstance(stmt, ast_nodes.ReturnStatement):
        walk_expr(stmt.expr)
    elif isinstance(stmt, ast_nodes.FormStatement):
        for f in stmt.fields:
            if f.validation:
                walk_expr(f.validation.min_expr)
                walk_expr(f.validation.max_expr)
    elif isinstance(stmt, ast_nodes.AskUserStatement):
        if stmt.validation:
            walk_expr(stmt.validation.min_expr)
            walk_expr(stmt.validation.max_expr)
    return calls


def _lint_statements(
    statements: list[ast_nodes.Statement | ast_nodes.FlowAction],
    helper_calls: set[str],
    file: Optional[str],
    external_used: Optional[Set[str]] = None,
    config: Optional[LintConfig] = None,
    initial_scope: Optional[Set[str]] = None,
) -> list[LintFinding]:
    config = config or LintConfig()
    findings: list[LintFinding] = []
    scope_stack: list[Set[str]] = [set(initial_scope or set())]
    declared_global: set[str] = set(initial_scope or set())
    used: set[str] = set()

    def declare(name: str, span):
        nonlocal findings
        for scope in scope_stack:
            if name in scope:
                finding = _make("N3-L005", "warning", f"Variable '{name}' shadows an outer variable", file, span, config)
                if finding:
                    findings.append(finding)
                break
        scope_stack[-1].add(name)
        declared_global.add(name)

    def mark_used(name: str):
        used.add(name)

    def walk_expr(expr: ast_nodes.Expr | None):
        if expr is None:
            return
        if isinstance(expr, ast_nodes.Identifier):
            mark_used(expr.name)
        elif isinstance(expr, ast_nodes.RecordFieldAccess):
            walk_expr(expr.target)
        elif isinstance(expr, ast_nodes.UnaryOp):
            walk_expr(expr.operand)
        elif isinstance(expr, ast_nodes.BinaryOp):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, ast_nodes.PatternExpr):
            for p in expr.pairs:
                walk_expr(p.value)
        elif isinstance(expr, ast_nodes.FunctionCall):
            helper_calls.add(expr.name)
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, ast_nodes.FilterExpression):
            walk_expr(expr.source)
            walk_expr(expr.predicate)
        elif isinstance(expr, ast_nodes.MapExpression):
            walk_expr(expr.source)
            walk_expr(expr.mapper)
        elif isinstance(expr, ast_nodes.BuiltinCall):
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, ast_nodes.ListBuiltinCall):
            walk_expr(expr.expr)
        elif isinstance(expr, ast_nodes.RecordLiteral):
            for f in expr.fields:
                walk_expr(f.value)
        elif isinstance(expr, ast_nodes.ListLiteral):
            for item in expr.items:
                walk_expr(item)
        elif isinstance(expr, ast_nodes.IndexExpr):
            walk_expr(expr.seq)
            walk_expr(expr.index)
        elif isinstance(expr, ast_nodes.SliceExpr):
            walk_expr(expr.seq)
            walk_expr(expr.start)
            walk_expr(expr.end)

    def walk_statement(stmt: ast_nodes.Statement | ast_nodes.FlowAction):
        if isinstance(stmt, ast_nodes.LetStatement):
            declare(stmt.name, stmt.span)
            if stmt.uses_equals:
                finding = _make("N3-L006", "info", f"Prefer 'let {stmt.name} be ...' over '=' style", file, stmt.span, config)
                if finding:
                    findings.append(finding)
                legacy = _make("N3-L007", "warning", "Legacy '=' assignment detected; prefer English 'be'", file, stmt.span, config)
                if legacy:
                    findings.append(legacy)
            walk_expr(stmt.expr)
        elif isinstance(stmt, ast_nodes.SetStatement):
            walk_expr(stmt.expr)
        elif isinstance(stmt, ast_nodes.LogStatement):
            walk_expr(stmt.metadata)
        elif isinstance(stmt, ast_nodes.IfStatement):
            for br in stmt.branches:
                walk_expr(br.condition)
                scope_stack.append(set())
                for a in br.actions:
                    walk_statement(a)
                scope_stack.pop()
        elif isinstance(stmt, ast_nodes.MatchStatement):
            walk_expr(stmt.target)
            seen_literals: set = set()
            for br in stmt.branches:
                if isinstance(br.pattern, ast_nodes.Literal):
                    lit_val = br.pattern.value
                    if lit_val in seen_literals:
                        finding = _make("N3-L003", "warning", "Duplicate match branch is unreachable", file, br.pattern.span, config)
                        if finding:
                            findings.append(finding)
                    else:
                        seen_literals.add(lit_val)
                if isinstance(br.pattern, ast_nodes.Expr):
                    walk_expr(br.pattern)
                scope_stack.append(set())
                for a in br.actions:
                    walk_statement(a)
                scope_stack.pop()
        elif isinstance(stmt, ast_nodes.ForEachLoop):
            declare(stmt.var_name, stmt.span)
            walk_expr(stmt.iterable)
            scope_stack.append(set())
            for a in stmt.body:
                walk_statement(a)
            scope_stack.pop()
        elif isinstance(stmt, ast_nodes.RepeatUpToLoop):
            if isinstance(stmt.count, ast_nodes.Literal) and isinstance(stmt.count.value, (int, float)) and stmt.count.value > 1000:
                finding = _make("N3-L004", "warning", "Loop bound is very large; consider lowering it", file, stmt.count.span, config)
                if finding:
                    findings.append(finding)
            walk_expr(stmt.count)
            scope_stack.append(set())
            for a in stmt.body:
                walk_statement(a)
            scope_stack.pop()
        elif isinstance(stmt, ast_nodes.RetryStatement):
            walk_expr(stmt.count)
            scope_stack.append(set())
            for a in stmt.body:
                walk_statement(a)
            scope_stack.pop()
        elif isinstance(stmt, ast_nodes.AskUserStatement):
            declare(stmt.var_name, stmt.span)
            if stmt.validation:
                walk_expr(stmt.validation.min_expr)
                walk_expr(stmt.validation.max_expr)
        elif isinstance(stmt, ast_nodes.FormStatement):
            declare(stmt.name, stmt.span)
            for f in stmt.fields:
                if f.validation:
                    walk_expr(f.validation.min_expr)
                    walk_expr(f.validation.max_expr)
        elif isinstance(stmt, ast_nodes.ReturnStatement):
            walk_expr(stmt.expr)
        elif isinstance(stmt, ast_nodes.FlowAction):
            # Flow actions do not declare variables.
            pass

    for stmt in statements:
        walk_statement(stmt)

    for name in declared_global:
        if name not in used and (external_used is None or name not in external_used):
            finding = _make("N3-L001", "warning", f"Variable '{name}' is never used", file, None, config)
            if finding:
                findings.append(finding)
    return findings


def _collect_identifiers_in_steps(steps: list[ast_nodes.FlowStepDecl]) -> set[str]:
    names: set[str] = set()

    def walk_expr(expr: ast_nodes.Expr | None):
        if expr is None:
            return
        if isinstance(expr, ast_nodes.Identifier):
            names.add(expr.name)
        elif isinstance(expr, ast_nodes.RecordFieldAccess):
            walk_expr(expr.target)
        elif isinstance(expr, ast_nodes.UnaryOp):
            walk_expr(expr.operand)
        elif isinstance(expr, ast_nodes.BinaryOp):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, ast_nodes.PatternExpr):
            for p in expr.pairs:
                walk_expr(p.value)
        elif isinstance(expr, ast_nodes.FilterExpression):
            walk_expr(expr.source)
            walk_expr(expr.predicate)
        elif isinstance(expr, ast_nodes.MapExpression):
            walk_expr(expr.source)
            walk_expr(expr.mapper)
        elif isinstance(expr, ast_nodes.FunctionCall):
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, ast_nodes.BuiltinCall):
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, ast_nodes.ListBuiltinCall):
            walk_expr(expr.expr)
        elif isinstance(expr, ast_nodes.RecordLiteral):
            for f in expr.fields:
                walk_expr(f.value)
        elif isinstance(expr, ast_nodes.ListLiteral):
            for item in expr.items:
                walk_expr(item)
        elif isinstance(expr, ast_nodes.IndexExpr):
            walk_expr(expr.seq)
            walk_expr(expr.index)
        elif isinstance(expr, ast_nodes.SliceExpr):
            walk_expr(expr.seq)
            walk_expr(expr.start)
            walk_expr(expr.end)

    def walk_statement(stmt: ast_nodes.Statement | ast_nodes.FlowAction):
        if isinstance(stmt, ast_nodes.LetStatement):
            walk_expr(stmt.expr)
        elif isinstance(stmt, ast_nodes.SetStatement):
            walk_expr(stmt.expr)
        elif isinstance(stmt, ast_nodes.IfStatement):
            for br in stmt.branches:
                walk_expr(br.condition)
                for a in br.actions:
                    walk_statement(a)
        elif isinstance(stmt, ast_nodes.MatchStatement):
            walk_expr(stmt.target)
            for br in stmt.branches:
                if isinstance(br.pattern, ast_nodes.Expr):
                    walk_expr(br.pattern)
                for a in br.actions:
                    walk_statement(a)
        elif isinstance(stmt, ast_nodes.ForEachLoop):
            walk_expr(stmt.iterable)
            for a in stmt.body:
                walk_statement(a)
        elif isinstance(stmt, ast_nodes.RepeatUpToLoop):
            walk_expr(stmt.count)
            for a in stmt.body:
                walk_statement(a)
        elif isinstance(stmt, ast_nodes.RetryStatement):
            walk_expr(stmt.count)
            for a in stmt.body:
                walk_statement(a)
        elif isinstance(stmt, ast_nodes.AskUserStatement):
            if stmt.validation:
                walk_expr(stmt.validation.min_expr)
                walk_expr(stmt.validation.max_expr)
        elif isinstance(stmt, ast_nodes.FormStatement):
            for f in stmt.fields:
                if f.validation:
                    walk_expr(f.validation.min_expr)
                    walk_expr(f.validation.max_expr)
        elif isinstance(stmt, ast_nodes.LogStatement):
            walk_expr(stmt.metadata)
        elif isinstance(stmt, ast_nodes.ReturnStatement):
            walk_expr(stmt.expr)
        # FlowAction has no expressions to walk.

    for step in steps:
        for stmt in step.statements or []:
            walk_statement(stmt)
        for br in step.conditional_branches or []:
            walk_expr(br.condition)
            for act in br.actions:
                walk_statement(act)
    return names


def _actions_from_conditional(branches: Optional[list[ast_nodes.ConditionalBranch]]) -> list[ast_nodes.Statement | ast_nodes.FlowAction]:
    actions: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
    for br in branches or []:
        actions.extend(br.actions)
    return actions


def _make(rule_id: str, severity: str, msg: str, file: Optional[str], span, config: Optional[LintConfig]) -> Optional[LintFinding]:
    config = config or LintConfig()
    sev = config.severity_for(rule_id, severity)
    if sev is None:
        return None
    line = getattr(span, "line", None) if span else None
    column = getattr(span, "column", None) if span else None
    return LintFinding(rule_id=rule_id, severity=sev, message=msg, file=file, line=line, column=column, span=span)
