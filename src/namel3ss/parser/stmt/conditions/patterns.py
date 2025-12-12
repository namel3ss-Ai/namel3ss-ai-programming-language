"""Pattern expression parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes

__all__ = ["parse_condition_expr", "parse_pattern_expr"]


def parse_condition_expr(self) -> ast_nodes.Expr:
    token = self.peek()
    next_token = self.peek_offset(1)
    if token.type in {"IDENT", "KEYWORD"} and next_token and next_token.value == "matches":
        return self.parse_pattern_expr()
    return self.parse_expression()


def parse_pattern_expr(self) -> ast_nodes.PatternExpr:
    subject_tok = self.consume_any({"IDENT", "KEYWORD"})
    subject = ast_nodes.Identifier(name=subject_tok.value or "", span=self._span(subject_tok))
    self.consume("KEYWORD", "matches")
    if not self.match("LBRACE"):
        raise self.error("Expected '{' to start pattern.", self.peek())
    pairs: list[ast_nodes.PatternPair] = []
    while not self.check("RBRACE"):
        key_tok = self.consume_any({"IDENT"})
        if not key_tok.value or not key_tok.value.isidentifier():
            raise self.error("Pattern keys must be identifiers.", key_tok)
        self.consume("COLON")
        if self.check("RBRACE"):
            raise self.error("Expected a value after ':' in pattern.", self.peek())
        if self.check("LBRACE"):
            raise self.error("Nested patterns are not supported in Phase 5.", self.peek())
        value_expr = self.parse_expression()
        if isinstance(value_expr, ast_nodes.PatternExpr):
            raise self.error("Nested patterns are not supported in Phase 5.", key_tok)
        pairs.append(ast_nodes.PatternPair(key=key_tok.value, value=value_expr))
        if self.match("COMMA"):
            continue
        break
    if not self.match("RBRACE"):
        raise self.error("Expected '}' to close pattern.", self.peek())
    self.optional_newline()
    return ast_nodes.PatternExpr(subject=subject, pairs=pairs, span=self._span(subject_tok))
