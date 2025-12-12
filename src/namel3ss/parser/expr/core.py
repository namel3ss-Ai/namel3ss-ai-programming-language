"""Expression parsing helpers extracted from the legacy parser.

These functions are attached to the legacy `Parser` class as methods with
identical behavior. They rely on the Parser instance to supply token helpers
(`consume`, `match_value`, etc.) and to construct AST nodes via `ast_nodes`.
"""

from __future__ import annotations

from ... import ast_nodes

__all__ = [
    "parse_expression",
    "parse_or",
    "parse_and",
    "parse_not",
    "parse_comparison",
    "parse_add",
    "parse_mul",
    "parse_unary",
    "parse_primary",
    "parse_postfix",
    "parse_list_literal",
    "parse_record_literal",
]


def parse_expression(self) -> ast_nodes.Expr:
    return self.parse_or()


def parse_or(self) -> ast_nodes.Expr:
    expr = self.parse_and()
    while self.match_value("KEYWORD", "or"):
        right = self.parse_and()
        expr = ast_nodes.BinaryOp(left=expr, op="or", right=right)
    return expr


def parse_and(self) -> ast_nodes.Expr:
    expr = self.parse_not()
    while self.match_value("KEYWORD", "and"):
        right = self.parse_not()
        expr = ast_nodes.BinaryOp(left=expr, op="and", right=right)
    return expr


def parse_not(self) -> ast_nodes.Expr:
    if self.match_value("KEYWORD", "not"):
        operand = self.parse_not()
        return ast_nodes.UnaryOp(op="not", operand=operand)
    return self.parse_comparison()


def parse_comparison(self) -> ast_nodes.Expr:
    expr = self.parse_add()
    while True:
        token = self.peek()
        if token.type == "OP" and token.value in {"==", "!=", "<", ">", "<=", ">="}:
            op_tok = self.consume("OP")
            right = self.parse_add()
            expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
            continue
        if token.type == "OP" and token.value == "=":
            self.consume("OP", "=")
            right = self.parse_add()
            expr = ast_nodes.BinaryOp(left=expr, op="==", right=right)
            continue
        if token.type == "KEYWORD" and token.value == "is":
            self.consume("KEYWORD", "is")
            op = "=="
            if self.match_value("KEYWORD", "not"):
                op = "!="
                if self.peek().value == "equal":
                    self.consume("KEYWORD", "equal")
                    if self.peek().value == "to":
                        self.consume("KEYWORD", "to")
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                continue
            if self.match_value("KEYWORD", "greater"):
                if self.peek().value == "than":
                    self.consume("KEYWORD", "than")
                op = ">"
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                continue
            if self.match_value("KEYWORD", "less"):
                if self.peek().value == "than":
                    self.consume("KEYWORD", "than")
                op = "<"
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                continue
            if self.match_value("KEYWORD", "at"):
                if self.match_value("KEYWORD", "least"):
                    op = ">="
                elif self.match_value("KEYWORD", "most"):
                    op = "<="
                else:
                    raise self.error("Expected 'least' or 'most' after 'is at'", self.peek())
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                continue
            if self.peek().value == "equal":
                self.consume("KEYWORD", "equal")
                if self.peek().value == "to":
                    self.consume("KEYWORD", "to")
            right = self.parse_add()
            expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
            continue
        break
    return expr


def parse_add(self) -> ast_nodes.Expr:
    expr = self.parse_mul()
    while True:
        token = self.peek()
        if token.type == "OP" and token.value in {"+", "-"}:
            op_tok = self.consume("OP")
            right = self.parse_mul()
            expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
            continue
        if token.type == "KEYWORD" and token.value in {"plus", "minus"}:
            op_val = "+" if token.value == "plus" else "-"
            self.consume("KEYWORD")
            right = self.parse_mul()
            expr = ast_nodes.BinaryOp(left=expr, op=op_val, right=right)
            continue
        break
    return expr


