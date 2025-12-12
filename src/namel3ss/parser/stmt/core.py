"""Core statement parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from ... import ast_nodes

__all__ = [
    "parse_statement_or_action",
    "parse_statement_block",
    "parse_if_statement",
    "parse_match_statement",
    "parse_guard_statement",
    "parse_try_catch_statement",
    "_parse_destructuring_pattern",
    "_split_field_access_expr",
    "parse_let_statement",
    "parse_collection_pipeline_steps",
    "parse_set_statement",
    "parse_repeat_statement",
    "parse_retry_statement",
]


def parse_statement_or_action(self) -> ast_nodes.Statement | ast_nodes.FlowAction:
    token = self.peek()
    if token.value == "let":
        return self.parse_let_statement()
    if token.value == "set":
        return self.parse_set_statement()
    if token.value == "repeat":
        return self.parse_repeat_statement()
    if token.value == "retry":
        return self.parse_retry_statement()
    if token.value == "match":
        return self.parse_match_statement()
    if token.value == "guard":
        return self.parse_guard_statement()
    if token.value == "ask":
        return self.parse_ask_statement()
    if token.value == "form":
        return self.parse_form_statement()
    if token.value == "log":
        return self.parse_log_statement()
    if token.value == "note":
        return self.parse_note_statement()
    if token.value == "checkpoint":
        return self.parse_checkpoint_statement()
    if token.value == "return":
        return self.parse_return_statement()
    if token.value == "try":
        return self.parse_try_catch_statement()
    if token.value == "do":
        return self._parse_do_action()
    if token.value == "go":
        return self.parse_goto_action()
    if token.value == "navigate":
        raise self.error(
            "N3L-PARSE-NAVIGATE: 'navigate' is only supported in UI click handlers; in flows use 'go to page \"...\"' or 'go to flow \"...\"'.",
            token,
        )
    if token.value == "output":
        raise self.error(
            "N3L-PARSE-OUTPUT: 'output to' is not part of the language yet; use let/set and step.<name>.output to route outputs.",
            token,
        )
    if token.value in {"if", "when", "otherwise", "unless", "else"}:
        return self.parse_if_statement()
    if token.value == "let":
        return self.parse_let_statement()
    raise self.error(f"Unexpected statement '{token.value}'", token)


def parse_statement_block(self) -> list[ast_nodes.Statement | ast_nodes.FlowAction]:
    statements: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        statements.append(self.parse_statement_or_action())
    return statements


def parse_if_statement(self) -> ast_nodes.IfStatement:
    token = self.peek()
    if token.value not in {"if", "when", "unless"}:
        if token.value in {"otherwise", "else"}:
            raise self.error("Found 'otherwise/else' without preceding if/when", token)
        raise self.error(f"Unexpected conditional '{token.value}'", token)
    branches: list[ast_nodes.ConditionalBranch] = []

    def parse_branch(label: str, start_token) -> None:
        cond = self.parse_condition_expr()
        binding = self._parse_optional_binding()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(
            ast_nodes.ConditionalBranch(
                condition=cond,
                actions=actions,
                label=label,
                binding=binding,
                span=self._span(start_token),
            )
        )

    start_tok = self.consume("KEYWORD")
    parse_branch(start_tok.value, start_tok)
    while self.peek().value in {"otherwise", "else"}:
        other_tok = self.consume("KEYWORD")
        label = other_tok.value
        cond = None
        binding = None
        if other_tok.value == "otherwise" and self.peek().value == "if":
            self.consume("KEYWORD", "if")
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            label = "otherwise-if"
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(
            ast_nodes.ConditionalBranch(
                condition=cond,
                actions=actions,
                label=label,
                binding=binding,
                span=self._span(other_tok),
            )
        )
    return ast_nodes.IfStatement(branches=branches, span=self._span(start_tok))


def parse_match_statement(self) -> ast_nodes.MatchStatement:
    start_tok = self.consume("KEYWORD", "match")
    target_expr = self.parse_expression()
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    branches: list[ast_nodes.MatchBranch] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "otherwise":
            self.consume("KEYWORD", "otherwise")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(ast_nodes.MatchBranch(pattern=None, actions=actions, label="otherwise"))
            continue
        self.consume("KEYWORD", "when")
        pat_token = self.peek()
        pattern: ast_nodes.Expr | ast_nodes.SuccessPattern | ast_nodes.ErrorPattern | None
        binding: str | None = None
        if pat_token.value == "success":
            self.consume("KEYWORD", "success")
            binding = self._parse_optional_binding()
            if not self.check("COLON"):
                raise self.error(
                    "N3CF-900: I expected ':' after 'when success'. If you want to bind the value, write 'when success as value:'.",
                    self.peek(),
                )
            pattern = ast_nodes.SuccessPattern(binding=binding, span=self._span(pat_token))
        elif pat_token.value == "error":
            self.consume("KEYWORD", "error")
            binding = self._parse_optional_binding()
            if not self.check("COLON"):
                raise self.error(
                    "N3CF-901: I expected ':' after 'when error'. If you want to bind the error, write 'when error as err:'.",
                    self.peek(),
                )
            pattern = ast_nodes.ErrorPattern(binding=binding, span=self._span(pat_token))
        else:
            pattern = self.parse_expression()
            if not isinstance(pattern, ast_nodes.Literal) or not isinstance(pattern.value, (str, int, float, bool, type(None))):
                raise self.error(
                    "This match pattern form is not supported in Control Flow v1. Use literal patterns or rewrite this as an if / otherwise if / else chain.",
                    pat_token,
                )
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(ast_nodes.MatchBranch(pattern=pattern, actions=actions, label="when"))
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.MatchStatement(target=target_expr, branches=branches, span=self._span(start_tok))


def parse_guard_statement(self) -> ast_nodes.GuardStatement:
    start_tok = self.consume("KEYWORD", "guard")
    if self.check("COLON"):
        raise self.error("Expected a condition after guard.", self.peek())
    condition = self.parse_condition_expr()
    if not self.match("COLON"):
        raise self.error("Expected ':' after the guard condition.", self.peek())
    self.consume("NEWLINE")
    self.consume("INDENT")
    body = self.parse_statement_block()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.GuardStatement(condition=condition, body=body, span=self._span(start_tok))


def parse_try_catch_statement(self) -> ast_nodes.TryCatchStatement:
    start_tok = self.consume("KEYWORD", "try")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    try_block = self.parse_statement_block()
    self.consume("DEDENT")
    self.optional_newline()
    catch_tok = self.consume("KEYWORD", "catch")
    if self.peek().type != "IDENT" and self.peek().type != "KEYWORD":
        raise self.error("N3L-601: catch must specify an error identifier (e.g. 'catch err:').", self.peek())
    err_tok = self.consume_any({"IDENT", "KEYWORD"})
    error_ident = err_tok.value or ""
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    catch_block = self.parse_statement_block()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.TryCatchStatement(
        try_block=try_block,
        error_identifier=error_ident,
        catch_block=catch_block,
        span=self._span(start_tok),
    )


def _parse_destructuring_pattern(self) -> ast_nodes.DestructuringPattern | None:
    if self.match("LBRACE"):
        fields: list[ast_nodes.DestructuringField] = []
        while not self.check("RBRACE"):
            field_tok = self.consume_any({"IDENT", "KEYWORD"})
            alias = None
            if self.match_value("KEYWORD", "as"):
                alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = alias_tok.value or None
            fields.append(ast_nodes.DestructuringField(name=field_tok.value or "", alias=alias))
            if self.match("COMMA"):
                continue
            if self.check("RBRACE"):
                break
            raise self.error("Expected ',' or '}' in destructuring pattern", self.peek())
        self.consume("RBRACE")
        return ast_nodes.DestructuringPattern(kind="record", fields=fields)
    if self.match("LBRACKET"):
        elements: list[str] = []
        while not self.check("RBRACKET"):
            elt_tok = self.consume_any({"IDENT", "KEYWORD"})
            elements.append(elt_tok.value or "")
            if self.match("COMMA"):
                continue
            if self.check("RBRACKET"):
                break
            raise self.error("Expected ',' or ']' in list destructuring pattern", self.peek())
        self.consume("RBRACKET")
        return ast_nodes.DestructuringPattern(kind="list", fields=elements)
    return None


def _split_field_access_expr(self, expr: ast_nodes.Expr) -> tuple[ast_nodes.Expr | None, str | None]:
    if isinstance(expr, ast_nodes.RecordFieldAccess):
        return expr.target, expr.field
    if isinstance(expr, ast_nodes.VarRef) and expr.path:
        base_path = expr.path[:-1]
        field = expr.path[-1]
        dotted = ".".join([expr.root] + base_path) if base_path else expr.root
        base_expr = ast_nodes.VarRef(
            name=dotted,
            root=expr.root,
            path=base_path,
            kind=expr.kind,
            span=expr.span,
        )
        return base_expr, field
    return None, None


def parse_let_statement(self) -> ast_nodes.LetStatement:
    start = self.consume("KEYWORD", "let")
    is_constant = False
    if self.peek().value == "constant":
        self.advance()
        is_constant = True
    pattern = self._parse_destructuring_pattern()
    name_tok = None
    if not pattern:
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
    if self.match_value("KEYWORD", "be"):
        expr = self.parse_expression()
    elif self.peek().type == "OP" and self.peek().value == "=":
        tok = self.peek()
        raise self.error("let x = ... is not supported. Write let x be ... instead.", tok)
    else:
        raise self.error("Expected 'be' after variable name", self.peek())
    if self.match_value("KEYWORD", "if"):
        raise self.error(
            "Inline conditional expressions like value if condition else other are not supported. Use an if / otherwise if / else block instead.",
            self.peek(),
        )
    if self.match("COLON"):
        self.consume("NEWLINE")
        self.consume("INDENT")
        pipeline_steps = self.parse_collection_pipeline_steps()
        self.consume("DEDENT")
        expr = ast_nodes.CollectionPipeline(source=expr, steps=pipeline_steps, span=self._span(start))
        self.optional_newline()
    return ast_nodes.LetStatement(
        name=name_tok.value if name_tok else "",
        expr=expr,
        uses_equals=False,
        is_constant=is_constant,
        pattern=pattern,
        span=self._span(start),
    )


def parse_collection_pipeline_steps(self) -> list[ast_nodes.CollectionPipelineStep]:
    steps: list[ast_nodes.CollectionPipelineStep] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        token = self.peek()
        if token.value == "keep":
            keep_tok = self.consume("KEYWORD", "keep")
            if not self.match_value("KEYWORD", "rows"):
                raise self.error("Expected 'rows' after keep in collection pipeline.", self.peek())
            if not self.match_value("KEYWORD", "where"):
                raise self.error("Expected 'where' in keep rows pipeline step.", self.peek())
            condition = self.parse_expression()
            steps.append(ast_nodes.CollectionKeepRowsStep(condition=condition, span=self._span(keep_tok)))
            self.optional_newline()
            continue
        if token.value == "drop":
            drop_tok = self.consume("KEYWORD", "drop")
            if not self.match_value("KEYWORD", "rows"):
                raise self.error("Expected 'rows' after drop in collection pipeline.", self.peek())
            if not self.match_value("KEYWORD", "where"):
                raise self.error("Expected 'where' in drop rows pipeline step.", self.peek())
            condition = self.parse_expression()
            steps.append(ast_nodes.CollectionDropRowsStep(condition=condition, span=self._span(drop_tok)))
            self.optional_newline()
            continue
        if token.value == "group":
            group_tok = self.consume("KEYWORD", "group")
            if not self.match_value("KEYWORD", "by"):
                raise self.error("Expected 'by' after group in collection pipeline.", self.peek())
            key_expr = self.parse_expression()
            if not self.match("COLON"):
                raise self.error("Expected ':' after group by key.", self.peek())
            self.consume("NEWLINE")
            self.consume("INDENT")
            body = self.parse_statement_block()
            self.consume("DEDENT")
            steps.append(ast_nodes.CollectionGroupByStep(key=key_expr, body=body, span=self._span(group_tok)))
            self.optional_newline()
            continue
        if token.value == "sort":
            sort_tok = self.consume("KEYWORD", "sort")
            kind_token = self.consume("KEYWORD")
            if kind_token.value not in {"rows", "groups"}:
                raise self.error("sort must specify 'rows' or 'groups' before 'by'.", kind_token)
            if not self.match_value("KEYWORD", "by"):
                raise self.error("Expected 'by' in sort pipeline step.", self.peek())
            key_expr = self.parse_expression()
            direction = "asc"
            if self.peek().value in {"descending", "ascending"}:
                dir_tok = self.consume("KEYWORD")
                direction = "desc" if dir_tok.value == "descending" else "asc"
            steps.append(ast_nodes.CollectionSortStep(kind=kind_token.value, key=key_expr, direction=direction, span=self._span(sort_tok)))
            self.optional_newline()
            continue
        if token.value == "take":
            take_tok = self.consume("KEYWORD", "take")
            if not self.match_value("KEYWORD", "first"):
                raise self.error("Expected 'first' after take in collection pipeline.", self.peek())
            count_expr = self.parse_expression()
            steps.append(ast_nodes.CollectionTakeStep(count=count_expr, span=self._span(take_tok)))
            self.optional_newline()
            continue
        if token.value == "skip":
            skip_tok = self.consume("KEYWORD", "skip")
            if not self.match_value("KEYWORD", "first"):
                raise self.error("Expected 'first' after skip in collection pipeline.", self.peek())
            count_expr = self.parse_expression()
            steps.append(ast_nodes.CollectionSkipStep(count=count_expr, span=self._span(skip_tok)))
            self.optional_newline()
            continue
        raise self.error("Unexpected statement in collection pipeline.", token)
    return steps


def parse_set_statement(self) -> ast_nodes.SetStatement:
    start = self.consume("KEYWORD", "set")
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    full_name = name_tok.value or ""
    if self.match_value("OP", "."):
        field_tok = self.consume_any({"IDENT", "KEYWORD"})
        full_name = f"{name_tok.value}.{field_tok.value}"
    if self.match_value("KEYWORD", "be") or self.match_value("KEYWORD", "to"):
        expr = self.parse_expression()
    elif self.peek().type == "OP" and self.peek().value == "=":
        tok = self.peek()
        raise self.error("set state.x = ... is not supported. Write set state.x be ... instead.", tok)
    else:
        raise self.error("Expected 'be' or 'to' after target in set statement", self.peek())
    if self.match_value("KEYWORD", "if"):
        raise self.error(
            "Inline conditional expressions like value if condition else other are not supported. Use an if / otherwise if / else block instead.",
            self.peek(),
        )
    return ast_nodes.SetStatement(name=full_name, expr=expr, span=self._span(start))


def parse_repeat_statement(self) -> ast_nodes.Statement:
    repeat_tok = self.consume("KEYWORD", "repeat")
    if self.peek().value == "for":
        self.consume("KEYWORD", "for")
        self.consume("KEYWORD", "each")
        pattern = self._parse_destructuring_pattern()
        var_tok = None
        if not pattern:
            var_tok = self.consume_any({"IDENT", "KEYWORD"})
        self.consume("KEYWORD", "in")
        if self.peek().value == "step" and self.peek_offset(1).type == "STRING":
            step_tok = self.consume("KEYWORD", "step")
            name_tok = self.consume("STRING")
            if self.peek().type in {"IDENT", "KEYWORD"} and self.peek().value == "output":
                self.consume_any({"IDENT", "KEYWORD"})
            iterable_expr = ast_nodes.Identifier(name=f"step.{name_tok.value}.output", span=self._span(step_tok))
        else:
            iterable_expr = self.parse_expression()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        body = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.ForEachLoop(
            var_name=var_tok.value if var_tok else "item",
            pattern=pattern,
            iterable=iterable_expr,
            body=body,
            span=self._span(repeat_tok),
        )
    if self.peek().value == "up":
        self.consume("KEYWORD", "up")
        self.consume("KEYWORD", "to")
        count_expr = self.parse_expression()
        self.consume("KEYWORD", "times")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        body = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RepeatUpToLoop(count=count_expr, body=body, span=self._span(repeat_tok))
    raise self.error("Expected 'for each' or 'up to' after repeat", self.peek())


def parse_retry_statement(self) -> ast_nodes.RetryStatement:
    retry_tok = self.consume("KEYWORD", "retry")
    self.consume("KEYWORD", "up")
    self.consume("KEYWORD", "to")
    count_expr = self.parse_expression()
    if self.peek().value == "times":
        self.consume("KEYWORD", "times")
    with_backoff = False
    if self.peek().value == "with":
        self.consume("KEYWORD", "with")
        self.consume("KEYWORD", "backoff")
        with_backoff = True
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    body = self.parse_statement_block()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.RetryStatement(count=count_expr, with_backoff=with_backoff, body=body, span=self._span(retry_tok))
