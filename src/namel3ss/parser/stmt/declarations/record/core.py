"""Record declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from typing import Set

from namel3ss import ast_nodes

__all__ = ["parse_record"]


def parse_record(self) -> ast_nodes.RecordDecl:
    start = self.consume("KEYWORD", "record")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume_any({"STRING", "IDENT"})
    else:
        tok = self.peek()
        if tok.type in {"STRING", "IDENT"}:
            raise self.error(
                f'record "{tok.value}": is not supported. Use record is "{tok.value}": instead.',
                tok,
            )
        raise self.error("Expected 'is' after 'record'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    frame_name: str | None = None
    field_decls: list[ast_nodes.RecordFieldDecl] = []
    allowed_fields: Set[str] = {"frame", "fields"}
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_token = self.consume("KEYWORD")
        if field_token.value not in allowed_fields:
            raise self.error(
                f"Unexpected field '{field_token.value}' in record block",
                field_token,
            )
        if field_token.value == "frame":
            if self.match_value("KEYWORD", "is"):
                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            frame_name = frame_tok.value or ""
            self.optional_newline()
            continue
        if field_token.value == "fields":
            self.consume("COLON")
            self.consume("NEWLINE")
            if self.check("INDENT"):
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_name_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    field_type: str | None = None
                    primary_key = False
                    required = False
                    default_expr: ast_nodes.Expr | None = None
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        field_tok = self.consume_any({"KEYWORD", "IDENT"})
                        if field_tok.value == "type":
                            self.consume("KEYWORD", "is")
                            type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            field_type = type_tok.value
                        elif field_tok.value == "default":
                            self.consume("KEYWORD", "is")
                            if self.check("STRING"):
                                default_expr = ast_nodes.StringLiteral(
                                    value=self.consume("STRING").value or "",
                                    span=self._span(field_tok),
                                )
                            else:
                                default_expr = self.parse_expression()
                        elif field_tok.value == "required":
                            required = True
                            if self.match_value("KEYWORD", "is"):
                                bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                                required = (bool_tok.value or "").lower() == "true"
                        elif field_tok.value == "primary_key":
                            primary_key = True
                        else:
                            raise self.error(
                                f"Unexpected field '{field_tok.value}' in record field",
                                field_tok,
                            )
                        self.optional_newline()
                    self.consume("DEDENT")
                    field_decls.append(
                        ast_nodes.RecordFieldDecl(
                            name=field_name_tok.value or "",
                            type=field_type,
                            required=required,
                            primary_key=primary_key,
                            default_expr=default_expr,
                            span=self._span(field_name_tok),
                        )
                    )
                self.consume("DEDENT")
            self.optional_newline()
            continue
    self.consume("DEDENT")
    self.optional_newline()

    return ast_nodes.RecordDecl(
        name=name_tok.value or "",
        frame=frame_name or "",
        fields=field_decls,
        span=self._span(start),
    )