def parse_mul(self) -> ast_nodes.Expr:
    expr = self.parse_unary()
    while True:
        token = self.peek()
        if token.type == "OP" and token.value in {"*", "/", "%"}:
            op_tok = self.consume("OP")
            right = self.parse_unary()
            expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
            continue
        if token.type == "KEYWORD" and token.value in {"times", "divided"}:
            next_tok = self.peek_offset(1)
            if token.value == "times" and next_tok and next_tok.type in {"COLON", "DEDENT", "NEWLINE", "EOF"}:
                break
            if token.value == "times" and next_tok and next_tok.value in {"with", "backoff"}:
                break
            op_val = "*"
            if token.value == "divided":
                op_val = "/"
                self.consume("KEYWORD", "divided")
                if self.peek().value == "by":
                    self.consume("KEYWORD", "by")
            else:
                self.consume("KEYWORD", "times")
            right = self.parse_unary()
            expr = ast_nodes.BinaryOp(left=expr, op=op_val, right=right)
            continue
        break
    return expr


def parse_unary(self) -> ast_nodes.Expr:
    if self.match_value("OP", "+"):
        return ast_nodes.UnaryOp(op="+", operand=self.parse_unary())
    if self.match_value("OP", "-"):
        return ast_nodes.UnaryOp(op="-", operand=self.parse_unary())
    if self.match_value("KEYWORD", "plus"):
        return ast_nodes.UnaryOp(op="+", operand=self.parse_unary())
    if self.match_value("KEYWORD", "minus"):
        return ast_nodes.UnaryOp(op="-", operand=self.parse_unary())
    token = self.peek()
    if token.value == "get":
        start = self.consume_any({"IDENT", "KEYWORD"})
        target_expr = self.parse_expression()
        self.consume("KEYWORD", "otherwise")
        default_expr = self.parse_expression()
        record_expr, field_name = self._split_field_access_expr(target_expr)
        if not field_name or record_expr is None:
            raise self.error(
                "get ... otherwise ... requires a field access like record.field",
                start,
            )
        return ast_nodes.GetRecordFieldWithDefault(record=record_expr, field=field_name, default=default_expr, span=self._span(start))
    if token.value == "has" and self.peek_offset(1).value == "key":
        start = self.consume_any({"IDENT", "KEYWORD"})
        self.consume("KEYWORD", "key")
        key_tok = self.consume("STRING")
        self.consume("KEYWORD", "on")
        record_expr = self.parse_expression()
        return ast_nodes.HasKeyOnRecord(record=record_expr, key=key_tok.value or "", span=self._span(start))
    builtin_call_names = {
        "length",
        "first",
        "last",
        "sorted",
        "reverse",
        "unique",
        "sum",
        "count",
        "append",
        "remove",
        "insert",
        "trim",
        "lowercase",
        "uppercase",
        "replace",
        "split",
        "join",
        "slugify",
        "minimum",
        "maximum",
        "mean",
        "min",
        "max",
        "average",
        "round",
        "abs",
        "current_timestamp",
        "current_date",
        "random_uuid",
        "filter",
        "map",
        "any",
        "all",
    }
    if token.type in {"IDENT", "KEYWORD"} and self.peek_offset(1).type == "LPAREN" and token.value in builtin_call_names:
        return self.parse_builtin_call()
    if token.type == "KEYWORD" and token.value in {"any"}:
        return self.parse_english_any()
    if token.type == "KEYWORD" and token.value == "all":
        return self.parse_english_all()
    if token.type == "KEYWORD" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "count", "append", "remove", "insert", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "round", "absolute", "current", "random"}:
        return self.parse_english_builtin()
    return self.parse_primary()


