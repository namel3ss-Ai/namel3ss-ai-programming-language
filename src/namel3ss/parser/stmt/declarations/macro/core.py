"""Parsing helpers for macros, helpers, and rulegroup declarations."""

from __future__ import annotations

from typing import Any

from namel3ss import ast_nodes

__all__ = [
    "parse_condition_macro",
    "parse_rulegroup",
    "parse_helper",
    "parse_macro",
    "parse_macro_test",
    "parse_macro_use",
    "_parse_macro_fields_block",
]


def parse_condition_macro(self) -> ast_nodes.ConditionMacroDecl:
    start = self.consume("KEYWORD", "define")
    self.consume("KEYWORD", "condition")
    name_tok = self.consume("STRING")
    self.consume("KEYWORD", "as")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    if self.check("DEDENT"):
        raise self.error("Condition macro body cannot be empty.", self.peek())
    expr = self.parse_expression()
    self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.ConditionMacroDecl(name=name_tok.value or "", expr=expr, span=self._span(start))


def parse_rulegroup(self) -> ast_nodes.RuleGroupDecl:
    start = self.consume("KEYWORD", "define")
    self.consume("KEYWORD", "rulegroup")
    name_tok = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    conditions: list[ast_nodes.RuleGroupCondition] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        self.consume("KEYWORD", "condition")
        cond_name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        if self.check("DEDENT"):
            raise self.error(
                f"Condition '{cond_name_tok.value}' in rulegroup '{name_tok.value}' must have a non-empty expression.",
                cond_name_tok,
            )
        expr = self.parse_expression()
        self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        conditions.append(
            ast_nodes.RuleGroupCondition(
                name=cond_name_tok.value or "",
                expr=expr,
                span=self._span(cond_name_tok),
            )
        )
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.RuleGroupDecl(name=name_tok.value or "", conditions=conditions, span=self._span(start))


def parse_helper(self) -> ast_nodes.HelperDecl:
    start = self.consume("KEYWORD", "define")
    self.consume("KEYWORD", "helper")
    name_tok = self.consume("STRING")
    identifier = name_tok.value or ""
    params: list[str] = []
    return_name: str | None = None
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    while True:
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "takes":
            self.consume("KEYWORD", "takes")
            while True:
                param_tok = self.consume_any({"IDENT", "KEYWORD"})
                params.append(param_tok.value or "")
                if self.match("COMMA"):
                    continue
                break
            self.optional_newline()
            continue
        if tok.value == "returns":
            self.consume("KEYWORD", "returns")
            ret_tok = self.consume_any({"IDENT", "KEYWORD"})
            return_name = ret_tok.value
            self.optional_newline()
            continue
        break
    body = self.parse_statement_block()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.HelperDecl(
        name=name_tok.value or "",
        identifier=identifier,
        params=params,
        return_name=return_name,
        body=body,
        span=self._span(start),
    )


def parse_macro(self) -> ast_nodes.MacroDecl:
    start = self.consume("KEYWORD", "macro")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(
                f'macro "{tok.value}": is not supported. Use macro is "{tok.value}": instead.',
                tok,
            )
        raise self.error("Expected 'is' after 'macro'", tok)
    self.consume("KEYWORD", "using")
    self.consume("KEYWORD", "ai")
    model_tok = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    description = None
    version = None
    sample = None
    params: list[str] = []
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.consume_any({"KEYWORD"})
            if tok.value == "description":
                desc_tok = self.consume("STRING")
                description = desc_tok.value
                self.optional_newline()
                continue
            if tok.value == "version":
                if self.match_value("KEYWORD", "is"):
                    pass
                ver_tok = self.consume("STRING")
                version = ver_tok.value
                self.optional_newline()
                continue
            if tok.value == "sample":
                sample_tok = self.consume("STRING")
                sample = sample_tok.value
                self.optional_newline()
                continue
            if tok.value == "parameters":
                params = []
                while True:
                    p_tok = self.consume_any({"IDENT", "KEYWORD"})
                    params.append(p_tok.value or "")
                    if self.match("COMMA"):
                        continue
                    break
                self.optional_newline()
                continue
            raise self.error("N3M-1002: invalid macro clause", tok)
        self.consume("DEDENT")
    self.optional_newline()
    if not description:
        raise self.error("N3M-1000: macro missing description", start)
    return ast_nodes.MacroDecl(
        name=name_tok.value or "",
        ai_model=model_tok.value or "",
        version=version,
        description=description,
        sample=sample,
        parameters=params,
        span=self._span(start),
    )


