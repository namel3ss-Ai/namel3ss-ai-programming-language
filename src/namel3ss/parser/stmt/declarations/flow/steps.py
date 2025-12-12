"""Flow declaration parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from typing import Set

from namel3ss import ast_nodes

__all__ = [
    "_parse_step_body",
    "_build_flow_step_decl",
    "parse_flow_step",
    "parse_flow_decl",
]


def _parse_step_body(
    self, allow_fields: bool = True
) -> tuple[
    str | None,
    str | None,
    str | None,
    dict[str, object],
    list[ast_nodes.Statement | ast_nodes.FlowAction],
    list[ast_nodes.ConditionalBranch] | None,
    ast_nodes.FlowAction | None,
    ast_nodes.Expr | None,
    ast_nodes.Expr | None,
]:
    kind = None
    target = None
    message = None
    extra_params: dict[str, object] = {}
    statements: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
    conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
    goto_action: ast_nodes.FlowAction | None = None
    when_expr: ast_nodes.Expr | None = None
    timeout_expr: ast_nodes.Expr | None = None
    record_query: ast_nodes.RecordQuery | None = None
    allowed_fields: Set[str] = {
        "kind",
        "target",
        "tool",
        "tools",
        "message",
        "frame",
        "record",
        "vector_store",
        "values",
        "where",
        "set",
        "query_text",
        "top_k",
        "pipeline",
        "question",
        "query",
        "params",
        "on_success",
        "on_error",
        "goto",
        "stream",
        "when",
        "timeout",
        "with",
        "output",
        "tools_mode",
    }
    if not allow_fields:
        allowed_fields = {"do"}

    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        next_tok = self.peek()
        if next_tok.value == "find":
            find_tok = self.consume_any({"KEYWORD", "IDENT"})
            alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
            alias = alias_tok.value or ""
            if not self.match_value("KEYWORD", "where"):
                raise self.error("Expected 'where' after find <alias>", self.peek())
            where_cond = self._parse_where_conditions()
            record_query = ast_nodes.RecordQuery(
                alias=alias,
                record_name=None,
                where_condition=where_cond,
                order_by=[],
                relationships=[],
                span=self._span(find_tok),
            )
            if kind is None:
                kind = "find"
            if target is None:
                target = alias
            continue
        if next_tok.value == "order":
            order_tok = self.consume_any({"KEYWORD", "IDENT"})
            alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
            alias = alias_tok.value or ""
            self.consume("KEYWORD", "by")
            order_items: list[ast_nodes.RecordOrderBy] = []
            while True:
                field_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                direction = "asc"
                if self.peek().type == "KEYWORD" and self.peek().value in {"ascending", "descending", "asc", "desc"}:
                    dir_tok = self.consume("KEYWORD")
                    direction = "asc" if dir_tok.value in {"ascending", "asc"} else "desc"
                order_items.append(
                    ast_nodes.RecordOrderBy(field_name=field_tok.value or "", direction=direction, span=self._span(field_tok))
                )
                if self.match("COMMA"):
                    continue
                break
            if record_query is None:
                record_query = ast_nodes.RecordQuery(
                    alias=alias, record_name=None, where_condition=None, order_by=[], relationships=[], span=self._span(order_tok)
                )
            if record_query.order_by is None:
                record_query.order_by = []
            record_query.order_by.extend(order_items)
            self.optional_newline()
            continue
        if next_tok.value == "limit":
            limit_tok = self.consume_any({"KEYWORD", "IDENT"})
            alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
            self.consume("KEYWORD", "to")
            expr = self.parse_expression()
            if record_query is None:
                record_query = ast_nodes.RecordQuery(
                    alias=alias_tok.value or "", record_name=None, where_condition=None, relationships=[], span=self._span(limit_tok)
                )
            record_query.limit_expr = expr
            self.optional_newline()
            continue
        if next_tok.value == "offset":
            offset_tok = self.consume_any({"KEYWORD", "IDENT"})
            alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
            self.consume("KEYWORD", "by")
            expr = self.parse_expression()
            if record_query is None:
                record_query = ast_nodes.RecordQuery(
                    alias=alias_tok.value or "", record_name=None, where_condition=None, relationships=[], span=self._span(offset_tok)
                )
            record_query.offset_expr = expr
            self.optional_newline()
            continue
        if next_tok.value == "by":
            by_tok = self.consume_any({"KEYWORD", "IDENT"})
            key_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            by_values: dict[str, ast_nodes.Expr] = {}
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                field_tok = self.consume_any({"IDENT", "KEYWORD"})
                self.consume("COLON")
                val_expr = self.parse_expression()
                by_values[field_tok.value or ""] = val_expr
                self.optional_newline()
            self.consume("DEDENT")
            if key_tok.value == "id":
                extra_params["by_id"] = by_values
            else:
                extra_params[f"by_{(key_tok.value or '').replace(' ', '_')}"] = by_values
            self.optional_newline()
            continue
        if (next_tok.value or "") not in allowed_fields:
            statements.append(self.parse_statement_or_action())
            continue
        field_tok = self.consume_any({"KEYWORD", "IDENT"})
        field_name = field_tok.value or ""
        if field_name == "kind":
            if not self.match_value("KEYWORD", "is"):
                self.consume("COLON")
            next_tok = self.peek()
            if next_tok.type == "STRING":
                kind_tok = self.consume("STRING")
                kind = kind_tok.value
            else:
                kind_tok = self.consume_any({"KEYWORD", "IDENT"})
                kind = kind_tok.value
            self.optional_newline()
            continue
        if field_name in {"target", "tool", "frame", "record", "vector_store"}:
            if not self.match_value("KEYWORD", "is"):
                self.consume("COLON")
            target_tok = self.consume("STRING")
            if field_name == "target":
                target = target_tok.value
            elif field_name == "tool":
                target = target_tok.value
                if kind is None:
                    kind = "tool"
            elif field_name == "frame":
                target = target_tok.value
                if kind is None:
                    kind = "vector_index_frame"
            elif field_name == "record":
                target = target_tok.value
                if kind is None:
                    kind = "vector_upsert_frame_record"
            elif field_name == "vector_store":
                target = target_tok.value
            self.optional_newline()
            continue
        if field_name == "tools":
            self.consume("COLON")
            if not self.check("LBRACKET"):
                raise self.error("Expected '[' after tools:", self.peek())
            self.consume("LBRACKET")
            tools_list = []
            if not self.check("RBRACKET"):
                while True:
                    tool_tok = self.consume("STRING")
                    tools_list.append(tool_tok.value or "")
                    if self.match("COMMA"):
                        continue
                    break
            self.consume("RBRACKET")
            extra_params["tools"] = tools_list
            if kind is None:
                kind = "tool"
            self.optional_newline()
            continue
        if field_name == "message":
            self.consume("COLON")
            if self.check("STRING"):
                msg_tok = self.consume("STRING")
                message = msg_tok.value
                self.optional_newline()
            else:
                self.consume("NEWLINE")
                self.consume("INDENT")
                msg_tok = self.consume("STRING")
                message = msg_tok.value
                self.optional_newline()
                self.consume("DEDENT")
            continue
        if field_name in {"values", "query_text", "question", "query"}:
            self.consume("COLON")
            if field_name == "values":
                if self.match("NEWLINE"):
                    self.consume("INDENT")
                    values_dict: dict[str, ast_nodes.Expr] = {}
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        key_tok = self.consume_any({"IDENT", "KEYWORD"})
                        self.consume("COLON")
                        val_expr = self.parse_expression()
                        values_dict[key_tok.value or ""] = val_expr
                        self.optional_newline()
                    self.consume("DEDENT")
                    extra_params["values"] = values_dict
                    self.optional_newline()
                    continue
                expr = self.parse_expression()
                extra_params["values"] = expr
            elif field_name == "query_text":
                expr = self.parse_expression()
                extra_params["query_text"] = expr
            elif field_name == "question":
                expr = self.parse_expression()
                extra_params["question"] = expr
            elif field_name == "query":
                expr = self.parse_expression()
                extra_params["query"] = expr
            self.optional_newline()
            continue
        if field_name == "params":
            self.consume("COLON")
            params: dict[str, ast_nodes.Expr] = {}
            if self.check("NEWLINE"):
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    param_key_tok = self.consume_any({"IDENT", "KEYWORD"})
                    self.consume("COLON")
                    param_val_expr = self.parse_expression()
                    params[param_key_tok.value or ""] = param_val_expr
                    self.optional_newline()
                self.consume("DEDENT")
            else:
                while True:
                    param_key_tok = self.consume_any({"IDENT", "KEYWORD"})
                    self.consume("COLON")
                    param_val_expr = self.parse_expression()
                    params[param_key_tok.value or ""] = param_val_expr
                    if self.match("COMMA"):
                        continue
                    break
            extra_params["params"] = params
            self.optional_newline()
            continue
        if field_name == "where":
            extra_params["where"] = self._parse_where_conditions()
            continue
        if field_name == "set":
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            set_values: dict[str, ast_nodes.Expr] = {}
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                set_key_tok = self.consume_any({"IDENT", "KEYWORD"})
                self.consume("COLON")
                set_val_expr = self.parse_expression()
                set_values[set_key_tok.value or ""] = set_val_expr
                self.optional_newline()
            self.consume("DEDENT")
            extra_params["set"] = set_values
            self.optional_newline()
            continue
        if field_name in {"top_k", "timeout"}:
            self.consume("COLON")
            expr = self.parse_expression() if field_name == "top_k" else self._parse_duration_value()
            if field_name == "top_k":
                extra_params["top_k"] = expr
            else:
                timeout_expr = expr
            self.optional_newline()
            continue
        if field_name == "pipeline":
            self.consume("COLON")
            pipeline_tok = self.consume("STRING")
            extra_params["pipeline"] = pipeline_tok.value
            self.optional_newline()
            continue
        if field_name == "on_success":
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            statements.extend(self.parse_statement_block())
            self.consume("DEDENT")
            self.optional_newline()
            continue
        if field_name == "on_error":
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            conditional_branches = conditional_branches or []
            conditional_branches.append(
                ast_nodes.ConditionalBranch(
                    condition=ast_nodes.Identifier(name="error", span=self._span(field_tok)),
                    actions=self.parse_statement_block(),
                    label="error",
                    span=self._span(field_tok),
                )
            )
            self.consume("DEDENT")
            self.optional_newline()
            continue
        if field_name == "goto":
            self.consume("COLON")
            goto_action = self.parse_goto_action(allow_page=True)
            self.optional_newline()
            continue
        if field_name == "when":
            self.consume("COLON")
            when_expr = self.parse_condition_expr()
            self.optional_newline()
            continue
        if field_name == "tools_mode":
            self.consume("COLON")
            tools_mode_tok = self.consume_any({"IDENT", "KEYWORD"})
            extra_params["tools_mode"] = tools_mode_tok.value
            self.optional_newline()
            continue
        if field_name == "do":
            if not allow_fields:
                raise self.error("Unexpected 'do' block in this context.", field_tok)
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            statements.extend(self.parse_do_actions())
            self.consume("DEDENT")
            self.optional_newline()
            continue
        if field_name == "output":
            self.consume("COLON")
            output_tok = self.consume_any({"IDENT", "KEYWORD"})
            extra_params["output"] = output_tok.value
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{field_name}' in step", field_tok)

    if record_query is not None:
        extra_params["query"] = record_query

    return (
        kind,
        target,
        message,
        extra_params,
        statements,
        conditional_branches,
        goto_action,
        when_expr,
        timeout_expr,
    )


def _build_flow_step_decl(
    self,
    step_name_token,
    alias,
    kind,
    target,
    message,
    extra_params,
    statements,
    conditional_branches,
    goto_action,
    when_expr,
    timeout_expr,
):
    stream_kwargs = {}
    tools_mode = "auto"
    if extra_params.get("tools_mode") in {"off", "auto", "required"}:
        tools_mode = extra_params["tools_mode"]
    if isinstance(extra_params.get("tools"), list):
        stream_kwargs["tools"] = extra_params["tools"]
    if extra_params.get("where") is not None:
        extra_params["where"] = extra_params["where"]
    if extra_params.get("set") is not None:
        extra_params["set"] = extra_params["set"]
    if extra_params.get("params") is not None:
        stream_kwargs["params"] = extra_params["params"]
    if extra_params.get("output") is not None:
        extra_params["output"] = extra_params["output"]
    if extra_params.get("pipeline") is not None:
        extra_params["pipeline"] = extra_params["pipeline"]
    if extra_params.get("question") is not None:
        extra_params["question"] = extra_params["question"]
    if extra_params.get("query_text") is not None:
        extra_params["query_text"] = extra_params["query_text"]
    if extra_params.get("query") is not None:
        extra_params["query"] = extra_params["query"]
    if extra_params.get("values") is not None:
        extra_params["values"] = extra_params["values"]
    if extra_params.get("top_k") is not None:
        extra_params["top_k"] = extra_params["top_k"]

    if conditional_branches:
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            alias=alias,
            kind="when",
            target=None,
            message=message,
            params=extra_params,
            when=None,
            timeout=timeout_expr,
            conditionals=conditional_branches,
            tools_mode=tools_mode,
            span=self._span(step_name_token),
        )
    if statements:
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            alias=alias,
            kind="do",
            target=None,
            message=message,
            params=extra_params,
            statements=statements,
            when_expr=when_expr,
            timeout=timeout_expr,
            tools_mode=tools_mode,
            span=self._span(step_name_token),
        )
    if goto_action:
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            alias=alias,
            kind="goto_flow",
            target=goto_action.target,
            when_expr=when_expr,
            timeout=timeout_expr,
            **stream_kwargs,
            tools_mode=tools_mode,
            span=self._span(step_name_token),
        )
    if kind == "tool" and not target:
        raise self.error("N3L-963: Tool call step must specify a target tool.", step_name_token)
    if kind is None:
        raise self.error("Missing 'kind' in step", step_name_token)
    if target is None and kind in {"vector_query", "vector_index_frame", "rag_query"}:
        target = step_name_token.value or ""
    if target is None:
        raise self.error("Missing 'target' in step", step_name_token)
    return ast_nodes.FlowStepDecl(
        name=step_name_token.value or "",
        alias=alias,
        kind=kind,
        target=target,
        message=message,
        params=extra_params or {},
        when_expr=when_expr,
        timeout=timeout_expr,
        **stream_kwargs,
        tools_mode=tools_mode,
        span=self._span(step_name_token),
    )


def parse_flow_step(self, step_name_token) -> ast_nodes.FlowStepDecl:
    alias = None
    if self.peek().value == "as":
        self.consume("KEYWORD", "as")
        alias_tok = self.consume_any({"IDENT", "KEYWORD"})
        alias = alias_tok.value or None
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    (
        kind,
        target,
        message,
        extra_params,
        statements,
        conditional_branches,
        goto_action,
        when_expr,
        timeout_expr,
    ) = self._parse_step_body(allow_fields=True)
    self.consume("DEDENT")
    self.optional_newline()
    return self._build_flow_step_decl(
        step_name_token,
        alias,
        kind,
        target,
        message,
        extra_params,
        statements,
        conditional_branches,
        goto_action,
        when_expr,
        timeout_expr,
    )


def parse_flow_decl(self) -> ast_nodes.FlowDecl:
    start = self.consume("KEYWORD", "flow")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(
                f'flow "{tok.value}": is not supported. Use flow is "{tok.value}": instead.',
                tok,
            )
        raise self.error("Expected 'is' after 'flow'", tok)
    description = None
    if self.peek().value == "description":
        self.consume("KEYWORD", "description")
        if self.match_value("KEYWORD", "is"):
            pass
        desc_tok = self.consume("STRING")
        description = desc_tok.value
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    steps: list[ast_nodes.FlowStepDecl] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        header_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
        step_name_token = header_tok
        if header_tok.value == "step":
            if self.match_value("KEYWORD", "is"):
                step_name_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                tok = self.peek()
                if tok.type in {"STRING", "IDENT", "KEYWORD"}:
                    raise self.error(
                        f'step "{tok.value}": is not supported. Use step is "{tok.value}": instead.',
                        tok,
                    )
                raise self.error("Expected 'is' after 'step'", tok)
        steps.append(self.parse_flow_step(step_name_token))
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.FlowDecl(name=name_tok.value or "", description=description, steps=steps, span=self._span(start))
