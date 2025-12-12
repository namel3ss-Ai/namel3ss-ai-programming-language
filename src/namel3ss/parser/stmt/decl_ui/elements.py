"""Layout element parsing helpers (sections, cards, rows, columns, messages)."""

from __future__ import annotations

from .... import ast_nodes
from ....errors import ParseError

__all__ = [
    "parse_layout_section",
    "parse_card",
    "parse_row",
    "parse_column",
    "parse_message_list",
    "parse_message",
]


def parse_layout_section(self) -> ast_nodes.SectionDecl:
    if self.peek().value == "section":
        start = self.consume("KEYWORD", "section")
    else:
        start = self.peek()
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume("STRING")
    else:
        name_tok = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    layout: list[ast_nodes.LayoutElement] = []
    components: list[ast_nodes.ComponentDecl] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        parsed_layout = False
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "component":
                self.consume("KEYWORD", "component")
                components.append(self.parse_component())
                parsed_layout = True
                continue
            if self.peek().value == "show":
                components.append(self.parse_english_component())
                parsed_layout = True
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            layout, styles = self.parse_layout_block([])
            parsed_layout = True
            break
        if not parsed_layout:
            layout = []
        self.consume("DEDENT")
    self.optional_newline()
    if parsed_layout and not components and layout:
        components = [c for c in layout]
    return ast_nodes.SectionDecl(
        name=name_tok.value or "",
        components=components,
        layout=layout,
        styles=styles,
        class_name=class_name,
        style=style_map,
        span=self._span(start),
    )


def parse_card(self) -> ast_nodes.CardNode:
    start = self.consume("KEYWORD", "card")
    title = ""
    if self.match_value("KEYWORD", "is"):
        title_tok = self.consume_any({"STRING", "IDENT"})
        title = title_tok.value or ""
    elif self.check("STRING") or self.check("IDENT"):
        title_tok = self.consume_any({"STRING", "IDENT"})
        title = title_tok.value or ""
    self.consume("COLON")
    self.consume("NEWLINE")
    children: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        parsed_layout = False
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            children, styles = self.parse_layout_block([])
            parsed_layout = True
            break
        if not parsed_layout:
            children = []
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.CardNode(
        title=title,
        children=children,
        styles=styles,
        class_name=class_name,
        style=style_map,
        span=self._span(start),
    )


def parse_row(self) -> ast_nodes.RowNode:
    start = self.consume("KEYWORD", "row")
    if self.match_value("KEYWORD", "is"):
        self.consume_any({"STRING", "IDENT"})
    self.consume("COLON")
    self.consume("NEWLINE")
    children: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        parsed_layout = False
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            children, styles = self.parse_layout_block([])
            parsed_layout = True
            break
        if not parsed_layout:
            children = []
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.RowNode(children=children, styles=styles, class_name=class_name, style=style_map, span=self._span(start))


def parse_column(self) -> ast_nodes.ColumnNode:
    start = self.consume("KEYWORD", "column")
    if self.match_value("KEYWORD", "is"):
        self.consume_any({"STRING", "IDENT"})
    self.consume("COLON")
    self.consume("NEWLINE")
    children: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        parsed_layout = False
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            children, styles = self.parse_layout_block([])
            parsed_layout = True
            break
        if not parsed_layout:
            children = []
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.ColumnNode(children=children, styles=styles, class_name=class_name, style=style_map, span=self._span(start))


def parse_message_list(self) -> ast_nodes.MessageListNode:
    start = self.consume("KEYWORD", "message_list")
    self.consume("COLON")
    self.consume("NEWLINE")
    children: list[ast_nodes.MessageNode] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.peek().value == "message":
                children.append(self.parse_message())
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            if self.match("NEWLINE"):
                continue
            raise ParseError(f"Unexpected token inside message_list: {self.peek().value}")
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.MessageListNode(
        children=children,
        styles=styles,
        class_name=class_name,
        style=style_map,
        span=self._span(start),
    )


def parse_message(self) -> ast_nodes.MessageNode:
    start = self.consume("KEYWORD", "message")
    name = None
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume_any({"STRING", "IDENT"})
        name = name_tok.value
    elif self.check("STRING") or self.check("IDENT"):
        name_tok = self.consume_any({"STRING", "IDENT"})
        name = name_tok.value
    self.consume("COLON")
    self.consume("NEWLINE")
    role_expr = None
    text_expr = None
    class_name = None
    style_map: dict[str, str] = {}
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.peek().value == "message":
                break
            if self.peek().value == "role":
                self.consume("KEYWORD", "role")
                if self.match_value("KEYWORD", "is"):
                    role_expr = self.parse_expression()
                else:
                    role_expr = self.parse_expression()
                self.optional_newline()
                continue
            if self.peek().value == "text":
                self.consume("KEYWORD", "text")
                if self.match_value("KEYWORD", "is"):
                    text_expr = self.parse_expression()
                else:
                    text_expr = self.parse_expression()
                self.optional_newline()
                continue
            if self.peek().value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if self.peek().value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            if self.match("NEWLINE"):
                continue
            raise ParseError(f"Unexpected token in message block: {self.peek().value}")
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.MessageNode(
        name=name,
        role=role_expr,
        text_expr=text_expr,
        class_name=class_name,
        style=style_map,
        span=self._span(start),
    )
