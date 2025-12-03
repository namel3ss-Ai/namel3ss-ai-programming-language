"""
Parser for the minimal Namel3ss V3 language slice.
"""

from __future__ import annotations

from typing import List, Set

from . import ast_nodes
from .errors import ParseError
from .lexer import Lexer, Token


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.position = 0

    @classmethod
    def from_source(cls, source: str) -> "Parser":
        return cls(Lexer(source).tokenize())

    def parse_module(self) -> ast_nodes.Module:
        module = ast_nodes.Module()
        while not self.check("EOF"):
            if self.match("NEWLINE"):
                continue
            module.declarations.append(self.parse_declaration())
        return module

    def parse_declaration(self) -> ast_nodes.Declaration:
        token = self.peek()
        if token.type != "KEYWORD":
            raise self.error("Expected a declaration", token)

        if token.value == "use":
            return self.parse_use()
        if token.value == "app":
            return self.parse_app()
        if token.value == "page":
            return self.parse_page()
        if token.value == "model":
            return self.parse_model()
        if token.value == "ai":
            return self.parse_ai()
        if token.value == "agent":
            return self.parse_agent()
        if token.value == "memory":
            return self.parse_memory()
        if token.value == "flow":
            return self.parse_flow()
        if token.value == "plugin":
            return self.parse_plugin()
        raise self.error(f"Unexpected declaration '{token.value}'", token)

    def parse_use(self) -> ast_nodes.UseImport:
        start = self.consume("KEYWORD", "use")
        path = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.UseImport(path=path.value or "", span=self._span(start))

    def parse_app(self) -> ast_nodes.AppDecl:
        start = self.consume("KEYWORD", "app")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        description = None
        entry_page = None

        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value == "description":
                desc_token = self.consume("STRING")
                description = desc_token.value
            elif field_token.value == "entry_page":
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

    def parse_page(self) -> ast_nodes.PageDecl:
        start = self.consume("KEYWORD", "page")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        title = None
        route = None
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
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in page block",
                    field_token,
                )
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
                sections.append(self.parse_section())
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
            span=self._span(start),
        )

    def parse_model(self) -> ast_nodes.ModelDecl:
        start = self.consume("KEYWORD", "model")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        provider = None
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value == "provider":
                provider_token = self.consume("STRING")
                provider = provider_token.value
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

    def parse_ai(self) -> ast_nodes.AICallDecl:
        start = self.consume("KEYWORD", "ai")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        model_name = None
        input_source = None
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value == "model":
                model_tok = self.consume("STRING")
                model_name = model_tok.value
            elif field_token.value == "input":
                self.consume("KEYWORD", "from")
                source_tok = self.consume_any({"IDENT", "STRING"})
                input_source = source_tok.value
            else:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in ai block", field_token
                )
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.AICallDecl(
            name=name.value or "",
            model_name=model_name,
            input_source=input_source,
            span=self._span(start),
        )

    def parse_agent(self) -> ast_nodes.AgentDecl:
        start = self.consume("KEYWORD", "agent")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        goal = None
        personality = None
        allowed_fields: Set[str] = {"goal", "personality"}
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in agent block",
                    field_token,
                )
            value_token = self.consume_string_value(
                field_token, field_token.value or "agent field"
            )
            if field_token.value == "goal":
                goal = value_token.value
            elif field_token.value == "personality":
                personality = value_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.AgentDecl(
            name=name.value or "",
            goal=goal,
            personality=personality,
            span=self._span(start),
        )

    def parse_memory(self) -> ast_nodes.MemoryDecl:
        start = self.consume("KEYWORD", "memory")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        memory_type = None
        allowed_fields: Set[str] = {"type"}
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in memory block",
                    field_token,
                )
            value_token = self.consume_string_value(field_token, "type")
            memory_type = value_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.MemoryDecl(
            name=name.value or "", memory_type=memory_type, span=self._span(start)
        )

    def parse_flow(self) -> ast_nodes.FlowDecl:
        start = self.consume("KEYWORD", "flow")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        description = None
        steps: List[ast_nodes.FlowStepDecl] = []
        if self.check("INDENT"):
            self.consume("INDENT")
            allowed_fields: Set[str] = {"description", "step"}
            while not self.check("DEDENT"):
                field_token = self.consume("KEYWORD")
                if field_token.value not in allowed_fields:
                    raise self.error(
                        f"Unexpected field '{field_token.value}' in flow block",
                        field_token,
                    )
                if field_token.value == "description":
                    value_token = self.consume_string_value(field_token, "description")
                    description = value_token.value
                    self.optional_newline()
                elif field_token.value == "step":
                    steps.append(self.parse_flow_step())
                else:
                    raise self.error(
                        f"Unexpected field '{field_token.value}' in flow block",
                        field_token,
                    )
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.FlowDecl(
            name=name.value or "",
            description=description,
            steps=steps,
            span=self._span(start),
        )

    def parse_plugin(self) -> ast_nodes.PluginDecl:
        start = self.consume("KEYWORD", "plugin")
        name = self.consume("STRING")
        description = None
        if self.check("COLON"):
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            while not self.check("DEDENT"):
                field_token = self.consume("KEYWORD")
                if field_token.value != "description":
                    raise self.error(
                        f"Unexpected field '{field_token.value}' in plugin block",
                        field_token,
                    )
                desc_token = self.consume_string_value(field_token, "description")
                description = desc_token.value
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
        else:
            self.optional_newline()
        return ast_nodes.PluginDecl(
            name=name.value or "", description=description, span=self._span(start)
        )

    def parse_section(self) -> ast_nodes.SectionDecl:
        section_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        components: List[ast_nodes.ComponentDecl] = []
        while not self.check("DEDENT"):
            token = self.consume("KEYWORD")
            if token.value != "component":
                raise self.error(
                    f"Unexpected field '{token.value}' in section block", token
                )
            components.append(self.parse_component())
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.SectionDecl(
            name=section_name_token.value or "",
            components=components,
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

    def parse_flow_step(self) -> ast_nodes.FlowStepDecl:
        step_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        kind = None
        target = None
        allowed_fields: Set[str] = {"kind", "target"}
        while not self.check("DEDENT"):
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in step block",
                    field_token,
                )
            if field_token.value == "kind":
                kind_token = self.consume_string_value(field_token, "kind")
                kind = kind_token.value
            elif field_token.value == "target":
                target_token = self.consume_string_value(field_token, "target")
                target = target_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        if kind is None:
            raise self.error("Missing 'kind' in step", step_name_token)
        if target is None:
            raise self.error("Missing 'target' in step", step_name_token)
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            kind=kind,
            target=target,
            span=self._span(step_name_token),
        )

    def optional_newline(self) -> None:
        if self.check("NEWLINE"):
            self.advance()

    def consume_string_value(self, field_token: Token, field_name: str) -> Token:
        if not self.check("STRING"):
            raise self.error(f"Expected string after '{field_name}'", self.peek())
        return self.consume("STRING")

    def consume(self, token_type: str, value: str | None = None) -> Token:
        token = self.peek()
        if token.type != token_type:
            raise self.error(f"Expected {token_type}", token)
        if value is not None and token.value != value:
            raise self.error(f"Expected '{value}'", token)
        self.advance()
        return token

    def consume_any(self, token_types: set[str]) -> Token:
        token = self.peek()
        if token.type not in token_types:
            raise self.error(f"Expected one of {token_types}", token)
        self.advance()
        return token

    def match(self, token_type: str) -> bool:
        if self.check(token_type):
            self.advance()
            return True
        return False

    def check(self, token_type: str) -> bool:
        return self.peek().type == token_type

    def peek(self) -> Token:
        return self.tokens[self.position]

    def advance(self) -> Token:
        token = self.tokens[self.position]
        self.position = min(self.position + 1, len(self.tokens) - 1)
        return token

    def error(self, message: str, token: Token) -> ParseError:
        return ParseError(message, token.line, token.column)

    def _span(self, token: Token) -> ast_nodes.Span:
        return ast_nodes.Span(line=token.line, column=token.column)


def parse_source(source: str) -> ast_nodes.Module:
    """Parse helper for tests and tooling."""
    return Parser.from_source(source).parse_module()
