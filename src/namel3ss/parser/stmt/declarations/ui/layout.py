"""Layout block parsing helpers for UI declarations."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_layout_block"]


def parse_layout_block(self, container_styles: list[ast_nodes.UIStyle] | None = None) -> tuple[list[ast_nodes.LayoutElement], list[ast_nodes.UIStyle]]:
    elements: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = container_styles or []
    last_element: ast_nodes.LayoutElement | None = None
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        if self.peek().type == "INDENT":
            self.consume("INDENT")
            if last_element is None:
                raise self.error("N3U-3101: style outside of a page or section", self.peek())
            last_element.styles.extend(self._parse_style_block())
            self.consume("DEDENT")
            self.optional_newline()
            continue
        tok = self.peek()
        if self._is_style_token(tok):
            styles.extend(self._parse_style_block())
            continue
        if tok.value == "section":
            sec = self.parse_layout_section()
            elements.append(sec)
            last_element = sec
            continue
        if tok.value == "card":
            card = self.parse_card()
            elements.append(card)
            last_element = card
            continue
        if tok.value == "message_list":
            mlist = self.parse_message_list()
            elements.append(mlist)
            last_element = mlist
            continue
        if tok.value == "message":
            msg = self.parse_message()
            elements.append(msg)
            last_element = msg
            continue
        if tok.value == "row":
            row = self.parse_row()
            elements.append(row)
            last_element = row
            continue
        if tok.value == "column":
            col = self.parse_column()
            elements.append(col)
            last_element = col
            continue
        if tok.value == "state":
            state_tok = self.consume("KEYWORD", "state")
            name_tok = self.consume_any({"IDENT", "KEYWORD"})
            self.consume("KEYWORD", "is")
            expr = self.parse_expression()
            node = ast_nodes.UIStateDecl(name=name_tok.value or "", expr=expr, span=self._span(state_tok))
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "heading":
            self.consume("KEYWORD", "heading")
            txt_tok = self.consume("STRING")
            class_name = None
            style_map: dict[str, str] = {}
            node = ast_nodes.HeadingNode(text=txt_tok.value or "", span=self._span(txt_tok))
            if self.match("COLON"):
                self.consume("NEWLINE")
                if not self.check("INDENT"):
                    raise self.error("N3U-1301: invalid heading block", self.peek())
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if field_tok.value == "value":
                        if self.match_value("KEYWORD", "is"):
                            value_expr = self.parse_expression()
                        else:
                            value_expr = self.parse_expression()
                        if isinstance(value_expr, ast_nodes.Literal) and isinstance(value_expr.value, str):
                            node.text = value_expr.value
                    elif field_tok.value == "class":
                        class_name = self._parse_class_value()
                    elif field_tok.value == "style":
                        style_map = self.parse_style_map_block()
                    else:
                        raise self.error(f"Unexpected field '{field_tok.value}' in heading", field_tok)
                    self.optional_newline()
                self.consume("DEDENT")
            node.class_name = class_name
            node.style = style_map
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "text":
            start_tok = self.consume("KEYWORD", "text")
            class_name = None
            style_map: dict[str, str] = {}
            text_expr = None
            if self.match_value("KEYWORD", "is"):
                if self.check("STRING"):
                    txt_tok = self.consume("STRING")
                    literal_text = txt_tok.value or ""
                else:
                    text_expr = self.parse_expression()
                    literal_text = text_expr.value if isinstance(text_expr, ast_nodes.Literal) and isinstance(text_expr.value, str) else ""
            elif self.check("STRING") and self.peek_offset(1).type in {"NEWLINE", "DEDENT", "EOF"}:
                txt_tok = self.consume("STRING")
                literal_text = txt_tok.value or ""
            else:
                text_expr = self.parse_expression()
                literal_text = text_expr.value if isinstance(text_expr, ast_nodes.Literal) and isinstance(text_expr.value, str) else ""
            node = ast_nodes.TextNode(text=literal_text, expr=text_expr, span=self._span(start_tok))
            if self.match("COLON"):
                self.consume("NEWLINE")
                if not self.check("INDENT"):
                    raise self.error("N3U-1301: invalid text block", self.peek())
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if field_tok.value == "value":
                        if self.match_value("KEYWORD", "is"):
                            text_expr = self.parse_expression()
                        else:
                            text_expr = self.parse_expression()
                        if isinstance(text_expr, ast_nodes.Literal) and isinstance(text_expr.value, str):
                            literal_text = text_expr.value
                    elif field_tok.value == "class":
                        class_name = self._parse_class_value()
                    elif field_tok.value == "style":
                        style_map = self.parse_style_map_block()
                    else:
                        raise self.error(f"Unexpected field '{field_tok.value}' in text block", field_tok)
                    self.optional_newline()
                self.consume("DEDENT")
                node.expr = text_expr
                node.text = literal_text
            node.class_name = class_name
            node.style = style_map
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "image":
            self.consume("KEYWORD", "image")
            url_tok = self.consume("STRING")
            class_name = None
            style_map: dict[str, str] = {}
            node = ast_nodes.ImageNode(url=url_tok.value or "", span=self._span(url_tok))
            if self.match("COLON"):
                self.consume("NEWLINE")
                if not self.check("INDENT"):
                    raise self.error("N3U-1301: invalid image block", self.peek())
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if field_tok.value in {"url", "src"}:
                        if self.match_value("KEYWORD", "is"):
                            if not self.check("STRING"):
                                raise self.error("N3U-3102: image url must be string", self.peek())
                            url_tok = self.consume("STRING")
                            node.url = url_tok.value or ""
                        else:
                            if not self.check("STRING"):
                                raise self.error("N3U-3102: image url must be string", self.peek())
                            url_tok = self.consume("STRING")
                            node.url = url_tok.value or ""
                    elif field_tok.value == "class":
                        class_name = self._parse_class_value()
                    elif field_tok.value == "style":
                        style_map = self.parse_style_map_block()
                    else:
                        raise self.error(f"Unexpected field '{field_tok.value}' in image", field_tok)
                    self.optional_newline()
                self.consume("DEDENT")
            node.class_name = class_name
            node.style = style_map
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "input":
            start_tok = self.consume("KEYWORD", "input")
            if self.match_value("KEYWORD", "is"):
                label_tok = self.consume("STRING")
            else:
                label_tok = self.consume("STRING")
            var_name = None
            field_type = None
            validation: ast_nodes.UIValidationRules | None = None
            class_name = None
            style_map: dict[str, str] = {}
            if self.match("COLON"):
                self.consume("NEWLINE")
                self.consume("INDENT")
                validation = ast_nodes.UIValidationRules()
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if field_tok.value == "bind":
                        if self.match_value("KEYWORD", "is"):
                            var_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                        else:
                            var_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                        var_name = var_tok.value
                    elif field_tok.value == "type":
                        if self.match_value("KEYWORD", "is"):
                            type_tok = self.consume_any({"IDENT", "KEYWORD"})
                        else:
                            type_tok = self.consume_any({"IDENT", "KEYWORD"})
                        field_type = type_tok.value
                    elif field_tok.value in {"required", "min_length", "max_length", "pattern", "message"}:
                        if self.match_value("KEYWORD", "is"):
                            expr = self.parse_expression()
                        else:
                            expr = self.parse_expression()
                        if isinstance(expr, ast_nodes.Literal):
                            if field_tok.value == "required":
                                validation.required = bool(expr.value)
                            elif field_tok.value == "min_length":
                                validation.min_length = int(expr.value)
                            elif field_tok.value == "max_length":
                                validation.max_length = int(expr.value)
                            elif field_tok.value == "pattern":
                                validation.pattern = str(expr.value)
                            elif field_tok.value == "message":
                                validation.message = str(expr.value)
                    elif field_tok.value == "class":
                        class_name = self._parse_class_value()
                    elif field_tok.value == "style":
                        style_map = self.parse_style_map_block()
                    else:
                        raise self.error(f"Unexpected field '{field_tok.value}' in input", field_tok)
                    self.optional_newline()
                self.consume("DEDENT")
            else:
                self.consume("KEYWORD", "as")
                var_tok = self.consume_any({"IDENT"})
                var_name = var_tok.value
                if self.peek().value == "type":
                    self.consume("KEYWORD", "type")
                    self.consume("KEYWORD", "is")
                    type_tok = self.consume_any({"IDENT", "KEYWORD"})
                    field_type = type_tok.value
            node = ast_nodes.UIInputNode(
                label=label_tok.value or "",
                var_name=var_name or "",
                field_type=field_type,
                validation=validation,
                class_name=class_name,
                style=style_map,
                span=self._span(start_tok),
            )
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "textarea":
            start_tok = self.consume("KEYWORD", "textarea")
            if self.match_value("KEYWORD", "is"):
                label_tok = self.consume("STRING")
            else:
                label_tok = self.consume("STRING")
            var_name = None
            validation = None
            class_name = None
            style_map: dict[str, str] = {}
            if self.match("COLON"):
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    validation = ast_nodes.UIValidationRules()
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        field_tok = self.consume_any({"KEYWORD", "IDENT"})
                        if field_tok.value == "bind":
                            if self.match_value("KEYWORD", "is"):
                                var_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                            else:
                                var_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                            var_name = var_tok.value
                        elif field_tok.value in {"required", "min_length", "max_length", "pattern", "message"}:
                            if self.match_value("KEYWORD", "is"):
                                expr = self.parse_expression()
                            else:
                                expr = self.parse_expression()
                            if isinstance(expr, ast_nodes.Literal):
                                if field_tok.value == "required":
                                    validation.required = bool(expr.value)
                                elif field_tok.value == "min_length":
                                    validation.min_length = int(expr.value)
                                elif field_tok.value == "max_length":
                                    validation.max_length = int(expr.value)
                                elif field_tok.value == "pattern":
                                    validation.pattern = str(expr.value)
                                elif field_tok.value == "message":
                                    validation.message = str(expr.value)
                        elif field_tok.value == "class":
                            class_name = self._parse_class_value()
                        elif field_tok.value == "style":
                            style_map = self.parse_style_map_block()
                        else:
                            raise self.error(f"Unexpected field '{field_tok.value}' in textarea", field_tok)
                        self.optional_newline()
                    self.consume("DEDENT")
            elif self.peek().value == "bind":
                self.consume("KEYWORD", "bind")
                if self.match_value("KEYWORD", "is"):
                    var_tok = self.consume_any({"IDENT"})
                else:
                    var_tok = self.consume_any({"IDENT"})
                var_name = var_tok.value
            node = ast_nodes.TextareaNode(label=label_tok.value or "", var_name=var_name, validation=validation, span=self._span(start_tok))
            node.class_name = class_name
            node.style = style_map
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "button":
            node = self.parse_button()
            elements.append(node)
            last_element = node
            continue
        if tok.value == "badge":
            start_tok = self.consume("KEYWORD", "badge")
            if self.match_value("KEYWORD", "is"):
                txt_tok = self.consume("STRING")
            else:
                txt_tok = self.consume("STRING")
            class_name = None
            style_map: dict[str, str] = {}
            node = ast_nodes.BadgeNode(text=txt_tok.value or "", span=self._span(start_tok))
            if self.match("COLON"):
                self.consume("NEWLINE")
                if not self.check("INDENT"):
                    raise self.error("N3U-1301: invalid badge block", self.peek())
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if field_tok.value == "text":
                        if self.match_value("KEYWORD", "is"):
                            val_expr = self.parse_expression()
                        else:
                            val_expr = self.parse_expression()
                        if isinstance(val_expr, ast_nodes.Literal) and isinstance(val_expr.value, str):
                            node.text = val_expr.value
                    elif field_tok.value == "class":
                        class_name = self._parse_class_value()
                    elif field_tok.value == "style":
                        style_map = self.parse_style_map_block()
                    else:
                        raise self.error(f"Unexpected field '{field_tok.value}' in badge", field_tok)
                    self.optional_newline()
                self.consume("DEDENT")
            node.class_name = class_name
            node.style = style_map
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.value == "when":
            node = self.parse_ui_conditional()
            elements.append(node)
            last_element = node
            continue
        if tok.value == "use":
            self.consume("KEYWORD", "use")
            if self.peek().value != "form":
                raise self.error("N3U-1201: invalid form reference", self.peek())
            self.consume("KEYWORD", "form")
            form_tok = self.consume("STRING")
            node = ast_nodes.EmbedFormNode(form_name=form_tok.value or "", span=self._span(form_tok))
            elements.append(node)
            last_element = node
            self.optional_newline()
            continue
        if tok.type == "IDENT":
            node = self.parse_component_call()
            elements.append(node)
            last_element = node
            continue
        raise self.error("N3U-1300: layout element outside of page/section", tok)
    return elements, styles
