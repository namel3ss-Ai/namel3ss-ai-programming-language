"""UI component parsing helpers (component decls, calls, buttons, sections)."""

from __future__ import annotations

from typing import List

from .... import ast_nodes

__all__ = [
    "parse_ui_component_decl",
    "parse_component_call",
    "parse_button",
    "_parse_navigate_action",
    "parse_ui_conditional",
    "parse_section",
    "parse_component",
    "parse_english_component",
]


def parse_ui_component_decl(self) -> ast_nodes.UIComponentDecl:
    start_tok = self.consume("KEYWORD", "component")
    name_tok = self.consume("STRING")
    params: list[str] = []
    render_layout: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = []
    class_name = None
    style_map: dict[str, str] = {}
    self.consume("COLON")
    self.consume("NEWLINE")
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "takes":
                self.consume("KEYWORD", "takes")
                while True:
                    ident_tok = self.consume_any({"IDENT", "KEYWORD"})
                    params.append(ident_tok.value or "")
                    if self.match_value("COMMA", ","):
                        continue
                    break
                self.optional_newline()
                continue
            if tok.value == "render":
                self.consume("KEYWORD", "render")
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    render_layout, styles = self.parse_layout_block([])
                    self.consume("DEDENT")
                self.optional_newline()
                continue
            if tok.value == "class":
                self.consume("KEYWORD", "class")
                class_name = self._parse_class_value()
                self.optional_newline()
                continue
            if tok.value == "style":
                self.consume("KEYWORD", "style")
                style_map = self.parse_style_map_block()
                self.optional_newline()
                continue
            raise self.error("N3U-3501: missing render block", tok)
        self.consume("DEDENT")
    self.optional_newline()
    if not render_layout:
        raise self.error("N3U-3501: missing render block", start_tok)
    return ast_nodes.UIComponentDecl(
        name=name_tok.value or "",
        params=params,
        render=render_layout,
        styles=styles,
        class_name=class_name,
        style=style_map,
        span=self._span(start_tok),
    )


def parse_component_call(self) -> ast_nodes.UIComponentCall:
    name_tok = self.consume_any({"IDENT"})
    args: list[ast_nodes.Expr] = []
    named_args: dict[str, list[ast_nodes.Statement | ast_nodes.FlowAction]] = {}
    class_name = None
    style_map: dict[str, str] = {}
    if not self.check("COLON"):
        args.append(self.parse_expression())
    if self.peek().value == ":" or self.check("COLON"):
        self.consume("COLON")
        self.consume("NEWLINE")
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                if key_tok.value == "class":
                    class_name = self._parse_class_value()
                    self.optional_newline()
                    continue
                if key_tok.value == "style":
                    style_map = self.parse_style_map_block()
                    self.optional_newline()
                    continue
                self.consume("COLON")
                block_items: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
                if self.check("NEWLINE"):
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            if self.peek().value in {"do", "go"}:
                                block_items.append(self.parse_statement_or_action())
                                self.optional_newline()
                                continue
                            block_items.append(self.parse_statement_or_action())
                        self.consume("DEDENT")
                named_args[key_tok.value or ""] = block_items
                self.optional_newline()
            self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.UIComponentCall(
        name=name_tok.value or "",
        args=args,
        named_args=named_args,
        class_name=class_name,
        style=style_map,
        span=self._span(name_tok),
    )


