"""UI style parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes
from namel3ss.lexer import Token

__all__ = ["_is_style_token", "_parse_style_block", "parse_style_line", "parse_style_map_block", "_parse_class_value"]


def _is_style_token(self, tok: Token) -> bool:
    return tok.value in {
        "color",
        "background",
        "align",
        "padding",
        "margin",
        "gap",
        "layout",
    }


def _parse_style_block(self) -> list[ast_nodes.UIStyle]:
    styles: list[ast_nodes.UIStyle] = []
    while not self.check("DEDENT") and not self.check("EOF"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if not self._is_style_token(tok):
            break
        styles.append(self.parse_style_line())
        self.optional_newline()
    return styles


def parse_style_line(self) -> ast_nodes.UIStyle:
    tok = self.consume("KEYWORD")
    kind = tok.value or ""
    value: object = None
    if kind == "color":
        self.consume("KEYWORD", "is")
        if self.check("STRING"):
            val_tok = self.consume("STRING")
            value = val_tok.value or ""
        else:
            ident_tok = self.consume_any({"IDENT", "KEYWORD"})
            value = ident_tok.value or ""
        return ast_nodes.UIStyle(kind="color", value=value, span=self._span(tok))
    if kind == "background":
        self.consume("KEYWORD", "color")
        self.consume("KEYWORD", "is")
        if self.check("STRING"):
            val_tok = self.consume("STRING")
            value = val_tok.value or ""
        else:
            ident_tok = self.consume_any({"IDENT", "KEYWORD"})
            value = ident_tok.value or ""
        return ast_nodes.UIStyle(kind="background", value=value, span=self._span(tok))
    if kind == "align":
        if self.peek().value == "vertically":
            self.consume("KEYWORD", "vertically")
            self.consume("KEYWORD", "is")
            val_tok = self.consume_any({"IDENT", "KEYWORD"})
            if (val_tok.value or "") not in {"top", "middle", "bottom"}:
                raise self.error("N3U-3200: invalid alignment keyword", val_tok)
            return ast_nodes.UIStyle(kind="align_vertical", value=val_tok.value or "", span=self._span(tok))
        self.consume("KEYWORD", "is")
        val_tok = self.consume_any({"IDENT", "KEYWORD"})
        if (val_tok.value or "") not in {"left", "center", "right"}:
            raise self.error("N3U-3200: invalid alignment keyword", val_tok)
        return ast_nodes.UIStyle(kind="align", value=val_tok.value or "", span=self._span(tok))
    if kind == "layout":
        self.consume("KEYWORD", "is")
        if self.peek().value in {"two", "three"}:
            first = self.consume_any({"IDENT", "KEYWORD"})
            second = self.consume_any({"IDENT", "KEYWORD"})
            value = f"{first.value} {second.value}"
        else:
            val_tok = self.consume_any({"IDENT", "KEYWORD"})
            value = val_tok.value or ""
        if value not in {"row", "column", "two columns", "three columns"}:
            raise self.error("N3U-3300: invalid layout type", tok)
        return ast_nodes.UIStyle(kind="layout", value=value, span=self._span(tok))
    if kind in {"padding", "margin", "gap"}:
        self.consume("KEYWORD", "is")
        val_tok = self.consume_any({"IDENT", "KEYWORD"})
        if (val_tok.value or "") not in {"small", "medium", "large"}:
            raise self.error("N3U-3400: invalid spacing size", val_tok)
        return ast_nodes.UIStyle(kind=kind, value=val_tok.value or "", span=self._span(tok))
    raise self.error("N3U-3101: style outside of a page or section", tok)


def parse_style_map_block(self) -> dict[str, str]:
    style_map: dict[str, str] = {}
    self.consume("COLON")
    self.consume("NEWLINE")
    if not self.check("INDENT"):
        raise self.error("N3U-3500: style block must be indented", self.peek())
    self.consume("INDENT")
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        key_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
        self.consume("COLON")
        if not self.check("STRING"):
            raise self.error("N3U-3501: style values must be string literals", self.peek())
        val_tok = self.consume("STRING")
        style_map[key_tok.value or ""] = val_tok.value or ""
        self.optional_newline()
    self.consume("DEDENT")
    return style_map


def _parse_class_value(self) -> str:
    if self.match_value("KEYWORD", "is"):
        if not self.check("STRING"):
            raise self.error("N3U-3502: class value must be a string literal", self.peek())
        tok = self.consume("STRING")
    else:
        if not self.check("STRING"):
            raise self.error("N3U-3502: class value must be a string literal", self.peek())
        tok = self.consume("STRING")
    return tok.value or ""