def parse_primary(self) -> ast_nodes.Expr:
    token = self.peek()
    if token.type == "STRING":
        tok = self.consume("STRING")
        return ast_nodes.Literal(value=tok.value, span=self._span(tok))
    if token.type == "NUMBER":
        tok = self.consume("NUMBER")
        try:
            num_val: object
            if "." in (tok.value or ""):
                num_val = float(tok.value)
            else:
                num_val = int(tok.value)
        except Exception:
            num_val = tok.value
        expr: ast_nodes.Expr = ast_nodes.Literal(value=num_val, span=self._span(tok))
        return self.parse_postfix(expr)
    if token.type == "LBRACKET":
        return self.parse_postfix(self.parse_list_literal())
    if token.type == "LBRACE":
        return self.parse_postfix(self.parse_record_literal())
    if token.type in {"IDENT", "KEYWORD"}:
        # Function-style builtins
        if self.peek_offset(1).type == "LPAREN" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "count", "append", "remove", "insert", "filter", "map", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "min", "max", "average", "round", "abs", "current_timestamp", "current_date", "random_uuid", "any", "all"}:
            return self.parse_builtin_call()
        if self.peek_offset(1).type == "LPAREN":
            return self.parse_postfix(self.parse_function_call())
        tok = self.consume(token.type)
        if tok.value in {"true", "false"}:
            expr = ast_nodes.Literal(value=tok.value == "true", span=self._span(tok))
        else:
            value = tok.value or ""
            if "." in value:
                parts = value.split(".")
                expr = ast_nodes.VarRef(name=value, root=parts[0], path=parts[1:], kind=ast_nodes.VarRefKind.UNKNOWN, span=self._span(tok))
            else:
                expr = ast_nodes.VarRef(name=value, root=value, path=[], kind=ast_nodes.VarRefKind.UNKNOWN, span=self._span(tok))
        return self.parse_postfix(expr)
    if token.type == "LPAREN":
        self.consume("LPAREN")
        inner = self.parse_expression()
        if not self.match("RPAREN"):
            raise self.error("Expected ')' to close expression", self.peek())
        return self.parse_postfix(inner)
    raise self.error("Expected expression", token)


def parse_postfix(self, expr: ast_nodes.Expr) -> ast_nodes.Expr:
    while True:
        if self.match("LBRACKET"):
            start_expr = None
            end_expr = None
            if self.match("COLON"):
                if not self.check("RBRACKET"):
                    end_expr = self.parse_expression()
            else:
                start_expr = self.parse_expression()
                if self.match("COLON"):
                    if not self.check("RBRACKET"):
                        end_expr = self.parse_expression()
                else:
                    if not self.match("RBRACKET"):
                        raise self.error("Expected ']' after index", self.peek())
                    expr = ast_nodes.IndexExpr(seq=expr, index=start_expr)
                    continue
            if not self.match("RBRACKET"):
                raise self.error("Expected ']' to close slice", self.peek())
            expr = ast_nodes.SliceExpr(seq=expr, start=start_expr, end=end_expr)
            continue
        break
    return expr


def parse_list_literal(self) -> ast_nodes.ListLiteral:
    self.consume("LBRACKET")
    items: list[ast_nodes.Expr] = []
    if self.check("RBRACKET"):
        self.consume("RBRACKET")
        return ast_nodes.ListLiteral(items=items)
    while True:
        items.append(self.parse_expression())
        if self.match("COMMA"):
            continue
        break
    if not self.match("RBRACKET"):
        raise self.error("Expected ']' after list literal", self.peek())
    return ast_nodes.ListLiteral(items=items)


def parse_record_literal(self) -> ast_nodes.RecordLiteral:
    self.consume("LBRACE")
    fields: list[ast_nodes.RecordField] = []
    if self.check("RBRACE"):
        self.consume("RBRACE")
        return ast_nodes.RecordLiteral(fields=fields)
    while not self.check("RBRACE"):
        key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
        self.consume("COLON")
        value_expr = self.parse_expression()
        fields.append(ast_nodes.RecordField(key=key_tok.value or "", value=value_expr))
        if self.match("COMMA"):
            continue
        break
    if not self.match("RBRACE"):
        raise self.error("Expected '}' after record literal", self.peek())
    return ast_nodes.RecordLiteral(fields=fields)
