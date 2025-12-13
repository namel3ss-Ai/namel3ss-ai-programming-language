"""Tool declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes
from namel3ss.parser.errors import ParseError

__all__ = ["parse_tool"]


def parse_tool(self) -> ast_nodes.ToolDeclaration:
    start = self.consume("KEYWORD", "tool")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume_any({"STRING", "IDENT"})
    else:
        tok = self.peek()
        if tok.type in {"STRING", "IDENT"}:
            raise self.error(f'tool "{tok.value}": is not supported. Use tool is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'tool'", tok)
    name = name_tok.value or ""
    kind = None
    method = None
    url_template = None
    url_expr: ast_nodes.Expr | None = None
    query_template: ast_nodes.Expr | None = None
    headers: dict[str, ast_nodes.Expr] = {}
    query_params: dict[str, ast_nodes.Expr] = {}
    body_fields: dict[str, ast_nodes.Expr] = {}
    body_template: ast_nodes.Expr | None = None
    variables: dict[str, ast_nodes.Expr] = {}
    input_fields: list[str] = []
    timeout_expr: ast_nodes.Expr | None = None
    retry_cfg: ast_nodes.ToolRetryConfig | None = None
    auth_cfg: ast_nodes.ToolAuthConfig | None = None
    response_schema: ast_nodes.ResponseSchema | None = None
    logging_level: str | None = None
    rate_limit_cfg: ast_nodes.ToolRateLimitConfig | None = None
    multipart_expr: ast_nodes.Expr | None = None
    query_encoding: str | None = None
    function_path: str | None = None
    self.consume("COLON")
    self.consume("NEWLINE")
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            tok = self.peek()
            if tok.value == "kind":
                self.consume("KEYWORD", "kind")
                if self.match_value("KEYWORD", "is"):
                    kind_tok = self.consume_any({"STRING", "IDENT"})
                else:
                    kind_tok = self.consume_any({"STRING", "IDENT"})
                kind = kind_tok.value
                self.optional_newline()
                continue
            if tok.value == "method":
                self.consume("KEYWORD", "method")
                if self.match_value("KEYWORD", "is"):
                    method_tok = self.consume_any({"STRING", "IDENT"})
                else:
                    method_tok = self.consume_any({"STRING", "IDENT"})
                method = method_tok.value
                self.optional_newline()
                continue
            if tok.value == "url_template":
                self.consume("KEYWORD", "url_template")
                self.consume("KEYWORD", "is")
                url_tok = self.consume("STRING")
                url_template = url_tok.value
                self.optional_newline()
                continue
            if tok.value == "url":
                self.consume("KEYWORD", "url")
                self.consume("KEYWORD", "is")
                url_expr = self.parse_expression()
                self.optional_newline()
                continue
            if tok.value == "function_path":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.peek().value == "is":
                    self.consume_any({"KEYWORD"})
                val_tok = self.consume_any({"STRING", "IDENT"})
                function_path = val_tok.value
                self.optional_newline()
                continue
            if tok.value == "retry":
                retry_cfg = self._parse_tool_retry_block(tok)
                self.optional_newline()
                continue
            if tok.value == "auth":
                auth_cfg = self._parse_tool_auth_block(tok)
                self.optional_newline()
                continue
            if tok.value == "rate_limit":
                rate_limit_cfg = self._parse_tool_rate_limit_block(tok)
                self.optional_newline()
                continue
            if tok.value == "headers":
                self.consume("KEYWORD", "headers")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    name_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    self.consume("COLON")
                    headers[name_token.value or ""] = self.parse_expression()
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "query_params":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    param_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    self.consume("COLON")
                    query_params[param_token.value or ""] = self.parse_expression()
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "query":
                self.consume("KEYWORD", "query")
                self.match_value("KEYWORD", "is")
                if self.match("COLON"):
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    fields: list[ast_nodes.RecordField] = []
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        field_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                        self.consume("COLON")
                        value_expr = self.parse_expression()
                        fields.append(ast_nodes.RecordField(key=field_token.value or "", value=value_expr))
                        self.optional_newline()
                    self.consume("DEDENT")
                    for f in fields:
                        query_params[f.key] = f.value
                    query_template = ast_nodes.RecordLiteral(fields=fields, span=self._span(tok))
                    self.optional_newline()
                else:
                    query_template = self.parse_expression()
                self.optional_newline()
                continue
            if tok.value == "body_fields":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    self.consume("COLON")
                    body_fields[field_token.value or ""] = self.parse_expression()
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "body":
                self.consume("KEYWORD", "body")
                self.match_value("KEYWORD", "is")
                if self.match("COLON"):
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    fields: list[ast_nodes.RecordField] = []
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        field_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                        self.consume("COLON")
                        value_expr = self.parse_expression()
                        fields.append(ast_nodes.RecordField(key=field_token.value or "", value=value_expr))
                        self.optional_newline()
                    self.consume("DEDENT")
                    for f in fields:
                        body_fields[f.key] = f.value
                    body_template = ast_nodes.RecordLiteral(fields=fields, span=self._span(tok))
                    self.optional_newline()
                else:
                    body_template = self.parse_expression()
                self.optional_newline()
                continue
            if tok.value == "multipart":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("KEYWORD", "is")
                multipart_expr = self.parse_expression()
                self.optional_newline()
                continue
            if tok.value == "variables":
                self.consume("KEYWORD", "variables")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    self.consume("COLON")
                    variables[field_token.value or ""] = self.parse_expression()
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "inputs":
                self.consume("KEYWORD", "inputs")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    input_fields.append(field_token.value or "")
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "timeout_seconds":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                timeout_expr = self.parse_expression()
                self.optional_newline()
                continue
            if tok.value == "timeout":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.match_value("KEYWORD", "is"):
                    timeout_expr = self.parse_expression()
                else:
                    self.consume("COLON")
                    timeout_expr = self.parse_expression()
                if self.peek().value in {"second", "seconds", "sec", "secs", "s"}:
                    self.advance()
                self.optional_newline()
                continue
            if tok.value == "logging_level":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.peek().value == "is":
                    self.consume_any({"KEYWORD"})
                level_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                logging_level = level_tok.value
                self.optional_newline()
                continue
            if tok.value == "logging":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.peek().value == "is":
                    self.consume_any({"KEYWORD"})
                level_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                logging_level = level_tok.value
                self.optional_newline()
                continue
            if tok.value == "response_schema":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                response_schema = self._parse_response_schema()
                self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "retry_config":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                retry_cfg = self._parse_retry_block()
                self.optional_newline()
                continue
            if tok.value == "auth_config":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                auth_cfg = self._parse_auth_block()
                self.optional_newline()
                continue
            if tok.value == "rate_limit_config":
                self.consume_any({"KEYWORD", "IDENT"})
                self.consume("COLON")
                self.consume("NEWLINE")
                rate_limit_cfg = self._parse_rate_limit_block()
                self.optional_newline()
                continue
            if tok.value == "query_encoding":
                self.consume_any({"KEYWORD", "IDENT"})
                self.match_value("KEYWORD", "is")
                if self.match("COLON"):
                    enc_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    enc_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                query_encoding = enc_tok.value
                self.optional_newline()
                continue
            raise self.error(f"Unexpected field '{tok.value}' in tool declaration", tok)
        self.consume("DEDENT")
    self.optional_newline()
    if multipart_expr is not None and body_template is not None:
        raise self.error("multipart and body cannot be used together in a tool declaration.", start)
    return ast_nodes.ToolDeclaration(
        name=name,
        kind=kind,
        method=method,
        url_template=url_template,
        url_expr=url_expr,
        query_template=query_template,
        headers=headers,
        query_params=query_params,
        body_fields=body_fields,
        body_template=body_template,
        variables=variables,
        input_fields=input_fields,
        timeout_expr=timeout_expr,
        retry=retry_cfg,
        auth=auth_cfg,
        response_schema=response_schema,
        logging_level=logging_level,
        rate_limit=rate_limit_cfg,
        multipart_expr=multipart_expr,
        query_encoding=query_encoding,
        function_path=function_path,
        span=self._span(start),
    )


def _parse_tool_retry_block(self, start_tok) -> ast_nodes.ToolRetryConfig:
    self.consume("KEYWORD", "retry")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    cfg = ast_nodes.ToolRetryConfig()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "max_attempts":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.max_attempts = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "backoff":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            backoff_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            cfg.backoff = backoff_tok.value
            self.optional_newline()
            continue
        if tok.value == "initial_delay":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is") or self.match_value("KEYWORD", "are")
            cfg.initial_delay = self.parse_expression()
            if self.peek().value in {"second", "seconds", "sec", "secs", "s"}:
                self.advance()
            self.optional_newline()
            continue
        if tok.value == "max_delay":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is") or self.match_value("KEYWORD", "are")
            cfg.max_delay = self.parse_expression()
            if self.peek().value in {"second", "seconds", "sec", "secs", "s"}:
                self.advance()
            self.optional_newline()
            continue
        if tok.value == "jitter":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.jitter = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "retry_on_status":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is") or self.match_value("KEYWORD", "are")
            cfg.retry_on_status = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "retry_on_exceptions":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is") or self.match_value("KEYWORD", "are")
            cfg.retry_on_exceptions = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "allow_unsafe":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.allow_unsafe = self.parse_expression()
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{tok.value}' in retry block", tok)
    self.consume("DEDENT")
    return cfg


def _parse_tool_auth_block(self, start_tok) -> ast_nodes.ToolAuthConfig:
    self.consume("KEYWORD", "auth")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    cfg = ast_nodes.ToolAuthConfig()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "kind":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            kind_tok = self.consume_any({"STRING", "IDENT"})
            cfg.kind = kind_tok.value
            self.optional_newline()
            continue
        if tok.value == "token":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.token = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "username":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.username = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "password":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.password = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "location":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            loc_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            cfg.location = loc_tok.value
            self.optional_newline()
            continue
        if tok.value == "name":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            name_tok = self.consume_any({"STRING", "IDENT"})
            cfg.name = name_tok.value
            self.optional_newline()
            continue
        if tok.value == "value":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.value = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "token_url":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.token_url = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "client_id":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.client_id = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "client_secret":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.client_secret = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "scopes":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            scopes_expr = self.parse_expression()
            if isinstance(scopes_expr, ast_nodes.ListLiteral):
                cfg.scopes = [el.value for el in scopes_expr.items if isinstance(el, ast_nodes.Literal)]
            self.optional_newline()
            continue
        if tok.value == "audience":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.audience = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "cache":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cache_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            cfg.cache = cache_tok.value
            self.optional_newline()
            continue
        if tok.value == "issuer":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.issuer = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "subject":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.subject = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "private_key":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.private_key = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "algorithm":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            alg_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            cfg.algorithm = alg_tok.value
            self.optional_newline()
            continue
        if tok.value == "claims":
            self.consume_any({"KEYWORD", "IDENT"})
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                claim_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                self.consume("COLON")
                cfg.claims[claim_token.value or ""] = self.parse_expression()
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{tok.value}' in auth block", tok)
    self.consume("DEDENT")
    return cfg


def _parse_tool_rate_limit_block(self, start_tok) -> ast_nodes.ToolRateLimitConfig:
    self.consume("KEYWORD", "rate_limit")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    cfg = ast_nodes.ToolRateLimitConfig()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "max_calls_per_minute":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.max_calls_per_minute = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "max_calls_per_second":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.max_calls_per_second = self.parse_expression()
            self.optional_newline()
            continue
        if tok.value == "burst":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            cfg.burst = self.parse_expression()
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{tok.value}' in rate_limit block", tok)
    self.consume("DEDENT")
    return cfg


def _parse_response_schema(self) -> ast_nodes.ResponseSchema:
    schema = ast_nodes.ResponseSchema()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "type":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            schema.type = type_tok.value
            self.optional_newline()
            continue
        if tok.value == "required":
            self.consume_any({"KEYWORD", "IDENT"})
            self.match_value("KEYWORD", "is")
            expr_val = self.parse_expression()
            if isinstance(expr_val, ast_nodes.ListLiteral):
                schema.required = [el.value for el in expr_val.items if isinstance(el, ast_nodes.Literal)]
            self.optional_newline()
            continue
        if tok.value == "properties":
            self.consume_any({"KEYWORD", "IDENT"})
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                prop_token = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                self.consume("COLON")
                if self.match("NEWLINE"):
                    prop_type = None
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            inner_tok = self.peek()
                            if inner_tok.value == "type":
                                self.consume_any({"KEYWORD", "IDENT"})
                                self.match_value("KEYWORD", "is")
                                type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                prop_type = type_tok.value
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{inner_tok.value}' in property definition", inner_tok)
                        self.consume("DEDENT")
                else:
                    prop_expr = self.parse_expression()
                    prop_type = prop_expr.value if isinstance(prop_expr, ast_nodes.Literal) else None
                schema.properties[prop_token.value or ""] = ast_nodes.SimpleTypeSchema(type=prop_type)
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{tok.value}' in response_schema", tok)
    return schema


# Legacy aliases used elsewhere in the parser.
_parse_retry_block = _parse_tool_retry_block
_parse_auth_block = _parse_tool_auth_block
_parse_rate_limit_block = _parse_tool_rate_limit_block
