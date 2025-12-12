"""Memory declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from typing import Set

from .... import ast_nodes

__all__ = ["parse_memory", "parse_memory_profile"]


def parse_memory(self) -> ast_nodes.MemoryDecl:
    start = self.consume("KEYWORD", "memory")
    name = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    memory_type = None
    retention = None
    allowed_fields: Set[str] = {"type", "retention"}
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_token = self.consume("KEYWORD")
        if field_token.value not in allowed_fields:
            raise self.error(
                f"Unexpected field '{field_token.value}' in memory block",
                field_token,
            )
        value_token = self.consume_string_value(field_token, field_token.value or "memory field")
        if field_token.value == "type":
            memory_type = value_token.value
        elif field_token.value == "retention":
            retention = value_token.value
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()

    return ast_nodes.MemoryDecl(
        name=name.value or "", memory_type=memory_type, retention=retention, span=self._span(start)
    )


def parse_memory_profile(self) -> ast_nodes.MemoryProfileDecl:
    start = self.consume("KEYWORD", "memory")
    profile_tok = self.consume_any({"KEYWORD", "IDENT"})
    if (profile_tok.value or "").lower() != "profile":
        raise self.error("Expected 'profile' after memory when declaring a memory profile.", profile_tok)
    self.consume("KEYWORD", "is")
    name_tok = self.consume("STRING")
    owner_label = f"memory profile '{name_tok.value or ''}'"
    config = self._parse_memory_block(owner_label, start)
    return ast_nodes.MemoryProfileDecl(name=name_tok.value or "", config=config, span=self._span(start))
