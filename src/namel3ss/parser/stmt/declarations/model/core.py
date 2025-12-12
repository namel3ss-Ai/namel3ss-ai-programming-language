"""Model declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_model"]


def parse_model(self) -> ast_nodes.ModelDecl:
    start = self.consume("KEYWORD", "model")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'model "{tok.value}": is not supported. Use model is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'model'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    provider = None
    while not self.check("DEDENT"):
        field_token = self.consume("KEYWORD")
        if field_token.value == "provider":
            if self.match_value("KEYWORD", "is"):
                provider_token = self.consume("STRING")
                provider = provider_token.value
            else:
                tok = self.peek()
                if tok.type == "STRING":
                    raise self.error(
                        f'provider "{tok.value}" is not supported. Use provider is "{tok.value}" instead.', tok
                    )
                raise self.error("Expected 'is' after 'provider'", tok)
        else:
            raise self.error(
                f"Unexpected field '{field_token.value}' in model block",
                field_token,
            )
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()

    return ast_nodes.ModelDecl(
        name=name.value or "", provider=provider, span=self._span(start)
    )