def parse_button(self) -> ast_nodes.UIButtonNode:
    start_tok = self.consume("KEYWORD", "button")
    if self.match_value("KEYWORD", "is"):
        label_tok = self.consume_any({"STRING", "IDENT"})
    else:
        label_tok = self.consume_any({"STRING", "IDENT"})
    label_text = label_tok.value or ""
    self.consume("COLON")
    self.consume("NEWLINE")
    if not self.check("INDENT"):
        raise self.error("N3U-2201: on click missing or empty", self.peek())
    self.consume("INDENT")
    handler: ast_nodes.UIClickHandler | None = None
    label_expr = None
    class_name = None
    style_map: dict[str, str] = {}
    if label_tok.type == "IDENT":
        label_expr = ast_nodes.Identifier(name=label_tok.value or "", span=self._span(label_tok))
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        if tok.value == "label":
            self.consume_any({"KEYWORD", "IDENT"})
            if self.match_value("KEYWORD", "is"):
                lbl_tok = self.consume_any({"STRING", "IDENT"})
            else:
                lbl_tok = self.consume_any({"STRING", "IDENT"})
            label_text = lbl_tok.value or ""
            if lbl_tok.type == "IDENT":
                label_expr = ast_nodes.Identifier(name=lbl_tok.value or "", span=self._span(lbl_tok))
            else:
                label_expr = None
            self.optional_newline()
            continue
        if tok.value == "class":
            self.consume_any({"KEYWORD", "IDENT"})
            class_name = self._parse_class_value()
            self.optional_newline()
            continue
        if tok.value == "style":
            self.consume_any({"KEYWORD", "IDENT"})
            style_map = self.parse_style_map_block()
            self.optional_newline()
            continue
        if tok.value == "on":
            self.consume("KEYWORD", "on")
            self.consume("KEYWORD", "click")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions: list[ast_nodes.ClickAction] = []
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                if self.peek().value == "do":
                    actions.append(self._parse_do_action())
                    self.optional_newline()
                    continue
                if self.peek().value == "go":
                    actions.append(self.parse_goto_action(allow_page=True))
                    self.optional_newline()
                    continue
                if self.peek().value == "navigate":
                    actions.append(self._parse_navigate_action())
                    self.optional_newline()
                    continue
                raise self.error("N3U-2202: invalid action in click handler", self.peek())
            self.consume("DEDENT")
            if actions:
                navigate_actions = [act for act in actions if getattr(act, "kind", None) == "navigate"]
                if navigate_actions and len(navigate_actions) != len(actions):
                    button_name = label_text or "<button>"
                    raise self.error(
                        f"N3L-1300: Click handler for button '{button_name}' cannot contain both a flow call and navigation. Choose one action.",
                        start_tok,
                    )
            handler = ast_nodes.UIClickHandler(actions=actions, span=self._span(tok))
            self.optional_newline()
            continue
        raise self.error("N3U-2201: on click missing or empty", tok)
    self.consume("DEDENT")
    self.optional_newline()
    if not handler or not handler.actions:
        raise self.error("N3U-2201: on click missing or empty", start_tok)
    return ast_nodes.UIButtonNode(
        label=label_text,
        label_expr=label_expr,
        handler=handler,
        class_name=class_name,
        style=style_map,
        span=self._span(start_tok),
    )


def _parse_navigate_action(self) -> ast_nodes.NavigateAction:
    start_tok = self.consume("KEYWORD", "navigate")
    self.match_value("KEYWORD", "to")
    target_path = None
    target_page = None
    if self.match_value("KEYWORD", "page"):
        if self.match_value("KEYWORD", "is"):
            if not self.check("STRING") and not self.check("IDENT"):
                raise self.error("N3L-950: navigate action must specify a path or page.", self.peek())
            page_tok = self.consume_any({"STRING", "IDENT"})
        else:
            if not self.check("STRING") and not self.check("IDENT"):
                raise self.error("N3L-950: navigate action must specify a path or page.", self.peek())
            page_tok = self.consume_any({"STRING", "IDENT"})
        target_page = page_tok.value
    else:
        if self.match_value("KEYWORD", "is"):
            if not self.check("STRING"):
                raise self.error("N3L-950: navigate action must specify a path or page.", self.peek())
            path_tok = self.consume("STRING")
        else:
            if not self.check("STRING"):
                raise self.error("N3L-950: navigate action must specify a path or page.", self.peek())
            path_tok = self.consume("STRING")
        target_path = path_tok.value
    if not target_path and not target_page:
        raise self.error("N3L-950: navigate action must specify a path or page.", start_tok)
    return ast_nodes.NavigateAction(kind="navigate", target_path=target_path, target_page_name=target_page, span=self._span(start_tok))


