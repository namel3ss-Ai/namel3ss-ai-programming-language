"""Builtin expression parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from ... import ast_nodes

__all__ = [
    "parse_english_builtin",
    "parse_english_all",
    "parse_english_any",
    "parse_builtin_call",
    "parse_function_call",
]


def parse_english_builtin(self) -> ast_nodes.Expr:
    tok = self.consume("KEYWORD")
    name = tok.value or ""
    if name == "sorted":
        if self.peek().value == "form":
            self.consume("KEYWORD", "form")
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.ListBuiltinCall(name=name, expr=operand)
    elif name == "unique":
        if self.peek().value == "elements":
            self.consume("KEYWORD", "elements")
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.ListBuiltinCall(name=name, expr=operand)
    elif name in {"length", "first", "last", "reverse", "sum", "count"}:
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.ListBuiltinCall(name=name, expr=operand)
    elif name in {"trim", "lowercase", "uppercase", "slugify"}:
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.BuiltinCall(name=name, args=[operand])
    elif name == "replace":
        pattern_expr = self.parse_expression()
        self.consume("KEYWORD", "with")
        replacement_expr = self.parse_expression()
        self.consume("KEYWORD", "in")
        base_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="replace", args=[base_expr, pattern_expr, replacement_expr])
    elif name == "append":
        list_expr = self.parse_expression()
        self.consume("KEYWORD", "with")
        value_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="append", args=[list_expr, value_expr])
    elif name == "remove":
        value_expr = self.parse_expression()
        self.consume("KEYWORD", "from")
        list_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="remove", args=[list_expr, value_expr])
    elif name == "insert":
        value_expr = self.parse_expression()
        self.consume("KEYWORD", "at")
        index_expr = self.parse_expression()
        self.consume("KEYWORD", "into")
        list_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="insert", args=[list_expr, index_expr, value_expr])
    elif name == "split":
        base_expr = self.parse_expression()
        self.consume("KEYWORD", "by")
        sep_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="split", args=[base_expr, sep_expr])
    elif name == "join":
        items_expr = self.parse_expression()
        self.consume("KEYWORD", "with")
        sep_expr = self.parse_expression()
        return ast_nodes.BuiltinCall(name="join", args=[items_expr, sep_expr])
    elif name in {"minimum", "maximum", "mean"}:
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.ListBuiltinCall(name=name, expr=operand)
    elif name == "round":
        value_expr = self.parse_unary()
        if self.peek().value == "to":
            self.consume("KEYWORD", "to")
            precision_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="round", args=[value_expr, precision_expr])
        return ast_nodes.BuiltinCall(name="round", args=[value_expr])
    elif name == "absolute":
        if self.peek().value == "value":
            self.consume("KEYWORD", "value")
        if self.peek().value == "of":
            self.consume("KEYWORD", "of")
        operand = self.parse_unary()
        return ast_nodes.BuiltinCall(name="abs", args=[operand])
    elif name == "current":
        next_tok = self.consume("KEYWORD")
        if next_tok.value == "timestamp":
            return ast_nodes.BuiltinCall(name="current_timestamp", args=[])
        if next_tok.value == "date":
            return ast_nodes.BuiltinCall(name="current_date", args=[])
        raise self.error("Expected 'timestamp' or 'date' after 'current'", next_tok)
    elif name == "random":
        next_tok = self.consume("KEYWORD")
        if next_tok.value != "uuid":
            raise self.error("Expected 'uuid' after 'random'", next_tok)
        return ast_nodes.BuiltinCall(name="random_uuid", args=[])
    raise self.error(f"Unsupported builtin '{name}'", tok)


def parse_english_all(self) -> ast_nodes.Expr:
    start = self.consume("KEYWORD", "all")
    # Legacy data syntax is no longer supported; guide users to pipelines.
    raise self.error(
        "The legacy 'all ...' data syntax is no longer supported. Use a collection pipeline instead, for example:\n"
        "let filtered be <source>:\n"
        "  keep rows where ...",
        start,
    )


def parse_english_any(self) -> ast_nodes.Expr:
    self.consume("KEYWORD", "any")
    var_tok = self.consume_any({"IDENT"})
    self.consume("KEYWORD", "in")
    source_expr = self.parse_expression()
    self.consume("KEYWORD", "where")
    predicate = self.parse_expression()
    return ast_nodes.AnyExpression(source=source_expr, var_name=var_tok.value or "item", predicate=predicate)


def parse_builtin_call(self) -> ast_nodes.Expr:
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    name = name_tok.value or ""
    self.consume("LPAREN")
    if name in {"filter", "map"}:
        raise self.error(
            "filter(...) / map(...) are no longer supported. Use a collection pipeline instead (for example: keep rows where ...).",
            name_tok,
        )
    if name in {"any", "all"}:
        raise self.error(
            f"The legacy '{name}(...)' data syntax is no longer supported. Rewrite this as a collection pipeline with keep rows where ....",
            name_tok,
        )
    args: list[ast_nodes.Expr] = []
    if not self.check("RPAREN"):
        args.append(self.parse_expression())
        while self.match("COMMA"):
            args.append(self.parse_expression())
    if not self.match("RPAREN"):
        if self.check("RPAREN"):
            self.consume("RPAREN")
        else:
            raise self.error("Expected ')' to close call", self.peek())
    if name in {"length", "first", "last", "sorted", "reverse", "unique", "sum"} and len(args) == 1:
        return ast_nodes.ListBuiltinCall(name=name, expr=args[0])
    return ast_nodes.BuiltinCall(name=name, args=args)


def parse_function_call(self) -> ast_nodes.FunctionCall:
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    name = name_tok.value or ""
    self.consume("LPAREN")
    args: list[ast_nodes.Expr] = []
    if not self.check("RPAREN"):
        args.append(self.parse_expression())
        while self.match("COMMA"):
            args.append(self.parse_expression())
    if not self.match("RPAREN"):
        if self.check("RPAREN"):
            self.consume("RPAREN")
        else:
            raise self.error("Expected ')' to close function call", self.peek())
    return ast_nodes.FunctionCall(name=name, args=args, span=self._span(name_tok))
