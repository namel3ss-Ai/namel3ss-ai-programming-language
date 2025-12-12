"""Block-level statement helpers (ask/form/log/etc.) extracted from legacy parser."""

from __future__ import annotations

from ... import ast_nodes

__all__ = [
    "parse_ask_statement",
    "parse_form_statement",
    "parse_log_statement",
    "parse_note_statement",
    "parse_checkpoint_statement",
    "parse_return_statement",
    "_parse_do_action",
    "parse_do_actions",
    "parse_goto_action",
    "parse_conditional_into",
    "_parse_optional_binding",
]


def parse_ask_statement(self) -> ast_nodes.AskUserStatement:
    start_tok = self.consume("KEYWORD", "ask")
    self.consume("KEYWORD", "user")
    self.consume("KEYWORD", "for")
    if not self.check("STRING"):
        raise self.error("N3-5000: ask user label must be a string literal", self.peek())
    label_tok = self.consume("STRING")
    self.consume("KEYWORD", "as")
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    validation: ast_nodes.InputValidation | None = None
    if self.match("NEWLINE"):
        if self.match("INDENT"):
            validation = self._parse_validation_block()
            self.consume("DEDENT")
        self.optional_newline()
    else:
        self.optional_newline()
    return ast_nodes.AskUserStatement(label=label_tok.value or "", var_name=name_tok.value or "", validation=validation, span=self._span(start_tok))


def parse_form_statement(self) -> ast_nodes.FormStatement:
    start_tok = self.consume("KEYWORD", "form")
    if not self.check("STRING"):
        raise self.error("N3-5010: form label must be a string literal", self.peek())
    label_tok = self.consume("STRING")
    self.consume("KEYWORD", "as")
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    fields: list[ast_nodes.FormField] = []
    seen_names: set[str] = set()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        self.consume("KEYWORD", "field")
        if not self.check("STRING"):
            raise self.error("N3-5010: form field label must be a string literal", self.peek())
        field_label_tok = self.consume("STRING")
        self.consume("KEYWORD", "as")
        field_name_tok = self.consume_any({"IDENT", "KEYWORD"})
        validation: ast_nodes.InputValidation | None = None
        if self.match("NEWLINE"):
            if self.match("INDENT"):
                validation = self._parse_validation_block(error_code="N3-5012")
                self.consume("DEDENT")
            self.optional_newline()
        else:
            self.optional_newline()
        if field_name_tok.value in seen_names:
            raise self.error("N3-5011: duplicate field identifier in form", field_name_tok)
        seen_names.add(field_name_tok.value or "")
        fields.append(
            ast_nodes.FormField(
                label=field_label_tok.value or "",
                name=field_name_tok.value or "",
                validation=validation,
            )
        )
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.FormStatement(label=label_tok.value or "", name=name_tok.value or "", fields=fields, span=self._span(start_tok))


def parse_log_statement(self) -> ast_nodes.LogStatement:
    start_tok = self.consume("KEYWORD", "log")
    level_tok = self.consume_any({"IDENT", "KEYWORD"})
    if level_tok.value not in {"info", "warning", "error"}:
        raise self.error("N3-5100: invalid log level", level_tok)
    if not self.check("STRING"):
        raise self.error("N3-5101: log message must be a string literal", self.peek())
    msg_tok = self.consume("STRING")
    metadata_expr: ast_nodes.Expr | None = None
    if self.peek().value == "with":
        self.consume("KEYWORD", "with")
        metadata_expr = self.parse_expression()
    self.optional_newline()
    return ast_nodes.LogStatement(level=level_tok.value or "info", message=msg_tok.value or "", metadata=metadata_expr, span=self._span(start_tok))


def parse_note_statement(self) -> ast_nodes.NoteStatement:
    start_tok = self.consume("KEYWORD", "note")
    if not self.check("STRING"):
        raise self.error("Note message must be a string literal", self.peek())
    msg_tok = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.NoteStatement(message=msg_tok.value or "", span=self._span(start_tok))


def parse_checkpoint_statement(self) -> ast_nodes.CheckpointStatement:
    start_tok = self.consume("KEYWORD", "checkpoint")
    if not self.check("STRING"):
        raise self.error("N3-5110: checkpoint label must be a string literal", self.peek())
    label_tok = self.consume("STRING")
    self.optional_newline()
    return ast_nodes.CheckpointStatement(label=label_tok.value or "", span=self._span(start_tok))


def parse_return_statement(self) -> ast_nodes.ReturnStatement:
    start_tok = self.consume("KEYWORD", "return")
    expr = None
    if not self.check("NEWLINE") and not self.check("DEDENT") and not self.check("EOF"):
        expr = self.parse_expression()
    self.optional_newline()
    return ast_nodes.ReturnStatement(expr=expr, span=self._span(start_tok))


