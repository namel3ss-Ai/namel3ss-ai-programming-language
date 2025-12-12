"""Validation helpers extracted from the legacy parser."""

from __future__ import annotations

from .. import ast_nodes

__all__ = ["_parse_validation_block"]


def _parse_validation_block(self, error_code: str = "N3-5001") -> ast_nodes.InputValidation:
    validation = ast_nodes.InputValidation()
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "type":
            self.consume("KEYWORD", "type")
            self.consume("KEYWORD", "is")
            t_tok = self.consume_any({"IDENT", "KEYWORD"})
            validation.field_type = t_tok.value
            self.optional_newline()
            continue
        if tok.value == "must":
            self.consume("KEYWORD", "must")
            self.consume("KEYWORD", "be")
            if self.peek().value == "at":
                self.consume("KEYWORD", "at")
            next_tok = self.peek()
            if next_tok.value == "least":
                self.consume("KEYWORD", "least")
                validation.min_expr = self.parse_expression()
                self.optional_newline()
                continue
            if next_tok.value == "most":
                self.consume("KEYWORD", "most")
                validation.max_expr = self.parse_expression()
                self.optional_newline()
                continue
            raise self.error(f"{error_code}: invalid validation rule for user input", next_tok)
        raise self.error(f"{error_code}: invalid validation rule for user input", tok)
    return validation
