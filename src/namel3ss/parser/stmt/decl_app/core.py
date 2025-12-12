"""App declaration parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes

__all__ = ["parse_app"]


def parse_app(self) -> ast_nodes.AppDecl:
    start = self.consume("KEYWORD", "app")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'app "{tok.value}": is not supported. Use app is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'app'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    description = None
    entry_page = None

    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_token = self.peek()
        if field_token.value == "starts":
            self.consume("KEYWORD", "starts")
            self.consume("KEYWORD", "at")
            self.consume("KEYWORD", "page")
            entry_token = self.consume("STRING")
            entry_page = entry_token.value
            self.optional_newline()
            continue
        field_token = self.consume("KEYWORD")
        if field_token.value == "description":
            if self.match_value("KEYWORD", "is"):
                pass
            desc_token = self.consume("STRING")
            description = desc_token.value
        elif field_token.value == "entry_page":
            if self.match_value("KEYWORD", "is"):
                pass
            entry_token = self.consume("STRING")
            entry_page = entry_token.value
        else:
            raise self.error(
                f"Unexpected field '{field_token.value}' in app block", field_token
            )
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()

    return ast_nodes.AppDecl(
        name=name.value or "",
        description=description,
        entry_page=entry_page,
        span=self._span(start),
    )
