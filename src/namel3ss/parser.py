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

        if token.value == "remember":
            return self.parse_english_memory()
        if token.value == "use" and self.peek_offset(1).value == "model":
            return self.parse_english_model()
        if token.value == "use":
            return self.parse_use()
        if token.value == "define" and self.peek_offset(1).value == "condition":
            return self.parse_condition_macro()
        if token.value == "define" and self.peek_offset(1).value == "rulegroup":
            return self.parse_rulegroup()
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

    def parse_english_memory(self) -> ast_nodes.MemoryDecl:
        start = self.consume("KEYWORD", "remember")
        self.consume("KEYWORD", "conversation")
        self.consume("KEYWORD", "as")
        name = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.MemoryDecl(
            name=name.value or "",
            memory_type="conversation",
            span=self._span(start),
        )

    def parse_english_model(self) -> ast_nodes.ModelDecl:
        start = self.consume("KEYWORD", "use")
        self.consume("KEYWORD", "model")
        name = self.consume("STRING")
        self.consume("KEYWORD", "provided")
        self.consume("KEYWORD", "by")
        provider = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.ModelDecl(
            name=name.value or "",
            provider=provider.value,
            span=self._span(start),
        )

    def parse_condition_macro(self) -> ast_nodes.ConditionMacroDecl:
        start = self.consume("KEYWORD", "define")
        self.consume("KEYWORD", "condition")
        name_tok = self.consume("STRING")
        self.consume("KEYWORD", "as")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        if self.check("DEDENT"):
            raise self.error("Condition macro body cannot be empty.", self.peek())
        expr = self.parse_expression()
        self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.ConditionMacroDecl(name=name_tok.value or "", expr=expr, span=self._span(start))

    def parse_rulegroup(self) -> ast_nodes.RuleGroupDecl:
        start = self.consume("KEYWORD", "define")
        self.consume("KEYWORD", "rulegroup")
        name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        conditions: list[ast_nodes.RuleGroupCondition] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            self.consume("KEYWORD", "condition")
            cond_name_tok = self.consume("STRING")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            if self.check("DEDENT"):
                raise self.error(
                    f"Condition '{cond_name_tok.value}' in rulegroup '{name_tok.value}' must have a non-empty expression.",
                    cond_name_tok,
                )
            expr = self.parse_expression()
            self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            conditions.append(
                ast_nodes.RuleGroupCondition(
                    name=cond_name_tok.value or "",
                    expr=expr,
                    span=self._span(cond_name_tok),
                )
            )
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RuleGroupDecl(name=name_tok.value or "", conditions=conditions, span=self._span(start))

    def parse_app(self) -> ast_nodes.AppDecl:
        start = self.consume("KEYWORD", "app")
        name = self.consume("STRING")
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
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
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
        description = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
            if field_token.value == "model":
                self.advance()
                model_tok = self.consume("STRING")
                model_name = model_tok.value
                self.optional_newline()
            elif field_token.value == "input":
                self.advance()
                self.consume("KEYWORD", "from")
                source_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                input_source = source_tok.value
                self.optional_newline()
            elif field_token.value == "when":
                self.consume("KEYWORD", "when")
                self.consume("KEYWORD", "called")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                model_name, input_source, description = self.parse_ai_called_block(
                    model_name, input_source, description
                )
                self.consume("DEDENT")
                self.optional_newline()
            elif field_token.value == "describe":
                self.consume("KEYWORD", "describe")
                self.consume("KEYWORD", "task")
                self.consume("KEYWORD", "as")
                desc_token = self.consume("STRING")
                description = desc_token.value
                self.optional_newline()
            elif field_token.value == "description":
                self.advance()
                desc_token = self.consume("STRING")
                description = desc_token.value
                self.optional_newline()
            else:
                self.consume("KEYWORD")  # raise if unexpected
                raise self.error(
                    f"Unexpected field '{field_token.value}' in ai block", field_token
                )
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.AICallDecl(
            name=name.value or "",
            model_name=model_name,
            input_source=input_source,
            description=description,
            span=self._span(start),
        )

    def parse_ai_called_block(
        self,
        model_name: str | None,
        input_source: str | None,
        description: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            token = self.peek()
            if token.value == "use":
                self.consume("KEYWORD", "use")
                self.consume("KEYWORD", "model")
                model_tok = self.consume("STRING")
                model_name = model_tok.value
                self.optional_newline()
            elif token.value == "input":
                self.consume("KEYWORD", "input")
                self.consume("KEYWORD", "comes")
                self.consume("KEYWORD", "from")
                source_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                input_source = source_tok.value
                self.optional_newline()
            elif token.value == "describe":
                self.consume("KEYWORD", "describe")
                self.consume("KEYWORD", "task")
                self.consume("KEYWORD", "as")
                desc_token = self.consume("STRING")
                description = desc_token.value
                self.optional_newline()
            else:
                self.consume("KEYWORD")
                raise self.error(
                    f"Unexpected field '{token.value}' in ai block", token
                )
        return model_name, input_source, description

    def parse_agent(self) -> ast_nodes.AgentDecl:
        start = self.consume("KEYWORD", "agent")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        goal = None
        personality = None
        conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
        allowed_fields: Set[str] = {"goal", "personality"}
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
            if field_token.value in {"if", "when", "otherwise", "unless"}:
                conditional_branches = conditional_branches or []
                self.parse_conditional_into(conditional_branches)
                continue
            if field_token.value == "the":
                self.consume("KEYWORD", "the")
                gp_token = self.consume("KEYWORD")
                self.consume("KEYWORD", "is")
                value_token = self.consume("STRING")
                if gp_token.value == "goal":
                    goal = value_token.value
                elif gp_token.value == "personality":
                    personality = value_token.value
                else:
                    raise self.error(
                        f"Unexpected field '{gp_token.value}' in agent block",
                        gp_token,
                    )
                self.optional_newline()
                continue
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
            conditional_branches=conditional_branches,
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
                if self.match("NEWLINE"):
                    continue
                field_token = self.peek()
                if field_token.value == "this":
                    self.consume("KEYWORD", "this")
                    self.consume("KEYWORD", "flow")
                    self.consume("KEYWORD", "will")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        prefix = None
                        if self.peek().value in {"first", "then", "finally"}:
                            prefix = self.consume("KEYWORD").value
                        steps.append(self.parse_english_flow_step(prefix))
                    self.consume("DEDENT")
                    self.optional_newline()
                    continue

                if field_token.value in {"first", "then", "finally"}:
                    prefix = self.consume("KEYWORD").value
                    steps.append(self.parse_english_flow_step(prefix))
                    continue

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
            if self.match("NEWLINE"):
                continue
            token = self.peek()
            if token.value == "component":
                self.consume("KEYWORD", "component")
                components.append(self.parse_component())
            elif token.value == "show":
                components.append(self.parse_english_component())
            else:
                token = self.consume("KEYWORD")
                raise self.error(
                    f"Unexpected field '{token.value}' in section block", token
                )
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

    def parse_english_component(self) -> ast_nodes.ComponentDecl:
        show_token = self.consume("KEYWORD", "show")
        comp_type = self.consume_any({"KEYWORD", "IDENT"})
        if comp_type.value not in {"text", "form"}:
            raise self.error(
                f"Unsupported component type '{comp_type.value}'", comp_type
            )
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

    def parse_flow_step(self) -> ast_nodes.FlowStepDecl:
        step_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        kind = None
        target = None
        message = None
        conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
        goto_action: ast_nodes.FlowAction | None = None
        allowed_fields: Set[str] = {"kind", "target", "message"}
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
            if field_token.value in {"if", "when", "otherwise", "unless"}:
                conditional_branches = conditional_branches or []
                self.parse_conditional_into(conditional_branches)
                continue
            if field_token.value == "go":
                if goto_action is not None or kind is not None or target is not None:
                    raise self.error("Unexpected 'go to flow' after step fields", field_token)
                goto_action = self.parse_goto_action()
                self.optional_newline()
                continue
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
            elif field_token.value == "message":
                msg_token = self.consume_string_value(field_token, "message")
                message = msg_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        if conditional_branches:
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                kind="condition",
                target=step_name_token.value or "",
                conditional_branches=conditional_branches,
                span=self._span(step_name_token),
            )
        if goto_action:
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                kind="goto_flow",
                target=goto_action.target,
                span=self._span(step_name_token),
            )
        if kind is None:
            raise self.error("Missing 'kind' in step", step_name_token)
        if target is None:
            raise self.error("Missing 'target' in step", step_name_token)
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            kind=kind,
            target=target,
            message=message,
            span=self._span(step_name_token),
        )

    def parse_english_flow_step(self, prefix: str | None) -> ast_nodes.FlowStepDecl:
        if prefix:
            # Prefix already consumed; used only for readability.
            self.consume("KEYWORD", "step")
        else:
            self.consume("KEYWORD", "step")
        step_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        self.consume("KEYWORD", "do")
        kind_token = self.consume_any({"KEYWORD", "IDENT"})
        if kind_token.value not in {"ai", "agent", "tool"}:
            raise self.error(
                f"Unsupported step kind '{kind_token.value}'", kind_token
            )
        target_token = self.consume("STRING")
        message = None
        if kind_token.value == "tool" and self.peek().value == "with":
            self.consume("KEYWORD", "with")
            self.consume("KEYWORD", "message")
            if self.check("COLON"):
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                msg_token = self.consume("STRING")
                message = msg_token.value
                self.optional_newline()
                self.consume("DEDENT")
            else:
                msg_token = self.consume("STRING")
                message = msg_token.value
        while self.match("NEWLINE"):
            continue
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            kind=kind_token.value,
            target=target_token.value or "",
            span=self._span(step_name_token),
            message=message,
        )

    # --------- Condition parsing and expressions ---------
    def parse_conditional_into(self, branches: list[ast_nodes.ConditionalBranch]) -> None:
        token = self.peek()
        if token.value == "unless":
            self.consume("KEYWORD", "unless")
            if self.check("COLON"):
                raise self.error("Expected a condition expression after 'unless'", token)
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_do_actions()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond, actions=actions, label="unless", binding=binding, span=self._span(token)
                )
            )
            return
        if token.value == "when":
            self.consume("KEYWORD", "when")
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_do_actions()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond, actions=actions, label="when", binding=binding, span=self._span(token)
                )
            )
            return
        if token.value == "if":
            self.consume("KEYWORD", "if")
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_do_actions()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond, actions=actions, label="if", binding=binding, span=self._span(token)
                )
            )
            return
        if token.value == "otherwise":
            if not branches:
                raise self.error("Found 'otherwise' without preceding if/when", token)
            if branches and branches[-1].label == "unless":
                raise self.error("'otherwise' cannot follow an 'unless' block.", token)
            self.consume("KEYWORD", "otherwise")
            if self.peek().value == "if":
                self.consume("KEYWORD", "if")
                cond = self.parse_condition_expr()
                binding = self._parse_optional_binding()
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                actions = self.parse_do_actions()
                self.consume("DEDENT")
                self.optional_newline()
                branches.append(
                    ast_nodes.ConditionalBranch(
                        condition=cond,
                        actions=actions,
                        label="otherwise-if",
                        binding=binding,
                        span=self._span(token),
                    )
                )
            else:
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                actions = self.parse_do_actions()
                self.consume("DEDENT")
                self.optional_newline()
                branches.append(
                    ast_nodes.ConditionalBranch(
                        condition=None, actions=actions, label="otherwise", span=self._span(token)
                    )
                )
            return
        raise self.error(f"Unexpected conditional '{token.value}'", token)

    def parse_condition_expr(self) -> ast_nodes.Expr:
        # Detect pattern expression: <identifier> matches { ... }
        token = self.peek()
        next_token = self.peek_offset(1)
        if token.type in {"IDENT", "KEYWORD"} and next_token and next_token.value == "matches":
            return self.parse_pattern_expr()
        return self.parse_expression()

    def parse_pattern_expr(self) -> ast_nodes.PatternExpr:
        subject_tok = self.consume_any({"IDENT", "KEYWORD"})
        subject = ast_nodes.Identifier(name=subject_tok.value or "", span=self._span(subject_tok))
        self.consume("KEYWORD", "matches")
        if not self.match("LBRACE"):
            raise self.error("Expected '{' to start pattern.", self.peek())
        pairs: list[ast_nodes.PatternPair] = []
        while not self.check("RBRACE"):
            key_tok = self.consume_any({"IDENT"})
            if not key_tok.value or not key_tok.value.isidentifier():
                raise self.error("Pattern keys must be identifiers.", key_tok)
            self.consume("COLON")
            if self.check("RBRACE"):
                raise self.error("Expected a value after ':' in pattern.", self.peek())
            if self.check("LBRACE"):
                raise self.error("Nested patterns are not supported in Phase 5.", self.peek())
            value_expr = self.parse_expression()
            if isinstance(value_expr, ast_nodes.PatternExpr):
                raise self.error("Nested patterns are not supported in Phase 5.", key_tok)
            pairs.append(ast_nodes.PatternPair(key=key_tok.value, value=value_expr))
            if self.match("COMMA"):
                continue
            break
        if not self.match("RBRACE"):
            raise self.error("Expected '}' to close pattern.", self.peek())
        self.optional_newline()
        return ast_nodes.PatternExpr(subject=subject, pairs=pairs, span=self._span(subject_tok))

    def _parse_optional_binding(self) -> str | None:
        if self.peek().value != "as":
            return None
        self.consume("KEYWORD", "as")
        if self.check("COLON"):
            raise self.error("Expected a variable name after 'as' in conditional binding.", self.peek())
        name_tok = self.consume("IDENT")
        if not name_tok.value or not name_tok.value.isidentifier():
            raise self.error("Binding name after 'as' must be a valid identifier.", name_tok)
        if self.peek().value == "as":
            raise self.error("Multiple 'as' bindings are not allowed in a single condition.", self.peek())
        return name_tok.value

    def parse_do_actions(self) -> list[ast_nodes.FlowAction]:
        actions: list[ast_nodes.FlowAction] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "go":
                actions.append(self.parse_goto_action())
                self.optional_newline()
                continue
            do_token = self.consume("KEYWORD", "do")
            kind_tok = self.consume_any({"KEYWORD", "IDENT"})
            if kind_tok.value not in {"ai", "agent", "tool"}:
                raise self.error(f"Unsupported action kind '{kind_tok.value}'", kind_tok)
            target_tok = self.consume("STRING")
            message = None
            if kind_tok.value == "tool" and self.peek().value == "with":
                self.consume("KEYWORD", "with")
                self.consume("KEYWORD", "message")
                if self.check("COLON"):
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    msg_tok = self.consume("STRING")
                    message = msg_tok.value
                    self.optional_newline()
                    self.consume("DEDENT")
                else:
                    msg_tok = self.consume("STRING")
                    message = msg_tok.value
            actions.append(
                ast_nodes.FlowAction(
                    kind=kind_tok.value or "",
                    target=target_tok.value or "",
                    message=message,
                    span=self._span(do_token),
                )
            )
            self.optional_newline()
        return actions

    def parse_goto_action(self) -> ast_nodes.FlowAction:
        go_tok = self.consume("KEYWORD", "go")
        self.consume("KEYWORD", "to")
        self.consume("KEYWORD", "flow")
        if not self.check("STRING"):
            raise self.error("Expected a string literal flow name after 'go to flow'.", self.peek())
        target_tok = self.consume("STRING")
        return ast_nodes.FlowAction(kind="goto_flow", target=target_tok.value or "", span=self._span(go_tok))

    def parse_expression(self) -> ast_nodes.Expr:
        return self.parse_or()

    def parse_or(self) -> ast_nodes.Expr:
        expr = self.parse_and()
        while self.match_value("KEYWORD", "or"):
            op = "or"
            right = self.parse_and()
            expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
        return expr

    def parse_and(self) -> ast_nodes.Expr:
        expr = self.parse_not()
        while self.match_value("KEYWORD", "and"):
            op = "and"
            right = self.parse_not()
            expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
        return expr

    def parse_not(self) -> ast_nodes.Expr:
        if self.match_value("KEYWORD", "not"):
            operand = self.parse_not()
            return ast_nodes.UnaryOp(op="not", operand=operand)
        return self.parse_comparison()

    def parse_comparison(self) -> ast_nodes.Expr:
        expr = self.parse_primary()
        token = self.peek()
        if token.type == "KEYWORD" and token.value == "is":
            self.consume("KEYWORD", "is")
            op = "is"
            if self.match_value("KEYWORD", "not"):
                op = "is not"
            right = self.parse_primary()
            expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
        elif token.type == "OP" and token.value in {"<", ">", "<=", ">="}:
            op_tok = self.consume("OP")
            right = self.parse_primary()
            expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
        return expr

    def parse_primary(self) -> ast_nodes.Expr:
        token = self.peek()
        if token.type == "STRING":
            tok = self.consume("STRING")
            return ast_nodes.Literal(value=tok.value, span=self._span(tok))
        if token.type == "NUMBER":
            tok = self.consume("NUMBER")
            try:
                num_val: object
                if "." in (tok.value or ""):
                    num_val = float(tok.value)
                else:
                    num_val = int(tok.value)
            except Exception:
                num_val = tok.value
            return ast_nodes.Literal(value=num_val, span=self._span(tok))
        if token.type in {"IDENT", "KEYWORD"}:
            tok = self.consume(token.type)
            if tok.value in {"true", "false"}:
                return ast_nodes.Literal(value=tok.value == "true", span=self._span(tok))
            return ast_nodes.Identifier(name=tok.value or "", span=self._span(tok))
        raise self.error("Expected expression", token)

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

    def match_value(self, token_type: str, value: str) -> bool:
        if self.check(token_type) and self.peek().value == value:
            self.advance()
            return True
        return False

    def check(self, token_type: str) -> bool:
        return self.peek().type == token_type

    def peek(self) -> Token:
        return self.tokens[self.position]

    def peek_offset(self, offset: int) -> Token:
        idx = min(self.position + offset, len(self.tokens) - 1)
        return self.tokens[idx]

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
