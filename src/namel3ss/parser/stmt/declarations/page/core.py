"""Page declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from typing import List, Set

from namel3ss import ast_nodes

__all__ = ["parse_page"]


def parse_page(self) -> ast_nodes.PageDecl:
    start = self.consume("KEYWORD", "page")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'page "{tok.value}": is not supported. Use page is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'page'", tok)
    route = None
    if self.match_value("KEYWORD", "at"):
        route_tok = self.consume("STRING")
        if not (route_tok.value or "").startswith("/"):
            raise self.error("N3U-1001: page route must begin with '/'", route_tok)
        route = route_tok.value or ""

    self.consume("COLON")
    self.consume("NEWLINE")
    layout: list[ast_nodes.LayoutElement] = []
    styles: list[ast_nodes.UIStyle] = []
    title = None
    description = None
    properties: List[ast_nodes.PageProperty] = []
    ai_calls: List[ast_nodes.AICallRef] = []
    agents: List[ast_nodes.PageAgentRef] = []
    memories: List[ast_nodes.PageMemoryRef] = []
    sections: List[ast_nodes.SectionDecl] = []
    allowed_fields: Set[str] = {
        "title",
        "route",
        "description",
        "ai_call",
        "agent",
        "memory",
        "section",
    }

    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
            if field_token.value in {"system", "system_prompt"}:
                raise self.error("system prompts are not supported inside a page", field_token)
            if field_token.value == "found":
                self.consume("KEYWORD", "found")
                self.consume("KEYWORD", "at")
                self.consume("KEYWORD", "route")
                value_token = self.consume("STRING")
                value = value_token.value or ""
                route = value
                properties.append(
                    ast_nodes.PageProperty(
                        key="route", value=value, span=self._span(value_token)
                    )
                )
                self.optional_newline()
                continue
            if field_token.value == "titled":
                self.consume("KEYWORD", "titled")
                value_token = self.consume("STRING")
                value = value_token.value or ""
                title = value
                properties.append(
                    ast_nodes.PageProperty(
                        key="title", value=value, span=self._span(value_token)
                    )
                )
                self.optional_newline()
                continue
            if field_token.value not in allowed_fields:
                # Treat any other token as the start of a layout block (e.g., heading/text/row/etc.).
                layout, styles = self.parse_layout_block([])
                break
            field_token = self.consume("KEYWORD")
            if field_token.value == "ai_call":
                ai_name_token = self.consume_string_value(field_token, "ai_call")
                ai_calls.append(
                    ast_nodes.AICallRef(
                        name=ai_name_token.value or "",
                        span=self._span(ai_name_token),
                    )
                )
            elif field_token.value == "agent":
                agent_token = self.consume_string_value(field_token, "agent")
                agents.append(
                    ast_nodes.PageAgentRef(
                        name=agent_token.value or "",
                        span=self._span(agent_token),
                    )
                )
            elif field_token.value == "memory":
                memory_token = self.consume_string_value(field_token, "memory")
                memories.append(
                    ast_nodes.PageMemoryRef(
                        name=memory_token.value or "",
                        span=self._span(memory_token),
                    )
                )
            elif field_token.value == "section":
                sec = self.parse_layout_section()
                sections.append(sec)
                layout.append(sec)
            else:
                value_token = self.consume_string_value(
                    field_token, field_token.value or "page field"
                )
                value = value_token.value or ""
                properties.append(
                    ast_nodes.PageProperty(
                        key=field_token.value or "",
                        value=value,
                        span=self._span(value_token),
                    )
                )
                if field_token.value == "title":
                    title = value
                elif field_token.value == "route":
                    route = value
                elif field_token.value == "description":
                    description = value
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.PageDecl(
        name=name.value or "",
        title=title,
        route=route,
        description=description,
        properties=properties,
        ai_calls=ai_calls,
        agents=agents,
        memories=memories,
        sections=sections,
        layout=layout,
        styles=styles,
        span=self._span(start),
    )