def parse_ui_conditional(self) -> ast_nodes.UIConditional:
    start_tok = self.consume("KEYWORD", "when")
    condition = self.parse_condition_expr()
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    when_children: list[ast_nodes.LayoutElement] = []
    otherwise_children: list[ast_nodes.LayoutElement] = []
    has_show = False
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        if self.peek().value == "show":
            has_show = True
            self.consume("KEYWORD", "show")
            self.consume("COLON")
            self.consume("NEWLINE")
            if self.check("INDENT"):
                self.consume("INDENT")
                when_children, _ = self.parse_layout_block([])
                self.consume("DEDENT")
            self.optional_newline()
            continue
        raise self.error("N3U-2302: unexpected content inside conditional", self.peek())
    self.consume("DEDENT")
    self.optional_newline()
    if self.peek().value == "otherwise":
        self.consume("KEYWORD", "otherwise")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "show":
                self.consume("KEYWORD", "show")
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    otherwise_children, _ = self.parse_layout_block([])
                    self.consume("DEDENT")
                self.optional_newline()
                continue
            raise self.error("N3U-2302: unexpected content inside conditional", self.peek())
        self.consume("DEDENT")
        self.optional_newline()
    if not has_show or (not when_children and not otherwise_children):
        raise self.error("N3U-2302: empty conditional blocks", start_tok)
    return ast_nodes.UIConditional(
        condition=condition,
        when_children=when_children,
        otherwise_children=otherwise_children,
        span=self._span(start_tok),
    )


def parse_section(self) -> ast_nodes.SectionDecl:
    if self.match_value("KEYWORD", "is"):
        section_name_token = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'section "{tok.value}": is not supported. Use section is "{tok.value}": instead.', tok)
        section_name_token = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    components: List[ast_nodes.ComponentDecl] = []
    layout: List[ast_nodes.LayoutElement] = []
    styles: List[ast_nodes.UIStyle] = []
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        token = self.peek()
        if token.value == "component":
            self.consume("KEYWORD", "component")
            components.append(self.parse_component())
        elif token.value == "show":
            components.append(self.parse_english_component())
        else:
            layout, styles = self.parse_layout_block([])
            break
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.SectionDecl(
        name=section_name_token.value or "",
        components=components,
        layout=layout,
        styles=styles,
        span=self._span(section_name_token),
    )


def parse_component(self) -> ast_nodes.ComponentDecl:
    comp_type_token = self.consume("STRING")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    props: List[ast_nodes.PageProperty] = []
    while not self.check("DEDENT"):
        field_token = self.consume("KEYWORD")
        if self.match_value("KEYWORD", "is"):
            value_token = self.consume("STRING")
        else:
            value_token = self.consume_string_value(field_token, field_token.value or "component field")
        props.append(
            ast_nodes.PageProperty(
                key=field_token.value or "",
                value=value_token.value or "",
                span=self._span(value_token),
            )
        )
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.ComponentDecl(
        type=comp_type_token.value or "",
        props=props,
        span=self._span(comp_type_token),
    )


def parse_english_component(self) -> ast_nodes.ComponentDecl:
    show_token = self.consume("KEYWORD", "show")
    comp_type = self.consume_any({"KEYWORD", "IDENT"})
    if comp_type.value not in {"text", "form"}:
        raise self.error(f"Unsupported component type '{comp_type.value}'", comp_type)
    if comp_type.value == "form" and self.peek().value == "asking":
        self.consume("KEYWORD", "asking")
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    value_token = self.consume("STRING")
    self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.ComponentDecl(
        type=comp_type.value or "",
        props=[
            ast_nodes.PageProperty(
                key="value",
                value=value_token.value or "",
                span=self._span(value_token),
            )
        ],
        span=self._span(show_token),
    )
