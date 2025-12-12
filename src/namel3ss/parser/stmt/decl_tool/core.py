"""Tool declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes
from ....errors import ParseError

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
                self.consume("KEYWORD", "is")
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
                self.consume("KEYWORD", "is")
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
            if tok.value == "logging_level":
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
                self.consume("COLON")
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
