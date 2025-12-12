"""Condition/WHERE parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes

__all__ = [
    "_parse_where_conditions",
    "_combine_conditions",
    "_parse_condition_expr",
    "_parse_condition_and",
    "_parse_condition_primary",
    "_expr_to_condition",
    "_parse_duration_value",
]


def _parse_where_conditions(self) -> ast_nodes.BooleanCondition:
    """Parse English-style WHERE conditions into a boolean condition tree."""
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    conditions: list[ast_nodes.BooleanCondition] = []
    connectors: list[str | None] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        leading: str | None = None
        if self.peek().value in {"and", "or"}:
            leading_tok = self.consume("KEYWORD")
            leading = leading_tok.value
        cond = self._parse_condition_expr()
        conditions.append(cond)
        connectors.append(leading)
        self.optional_newline()
    self.consume("DEDENT")
    if not conditions:
        raise self.error("A WHERE block needs at least one condition.", self.peek())
    if connectors[0] is not None:
        raise self.error(
            "I expected a condition before this connector. Write something like 'is_active is true and status is \"vip\"'.",
            self.peek(),
        )
    return self._combine_conditions(conditions, connectors)


def _combine_conditions(
    self, conditions: list[ast_nodes.BooleanCondition], connectors: list[str | None]
) -> ast_nodes.BooleanCondition:
    if not conditions:
        raise self.error("A WHERE block needs at least one condition.", self.peek())
    # Default connector is AND when omitted.
    segments: list[ast_nodes.BooleanCondition] = []
    current = conditions[0]
    for idx in range(1, len(conditions)):
        op = connectors[idx] or "and"
        right = conditions[idx]
        if op == "and":
            current = ast_nodes.ConditionAnd(left=current, right=right, span=self._span(self.peek()))
        elif op == "or":
            segments.append(current)
            current = right
        else:
            raise self.error("I don't understand this connector. Use 'and' or 'or'.", self.peek())
    segments.append(current)
    result = segments[0]
    for seg in segments[1:]:
        result = ast_nodes.ConditionOr(left=result, right=seg, span=self._span(self.peek()))
    return result


def _parse_condition_expr(self) -> ast_nodes.BooleanCondition:
    left = self._parse_condition_and()
    while not (self.check("NEWLINE") or self.check("DEDENT")) and self.match_value("KEYWORD", "or"):
        right = self._parse_condition_and()
        left = ast_nodes.ConditionOr(left=left, right=right, span=self._span(self.peek()))
    return left


def _parse_condition_and(self) -> ast_nodes.BooleanCondition:
    left = self._parse_condition_primary()
    while not (self.check("NEWLINE") or self.check("DEDENT")) and self.match_value("KEYWORD", "and"):
        right = self._parse_condition_primary()
        left = ast_nodes.ConditionAnd(left=left, right=right, span=self._span(self.peek()))
    return left


def _parse_condition_primary(self) -> ast_nodes.BooleanCondition:
    tok = self.peek()
    # Grouping: all of / any of
    if tok.value in {"all", "any"} and self.peek_offset(1).value == "of":
        is_all = tok.value == "all"
        self.advance()  # consume all/any
        self.consume("KEYWORD", "of")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        children: list[ast_nodes.BooleanCondition] = []
        connectors: list[str | None] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            leading: str | None = None
            if self.peek().value in {"and", "or"}:
                leading = self.consume("KEYWORD").value
            child = self._parse_condition_expr()
            children.append(child)
            connectors.append(leading)
            self.optional_newline()
        self.consume("DEDENT")
        if not children:
            raise self.error(
                f"'{'all' if is_all else 'any'} of:' needs at least one condition inside.",
                tok,
            )
        return (
            ast_nodes.ConditionAllGroup(children=children, span=self._span(tok))
            if is_all
            else ast_nodes.ConditionAnyGroup(children=children, span=self._span(tok))
        )

    field_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
    field_name = field_tok.value or ""
    start_span = self._span(field_tok)
    if not field_name:
        raise self.error("Field name missing in WHERE condition.", field_tok)
    if not self.match_value("KEYWORD", "is"):
        raise self.error(
            "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks.",
            self.peek(),
        )
    next_tok = self.peek()
    if next_tok.type == "KEYWORD" and next_tok.value not in {
        "not",
        "null",
        "greater",
        "less",
        "at",
        "one",
        "true",
        "false",
    }:
        raise self.error(
            "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks.",
            next_tok,
        )
    op = "eq"
    value_expr: ast_nodes.Expr | None = None
    if self.match_value("KEYWORD", "not"):
        if self.match_value("KEYWORD", "null") or self.match_value("IDENT", "null"):
            op = "is_not_null"
        else:
            op = "neq"
            value_expr = self.parse_expression()
    elif self.match_value("KEYWORD", "null") or self.match_value("IDENT", "null"):
        op = "is_null"
    elif self.match_value("KEYWORD", "greater"):
        self.consume("KEYWORD", "than")
        op = "gt"
        value_expr = self.parse_expression()
    elif self.match_value("KEYWORD", "less"):
        self.consume("KEYWORD", "than")
        op = "lt"
        value_expr = self.parse_expression()
    elif self.match_value("KEYWORD", "at"):
        limiter = self.consume("KEYWORD")
        if limiter.value == "least":
            op = "ge"
        elif limiter.value == "most":
            op = "le"
        else:
            raise self.error(
                "I don't understand this condition in a WHERE block. Use 'at least' or 'at most'.",
                limiter,
            )
        value_expr = self.parse_expression()
    elif self.peek().value == "one":
        self.advance()
        self.consume("KEYWORD", "of")
        op = "in"
        value_expr = self.parse_expression()
    else:
        value_expr = self.parse_expression()
    if op in {"eq", "neq", "gt", "lt", "ge", "le", "in"} and value_expr is None:
        raise self.error(
            "I don't understand this condition in a WHERE block. Use 'field is value', 'field is greater than value', or 'field is one of [...]'.",
            self.peek(),
        )
    return self._expr_to_condition(field_name, op, value_expr, start_span)


def _expr_to_condition(
    self, field_name: str, op: str, expr: ast_nodes.Expr | None, span: ast_nodes.Span | None
) -> ast_nodes.BooleanCondition:
    if isinstance(expr, ast_nodes.BinaryOp) and expr.op in {"and", "or"}:
        left_cond = self._expr_to_condition(field_name, op, expr.left, span)
        right_cond = self._expr_to_condition(field_name, op, expr.right, span)
        if expr.op == "and":
            return ast_nodes.ConditionAnd(left=left_cond, right=right_cond, span=span)
        return ast_nodes.ConditionOr(left=left_cond, right=right_cond, span=span)
    if isinstance(expr, ast_nodes.BinaryOp) and expr.op == "==" and isinstance(expr.left, ast_nodes.VarRef):
        return ast_nodes.ConditionLeaf(field_name=expr.left.name, op="eq", value_expr=expr.right, span=span)
    return ast_nodes.ConditionLeaf(field_name=field_name, op=op, value_expr=expr, span=span)


def _parse_duration_value(self) -> ast_nodes.Expr:
    tok = self.peek()
    if tok.type == "NUMBER":
        num_tok = self.consume("NUMBER")
        raw_val = num_tok.value or "0"
        try:
            number: float | int | str
            if "." in raw_val:
                number = float(raw_val)
            else:
                number = int(raw_val)
        except Exception:
            number = raw_val
        unit_tok = self.peek()
        if unit_tok.type in {"IDENT", "KEYWORD"}:
            unit_val = (unit_tok.value or "").lower()
            if unit_val in {"second", "seconds", "sec", "s", "millisecond", "milliseconds", "ms"}:
                self.advance()
                if unit_val.startswith("ms") or unit_val.startswith("millisecond"):
                    try:
                        number = float(number) / 1000.0
                    except Exception:
                        pass
        return ast_nodes.Literal(value=number, span=self._span(num_tok))
    return self.parse_expression()