def _parse_do_action(self) -> ast_nodes.FlowAction:
    do_token = self.consume("KEYWORD", "do")
    kind_tok = self.consume_any({"KEYWORD", "IDENT"})
    if kind_tok.value not in {"ai", "agent", "tool", "flow"}:
        raise self.error(f"Unsupported action kind '{kind_tok.value}'", kind_tok)
    target_tok = self.consume("STRING")
    message = None
    args: dict[str, ast_nodes.Expr] = {}
    if kind_tok.value == "flow" and self.peek().value == "with":
        self.consume("KEYWORD", "with")
        while True:
            key_tok = self.consume_any({"IDENT", "KEYWORD"})
            self.consume("COLON")
            val_expr = self.parse_expression()
            args[key_tok.value or ""] = val_expr
            if self.peek().type == "COMMA":
                self.consume("COMMA")
                continue
            break
    if kind_tok.value == "tool" and self.peek().value == "with":
        self.consume("KEYWORD", "with")
        self.consume("KEYWORD", "message")
        if self.check("COLON"):
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            msg_tok = self.consume("STRING")
            message = msg_tok.value
            self.optional_newline()
            self.consume("DEDENT")
        else:
            msg_tok = self.consume("STRING")
            message = msg_tok.value
    return ast_nodes.FlowAction(
        kind=kind_tok.value or "",
        target=target_tok.value or "",
        message=message,
        args=args,
        span=self._span(do_token),
    )


def parse_conditional_into(self, branches: list[ast_nodes.ConditionalBranch]) -> None:
    token = self.peek()
    if token.value == "unless":
        self.consume("KEYWORD", "unless")
        if self.check("COLON"):
            raise self.error("Expected a condition expression after 'unless'", token)
        cond = self.parse_condition_expr()
        binding = self._parse_optional_binding()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_do_actions()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(
            ast_nodes.ConditionalBranch(
                condition=cond, actions=actions, label="unless", binding=binding, span=self._span(token)
            )
        )
        return
    if token.value == "when":
        self.consume("KEYWORD", "when")
        cond = self.parse_condition_expr()
        binding = self._parse_optional_binding()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_do_actions()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(
            ast_nodes.ConditionalBranch(
                condition=cond, actions=actions, label="when", binding=binding, span=self._span(token)
            )
        )
        return
    if token.value == "if":
        self.consume("KEYWORD", "if")
        cond = self.parse_condition_expr()
        binding = self._parse_optional_binding()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        actions = self.parse_do_actions()
        self.consume("DEDENT")
        self.optional_newline()
        branches.append(
            ast_nodes.ConditionalBranch(
                condition=cond, actions=actions, label="if", binding=binding, span=self._span(token)
            )
        )
        return
    if token.value == "otherwise":
        if not branches:
            raise self.error("Found 'otherwise' without preceding if/when", token)
        if branches and branches[-1].label == "unless":
            raise self.error("'otherwise' cannot follow an 'unless' block.", token)
        self.consume("KEYWORD", "otherwise")
        if self.peek().value == "if":
            self.consume("KEYWORD", "if")
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_do_actions()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond,
                    actions=actions,
                    label="otherwise-if",
                    binding=binding,
                    span=self._span(token),
                )
            )
        else:
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_do_actions()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=None, actions=actions, label="otherwise", span=self._span(token)
                )
            )
        return
    raise self.error(f"Unexpected conditional '{token.value}'", token)


def _parse_optional_binding(self) -> str | None:
    if self.peek().value != "as":
        return None
    self.consume("KEYWORD", "as")
    if self.check("COLON"):
        raise self.error("Expected a variable name after 'as' in conditional binding.", self.peek())
    name_tok = self.consume_any({"IDENT", "KEYWORD"})
    if not name_tok.value or not name_tok.value.isidentifier():
        raise self.error("Binding name after 'as' must be a valid identifier.", name_tok)
    if self.peek().value == "as":
        raise self.error("Multiple 'as' bindings are not allowed in a single condition.", self.peek())
    return name_tok.value


def parse_do_actions(self) -> list[ast_nodes.FlowAction | ast_nodes.Statement]:
    actions: list[ast_nodes.FlowAction | ast_nodes.Statement] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        if self.peek().value == "go":
            actions.append(self.parse_goto_action())
            self.optional_newline()
            continue
        if self.peek().value in {"let", "set", "if", "when", "otherwise", "unless", "match", "retry", "ask", "form", "log", "note", "checkpoint", "return", "guard"}:
            actions.append(self.parse_statement_or_action())
            continue
        actions.append(self._parse_do_action())
        self.optional_newline()
    return actions


def parse_goto_action(self, allow_page: bool = False) -> ast_nodes.FlowAction:
    go_tok = self.consume("KEYWORD", "go")
    self.consume("KEYWORD", "to")
    target_kind_tok = self.consume_any({"KEYWORD", "IDENT"})
    if target_kind_tok.value not in {"flow", "page"}:
        raise self.error("Expected 'flow' or 'page' after 'go to'.", target_kind_tok)
    if not self.check("STRING"):
        raise self.error("Expected a string literal name after go to.", self.peek())
    target_tok = self.consume("STRING")
    kind = "goto_flow" if target_kind_tok.value == "flow" else "goto_page"
    if target_kind_tok.value == "page" and not allow_page:
        raise self.error("Unexpected 'go to page' in this context.", target_kind_tok)
    return ast_nodes.FlowAction(kind=kind, target=target_tok.value or "", span=self._span(go_tok))
