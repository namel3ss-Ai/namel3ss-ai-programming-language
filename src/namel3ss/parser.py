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
        if token.value == "from":
            return self.parse_from_import()
        if token.value == "define" and self.peek_offset(1).value == "condition":
            return self.parse_condition_macro()
        if token.value == "define" and self.peek_offset(1).value == "rulegroup":
            return self.parse_rulegroup()
        if token.value == "define" and self.peek_offset(1).value == "helper":
            return self.parse_helper()
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
        if token.value == "settings":
            return self.parse_settings()
        raise self.error(f"Unexpected declaration '{token.value}'", token)

    def parse_use(self) -> ast_nodes.UseImport:
        start = self.consume("KEYWORD", "use")
        if self.peek().value == "module":
            self.consume("KEYWORD", "module")
            mod = self.consume("STRING")
            self.optional_newline()
            return ast_nodes.ModuleUse(module=mod.value or "", span=self._span(start))
        path = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.UseImport(path=path.value or "", span=self._span(start))

    def parse_from_import(self) -> ast_nodes.ImportDecl:
        start = self.consume("KEYWORD", "from")
        module_tok = self.consume("STRING")
        self.consume("KEYWORD", "use")
        kind_tok = self.consume_any({"IDENT", "KEYWORD"})
        if kind_tok.value not in {"helper", "flow", "agent"}:
            raise self.error("Expected helper/flow/agent after 'use'", kind_tok)
        name_tok = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.ImportDecl(module=module_tok.value or "", kind=kind_tok.value or "", name=name_tok.value or "", span=self._span(start))

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

    def parse_helper(self) -> ast_nodes.HelperDecl:
        start = self.consume("KEYWORD", "define")
        self.consume("KEYWORD", "helper")
        name_tok = self.consume("STRING")
        identifier = name_tok.value or ""
        params: list[str] = []
        return_name: str | None = None
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        # Optional headers inside helper body
        while True:
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "takes":
                self.consume("KEYWORD", "takes")
                while True:
                    param_tok = self.consume_any({"IDENT", "KEYWORD"})
                    params.append(param_tok.value or "")
                    if self.match("COMMA"):
                        continue
                    break
                self.optional_newline()
                continue
            if tok.value == "returns":
                self.consume("KEYWORD", "returns")
                ret_tok = self.consume_any({"IDENT", "KEYWORD"})
                return_name = ret_tok.value
                self.optional_newline()
                continue
            break
        body = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.HelperDecl(
            name=name_tok.value or "",
            identifier=identifier,
            params=params,
            return_name=return_name,
            body=body,
            span=self._span(start),
        )

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

    def parse_settings(self) -> ast_nodes.SettingsDecl:
        start = self.consume("KEYWORD", "settings")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        envs: list[ast_nodes.EnvConfig] = []
        seen_envs: set[str] = set()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            self.consume("KEYWORD", "env")
            env_name_tok = self.consume("STRING")
            env_name = env_name_tok.value or ""
            if env_name in seen_envs:
                raise self.error("N3-6200: duplicate env definition", env_name_tok)
            seen_envs.add(env_name)
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            entries: list[ast_nodes.SettingEntry] = []
            seen_keys: set[str] = set()
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                if key_tok.value in seen_keys:
                    raise self.error("N3-6201: duplicate key inside env", key_tok)
                seen_keys.add(key_tok.value or "")
                if not self.match_value("KEYWORD", "be"):
                    raise self.error("Expected 'be' in env entry", self.peek())
                expr = self.parse_expression()
                entries.append(ast_nodes.SettingEntry(key=key_tok.value or "", expr=expr))
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            envs.append(ast_nodes.EnvConfig(name=env_name, entries=entries, span=self._span(env_name_tok)))
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.SettingsDecl(envs=envs, span=self._span(start))

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
        (
            kind,
            target,
            message,
            statements,
            conditional_branches,
            goto_action,
        ) = self._parse_step_body(allow_fields=True)
        self.consume("DEDENT")
        self.optional_newline()
        return self._build_flow_step_decl(
            step_name_token,
            kind,
            target,
            message,
            statements,
            conditional_branches,
            goto_action,
        )

    def parse_english_flow_step(self, prefix: str | None) -> ast_nodes.FlowStepDecl:
        if prefix:
            self.consume("KEYWORD", "step")
        else:
            self.consume("KEYWORD", "step")
        step_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        (
            kind,
            target,
            message,
            statements,
            conditional_branches,
            goto_action,
        ) = self._parse_step_body(allow_fields=False)
        self.consume("DEDENT")
        self.optional_newline()
        return self._build_flow_step_decl(
            step_name_token,
            kind,
            target,
            message,
            statements,
            conditional_branches,
            goto_action,
        )

    def _parse_step_body(
        self, allow_fields: bool = True
    ) -> tuple[str | None, str | None, str | None, list[ast_nodes.Statement | ast_nodes.FlowAction], list[ast_nodes.ConditionalBranch] | None, ast_nodes.FlowAction | None]:
        kind = None
        target = None
        message = None
        statements: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
        conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
        goto_action: ast_nodes.FlowAction | None = None
        allowed_fields: Set[str] = {"kind", "target", "message"} if allow_fields else set()
        script_mode = False
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            token = self.peek()
            if token.value == "go" and allow_fields and not script_mode and not statements and conditional_branches is None:
                goto_action = self.parse_goto_action()
                self.optional_newline()
                continue
            if token.value in {"let", "set", "do", "repeat", "match", "retry", "ask", "form", "log", "note", "checkpoint", "return"} or (token.value == "go" and script_mode):
                if token.value == "match":
                    script_mode = True
                    statements.append(self.parse_match_statement())
                    continue
                if token.value == "retry":
                    script_mode = True
                    statements.append(self.parse_retry_statement())
                    continue
                if token.value in {"ask", "form", "log", "note", "checkpoint"}:
                    script_mode = True
                    statements.append(self.parse_statement_or_action())
                    continue
                if token.value == "return":
                    script_mode = True
                    statements.append(self.parse_statement_or_action())
                    continue
                script_mode = True
                statements.append(self.parse_statement_or_action())
                continue
            if token.value in {"if", "when", "otherwise", "unless"}:
                if script_mode or statements:
                    script_mode = True
                    statements.append(self.parse_if_statement())
                else:
                    conditional_branches = conditional_branches or []
                    self.parse_conditional_into(conditional_branches)
                continue
            if not allow_fields:
                raise self.error(
                    f"Unexpected field '{token.value}' in step block",
                    token,
                )
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
        return kind, target, message, statements, conditional_branches, goto_action

    def _build_flow_step_decl(
        self,
        step_name_token,
        kind,
        target,
        message,
        statements,
        conditional_branches,
        goto_action,
    ) -> ast_nodes.FlowStepDecl:
        if statements:
            only_actions = all(isinstance(stmt, ast_nodes.FlowAction) for stmt in statements)
            if only_actions and len(statements) == 1 and not conditional_branches:
                action = statements[0]
                return ast_nodes.FlowStepDecl(
                    name=step_name_token.value or "",
                    kind=action.kind,
                    target=action.target,
                    message=action.message,
                    statements=[],
                    span=self._span(step_name_token),
                )
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                kind="script",
                target=target or "",
                message=message,
                statements=statements,
                span=self._span(step_name_token),
            )
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

    def parse_statement_or_action(self) -> ast_nodes.Statement | ast_nodes.FlowAction:
        token = self.peek()
        if token.value == "let":
            return self.parse_let_statement()
        if token.value == "set":
            return self.parse_set_statement()
        if token.value == "repeat":
            return self.parse_repeat_statement()
        if token.value == "retry":
            return self.parse_retry_statement()
        if token.value == "match":
            return self.parse_match_statement()
        if token.value == "ask":
            return self.parse_ask_statement()
        if token.value == "form":
            return self.parse_form_statement()
        if token.value == "log":
            return self.parse_log_statement()
        if token.value == "note":
            return self.parse_note_statement()
        if token.value == "checkpoint":
            return self.parse_checkpoint_statement()
        if token.value == "return":
            return self.parse_return_statement()
        if token.value == "do":
            return self._parse_do_action()
        if token.value == "go":
            return self.parse_goto_action()
        if token.value in {"if", "when", "otherwise", "unless"}:
            return self.parse_if_statement()
        raise self.error(f"Unexpected statement '{token.value}'", token)

    def parse_statement_block(self) -> list[ast_nodes.Statement | ast_nodes.FlowAction]:
        statements: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            statements.append(self.parse_statement_or_action())
        return statements

    def parse_if_statement(self) -> ast_nodes.IfStatement:
        token = self.peek()
        if token.value not in {"if", "when", "unless"}:
            if token.value == "otherwise":
                raise self.error("Found 'otherwise' without preceding if/when", token)
            raise self.error(f"Unexpected conditional '{token.value}'", token)
        branches: list[ast_nodes.ConditionalBranch] = []

        def parse_branch(label: str, start_token) -> None:
            cond = self.parse_condition_expr()
            binding = self._parse_optional_binding()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond,
                    actions=actions,
                    label=label,
                    binding=binding,
                    span=self._span(start_token),
                )
            )

        start_tok = self.consume("KEYWORD")
        parse_branch(start_tok.value, start_tok)
        while self.peek().value == "otherwise":
            other_tok = self.consume("KEYWORD", "otherwise")
            label = "otherwise"
            cond = None
            binding = None
            if self.peek().value == "if":
                self.consume("KEYWORD", "if")
                cond = self.parse_condition_expr()
                binding = self._parse_optional_binding()
                label = "otherwise-if"
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(
                ast_nodes.ConditionalBranch(
                    condition=cond,
                    actions=actions,
                    label=label,
                    binding=binding,
                    span=self._span(other_tok),
                )
            )
        return ast_nodes.IfStatement(branches=branches, span=self._span(start_tok))

    def parse_match_statement(self) -> ast_nodes.MatchStatement:
        start_tok = self.consume("KEYWORD", "match")
        target_expr = self.parse_expression()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        branches: list[ast_nodes.MatchBranch] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "otherwise":
                self.consume("KEYWORD", "otherwise")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                actions = self.parse_statement_block()
                self.consume("DEDENT")
                self.optional_newline()
                branches.append(ast_nodes.MatchBranch(pattern=None, actions=actions, label="otherwise"))
                continue
            self.consume("KEYWORD", "when")
            pat_token = self.peek()
            pattern: ast_nodes.Expr | ast_nodes.SuccessPattern | ast_nodes.ErrorPattern | None
            binding: str | None = None
            if pat_token.value == "success":
                self.consume("KEYWORD", "success")
                if self.peek().value == "as":
                    self.consume("KEYWORD", "as")
                    bind_tok = self.consume_any({"IDENT", "KEYWORD"})
                    binding = bind_tok.value
                pattern = ast_nodes.SuccessPattern(binding=binding)
            elif pat_token.value == "error":
                self.consume("KEYWORD", "error")
                if self.peek().value == "as":
                    self.consume("KEYWORD", "as")
                    bind_tok = self.consume_any({"IDENT", "KEYWORD"})
                    binding = bind_tok.value
                pattern = ast_nodes.ErrorPattern(binding=binding)
            else:
                pattern = self.parse_expression()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(ast_nodes.MatchBranch(pattern=pattern, binding=binding, actions=actions))
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.MatchStatement(target=target_expr, branches=branches, span=self._span(start_tok))

    def parse_let_statement(self) -> ast_nodes.LetStatement:
        start = self.consume("KEYWORD", "let")
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        uses_equals = False
        if self.match_value("KEYWORD", "be"):
            expr = self.parse_expression()
        elif self.match_value("OP", "="):
            uses_equals = True
            expr = self.parse_expression()
        else:
            raise self.error("Expected 'be' or '=' after variable name", self.peek())
        return ast_nodes.LetStatement(name=name_tok.value or "", expr=expr, uses_equals=uses_equals, span=self._span(start))

    def parse_set_statement(self) -> ast_nodes.SetStatement:
        start = self.consume("KEYWORD", "set")
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        if self.match_value("KEYWORD", "to") or self.match_value("OP", "="):
            expr = self.parse_expression()
        else:
            raise self.error("Expected 'to' after variable name in set statement", self.peek())
        return ast_nodes.SetStatement(name=name_tok.value or "", expr=expr, span=self._span(start))

    def parse_repeat_statement(self) -> ast_nodes.Statement:
        repeat_tok = self.consume("KEYWORD", "repeat")
        if self.peek().value == "for":
            self.consume("KEYWORD", "for")
            self.consume("KEYWORD", "each")
            var_tok = self.consume("IDENT")
            self.consume("KEYWORD", "in")
            iterable_expr = self.parse_expression()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            body = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            return ast_nodes.ForEachLoop(var_name=var_tok.value or "item", iterable=iterable_expr, body=body, span=self._span(repeat_tok))
        if self.peek().value == "up":
            self.consume("KEYWORD", "up")
            self.consume("KEYWORD", "to")
            count_expr = self.parse_expression()
            self.consume("KEYWORD", "times")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            body = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            return ast_nodes.RepeatUpToLoop(count=count_expr, body=body, span=self._span(repeat_tok))
        raise self.error("Expected 'for each' or 'up to' after repeat", self.peek())

    def parse_retry_statement(self) -> ast_nodes.RetryStatement:
        retry_tok = self.consume("KEYWORD", "retry")
        self.consume("KEYWORD", "up")
        self.consume("KEYWORD", "to")
        count_expr = self.parse_expression()
        if self.peek().value == "times":
            self.consume("KEYWORD", "times")
        with_backoff = False
        if self.peek().value == "with":
            self.consume("KEYWORD", "with")
            self.consume("KEYWORD", "backoff")
            with_backoff = True
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        body = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RetryStatement(count=count_expr, with_backoff=with_backoff, body=body, span=self._span(retry_tok))

    def _parse_validation_block(self, error_code: str = "N3-5001") -> ast_nodes.InputValidation:
        validation = ast_nodes.InputValidation()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "type":
                self.consume("KEYWORD", "type")
                self.consume("KEYWORD", "is")
                t_tok = self.consume_any({"IDENT", "KEYWORD"})
                validation.field_type = t_tok.value
                self.optional_newline()
                continue
            if tok.value == "must":
                self.consume("KEYWORD", "must")
                self.consume("KEYWORD", "be")
                if self.peek().value == "at":
                    self.consume("KEYWORD", "at")
                next_tok = self.peek()
                if next_tok.value == "least":
                    self.consume("KEYWORD", "least")
                    validation.min_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if next_tok.value == "most":
                    self.consume("KEYWORD", "most")
                    validation.max_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                raise self.error(f"{error_code}: invalid validation rule for user input", next_tok)
            raise self.error(f"{error_code}: invalid validation rule for user input", tok)
        return validation

    def parse_ask_statement(self) -> ast_nodes.AskUserStatement:
        start_tok = self.consume("KEYWORD", "ask")
        self.consume("KEYWORD", "user")
        self.consume("KEYWORD", "for")
        if not self.check("STRING"):
            raise self.error("N3-5000: ask user label must be a string literal", self.peek())
        label_tok = self.consume("STRING")
        self.consume("KEYWORD", "as")
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        validation: ast_nodes.InputValidation | None = None
        if self.match("NEWLINE"):
            if self.match("INDENT"):
                validation = self._parse_validation_block()
                self.consume("DEDENT")
            self.optional_newline()
        else:
            self.optional_newline()
        return ast_nodes.AskUserStatement(label=label_tok.value or "", var_name=name_tok.value or "", validation=validation, span=self._span(start_tok))

    def parse_form_statement(self) -> ast_nodes.FormStatement:
        start_tok = self.consume("KEYWORD", "form")
        if not self.check("STRING"):
            raise self.error("N3-5010: form label must be a string literal", self.peek())
        label_tok = self.consume("STRING")
        self.consume("KEYWORD", "as")
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        fields: list[ast_nodes.FormField] = []
        seen_names: set[str] = set()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            self.consume("KEYWORD", "field")
            if not self.check("STRING"):
                raise self.error("N3-5010: form field label must be a string literal", self.peek())
            field_label_tok = self.consume("STRING")
            self.consume("KEYWORD", "as")
            field_name_tok = self.consume_any({"IDENT", "KEYWORD"})
            validation: ast_nodes.InputValidation | None = None
            if self.match("NEWLINE"):
                if self.match("INDENT"):
                    validation = self._parse_validation_block(error_code="N3-5012")
                    self.consume("DEDENT")
                self.optional_newline()
            else:
                self.optional_newline()
            if field_name_tok.value in seen_names:
                raise self.error("N3-5011: duplicate field identifier in form", field_name_tok)
            seen_names.add(field_name_tok.value or "")
            fields.append(
                ast_nodes.FormField(
                    label=field_label_tok.value or "",
                    name=field_name_tok.value or "",
                    validation=validation,
                )
            )
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.FormStatement(label=label_tok.value or "", name=name_tok.value or "", fields=fields, span=self._span(start_tok))

    def parse_log_statement(self) -> ast_nodes.LogStatement:
        start_tok = self.consume("KEYWORD", "log")
        level_tok = self.consume_any({"IDENT", "KEYWORD"})
        if level_tok.value not in {"info", "warning", "error"}:
            raise self.error("N3-5100: invalid log level", level_tok)
        if not self.check("STRING"):
            raise self.error("N3-5101: log message must be a string literal", self.peek())
        msg_tok = self.consume("STRING")
        metadata_expr: ast_nodes.Expr | None = None
        if self.peek().value == "with":
            self.consume("KEYWORD", "with")
            metadata_expr = self.parse_expression()
        self.optional_newline()
        return ast_nodes.LogStatement(level=level_tok.value or "info", message=msg_tok.value or "", metadata=metadata_expr, span=self._span(start_tok))

    def parse_note_statement(self) -> ast_nodes.NoteStatement:
        start_tok = self.consume("KEYWORD", "note")
        if not self.check("STRING"):
            raise self.error("Note message must be a string literal", self.peek())
        msg_tok = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.NoteStatement(message=msg_tok.value or "", span=self._span(start_tok))

    def parse_checkpoint_statement(self) -> ast_nodes.CheckpointStatement:
        start_tok = self.consume("KEYWORD", "checkpoint")
        if not self.check("STRING"):
            raise self.error("N3-5110: checkpoint label must be a string literal", self.peek())
        label_tok = self.consume("STRING")
        self.optional_newline()
        return ast_nodes.CheckpointStatement(label=label_tok.value or "", span=self._span(start_tok))

    def parse_return_statement(self) -> ast_nodes.ReturnStatement:
        start_tok = self.consume("KEYWORD", "return")
        expr = None
        if not self.check("NEWLINE") and not self.check("DEDENT") and not self.check("EOF"):
            expr = self.parse_expression()
        self.optional_newline()
        return ast_nodes.ReturnStatement(expr=expr, span=self._span(start_tok))

    def _parse_do_action(self) -> ast_nodes.FlowAction:
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
        return ast_nodes.FlowAction(
            kind=kind_tok.value or "",
            target=target_tok.value or "",
            message=message,
            span=self._span(do_token),
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

    def parse_do_actions(self) -> list[ast_nodes.FlowAction | ast_nodes.Statement]:
        actions: list[ast_nodes.FlowAction | ast_nodes.Statement] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "go":
                actions.append(self.parse_goto_action())
                self.optional_newline()
                continue
            if self.peek().value in {"let", "set", "if", "when", "otherwise", "unless", "match", "retry", "ask", "form", "log", "note", "checkpoint", "return"}:
                actions.append(self.parse_statement_or_action())
                continue
            actions.append(self._parse_do_action())
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
            right = self.parse_and()
            expr = ast_nodes.BinaryOp(left=expr, op="or", right=right)
        return expr

    def parse_and(self) -> ast_nodes.Expr:
        expr = self.parse_not()
        while self.match_value("KEYWORD", "and"):
            right = self.parse_not()
            expr = ast_nodes.BinaryOp(left=expr, op="and", right=right)
        return expr

    def parse_not(self) -> ast_nodes.Expr:
        if self.match_value("KEYWORD", "not"):
            operand = self.parse_not()
            return ast_nodes.UnaryOp(op="not", operand=operand)
        return self.parse_comparison()

    def parse_comparison(self) -> ast_nodes.Expr:
        expr = self.parse_add()
        while True:
            token = self.peek()
            if token.type == "OP" and token.value in {"==", "!=", "<", ">", "<=", ">="}:
                op_tok = self.consume("OP")
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
                continue
            if token.type == "OP" and token.value == "=":
                self.consume("OP", "=")
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op="==", right=right)
                continue
            if token.type == "KEYWORD" and token.value == "is":
                self.consume("KEYWORD", "is")
                op = "=="
                if self.match_value("KEYWORD", "not"):
                    op = "!="
                    if self.peek().value == "equal":
                        self.consume("KEYWORD", "equal")
                        if self.peek().value == "to":
                            self.consume("KEYWORD", "to")
                    right = self.parse_add()
                    expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                    continue
                if self.match_value("KEYWORD", "greater"):
                    if self.peek().value == "than":
                        self.consume("KEYWORD", "than")
                    op = ">"
                    right = self.parse_add()
                    expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                    continue
                if self.match_value("KEYWORD", "less"):
                    if self.peek().value == "than":
                        self.consume("KEYWORD", "than")
                    op = "<"
                    right = self.parse_add()
                    expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                    continue
                if self.match_value("KEYWORD", "at"):
                    if self.match_value("KEYWORD", "least"):
                        op = ">="
                    elif self.match_value("KEYWORD", "most"):
                        op = "<="
                    else:
                        raise self.error("Expected 'least' or 'most' after 'is at'", self.peek())
                    right = self.parse_add()
                    expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                    continue
                if self.peek().value == "equal":
                    self.consume("KEYWORD", "equal")
                    if self.peek().value == "to":
                        self.consume("KEYWORD", "to")
                right = self.parse_add()
                expr = ast_nodes.BinaryOp(left=expr, op=op, right=right)
                continue
            break
        return expr

    def parse_add(self) -> ast_nodes.Expr:
        expr = self.parse_mul()
        while True:
            token = self.peek()
            if token.type == "OP" and token.value in {"+", "-"}:
                op_tok = self.consume("OP")
                right = self.parse_mul()
                expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
                continue
            if token.type == "KEYWORD" and token.value in {"plus", "minus"}:
                op_val = "+" if token.value == "plus" else "-"
                self.consume("KEYWORD")
                right = self.parse_mul()
                expr = ast_nodes.BinaryOp(left=expr, op=op_val, right=right)
                continue
            break
        return expr

    def parse_mul(self) -> ast_nodes.Expr:
        expr = self.parse_unary()
        while True:
            token = self.peek()
            if token.type == "OP" and token.value in {"*", "/", "%"}:
                op_tok = self.consume("OP")
                right = self.parse_unary()
                expr = ast_nodes.BinaryOp(left=expr, op=op_tok.value, right=right)
                continue
            if token.type == "KEYWORD" and token.value in {"times", "divided"}:
                next_tok = self.peek_offset(1)
                if token.value == "times" and next_tok and next_tok.type in {"COLON", "DEDENT", "NEWLINE", "EOF"}:
                    break
                if token.value == "times" and next_tok and next_tok.value in {"with", "backoff"}:
                    break
                op_val = "*"
                if token.value == "divided":
                    op_val = "/"
                    self.consume("KEYWORD", "divided")
                    if self.peek().value == "by":
                        self.consume("KEYWORD", "by")
                else:
                    self.consume("KEYWORD", "times")
                right = self.parse_unary()
                expr = ast_nodes.BinaryOp(left=expr, op=op_val, right=right)
                continue
            break
        return expr

    def parse_unary(self) -> ast_nodes.Expr:
        if self.match_value("OP", "+"):
            return ast_nodes.UnaryOp(op="+", operand=self.parse_unary())
        if self.match_value("OP", "-"):
            return ast_nodes.UnaryOp(op="-", operand=self.parse_unary())
        if self.match_value("KEYWORD", "plus"):
            return ast_nodes.UnaryOp(op="+", operand=self.parse_unary())
        if self.match_value("KEYWORD", "minus"):
            return ast_nodes.UnaryOp(op="-", operand=self.parse_unary())
        token = self.peek()
        builtin_call_names = {
            "length",
            "first",
            "last",
            "sorted",
            "reverse",
            "unique",
            "sum",
            "trim",
            "lowercase",
            "uppercase",
            "replace",
            "split",
            "join",
            "slugify",
            "minimum",
            "maximum",
            "mean",
            "min",
            "max",
            "average",
            "round",
            "abs",
            "current_timestamp",
            "current_date",
            "random_uuid",
            "filter",
            "map",
            "any",
            "all",
        }
        if token.type in {"IDENT", "KEYWORD"} and self.peek_offset(1).type == "LPAREN" and token.value in builtin_call_names:
            return self.parse_builtin_call()
        if token.type == "KEYWORD" and token.value in {"any"}:
            return self.parse_english_any()
        if token.type == "KEYWORD" and token.value == "all":
            return self.parse_english_all()
        if token.type == "KEYWORD" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "round", "absolute", "current", "random"}:
            return self.parse_english_builtin()
        return self.parse_primary()

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
            expr: ast_nodes.Expr = ast_nodes.Literal(value=num_val, span=self._span(tok))
            return self.parse_postfix(expr)
        if token.type == "LBRACKET":
            return self.parse_postfix(self.parse_list_literal())
        if token.type == "LBRACE":
            return self.parse_postfix(self.parse_record_literal())
        if token.type in {"IDENT", "KEYWORD"}:
            # Function-style builtins
            if self.peek_offset(1).type == "LPAREN" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "filter", "map", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "min", "max", "average", "round", "abs", "current_timestamp", "current_date", "random_uuid", "any", "all"}:
                return self.parse_builtin_call()
            if self.peek_offset(1).type == "LPAREN":
                return self.parse_postfix(self.parse_function_call())
            tok = self.consume(token.type)
            if tok.value in {"true", "false"}:
                expr = ast_nodes.Literal(value=tok.value == "true", span=self._span(tok))
            else:
                value = tok.value or ""
                if "." in value:
                    parts = value.split(".")
                    expr = ast_nodes.Identifier(name=parts[0], span=self._span(tok))
                    for part in parts[1:]:
                        expr = ast_nodes.RecordFieldAccess(target=expr, field=part)
                else:
                    expr = ast_nodes.Identifier(name=value, span=self._span(tok))
            return self.parse_postfix(expr)
        if token.type == "LPAREN":
            self.consume("LPAREN")
            inner = self.parse_expression()
            if not self.match("RPAREN"):
                raise self.error("Expected ')' to close expression", self.peek())
            return self.parse_postfix(inner)
        raise self.error("Expected expression", token)

    def parse_postfix(self, expr: ast_nodes.Expr) -> ast_nodes.Expr:
        while True:
            if self.match("LBRACKET"):
                start_expr = None
                end_expr = None
                if self.match("COLON"):
                    if not self.check("RBRACKET"):
                        end_expr = self.parse_expression()
                else:
                    start_expr = self.parse_expression()
                    if self.match("COLON"):
                        if not self.check("RBRACKET"):
                            end_expr = self.parse_expression()
                    else:
                        if not self.match("RBRACKET"):
                            raise self.error("Expected ']' after index", self.peek())
                        expr = ast_nodes.IndexExpr(seq=expr, index=start_expr)
                        continue
                if not self.match("RBRACKET"):
                    raise self.error("Expected ']' to close slice", self.peek())
                expr = ast_nodes.SliceExpr(seq=expr, start=start_expr, end=end_expr)
                continue
            break
        return expr

    def parse_list_literal(self) -> ast_nodes.ListLiteral:
        self.consume("LBRACKET")
        items: list[ast_nodes.Expr] = []
        if self.check("RBRACKET"):
            self.consume("RBRACKET")
            return ast_nodes.ListLiteral(items=items)
        while True:
            items.append(self.parse_expression())
            if self.match("COMMA"):
                continue
            break
        if not self.match("RBRACKET"):
            raise self.error("Expected ']' after list literal", self.peek())
        return ast_nodes.ListLiteral(items=items)

    def parse_record_literal(self) -> ast_nodes.RecordLiteral:
        self.consume("LBRACE")
        fields: list[ast_nodes.RecordField] = []
        if self.check("RBRACE"):
            self.consume("RBRACE")
            return ast_nodes.RecordLiteral(fields=fields)
        while not self.check("RBRACE"):
            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
            self.consume("COLON")
            value_expr = self.parse_expression()
            fields.append(ast_nodes.RecordField(key=key_tok.value or "", value=value_expr))
            if self.match("COMMA"):
                continue
            break
        if not self.match("RBRACE"):
            raise self.error("Expected '}' after record literal", self.peek())
        return ast_nodes.RecordLiteral(fields=fields)

    def parse_english_builtin(self) -> ast_nodes.Expr:
        tok = self.consume("KEYWORD")
        name = tok.value or ""
        if name == "sorted":
            if self.peek().value == "form":
                self.consume("KEYWORD", "form")
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.ListBuiltinCall(name=name, expr=operand)
        elif name == "unique":
            if self.peek().value == "elements":
                self.consume("KEYWORD", "elements")
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.ListBuiltinCall(name=name, expr=operand)
        elif name in {"length", "first", "last", "reverse", "sum"}:
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.ListBuiltinCall(name=name, expr=operand)
        elif name in {"trim", "lowercase", "uppercase", "slugify"}:
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.BuiltinCall(name=name, args=[operand])
        elif name == "replace":
            pattern_expr = self.parse_expression()
            self.consume("KEYWORD", "with")
            replacement_expr = self.parse_expression()
            self.consume("KEYWORD", "in")
            base_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="replace", args=[base_expr, pattern_expr, replacement_expr])
        elif name == "split":
            base_expr = self.parse_expression()
            self.consume("KEYWORD", "by")
            sep_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="split", args=[base_expr, sep_expr])
        elif name == "join":
            items_expr = self.parse_expression()
            self.consume("KEYWORD", "with")
            sep_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="join", args=[items_expr, sep_expr])
        elif name in {"minimum", "maximum", "mean"}:
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.BuiltinCall(name=name, args=[operand])
        elif name == "round":
            value_expr = self.parse_unary()
            if self.peek().value == "to":
                self.consume("KEYWORD", "to")
                precision_expr = self.parse_expression()
                return ast_nodes.BuiltinCall(name="round", args=[value_expr, precision_expr])
            return ast_nodes.BuiltinCall(name="round", args=[value_expr])
        elif name == "absolute":
            if self.peek().value == "value":
                self.consume("KEYWORD", "value")
            if self.peek().value == "of":
                self.consume("KEYWORD", "of")
            operand = self.parse_unary()
            return ast_nodes.BuiltinCall(name="abs", args=[operand])
        elif name == "current":
            next_tok = self.consume("KEYWORD")
            if next_tok.value == "timestamp":
                return ast_nodes.BuiltinCall(name="current_timestamp", args=[])
            if next_tok.value == "date":
                return ast_nodes.BuiltinCall(name="current_date", args=[])
            raise self.error("Expected 'timestamp' or 'date' after 'current'", next_tok)
        elif name == "random":
            next_tok = self.consume("KEYWORD")
            if next_tok.value != "uuid":
                raise self.error("Expected 'uuid' after 'random'", next_tok)
            return ast_nodes.BuiltinCall(name="random_uuid", args=[])
        raise self.error(f"Unsupported builtin '{name}'", tok)

    def parse_english_all(self) -> ast_nodes.Expr:
        self.consume("KEYWORD", "all")
        first_tok = self.consume_any({"IDENT"})
        first_val = first_tok.value or ""
        if "." in first_val:
            parts = first_val.split(".")
            first_expr: ast_nodes.Expr = ast_nodes.Identifier(name=parts[0], span=self._span(first_tok))
            for part in parts[1:]:
                first_expr = ast_nodes.RecordFieldAccess(target=first_expr, field=part)
        else:
            first_expr = ast_nodes.Identifier(name=first_val, span=self._span(first_tok))
        if self.peek().value == "in":
            self.consume("KEYWORD", "in")
            source_expr = self.parse_expression()
            self.consume("KEYWORD", "where")
            predicate = self.parse_expression()
            return ast_nodes.AllExpression(source=source_expr, var_name=first_tok.value or "item", predicate=predicate)
        if self.peek().value == "where":
            self.consume("KEYWORD", "where")
            predicate = self.parse_expression()
            return ast_nodes.FilterExpression(source=first_expr, var_name="item", predicate=predicate)
        if self.peek().value == "from":
            self.consume("KEYWORD", "from")
            source_expr = self.parse_expression()
            var_name = first_tok.value.split(".")[0] if first_tok.value else "item"
            return ast_nodes.MapExpression(source=source_expr, var_name=var_name, mapper=first_expr)
        raise self.error("Expected 'where' or 'from' after 'all' expression", self.peek())

    def parse_english_any(self) -> ast_nodes.Expr:
        self.consume("KEYWORD", "any")
        var_tok = self.consume_any({"IDENT"})
        self.consume("KEYWORD", "in")
        source_expr = self.parse_expression()
        self.consume("KEYWORD", "where")
        predicate = self.parse_expression()
        return ast_nodes.AnyExpression(source=source_expr, var_name=var_tok.value or "item", predicate=predicate)

    def parse_builtin_call(self) -> ast_nodes.Expr:
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        name = name_tok.value or ""
        self.consume("LPAREN")
        if name in {"filter", "map"}:
            source_expr = self.parse_expression()
            predicate = None
            mapper = None
            var_name = "item"
            if self.match("COMMA"):
                label_tok = self.consume_any({"KEYWORD"})
                if label_tok.value == "where":
                    if self.match("COLON"):
                        pass
                    predicate = self.parse_expression()
                elif label_tok.value == "to":
                    if self.match("COLON"):
                        pass
                    mapper = self.parse_expression()
                else:
                    raise self.error("Expected 'where' or 'to' keyword argument", label_tok)
            if not self.match("RPAREN"):
                if self.check("RPAREN"):
                    self.consume("RPAREN")
                else:
                    raise self.error("Expected ')' to close call", self.peek())
            if name == "filter":
                if predicate is None:
                    raise self.error("filter requires 'where' predicate", name_tok)
                return ast_nodes.FilterExpression(source=source_expr, var_name=var_name, predicate=predicate)
            if mapper is None:
                raise self.error("map requires 'to' mapper", name_tok)
            return ast_nodes.MapExpression(source=source_expr, var_name=var_name, mapper=mapper)
        if name in {"any", "all"}:
            source_expr = self.parse_expression() if not self.check("RPAREN") else ast_nodes.Literal(value=[])
            predicate = None
            if self.match("COMMA"):
                label_tok = self.consume_any({"KEYWORD"})
                if label_tok.value != "where":
                    raise self.error("Expected 'where' keyword argument", label_tok)
                if self.match("COLON"):
                    pass
                predicate = self.parse_expression()
            if not self.match("RPAREN"):
                if self.check("RPAREN"):
                    self.consume("RPAREN")
                else:
                    raise self.error("Expected ')' to close call", self.peek())
            if predicate is None:
                raise self.error(f"{name} requires a 'where' predicate", name_tok)
            if name == "any":
                return ast_nodes.AnyExpression(source=source_expr, var_name="item", predicate=predicate)
            return ast_nodes.AllExpression(source=source_expr, var_name="item", predicate=predicate)
        args: list[ast_nodes.Expr] = []
        if not self.check("RPAREN"):
            args.append(self.parse_expression())
            while self.match("COMMA"):
                args.append(self.parse_expression())
        if not self.match("RPAREN"):
            if self.check("RPAREN"):
                self.consume("RPAREN")
            else:
                raise self.error("Expected ')' to close call", self.peek())
        if name in {"length", "first", "last", "sorted", "reverse", "unique", "sum"} and len(args) == 1:
            return ast_nodes.ListBuiltinCall(name=name, expr=args[0])
        return ast_nodes.BuiltinCall(name=name, args=args)

    def parse_function_call(self) -> ast_nodes.FunctionCall:
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        name = name_tok.value or ""
        self.consume("LPAREN")
        args: list[ast_nodes.Expr] = []
        if not self.check("RPAREN"):
            args.append(self.parse_expression())
            while self.match("COMMA"):
                args.append(self.parse_expression())
        if not self.match("RPAREN"):
            if self.check("RPAREN"):
                self.consume("RPAREN")
            else:
                raise self.error("Expected ')' to close function call", self.peek())
        return ast_nodes.FunctionCall(name=name, args=args, span=self._span(name_tok))

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