def parse_macro_test(self) -> ast_nodes.MacroTestDecl:
    start = self.consume("KEYWORD", "macro")
    self.consume("KEYWORD", "test")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'macro test "{tok.value}": is not supported. Use macro test is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'macro test'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    uses: list[ast_nodes.MacroUse] = []
    expects: list[ast_nodes.MacroExpectation] = []
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "use":
                use_tok = self.consume("KEYWORD", "use")
                uses.append(self.parse_macro_use(use_tok))
                continue
            if tok.value == "expect":
                self.consume("KEYWORD", "expect")
                kind_tok = self.consume_any({"KEYWORD", "IDENT"})
                kind = (kind_tok.value or "").lower()
                if kind not in {"record", "flow", "page"}:
                    raise self.error("Expected record, flow, or page after expect", kind_tok)
                name_tok = self.consume("STRING")
                expects.append(
                    ast_nodes.MacroExpectation(
                        kind=kind,
                        name=name_tok.value or "",
                        span=self._span(kind_tok),
                    )
                )
                self.optional_newline()
                continue
            raise self.error("Invalid statement inside macro test block", tok)
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.MacroTestDecl(
        name=name_tok.value or "",
        uses=uses,
        expects=expects,
        span=self._span(start),
    )


def parse_macro_use(self, start_tok) -> ast_nodes.MacroUse:
    self.consume("KEYWORD", "macro")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(
                f'use macro "{tok.value}": is not supported. Use use macro is "{tok.value}" instead.',
                tok,
            )
        raise self.error("Expected 'is' after 'macro' in use statement", tok)
    args: dict[str, ast_nodes.Expr | Any] = {}
    if self.peek().value == "with":
        self.consume("KEYWORD", "with")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            key_tok = self.consume_any({"IDENT", "KEYWORD"})
            if key_tok.value == "fields" and self.peek().type == "COLON":
                args[key_tok.value or "fields"] = self._parse_macro_fields_block()
            else:
                if not self.match_value("KEYWORD", "is") and not self.match_value("KEYWORD", "are"):
                    raise self.error(
                        f"Expected 'is' after {key_tok.value} in macro arguments. Use '{key_tok.value} is \"value\"' instead.",
                        self.peek(),
                    )
                value_expr = self.parse_expression()
                args[key_tok.value or ""] = value_expr
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.MacroUse(macro_name=name_tok.value or "", args=args, span=self._span(start_tok))


def _parse_macro_fields_block(self) -> list[ast_nodes.MacroFieldSpec]:
    fields: list[ast_nodes.MacroFieldSpec] = []
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        start_tok = self.consume("KEYWORD")
        if start_tok.value != "field":
            raise self.error("Expected 'field is \"name\":' inside fields block.", start_tok)
        if not self.match_value("KEYWORD", "is"):
            raise self.error("Expected 'is' after field in fields block.", self.peek())
        name_tok = self.consume("STRING")
        if not self.match("COLON"):
            raise self.error("Expected ':' after field name.", self.peek())
        self.consume("NEWLINE")
        if not self.check("INDENT"):
            raise self.error("Field block must be indented.", self.peek())
        self.consume("INDENT")
        field_type = None
        required = None
        min_expr = None
        max_expr = None
        default_expr = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            inner_tok = self.consume_any({"KEYWORD", "IDENT"})
            if inner_tok.value == "type":
                if self.match_value("KEYWORD", "is"):
                    type_tok = self.consume_any({"STRING", "IDENT"})
                else:
                    type_tok = self.consume_any({"STRING", "IDENT"})
                field_type = type_tok.value
            elif inner_tok.value == "required":
                self.consume("KEYWORD", "is")
                val_tok = self.consume_any({"IDENT", "KEYWORD"})
                if val_tok.value not in {"true", "false"}:
                    raise self.error("required must be true or false", val_tok)
                required = True if val_tok.value == "true" else False
            elif inner_tok.value == "min":
                self.consume("KEYWORD", "is")
                min_expr = self.parse_expression()
            elif inner_tok.value == "max":
                self.consume("KEYWORD", "is")
                max_expr = self.parse_expression()
            elif inner_tok.value == "default":
                self.consume("KEYWORD", "is")
                default_expr = self.parse_expression()
            else:
                raise self.error(f"Unexpected field property '{inner_tok.value}'", inner_tok)
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        fields.append(
            ast_nodes.MacroFieldSpec(
                name=name_tok.value or "",
                field_type=field_type,
                required=required,
                min_expr=min_expr,
                max_expr=max_expr,
                default_expr=default_expr,
                span=self._span(start_tok),
            )
        )
    self.consume("DEDENT")
    return fields
