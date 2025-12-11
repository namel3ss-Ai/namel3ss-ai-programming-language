"""
Parser for the minimal Namel3ss V3 language slice.
"""

from __future__ import annotations

from typing import List, Set
from difflib import get_close_matches

from . import ast_nodes
from .errors import ParseError
from .lexer import Lexer, Token

SUPPORTED_MEMORY_KINDS = ("short_term", "long_term", "episodic", "semantic", "profile")


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.position = 0
        self._ai_field_candidates = {
            "model",
            "provider",
            "system",
            "system_prompt",
            "input",
            "when",
            "describe",
            "description",
            "memory",
            "use",
            "tools",
        }
        self._transaction_depth = 0

    @classmethod
    def from_source(cls, source: str) -> "Parser":
        return cls(Lexer(source).tokenize())

    def parse_module(self) -> ast_nodes.Module:
        module = ast_nodes.Module()
        while not self.check("EOF"):
            if self.match("NEWLINE"):
                continue
            if (
                self.position > 0
                and self.tokens[self.position - 1].type == "STRING"
                and self.tokens[self.position - 1].line == self.peek().line
                and self.peek().type == "KEYWORD"
            ):
                raise self.error(
                    f"N3L-PARSE-NEWLINE: Top-level blocks must start on a new line. Did you forget a newline before '{self.peek().value}'?",
                    self.peek(),
                )
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
            if self.peek_offset(1).value == "evaluation":
                return self.parse_agent_evaluation()
            return self.parse_agent()
        if token.value == "memory":
            if (self.peek_offset(1).value or "") == "profile":
                return self.parse_memory_profile()
            return self.parse_memory()
        if token.value == "record":
            return self.parse_record()
        if token.value == "auth":
            return self.parse_auth()
        if token.value == "frame":
            return self.parse_frame()
        if token.value == "vector_store":
            return self.parse_vector_store()
        if token.value == "graph":
            return self.parse_graph()
        if token.value == "graph_summary":
            return self.parse_graph_summary()
        if token.value == "tool":
            if (self.peek_offset(1).value or "") == "evaluation":
                return self.parse_tool_evaluation()
            return self.parse_tool()
        if token.value == "rag":
            next_tok = self.peek_offset(1)
            if next_tok.value == "pipeline":
                return self.parse_rag_pipeline()
            if next_tok.value == "evaluation":
                return self.parse_rag_evaluation()
            raise self.error("Expected 'pipeline' or 'evaluation' after 'rag'.", next_tok)
        if token.value == "macro":
            next_tok = self.peek_offset(1)
            if next_tok.value == "test":
                return self.parse_macro_test()
            return self.parse_macro()
        if token.value == "flow":
            return self.parse_flow()
        if token.value == "plugin":
            return self.parse_plugin()
        if token.value == "settings":
            return self.parse_settings()
        if token.value == "component":
            return self.parse_ui_component_decl()
        if token.value in {"heading", "text", "image"}:
            raise self.error("N3U-1300: layout element outside of a page or section", token)
        if token.value == "state":
            raise self.error("N3U-2000: state declared outside a page", token)
        if token.value == "input":
            raise self.error("N3U-2100: input outside of a page or section", token)
        if token.value == "button":
            raise self.error("N3U-2200: button outside of a page or section", token)
        if token.value in {"when", "otherwise", "show"}:
            raise self.error("N3U-2300: conditional outside of a page or section", token)
        if token.value == "table":
            raise self.error('Use frame is "name": with a table: block instead of top-level table declarations.', token)
        raise self.error(f"Unexpected declaration '{token.value}'", token)

    def parse_use(self) -> ast_nodes.UseImport:
        start = self.consume("KEYWORD", "use")
        if self.peek().value == "macro":
            return self.parse_macro_use(start)
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
        if self.match_value("KEYWORD", "is"):
            name = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'app "{tok.value}": is not supported. Use app is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'app'", tok)
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
                if self.match_value("KEYWORD", "is"):
                    pass
                desc_token = self.consume("STRING")
                description = desc_token.value
            elif field_token.value == "entry_page":
                if self.match_value("KEYWORD", "is"):
                    pass
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

    def parse_ai(self) -> ast_nodes.AICallDecl:
        start = self.consume("KEYWORD", "ai")
        if self.match_value("KEYWORD", "is"):
            name = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'ai "{tok.value}": is not supported. Use ai is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'ai'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        model_name = None
        provider_name = None
        input_source = None
        description = None
        system_prompt = None
        memory_name = None
        memory_config: ast_nodes.AiMemoryConfig | None = None
        memory_profiles: list[str] = []
        tool_bindings: list[ast_nodes.AiToolBinding] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.peek()
            if field_token.value == "model":
                self.advance()
                if self.match_value("KEYWORD", "is"):
                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    model_tok = self.consume("STRING")
                model_name = model_tok.value
                self.optional_newline()
            elif field_token.value == "provider":
                self.advance()
                if self.match_value("KEYWORD", "is"):
                    provider_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    provider_tok = self.consume("STRING")
                provider_name = provider_tok.value
                self.optional_newline()
            elif field_token.value == "system":
                if system_prompt is not None:
                    raise self.error(
                        "N3L-201: System prompt may only appear once inside an ai block.",
                        field_token,
                    )
                self.advance()
                if self.match_value("KEYWORD", "is"):
                    system_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    system_tok = self.consume("STRING")
                system_prompt = system_tok.value
                self.optional_newline()
            elif field_token.value == "system_prompt":
                if system_prompt is not None:
                    raise self.error(
                        "N3L-201: System prompt may only appear once inside an ai block.",
                        field_token,
                    )
                self.advance()
                if self.match_value("KEYWORD", "is"):
                    system_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    system_tok = self.consume("STRING")
                system_prompt = system_tok.value
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
            elif field_token.value == "memory":
                if memory_name is not None or memory_config is not None:
                    raise self.error(
                        f"N3L-802: AI '{name.value or ''}' has more than one 'memory:' section. I can only use one. Combine your settings into a single 'memory:' block, or move shared settings into a 'memory profile'.",
                        field_token,
                    )
                self.advance()
                if self.match_value("KEYWORD", "is"):
                    mem_tok = self.consume("STRING")
                    mem_kind = mem_tok.value or ""
                    if mem_kind != "conversation":
                        raise self.error(
                            f"N3L-1200: Unsupported memory kind '{mem_kind}' on AI '{name.value or ''}'. Only 'conversation' is supported in this version.",
                            mem_tok,
                        )
                    memory_config = ast_nodes.AiMemoryConfig(kind=mem_kind, span=self._span(mem_tok))
                    self.optional_newline()
                elif self.check("STRING"):
                    value_token = self.consume("STRING")
                    memory_name = value_token.value
                    self.optional_newline()
                else:
                    memory_config = self._parse_memory_block(f"AI '{name.value or ''}'", field_token)
            elif field_token.value == "use" and (self.peek_offset(1).value or "") == "memory":
                self.advance()
                self.consume("KEYWORD", "memory")
                self.consume("KEYWORD", "profile")
                profile_tok = self.consume("STRING")
                profile_name = profile_tok.value or ""
                if not profile_name:
                    raise self.error("Memory profile names must be non-empty.", profile_tok)
                if profile_name not in memory_profiles:
                    memory_profiles.append(profile_name)
                self.optional_newline()
            elif field_token.value == "tools":
                self.advance()
                tool_bindings.extend(self._parse_ai_tools_block())
            else:
                self.advance()
                hint = ""
                matches = get_close_matches(field_token.value or "", list(self._ai_field_candidates), n=1, cutoff=0.6)
                if matches:
                    hint = f" Did you mean '{matches[0]}'?"
                raise self.error(
                    f"N3L-PARSE-UNKNOWN-FIELD: Unexpected field '{field_token.value}' in ai block.{hint}",
                    field_token,
                )
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.AICallDecl(
            name=name.value or "",
            model_name=model_name,
            provider=provider_name,
            input_source=input_source,
            description=description,
            system_prompt=system_prompt,
            memory_name=memory_name,
            memory=memory_config,
            memory_profiles=memory_profiles,
            tools=tool_bindings,
            span=self._span(start),
        )

    def _parse_ai_tools_block(self) -> list[ast_nodes.AiToolBinding]:
        bindings: list[ast_nodes.AiToolBinding] = []
        self.consume("COLON")
        if self.match("NEWLINE"):
            if self.check("INDENT"):
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    if self.match("DASH"):
                        if self.match("NEWLINE"):
                            continue
                    binding = self._parse_ai_tool_binding_entry()
                    bindings.append(binding)
                    self.optional_newline()
                self.consume("DEDENT")
        else:
            bindings.append(self._parse_ai_tool_binding_entry())
        self.optional_newline()
        return bindings

    def _parse_ai_tool_binding_entry(self) -> ast_nodes.AiToolBinding:
        if self.check("STRING"):
            tok = self.consume("STRING")
            value = tok.value or ""
            return ast_nodes.AiToolBinding(
                internal_name=value,
                exposed_name=value,
                span=self._span(tok),
            )
        if self.peek().value == "tool":
            self.consume("KEYWORD", "tool")
            self.consume("KEYWORD", "is")
            name_tok = self.consume("STRING")
            internal_name = name_tok.value or ""
            exposed_name = internal_name
            binding_span = self._span(name_tok)
            # Allow inline alias (tool is "x" as is "alias")
            if self.match_value("KEYWORD", "as"):
                self.consume("KEYWORD", "is")
                alias_tok = self.consume("STRING")
                exposed_name = alias_tok.value or "" or internal_name
                binding_span = self._span(alias_tok)
            else:
                self.optional_newline()
                if self.check("INDENT"):
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        field_tok = self.consume("KEYWORD")
                        if field_tok.value == "as":
                            self.consume("KEYWORD", "is")
                            alias_tok = self.consume("STRING")
                            exposed_name = alias_tok.value or "" or internal_name
                            binding_span = self._span(alias_tok)
                        else:
                            raise self.error(
                                f"Unexpected field '{field_tok.value}' in tool binding.",
                                field_tok,
                            )
                        self.optional_newline()
                    self.consume("DEDENT")
            return ast_nodes.AiToolBinding(
                internal_name=internal_name,
                exposed_name=exposed_name or internal_name,
                span=binding_span,
            )
        tok = self.peek()
        raise self.error(
            "Expected a tool name or 'tool is \"name\"' entry inside tools list.",
            tok,
        )

    def _parse_memory_block(self, owner_label: str, field_token: Token) -> ast_nodes.AiMemoryConfig:
        start_span = self._span(field_token)
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        mem_kind: str | None = None
        mem_window: int | None = None
        mem_store: str | None = None
        short_term_cfg: ast_nodes.AiShortTermMemoryConfig | None = None
        long_term_cfg: ast_nodes.AiLongTermMemoryConfig | None = None
        episodic_cfg: ast_nodes.AiEpisodicMemoryConfig | None = None
        semantic_cfg: ast_nodes.AiSemanticMemoryConfig | None = None
        profile_cfg: ast_nodes.AiProfileMemoryConfig | None = None
        recall_rules: list[ast_nodes.AiRecallRule] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            mem_field = self.consume_any({"KEYWORD", "IDENT"})
            field_name = mem_field.value or ""
            if field_name == "kind":
                self.consume("KEYWORD", "is")
                kind_tok = self.consume("STRING")
                mem_kind = kind_tok.value or ""
            elif field_name == "window":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                mem_window = self._consume_positive_int(
                    num_tok, "N3L-1202: memory window must be a positive integer."
                )
            elif field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                mem_store = store_tok.value or ""
                if not mem_store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "kinds":
                (
                    short_term_cfg,
                    long_term_cfg,
                    episodic_cfg,
                    semantic_cfg,
                    profile_cfg,
                ) = self._parse_memory_kinds_block(owner_label)
                continue
            elif field_name == "recall":
                recall_rules = self._parse_memory_recall_block()
                continue
            else:
                raise self.error(f"Unexpected field '{field_name}' in memory block", mem_field)
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.AiMemoryConfig(
            kind=mem_kind,
            window=mem_window,
            store=mem_store,
            short_term=short_term_cfg,
            long_term=long_term_cfg,
            episodic=episodic_cfg,
            semantic=semantic_cfg,
            profile=profile_cfg,
            recall=recall_rules,
            span=start_span,
        )

    def _suggest_memory_kind(self, name: str) -> str | None:
        matches = get_close_matches(name, SUPPORTED_MEMORY_KINDS, n=1, cutoff=0.6)
        return matches[0] if matches else None

    def _parse_memory_kinds_block(
        self,
        owner_label: str,
    ) -> tuple[
        ast_nodes.AiShortTermMemoryConfig | None,
        ast_nodes.AiLongTermMemoryConfig | None,
        ast_nodes.AiEpisodicMemoryConfig | None,
        ast_nodes.AiSemanticMemoryConfig | None,
        ast_nodes.AiProfileMemoryConfig | None,
    ]:
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        short_term_cfg: ast_nodes.AiShortTermMemoryConfig | None = None
        long_term_cfg: ast_nodes.AiLongTermMemoryConfig | None = None
        episodic_cfg: ast_nodes.AiEpisodicMemoryConfig | None = None
        semantic_cfg: ast_nodes.AiSemanticMemoryConfig | None = None
        profile_cfg: ast_nodes.AiProfileMemoryConfig | None = None
        defined_kinds: set[str] = set()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            kind_tok = self.consume_any({"KEYWORD", "IDENT"})
            kind_name_raw = kind_tok.value or ""
            kind_name = (kind_name_raw or "").strip()
            bare_entry = False
            if not kind_name:
                raise self.error("Memory kind name cannot be empty.", kind_tok)
            if kind_name not in SUPPORTED_MEMORY_KINDS:
                suggestion = self._suggest_memory_kind(kind_name)
                hint = f" Did you mean '{suggestion}'?" if suggestion else ""
                raise self.error(
                    f"Memory kind '{kind_name}' is not supported.{hint} Supported kinds are: {', '.join(SUPPORTED_MEMORY_KINDS)}.",
                    kind_tok,
                )
            if kind_name in defined_kinds:
                raise self.error(
                    f"Memory kind '{kind_name}' is declared more than once for {owner_label}. Combine your settings into a single entry.",
                    kind_tok,
                )
            bare_entry = False
            if self.match("COLON"):
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    if self.check("DEDENT"):
                        self.consume("DEDENT")
                        bare_entry = True
                    else:
                        if kind_name == "short_term":
                            if short_term_cfg is not None:
                                raise self.error("short_term memory kind may only be defined once.", kind_tok)
                            short_term_cfg = self._parse_short_term_kind(owner_label)
                        elif kind_name == "long_term":
                            if long_term_cfg is not None:
                                raise self.error("long_term memory kind may only be defined once.", kind_tok)
                            long_term_cfg = self._parse_long_term_kind(owner_label)
                        elif kind_name == "episodic":
                            if episodic_cfg is not None:
                                raise self.error("episodic memory kind may only be defined once.", kind_tok)
                            episodic_cfg = self._parse_episodic_kind(owner_label)
                        elif kind_name == "semantic":
                            if semantic_cfg is not None:
                                raise self.error("semantic memory kind may only be defined once.", kind_tok)
                            semantic_cfg = self._parse_semantic_kind(owner_label)
                        elif kind_name == "profile":
                            if profile_cfg is not None:
                                raise self.error("profile memory kind may only be defined once.", kind_tok)
                            profile_cfg = self._parse_profile_kind(owner_label)
                        self.consume("DEDENT")
                else:
                    bare_entry = True
            else:
                bare_entry = True

            if bare_entry:
                if kind_name == "short_term":
                    if short_term_cfg is not None:
                        raise self.error("short_term memory kind may only be defined once.", kind_tok)
                    short_term_cfg = ast_nodes.AiShortTermMemoryConfig(span=self._span(kind_tok))
                elif kind_name == "long_term":
                    if long_term_cfg is not None:
                        raise self.error("long_term memory kind may only be defined once.", kind_tok)
                    long_term_cfg = ast_nodes.AiLongTermMemoryConfig(span=self._span(kind_tok))
                elif kind_name == "episodic":
                    if episodic_cfg is not None:
                        raise self.error("episodic memory kind may only be defined once.", kind_tok)
                    episodic_cfg = ast_nodes.AiEpisodicMemoryConfig(span=self._span(kind_tok))
                elif kind_name == "semantic":
                    if semantic_cfg is not None:
                        raise self.error("semantic memory kind may only be defined once.", kind_tok)
                    semantic_cfg = ast_nodes.AiSemanticMemoryConfig(span=self._span(kind_tok))
                elif kind_name == "profile":
                    if profile_cfg is not None:
                        raise self.error("profile memory kind may only be defined once.", kind_tok)
                    profile_cfg = ast_nodes.AiProfileMemoryConfig(span=self._span(kind_tok))
            defined_kinds.add(kind_name)
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        return short_term_cfg, long_term_cfg, episodic_cfg, semantic_cfg, profile_cfg

    def _parse_short_term_kind(self, owner_label: str) -> ast_nodes.AiShortTermMemoryConfig:
        window: int | None = None
        store: str | None = None
        retention_days: int | None = None
        pii_policy: str | None = None
        scope: str | None = None
        pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "window":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                window = self._consume_positive_int(
                    num_tok, "N3L-1202: memory window must be a positive integer."
                )
            elif field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                store = store_tok.value or ""
                if not store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "retention_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                retention_days = self._consume_positive_int(
                    num_tok, "N3L-1202: retention_days must be a positive integer."
                )
            elif field_name == "pii_policy":
                self.consume("KEYWORD", "is")
                policy_tok = self.consume("STRING")
                pii_policy = (policy_tok.value or "").strip()
            elif field_name == "scope":
                self.consume("KEYWORD", "is")
                scope_tok = self.consume("STRING")
                scope = (scope_tok.value or "").strip()
            elif field_name == "pipeline":
                pipeline = self._parse_memory_pipeline_block()
            else:
                raise self.error(f"Unexpected field '{field_name}' in short_term memory kind.", field_tok)
            self.optional_newline()
        return ast_nodes.AiShortTermMemoryConfig(
            window=window,
            store=store,
            retention_days=retention_days,
            pii_policy=pii_policy,
            scope=scope,
            pipeline=pipeline,
        )

    def _parse_long_term_kind(self, owner_label: str) -> ast_nodes.AiLongTermMemoryConfig:
        store: str | None = None
        pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
        retention_days: int | None = None
        pii_policy: str | None = None
        scope: str | None = None
        time_decay: ast_nodes.AiTimeDecayConfig | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                store = store_tok.value or ""
                if not store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "pipeline":
                pipeline = self._parse_memory_pipeline_block()
            elif field_name == "retention_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                retention_days = self._consume_positive_int(
                    num_tok, "N3L-1202: retention_days must be a positive integer."
                )
            elif field_name == "pii_policy":
                self.consume("KEYWORD", "is")
                policy_tok = self.consume("STRING")
                pii_policy = (policy_tok.value or "").strip()
            elif field_name == "scope":
                self.consume("KEYWORD", "is")
                scope_tok = self.consume("STRING")
                scope = (scope_tok.value or "").strip()
            elif field_name == "time_decay":
                if time_decay is not None:
                    raise self.error("time_decay may only be defined once in a long_term block.", field_tok)
                time_decay = self._parse_time_decay_block("long_term", field_tok)
            else:
                raise self.error(f"Unexpected field '{field_name}' in long_term memory kind.", field_tok)
            self.optional_newline()
        if not store:
            raise self.error(
                f"long_term memory kind on {owner_label} requires a 'store is \"...\"' entry.",
                self.peek(),
            )
        return ast_nodes.AiLongTermMemoryConfig(
            store=store,
            pipeline=pipeline,
            retention_days=retention_days,
            pii_policy=pii_policy,
            scope=scope,
            time_decay=time_decay,
        )

    def _parse_profile_kind(self, owner_label: str) -> ast_nodes.AiProfileMemoryConfig:
        store: str | None = None
        extract_facts: bool | None = None
        pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
        retention_days: int | None = None
        pii_policy: str | None = None
        scope: str | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                store = store_tok.value or ""
                if not store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "extract_facts":
                self.consume("KEYWORD", "is")
                bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                extract_facts = self._consume_bool_literal(
                    bool_tok, "extract_facts must be true or false."
                )
            elif field_name == "pipeline":
                pipeline = self._parse_memory_pipeline_block()
            elif field_name == "retention_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                retention_days = self._consume_positive_int(
                    num_tok, "N3L-1202: retention_days must be a positive integer."
                )
            elif field_name == "pii_policy":
                self.consume("KEYWORD", "is")
                policy_tok = self.consume("STRING")
                pii_policy = (policy_tok.value or "").strip()
            elif field_name == "scope":
                self.consume("KEYWORD", "is")
                scope_tok = self.consume("STRING")
                scope = (scope_tok.value or "").strip()
            else:
                raise self.error(f"Unexpected field '{field_name}' in profile memory kind.", field_tok)
            self.optional_newline()
        if not store:
            raise self.error(
                f"profile memory kind on {owner_label} requires a 'store is \"...\"' entry.",
                self.peek(),
            )
        return ast_nodes.AiProfileMemoryConfig(
            store=store,
            extract_facts=extract_facts,
            pipeline=pipeline,
            retention_days=retention_days,
            pii_policy=pii_policy,
            scope=scope,
        )

    def _parse_episodic_kind(self, owner_label: str) -> ast_nodes.AiEpisodicMemoryConfig:
        store: str | None = None
        retention_days: int | None = None
        pii_policy: str | None = None
        scope: str | None = None
        pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
        time_decay: ast_nodes.AiTimeDecayConfig | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                store = store_tok.value or ""
                if not store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "retention_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                retention_days = self._consume_positive_int(
                    num_tok, "N3L-1202: retention_days must be a positive integer."
                )
            elif field_name == "pii_policy":
                self.consume("KEYWORD", "is")
                policy_tok = self.consume("STRING")
                pii_policy = (policy_tok.value or "").strip()
            elif field_name == "scope":
                self.consume("KEYWORD", "is")
                scope_tok = self.consume("STRING")
                scope = (scope_tok.value or "").strip()
            elif field_name == "pipeline":
                pipeline = self._parse_memory_pipeline_block()
            elif field_name == "time_decay":
                if time_decay is not None:
                    raise self.error("time_decay may only be defined once in an episodic block.", field_tok)
                time_decay = self._parse_time_decay_block("episodic", field_tok)
            else:
                raise self.error(f"Unexpected field '{field_name}' in episodic memory kind.", field_tok)
            self.optional_newline()
        return ast_nodes.AiEpisodicMemoryConfig(
            store=store,
            retention_days=retention_days,
            pii_policy=pii_policy,
            scope=scope,
            pipeline=pipeline,
            time_decay=time_decay,
        )

    def _parse_semantic_kind(self, owner_label: str) -> ast_nodes.AiSemanticMemoryConfig:
        store: str | None = None
        retention_days: int | None = None
        pii_policy: str | None = None
        scope: str | None = None
        pipeline: list[ast_nodes.AiMemoryPipelineStep] | None = None
        time_decay: ast_nodes.AiTimeDecayConfig | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field_name = field_tok.value or ""
            if field_name == "store":
                self.consume("KEYWORD", "is")
                store_tok = self.consume("STRING")
                store = store_tok.value or ""
                if not store:
                    raise self.error("N3L-1203: memory store must be a non-empty string.", store_tok)
            elif field_name == "retention_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                retention_days = self._consume_positive_int(
                    num_tok, "N3L-1202: retention_days must be a positive integer."
                )
            elif field_name == "pii_policy":
                self.consume("KEYWORD", "is")
                policy_tok = self.consume("STRING")
                pii_policy = (policy_tok.value or "").strip()
            elif field_name == "scope":
                self.consume("KEYWORD", "is")
                scope_tok = self.consume("STRING")
                scope = (scope_tok.value or "").strip()
            elif field_name == "pipeline":
                pipeline = self._parse_memory_pipeline_block()
            elif field_name == "time_decay":
                if time_decay is not None:
                    raise self.error("time_decay may only be defined once in a semantic block.", field_tok)
                time_decay = self._parse_time_decay_block("semantic", field_tok)
            else:
                raise self.error(f"Unexpected field '{field_name}' in semantic memory kind.", field_tok)
            self.optional_newline()
        return ast_nodes.AiSemanticMemoryConfig(
            store=store,
            retention_days=retention_days,
            pii_policy=pii_policy,
            scope=scope,
            pipeline=pipeline,
            time_decay=time_decay,
        )

    def _parse_time_decay_block(self, kind_name: str, field_token: Token) -> ast_nodes.AiTimeDecayConfig:
        if self.match_value("KEYWORD", "is"):
            raise self.error(
                f"time_decay on {kind_name} memory uses block syntax. Try:\n  time_decay:\n    half_life_days is 30",
                field_token,
            )
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        half_life_days: int | None = None
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            inner_tok = self.consume_any({"KEYWORD", "IDENT"})
            inner_name = inner_tok.value or ""
            if inner_name == "half_life_days":
                self.consume("KEYWORD", "is")
                num_tok = self.consume("NUMBER")
                half_life_days = self._consume_positive_int(
                    num_tok, "time_decay half_life_days must be a positive integer."
                )
            else:
                raise self.error(
                    f"Unknown field '{inner_name}' inside time_decay for {kind_name} memory. Supported: half_life_days.",
                    inner_tok,
                )
            self.optional_newline()
        self.consume("DEDENT")
        if half_life_days is None:
            raise self.error(
                f"time_decay on {kind_name} memory requires 'half_life_days is <number>'.",
                field_token,
            )
        return ast_nodes.AiTimeDecayConfig(half_life_days=half_life_days, span=self._span(field_token))

    def _parse_memory_recall_block(self) -> list[ast_nodes.AiRecallRule]:
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        rules: list[ast_nodes.AiRecallRule] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            self.consume("DASH")
            rule = ast_nodes.AiRecallRule()
            start_tok = self.peek()
            nested_indent = 0
            while True:
                if nested_indent == 0 and (self.check("DEDENT") or self.check("DASH")):
                    break
                if self.match("NEWLINE"):
                    continue
                if self.match("INDENT"):
                    nested_indent += 1
                    continue
                if nested_indent > 0 and self.match("DEDENT"):
                    nested_indent -= 1
                    continue
                field_tok = self.consume_any({"KEYWORD", "IDENT"})
                field_name = field_tok.value or ""
                if field_name == "source":
                    self.consume("KEYWORD", "is")
                    source_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    rule.source = ((source_tok.value or "").strip()).lower()
                    if rule.source not in SUPPORTED_MEMORY_KINDS:
                        suggestion = self._suggest_memory_kind(rule.source)
                        hint = f" Did you mean '{suggestion}'?" if suggestion else ""
                        raise self.error(
                            f"N3L-1202: Memory recall source '{rule.source}' is not a supported memory kind.{hint} Supported kinds are: {', '.join(SUPPORTED_MEMORY_KINDS)}.",
                            source_tok,
                        )
                elif field_name == "count":
                    self.consume("KEYWORD", "is")
                    num_tok = self.consume("NUMBER")
                    rule.count = self._consume_positive_int(
                        num_tok, "N3L-1202: memory count must be a positive integer."
                    )
                elif field_name == "top_k":
                    self.consume("KEYWORD", "is")
                    num_tok = self.consume("NUMBER")
                    rule.top_k = self._consume_positive_int(
                        num_tok, "N3L-1202: memory top_k must be a positive integer."
                    )
                elif field_name == "include":
                    self.consume("KEYWORD", "is")
                    bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                    rule.include = self._consume_bool_literal(
                        bool_tok, "include must be true or false."
                    )
                else:
                    raise self.error(f"Unexpected field '{field_name}' in recall rule.", field_tok)
                self.optional_newline()
            if not rule.source:
                raise self.error("Recall rule must specify a source.", start_tok)
            if nested_indent != 0:
                raise self.error("Incomplete recall rule indentation.", self.peek())
            rules.append(rule)
        self.consume("DEDENT")
        self.optional_newline()
        return rules

    def _parse_memory_pipeline_block(self) -> list[ast_nodes.AiMemoryPipelineStep]:
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        steps: list[ast_nodes.AiMemoryPipelineStep] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.check("DASH"):
                steps.append(self._parse_legacy_pipeline_step())
                continue
            steps.append(self._parse_block_pipeline_step())
        self.consume("DEDENT")
        self.optional_newline()
        return steps

    def _parse_block_pipeline_step(self) -> ast_nodes.AiMemoryPipelineStep:
        start_tok = self.consume_any({"KEYWORD", "IDENT"})
        if (start_tok.value or "") != "step":
            raise self.error("Expected 'step is \"name\"' inside pipeline.", start_tok)
        self.consume("KEYWORD", "is")
        name_tok = self.consume("STRING")
        step = ast_nodes.AiMemoryPipelineStep(name=(name_tok.value or "").strip(), span=self._span(start_tok))
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            self._assign_pipeline_step_field(step, field_tok)
            self.optional_newline()
        self.consume("DEDENT")
        self._finalize_pipeline_step(step, start_tok)
        return step

    def _parse_legacy_pipeline_step(self) -> ast_nodes.AiMemoryPipelineStep:
        self.consume("DASH")
        step = ast_nodes.AiMemoryPipelineStep()
        start_tok = self.peek()
        nested_indent = 0
        while True:
            if nested_indent == 0 and (self.check("DEDENT") or self.check("DASH")):
                break
            if self.match("NEWLINE"):
                continue
            if self.match("INDENT"):
                nested_indent += 1
                continue
            if nested_indent > 0 and self.match("DEDENT"):
                nested_indent -= 1
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            self._assign_pipeline_step_field(step, field_tok)
            self.optional_newline()
        self._finalize_pipeline_step(step, start_tok)
        return step

    def _assign_pipeline_step_field(
        self,
        step: ast_nodes.AiMemoryPipelineStep,
        field_tok: Token,
    ) -> None:
        field_name = field_tok.value or ""
        if field_name == "step":
            self.consume("KEYWORD", "is")
            name_tok = self.consume("STRING")
            step.name = (name_tok.value or "").strip()
        elif field_name == "type":
            self.consume("KEYWORD", "is")
            type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            step.type = (type_tok.value or "").strip()
        elif field_name == "max_tokens":
            self.consume("KEYWORD", "is")
            num_tok = self.consume("NUMBER")
            step.max_tokens = self._consume_positive_int(
                num_tok, "N3L-1202: max_tokens must be a positive integer."
            )
        elif field_name == "target_kind":
            self.consume("KEYWORD", "is")
            target_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            step.target_kind = (target_tok.value or "").strip()
        elif field_name == "embedding_model":
            self.consume("KEYWORD", "is")
            embed_tok = self.consume("STRING")
            step.embedding_model = (embed_tok.value or "").strip()
        else:
            raise self.error(f"Unexpected field '{field_name}' in memory pipeline step.", field_tok)

    def _finalize_pipeline_step(
        self,
        step: ast_nodes.AiMemoryPipelineStep,
        start_tok: Token,
    ) -> None:
        if not (step.name or "").strip():
            raise self.error("Memory pipeline step requires a non-empty 'step' name.", start_tok)
        if not (step.type or "").strip():
            raise self.error("Memory pipeline step requires a 'type'.", start_tok)
        step.span = self._span(start_tok)

    def _consume_positive_int(self, token: Token, error_msg: str) -> int:
        try:
            value = int(token.value or "0")
        except Exception:
            value = 0
        if value <= 0:
            raise self.error(error_msg, token)
        return value

    def _consume_bool_literal(self, token: Token, error_msg: str) -> bool:
        literal = (token.value or "").lower()
        if literal not in {"true", "false"}:
            raise self.error(error_msg, token)
        return literal == "true"

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
        if self.match_value("KEYWORD", "is"):
            name = self.consume_any({"STRING", "IDENT"})
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'agent "{tok.value}": is not supported. Use agent is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'agent'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        goal = None
        personality = None
        system_prompt = None
        conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
        memory_name = None
        role = None
        can_delegate_to: list[str] | None = None
        allowed_fields: Set[str] = {"goal", "personality", "system", "system_prompt", "memory", "role", "can_delegate_to"}
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
                if self.match_value("KEYWORD", "is"):
                    pass
                value_token = self.consume_any({"STRING", "IDENT"})
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
                suggestion = get_close_matches(field_token.value or "", list(allowed_fields), n=1, cutoff=0.6)
                hint = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
                raise self.error(
                    f"N3L-PARSE-UNKNOWN-FIELD: Unexpected field '{field_token.value}' in agent block.{hint}",
                    field_token,
                )
            if field_token.value in {"system", "system_prompt"}:
                if system_prompt is not None:
                    raise self.error(
                        "N3L-201: System prompt may only appear once inside an agent block.",
                        field_token,
                    )
                if self.match_value("KEYWORD", "is"):
                    value_token = self.consume_any({"STRING", "IDENT"})
                else:
                    value_token = self.consume_string_value(
                        field_token, field_token.value or "agent field"
                    )
                system_prompt = value_token.value
            elif field_token.value == "memory":
                if memory_name is not None:
                    raise self.error(
                        "N3L-201: memory may only appear once inside an agent block.",
                        field_token,
                    )
                if self.match_value("KEYWORD", "is"):
                    value_token = self.consume_any({"STRING", "IDENT"})
                else:
                    value_token = self.consume_string_value(
                        field_token, field_token.value or "agent field"
                    )
                memory_name = value_token.value
            elif field_token.value == "role":
                if role is not None:
                    raise self.error("role may only appear once inside an agent block.", field_token)
                if self.match_value("KEYWORD", "is"):
                    value_token = self.consume_any({"STRING", "IDENT"})
                else:
                    value_token = self.consume_string_value(field_token, field_token.value or "agent field")
                role = value_token.value
            elif field_token.value == "can_delegate_to":
                if can_delegate_to is not None:
                    raise self.error("can_delegate_to may only appear once inside an agent block.", field_token)
                if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                    pass
                if self.peek().type == "LBRACKET":
                    can_delegate_to = self._parse_string_list_literal(self.peek())
                else:
                    value_token = self.consume_any({"STRING", "IDENT"})
                    can_delegate_to = [value_token.value]
            else:
                if self.match_value("KEYWORD", "is"):
                    value_token = self.consume_any({"STRING", "IDENT"})
                else:
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
            system_prompt=system_prompt,
            conditional_branches=conditional_branches,
            memory_name=memory_name,
            role=role,
            can_delegate_to=can_delegate_to,
            span=self._span(start),
        )

    def parse_memory(self) -> ast_nodes.MemoryDecl:
        start = self.consume("KEYWORD", "memory")
        name = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        memory_type = None
        retention = None
        allowed_fields: Set[str] = {"type", "retention"}
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in memory block",
                    field_token,
                )
            value_token = self.consume_string_value(field_token, field_token.value or "memory field")
            if field_token.value == "type":
                memory_type = value_token.value
            elif field_token.value == "retention":
                retention = value_token.value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.MemoryDecl(
            name=name.value or "", memory_type=memory_type, retention=retention, span=self._span(start)
        )

    def parse_memory_profile(self) -> ast_nodes.MemoryProfileDecl:
        start = self.consume("KEYWORD", "memory")
        profile_tok = self.consume_any({"KEYWORD", "IDENT"})
        if (profile_tok.value or "").lower() != "profile":
            raise self.error("Expected 'profile' after memory when declaring a memory profile.", profile_tok)
        self.consume("KEYWORD", "is")
        name_tok = self.consume("STRING")
        owner_label = f"memory profile '{name_tok.value or ''}'"
        config = self._parse_memory_block(owner_label, start)
        return ast_nodes.MemoryProfileDecl(name=name_tok.value or "", config=config, span=self._span(start))

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
                        is_unique = False
                        unique_scope: str | None = None
                        references_record: str | None = None
                        references_field: str | None = None
                        relationship_target: str | None = None
                        relationship_via_field: str | None = None
                        numeric_min_expr: ast_nodes.Expr | None = None
                        numeric_max_expr: ast_nodes.Expr | None = None
                        length_min_expr: ast_nodes.Expr | None = None
                        length_max_expr: ast_nodes.Expr | None = None
                        enum_values_literal: ast_nodes.ListLiteral | None = None
                        pattern_value: str | None = None
                        field_allowed = {"type", "primary_key", "required", "default", "must", "references", "relationship"}
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            prop_tok = self.consume("KEYWORD")
                            prop_name = prop_tok.value or ""
                            if prop_name == "primary":
                                if self.match_value("KEYWORD", "key"):
                                    prop_name = "primary_key"
                                else:
                                    raise self.error(
                                        "I expected 'key' after primary when declaring a primary key rule. Try 'primary key true'.",
                                        self.peek(),
                                    )
                            if prop_name not in field_allowed:
                                raise self.error(
                                    f"Unexpected field '{prop_tok.value}' inside record field '{field_name_tok.value}'.",
                                    prop_tok,
                                )
                            if prop_name == "type":
                                if self.match_value("KEYWORD", "is"):
                                    type_tok = self.consume_any({"STRING", "IDENT"})
                                else:
                                    type_tok = self.consume_any({"STRING", "IDENT"})
                                field_type = type_tok.value or ""
                            elif prop_name in {"primary_key", "required"}:
                                if self.match_value("KEYWORD", "is"):
                                    bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                                else:
                                    bool_tok = self.consume_any({"KEYWORD", "IDENT"})
                                bool_val = (bool_tok.value or "").lower()
                                if bool_val not in {"true", "false"}:
                                    raise self.error(
                                        f"Field '{prop_name}' must be 'true' or 'false'.",
                                        bool_tok,
                                    )
                                if prop_name == "primary_key":
                                    primary_key = bool_val == "true"
                                else:
                                    required = bool_val == "true"
                            elif prop_name == "default":
                                if self.match_value("KEYWORD", "is"):
                                    default_expr = self.parse_expression()
                                else:
                                    default_expr = self.parse_expression()
                            elif prop_name == "references":
                                if references_record:
                                    raise self.error(
                                        "I see more than one references rule on this field. Keep only a single references \"RecordName\" rule.",
                                        prop_tok,
                                    )
                                if self.match_value("KEYWORD", "is"):
                                    target_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    target_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                references_record = target_tok.value or ""
                                if not references_record:
                                    raise self.error(
                                        "I expected a record name after references.",
                                        target_tok,
                                    )
                                if self.match_value("KEYWORD", "by"):
                                    ref_field_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                    references_field = ref_field_tok.value or ""
                                    if not references_field:
                                        raise self.error(
                                            "I expected a field name after references ... by.",
                                            ref_field_tok,
                                        )
                            elif prop_name == "relationship":
                                if relationship_target:
                                    raise self.error(
                                        "I see more than one relationship rule on this field. Keep only one relationship declaration here.",
                                        prop_tok,
                                    )
                                self.consume("KEYWORD", "is")
                                target_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                relationship_target = target_tok.value or ""
                                if not relationship_target:
                                    raise self.error(
                                        "I expected a record name after relationship is.",
                                        target_tok,
                                    )
                                if self.match_value("KEYWORD", "by"):
                                    via_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                    relationship_via_field = via_tok.value or ""
                                    if not relationship_via_field:
                                        raise self.error(
                                            "I expected a field name after relationship ... by.",
                                            via_tok,
                                    )
                                else:
                                    raise self.error(
                                        "Relationship declarations must specify the field to use, e.g. relationship is \"User\" by user_id.",
                                        prop_tok,
                                    )
                            else:  # must ...
                                consumed_rule = False
                                if self.match_value("KEYWORD", "have"):
                                    consumed_rule = True
                                    self.consume("KEYWORD", "length")
                                    if not self.match_value("KEYWORD", "at"):
                                        raise self.error(
                                            "Length rules must say at least ... or at most ....",
                                            self.peek(),
                                        )
                                    bound_tok = self.consume("KEYWORD")
                                    expr = self.parse_expression()
                                    if bound_tok.value == "least":
                                        if length_min_expr is not None:
                                            raise self.error(
                                                "I already see a must have length at least rule on this field.",
                                                prop_tok,
                                            )
                                        length_min_expr = expr
                                    elif bound_tok.value == "most":
                                        if length_max_expr is not None:
                                            raise self.error(
                                                "I already see a must have length at most rule on this field.",
                                                prop_tok,
                                            )
                                        length_max_expr = expr
                                    else:
                                        raise self.error(
                                            "Length rules must say at least ... or at most ....",
                                            bound_tok,
                                        )
                                elif self.match_value("KEYWORD", "match"):
                                    consumed_rule = True
                                    self.consume("KEYWORD", "pattern")
                                    pattern_tok = self.consume("STRING")
                                    pattern_raw = pattern_tok.value or ""
                                    if not pattern_raw:
                                        raise self.error(
                                            "I expected a quoted pattern after must match pattern.",
                                            pattern_tok,
                                        )
                                    if pattern_value is not None:
                                        raise self.error(
                                            "I already see a must match pattern rule on this field.",
                                            pattern_tok,
                                        )
                                    pattern_value = pattern_raw
                                elif self.match_value("KEYWORD", "be"):
                                    consumed_rule = True
                                    if self.match_value("KEYWORD", "unique"):
                                        if is_unique:
                                            raise self.error(
                                                "I see more than one uniqueness rule on this field. Keep only one must be unique rule here.",
                                                prop_tok,
                                            )
                                        is_unique = True
                                        scope_value: str | None = None
                                        if self.match_value("KEYWORD", "within"):
                                            scope_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                            scope_value = scope_tok.value or ""
                                            if not scope_value:
                                                raise self.error(
                                                    "I expected a scope name after must be unique within.",
                                                    scope_tok,
                                                )
                                        unique_scope = scope_value
                                    elif self.match_value("KEYWORD", "present"):
                                        required = True
                                    elif self.match_value("KEYWORD", "at"):
                                        bound_tok = self.consume("KEYWORD")
                                        expr = self.parse_expression()
                                        if bound_tok.value == "least":
                                            if numeric_min_expr is not None:
                                                raise self.error(
                                                    "I already see a must be at least rule on this field.",
                                                    prop_tok,
                                                )
                                            numeric_min_expr = expr
                                        elif bound_tok.value == "most":
                                            if numeric_max_expr is not None:
                                                raise self.error(
                                                    "I already see a must be at most rule on this field.",
                                                    prop_tok,
                                                )
                                            numeric_max_expr = expr
                                        else:
                                            raise self.error(
                                                "Numeric rules must say at least ... or at most ....",
                                                bound_tok,
                                            )
                                    elif self.match_value("KEYWORD", "one"):
                                        self.consume("KEYWORD", "of")
                                        if enum_values_literal is not None:
                                            raise self.error(
                                                "I already see a must be one of rule on this field.",
                                                prop_tok,
                                            )
                                        if not self.check("LBRACKET"):
                                            raise self.error(
                                                'I expected a list like ["draft", "published"] after must be one of.',
                                                self.peek(),
                                            )
                                        enum_values_literal = self.parse_list_literal()
                                    else:
                                        raise self.error(
                                            "I don't understand this must be ... rule. Try must be unique, must be at least, must be at most, "
                                            "must be present, or must be one of [...].",
                                            self.peek(),
                                        )
                                if not consumed_rule:
                                    raise self.error(
                                        "I don't understand this must ... rule. Try must be unique, must be at least, must be at most, "
                                        "must be present, must have length at least, must have length at most, must be one of [...], or must match pattern \"...\".",
                                        self.peek(),
                                    )
                            self.optional_newline()
                        self.consume("DEDENT")
                        field_decls.append(
                            ast_nodes.RecordFieldDecl(
                                name=field_name_tok.value or "",
                                type=field_type or "",
                                primary_key=primary_key,
                                required=required,
                                default_expr=default_expr,
                                is_unique=is_unique,
                                unique_scope=unique_scope,
                                references_record=references_record,
                                references_field=references_field,
                                relationship_target=relationship_target,
                                relationship_via_field=relationship_via_field,
                                numeric_min_expr=numeric_min_expr,
                                numeric_max_expr=numeric_max_expr,
                                length_min_expr=length_min_expr,
                                length_max_expr=length_max_expr,
                                enum_values_expr=enum_values_literal,
                                pattern=pattern_value,
                                span=self._span(field_name_tok),
                            )
                        )
                        self.optional_newline()
                    self.consume("DEDENT")
                self.optional_newline()
                continue
        self.consume("DEDENT")
        self.optional_newline()
        if not frame_name:
            raise self.error("Record must specify a frame.", name_tok)
        if not field_decls:
            raise self.error("Record must declare at least one field.", name_tok)
        return ast_nodes.RecordDecl(
            name=name_tok.value or "",
            frame=frame_name or "",
            fields=field_decls,
            span=self._span(start),
        )

    def parse_auth(self) -> ast_nodes.AuthDecl:
        start = self.consume("KEYWORD", "auth")
        if self.match_value("KEYWORD", "is"):
            pass
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")

        backend = None
        user_record = None
        id_field = None
        identifier_field = None
        password_hash_field = None
        allowed_fields = {"backend", "user_record", "id_field", "identifier_field", "password_hash_field"}
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_token = self.consume("KEYWORD")
            if field_token.value not in allowed_fields:
                raise self.error(
                    f"Unexpected field '{field_token.value}' in auth block",
                    field_token,
                )
            if self.match_value("KEYWORD", "is"):
                value_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                value_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            value = value_tok.value or ""
            if field_token.value == "backend":
                backend = value
            elif field_token.value == "user_record":
                user_record = value
            elif field_token.value == "id_field":
                id_field = value
            elif field_token.value == "identifier_field":
                identifier_field = value
            elif field_token.value == "password_hash_field":
                password_hash_field = value
            self.optional_newline()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.AuthDecl(
            backend=backend,
            user_record=user_record,
            id_field=id_field,
            identifier_field=identifier_field,
            password_hash_field=password_hash_field,
            span=self._span(start),
        )

    def parse_vector_store(self) -> ast_nodes.VectorStoreDecl:
        start = self.consume("KEYWORD", "vector_store")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'vector_store "{tok.value}": is not supported. Use vector_store is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'vector_store'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")

        backend = None
        frame_name = None
        text_col = None
        id_col = None
        embedding_model = None
        metadata_columns: list[str] = []
        options: dict[str, str] = {}

        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                if tok.value == "backend":
                    self.consume("KEYWORD", "backend")
                    if self.match_value("KEYWORD", "is"):
                        backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    backend = backend_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "frame":
                    self.consume("KEYWORD", "frame")
                    if self.match_value("KEYWORD", "is"):
                        frame_tok = self.consume("STRING")
                    else:
                        frame_tok = self.consume("STRING")
                    frame_name = frame_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "text_column":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    text_col = t_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "id_column":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    id_col = i_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "embedding_model":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        e_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        e_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    embedding_model = e_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "metadata_columns":
                    self.consume("KEYWORD", "metadata_columns")
                    if self.match_value("KEYWORD", "are"):
                        pass
                    elif self.peek().value == "is":
                        self.consume_any({"KEYWORD"})
                    start_list_token = self.peek()
                    metadata_columns = self._parse_string_list_literal(start_list_token)
                    self.optional_newline()
                    continue
                # allow options passthrough as key "option is value"
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                key_name = key_tok.value or ""
                if self.match_value("KEYWORD", "is"):
                    val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                options[key_name] = val_tok.value or ""
                self.optional_newline()
            self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.VectorStoreDecl(
            name=name_tok.value or "",
            backend=backend,
            frame=frame_name,
            text_column=text_col,
            id_column=id_col,
            embedding_model=embedding_model,
            metadata_columns=metadata_columns,
            options=options,
            span=self._span(start),
        )

    def parse_graph(self) -> ast_nodes.GraphDecl:
        start = self.consume("KEYWORD", "graph")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'graph "{tok.value}": is not supported. Use graph is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'graph'", tok)
        name = name_tok.value or ""
        source_frame = None
        id_column = None
        text_column = None
        entities_cfg: ast_nodes.GraphEntitiesConfig | None = None
        relations_cfg: ast_nodes.GraphRelationsConfig | None = None
        storage_cfg: ast_nodes.GraphStorageConfig | None = None
        self.consume("COLON")
        self.consume("NEWLINE")
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                field_tok = self.consume_any({"KEYWORD", "IDENT"})
                field = field_tok.value or ""
                if field == "from":
                    if self.peek().value == "frame":
                        self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        frame_tok = self.consume_any({"STRING", "IDENT"})
                    else:
                        frame_tok = self.consume_any({"STRING", "IDENT"})
                    source_frame = frame_tok.value
                    self.optional_newline()
                    continue
                if field == "id_column":
                    if self.match_value("KEYWORD", "is"):
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    id_column = val_tok.value
                    self.optional_newline()
                    continue
                if field == "text_column":
                    if self.match_value("KEYWORD", "is"):
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    text_column = val_tok.value
                    self.optional_newline()
                    continue
                if field == "entities":
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    ent_model = None
                    ent_max = None
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            ent_field = self.consume_any({"KEYWORD", "IDENT"})
                            if ent_field.value == "model":
                                if self.match_value("KEYWORD", "is"):
                                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                ent_model = model_tok.value
                                self.optional_newline()
                                continue
                            if ent_field.value == "max_entities_per_doc":
                                if self.match_value("KEYWORD", "is"):
                                    ent_max = self.parse_expression()
                                else:
                                    ent_max = self.parse_expression()
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{ent_field.value}' in entities block", ent_field)
                        self.consume("DEDENT")
                    entities_cfg = ast_nodes.GraphEntitiesConfig(model=ent_model, max_entities_per_doc=ent_max, span=self._span(field_tok))
                    self.optional_newline()
                    continue
                if field == "relations":
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    rel_model = None
                    rel_max = None
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            rel_field = self.consume_any({"KEYWORD", "IDENT"})
                            if rel_field.value == "model":
                                if self.match_value("KEYWORD", "is"):
                                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                rel_model = model_tok.value
                                self.optional_newline()
                                continue
                            if rel_field.value == "max_relations_per_entity":
                                if self.match_value("KEYWORD", "is"):
                                    rel_max = self.parse_expression()
                                else:
                                    rel_max = self.parse_expression()
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{rel_field.value}' in relations block", rel_field)
                        self.consume("DEDENT")
                    relations_cfg = ast_nodes.GraphRelationsConfig(model=rel_model, max_relations_per_entity=rel_max, span=self._span(field_tok))
                    self.optional_newline()
                    continue
                if field == "storage":
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    nodes_frame = None
                    edges_frame = None
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            stor_field = self.consume_any({"KEYWORD", "IDENT"})
                            if stor_field.value == "nodes_frame":
                                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                nodes_frame = frame_tok.value
                                self.optional_newline()
                                continue
                            if stor_field.value == "edges_frame":
                                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                edges_frame = frame_tok.value
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{stor_field.value}' in storage block", stor_field)
                        self.consume("DEDENT")
                    storage_cfg = ast_nodes.GraphStorageConfig(nodes_frame=nodes_frame, edges_frame=edges_frame, span=self._span(field_tok))
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in graph block", field_tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.GraphDecl(
            name=name,
            source_frame=source_frame,
            id_column=id_column,
            text_column=text_column,
            entities=entities_cfg,
            relations=relations_cfg,
            storage=storage_cfg,
            span=self._span(start),
        )

    def parse_graph_summary(self) -> ast_nodes.GraphSummaryDecl:
        start = self.consume("KEYWORD", "graph_summary")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'graph_summary "{tok.value}": is not supported. Use graph_summary is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'graph_summary'", tok)
        name = name_tok.value or ""
        graph_name = None
        method = None
        max_nodes = None
        model = None
        self.consume("COLON")
        self.consume("NEWLINE")
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                field_tok = self.consume_any({"KEYWORD", "IDENT"})
                field = field_tok.value or ""
                if field == "graph":
                    if self.match_value("KEYWORD", "is"):
                        g_tok = self.consume_any({"STRING", "IDENT"})
                    else:
                        g_tok = self.consume_any({"STRING", "IDENT"})
                    graph_name = g_tok.value
                    self.optional_newline()
                    continue
                if field == "method":
                    if self.match_value("KEYWORD", "is"):
                        m_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        m_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    method = m_tok.value
                    self.optional_newline()
                    continue
                if field == "max_nodes_per_summary":
                    if self.match_value("KEYWORD", "is"):
                        max_nodes = self.parse_expression()
                    else:
                        max_nodes = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "model":
                    if self.match_value("KEYWORD", "is"):
                        model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    model = model_tok.value
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in graph_summary block", field_tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.GraphSummaryDecl(
            name=name,
            graph=graph_name,
            method=method,
            max_nodes_per_summary=max_nodes,
            model=model,
            span=self._span(start),
        )

    def parse_rag_evaluation(self) -> ast_nodes.RagEvaluationDecl:
        start = self.consume("KEYWORD", "rag")
        eval_tok = self.consume_any({"KEYWORD", "IDENT"})
        if (eval_tok.value or "") != "evaluation":
            raise self.error("Expected 'evaluation' after 'rag'.", eval_tok)
        if not self.match_value("KEYWORD", "is"):
            raise self.error('rag evaluation must use: rag evaluation is "Name":', self.peek())
        name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        pipeline_name: str | None = None
        dataset_frame: str | None = None
        question_column: str | None = None
        answer_column: str | None = None
        metrics: list[str] | None = None
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                field = tok.value or ""
                if field == "pipeline":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.peek().value == "is":
                        self.consume_any({"KEYWORD"})
                    p_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    pipeline_name = p_tok.value
                    self.optional_newline()
                    continue
                if field == "dataset":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        inner_tok = self.peek()
                        inner = inner_tok.value or ""
                        if inner == "from":
                            self.consume_any({"KEYWORD"})
                            next_tok = self.peek()
                            if next_tok.value == "frame":
                                self.consume_any({"KEYWORD", "IDENT"})
                            frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            dataset_frame = frame_tok.value
                            self.optional_newline()
                            continue
                        if inner == "question_column":
                            self.consume_any({"KEYWORD", "IDENT"})
                            if self.peek().value == "is":
                                self.consume_any({"KEYWORD"})
                            q_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            question_column = q_tok.value
                            self.optional_newline()
                            continue
                        if inner == "answer_column":
                            self.consume_any({"KEYWORD", "IDENT"})
                            if self.peek().value == "is":
                                self.consume_any({"KEYWORD"})
                            a_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            answer_column = a_tok.value
                            self.optional_newline()
                            continue
                        raise self.error(f"Unexpected field '{inner}' in dataset block", inner_tok)
                    self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if field == "metrics":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match("COLON"):
                        self.consume("NEWLINE")
                        self.consume("INDENT")
                        metrics_list: list[str] = []

                        def _append_metric(name: str) -> None:
                            if name not in metrics_list:
                                metrics_list.append(name)
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            if self.match("DASH"):
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            inner_tok = self.consume_any({"KEYWORD", "IDENT"})
                            if inner_tok.value == "measure":
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            if inner_tok.value == "measures":
                                if not self.match_value("KEYWORD", "are"):
                                    raise self.error("Use 'measures are [ ... ]' inside metrics.", inner_tok)
                                list_tok = self.peek()
                                if list_tok.type != "LBRACKET":
                                    raise self.error(
                                        'measures are expects a list of metric names like ["answer_correctness", "latency_seconds"].',
                                        list_tok,
                                    )
                                for itm in self._parse_string_list_literal(list_tok):
                                    _append_metric(itm)
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{inner_tok.value}' in metrics block", inner_tok)
                            self.optional_newline()
                        self.consume("DEDENT")
                        metrics = metrics_list
                        self.optional_newline()
                        continue
                    start_tok = self.peek()
                    if start_tok.type == "LBRACKET":
                        metrics = self._parse_string_list_literal(start_tok)
                    else:
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        metrics = [val_tok.value or ""]
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in rag evaluation block", tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RagEvaluationDecl(
            name=name_tok.value or "",
            pipeline=pipeline_name or "",
            dataset_frame=dataset_frame or "",
            question_column=question_column or "",
            answer_column=answer_column,
            metrics=metrics,
            span=self._span(start),
        )

    def parse_tool_evaluation(self) -> ast_nodes.ToolEvaluationDecl:
        start = self.consume("KEYWORD", "tool")
        eval_tok = self.consume_any({"KEYWORD", "IDENT"})
        if (eval_tok.value or "") != "evaluation":
            raise self.error("Expected 'evaluation' after 'tool'.", eval_tok)
        if not self.match_value("KEYWORD", "is"):
            raise self.error('tool evaluation must use: tool evaluation is "Name":', self.peek())
        name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        tool_name: str | None = None
        dataset_frame: str | None = None
        input_mapping: dict[str, str] = {}
        expected_cfg: ast_nodes.ToolExpectedConfig | None = None
        metrics: list[str] | None = None
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                field = tok.value or ""
                if field == "tool":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.peek().value == "is":
                        self.consume_any({"KEYWORD"})
                    t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    tool_name = t_tok.value
                    self.optional_newline()
                    continue
                if field in {"dataset_frame", "dataset"}:
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    dataset_frame = frame_tok.value
                    self.optional_newline()
                    continue
                if field == "input_mapping":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            self.consume("KEYWORD", "is")
                            col_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            input_mapping[key_tok.value or ""] = col_tok.value or ""
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if field == "expected":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    cfg = ast_nodes.ToolExpectedConfig()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            inner_tok = self.peek()
                            inner = inner_tok.value or ""
                            if inner == "status_column":
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                s_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.status_column = s_tok.value
                            elif inner in {"body_column", "text_column"}:
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                b_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.body_column = b_tok.value
                            else:
                                raise self.error(f"Unexpected field '{inner}' in expected block", inner_tok)
                            self.optional_newline()
                        self.consume("DEDENT")
                    expected_cfg = cfg
                    self.optional_newline()
                    continue
                if field == "metrics":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match("COLON"):
                        self.consume("NEWLINE")
                        self.consume("INDENT")
                        m_list: list[str] = []

                        def _append_metric(name: str) -> None:
                            if name not in m_list:
                                m_list.append(name)
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            if self.match("DASH"):
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            inner_tok = self.consume_any({"KEYWORD", "IDENT"})
                            if inner_tok.value == "measure":
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            if inner_tok.value == "measures":
                                if not self.match_value("KEYWORD", "are"):
                                    raise self.error("Use 'measures are [ ... ]' inside metrics.", inner_tok)
                                list_tok = self.peek()
                                if list_tok.type != "LBRACKET":
                                    raise self.error(
                                        'measures are expects a list of metric names like ["answer_correctness", "latency_seconds"].',
                                        list_tok,
                                    )
                                for itm in self._parse_string_list_literal(list_tok):
                                    _append_metric(itm)
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{inner_tok.value}' in metrics block", inner_tok)
                            self.optional_newline()
                        self.consume("DEDENT")
                        metrics = m_list
                        self.optional_newline()
                        continue
                    start_tok = self.peek()
                    if start_tok.type == "LBRACKET":
                        metrics = self._parse_string_list_literal(start_tok)
                    else:
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        metrics = [val_tok.value or ""]
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in tool evaluation block", tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.ToolEvaluationDecl(
            name=name_tok.value or "",
            tool=tool_name or "",
            dataset_frame=dataset_frame or "",
            input_mapping=input_mapping,
            expected=expected_cfg,
            metrics=metrics,
            span=self._span(start),
        )

    def parse_agent_evaluation(self) -> ast_nodes.AgentEvaluationDecl:
        start = self.consume("KEYWORD", "agent")
        eval_tok = self.consume_any({"KEYWORD", "IDENT"})
        if (eval_tok.value or "") != "evaluation":
            raise self.error("Expected 'evaluation' after 'agent'.", eval_tok)
        if not self.match_value("KEYWORD", "is"):
            raise self.error('agent evaluation must use: agent evaluation is "Name":', self.peek())
        name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        agent_name: str | None = None
        dataset_frame: str | None = None
        input_mapping: dict[str, str] = {}
        expected_cfg: ast_nodes.AgentExpectedConfig | None = None
        metrics: list[str] | None = None

        def _parse_bool(tok):
            return (tok.value or "").lower() in {"true", "yes", "on", "1"}

        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                field = tok.value or ""
                if field == "agent":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.peek().value == "is":
                        self.consume_any({"KEYWORD"})
                    a_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    agent_name = a_tok.value
                    self.optional_newline()
                    continue
                if field in {"dataset_frame", "dataset"}:
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    dataset_frame = frame_tok.value
                    self.optional_newline()
                    continue
                if field == "input_mapping":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            self.consume("KEYWORD", "is")
                            col_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            input_mapping[key_tok.value or ""] = col_tok.value or ""
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if field == "expected":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    cfg = ast_nodes.AgentExpectedConfig()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            inner_tok = self.peek()
                            inner = inner_tok.value or ""
                            if inner in {"answer_column", "expected_answer_column"}:
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                ans_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.answer_column = ans_tok.value
                            elif inner == "allow_llm_judge":
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                bool_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.allow_llm_judge = _parse_bool(bool_tok)
                            elif inner in {"judge_model", "judge"}:
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                j_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.judge_model = j_tok.value
                            elif inner in {"expected_tool_column", "tool_column", "expected_tools_column"}:
                                self.consume_any({"KEYWORD", "IDENT"})
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.expected_tool_column = t_tok.value
                            else:
                                raise self.error(f"Unexpected field '{inner}' in expected block", inner_tok)
                            self.optional_newline()
                        self.consume("DEDENT")
                    expected_cfg = cfg
                    self.optional_newline()
                    continue
                if field == "metrics":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match("COLON"):
                        self.consume("NEWLINE")
                        self.consume("INDENT")
                        m_list: list[str] = []

                        def _append_metric(name: str) -> None:
                            if name not in m_list:
                                m_list.append(name)
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            if self.match("DASH"):
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            inner_tok = self.consume_any({"KEYWORD", "IDENT"})
                            if inner_tok.value == "measure":
                                if self.peek().value == "is":
                                    self.consume_any({"KEYWORD"})
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                self.optional_newline()
                                continue
                            if inner_tok.value == "measures":
                                if not self.match_value("KEYWORD", "are"):
                                    raise self.error("Use 'measures are [ ... ]' inside metrics.", inner_tok)
                                list_tok = self.peek()
                                if list_tok.type != "LBRACKET":
                                    raise self.error(
                                        'measures are expects a list of metric names like ["answer_correctness", "latency_seconds"].',
                                        list_tok,
                                    )
                                for itm in self._parse_string_list_literal(list_tok):
                                    _append_metric(itm)
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{inner_tok.value}' in metrics block", inner_tok)
                            self.optional_newline()
                        self.consume("DEDENT")
                        metrics = m_list
                        self.optional_newline()
                        continue
                    start_tok = self.peek()
                    if start_tok.type == "LBRACKET":
                        metrics = self._parse_string_list_literal(start_tok)
                    else:
                        val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        metrics = [val_tok.value or ""]
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in agent evaluation block", tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.AgentEvaluationDecl(
            name=name_tok.value or "",
            agent=agent_name or "",
            dataset_frame=dataset_frame or "",
            input_mapping=input_mapping,
            expected=expected_cfg,
            metrics=metrics,
            span=self._span(start),
        )

    def parse_rag_pipeline(self) -> ast_nodes.RagPipelineDecl:
        start = self.consume("KEYWORD", "rag")
        self.consume("KEYWORD", "pipeline")
        if not self.match_value("KEYWORD", "is"):
            raise self.error('rag pipeline must use: rag pipeline is "Name":', self.peek())
        name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        stages: list[ast_nodes.RagPipelineStageDecl] = []
        default_vector_store: str | None = None
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                if tok.value == "use":
                    self.consume("KEYWORD", "use")
                    if self.match_value("KEYWORD", "vector_store"):
                        vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        default_vector_store = vs_tok.value
                        self.optional_newline()
                        continue
                    raise self.error("I expected 'vector_store' after 'use' in a rag pipeline.", tok)
                if tok.value == "stage":
                    stages.append(self._parse_rag_stage())
                    continue
                raise self.error(f"Unexpected field '{tok.value}' in rag pipeline block", tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RagPipelineDecl(
            name=name_tok.value or "",
            default_vector_store=default_vector_store,
            stages=stages,
            span=self._span(start),
        )

    def _parse_rag_stage(self) -> ast_nodes.RagPipelineStageDecl:
        start = self.consume("KEYWORD", "stage")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            name_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        stage_type: str | None = None
        ai_name: str | None = None
        vector_store: str | None = None
        stage_frame: str | None = None
        match_column: str | None = None
        max_rows_expr: ast_nodes.Expr | None = None
        group_by_col: str | None = None
        max_groups_expr: ast_nodes.Expr | None = None
        max_rows_per_group_expr: ast_nodes.Expr | None = None
        image_column: str | None = None
        text_column: str | None = None
        embedding_model: str | None = None
        output_vector_store: str | None = None
        max_items_expr: ast_nodes.Expr | None = None
        graph_name: str | None = None
        graph_summary_name: str | None = None
        top_k: ast_nodes.Expr | None = None
        where_expr: ast_nodes.Expr | None = None
        max_tokens: ast_nodes.Expr | None = None
        choices: list[str] | None = None
        max_queries: ast_nodes.Expr | None = None
        max_subquestions: ast_nodes.Expr | None = None
        from_stages: list[str] | None = None
        method: str | None = None
        max_hops: ast_nodes.Expr | None = None
        max_nodes: ast_nodes.Expr | None = None
        strategy: str | None = None
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                field_tok = self.consume_any({"KEYWORD", "IDENT"})
                field = field_tok.value or ""
                if field == "type":
                    if not self.match_value("KEYWORD", "is"):
                        raise self.error("Use 'type is \"...\"' inside a rag pipeline stage.", field_tok)
                    type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    stage_type = type_tok.value
                    self.optional_newline()
                    continue
                if field == "ai":
                    if self.match_value("KEYWORD", "is"):
                        ai_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        ai_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    ai_name = ai_tok.value
                    self.optional_newline()
                    continue
                if field == "vector_store":
                    if self.match_value("KEYWORD", "is"):
                        vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    vector_store = vs_tok.value
                    self.optional_newline()
                    continue
                if field == "frame":
                    if self.match_value("KEYWORD", "is"):
                        f_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        f_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    stage_frame = f_tok.value
                    self.optional_newline()
                    continue
                if field == "match_column":
                    if self.match_value("KEYWORD", "is"):
                        m_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        m_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    match_column = m_tok.value
                    self.optional_newline()
                    continue
                if field == "max_rows":
                    if self.match_value("KEYWORD", "is"):
                        max_rows_expr = self.parse_expression()
                    else:
                        max_rows_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "group_by":
                    if self.match_value("KEYWORD", "is"):
                        g_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        g_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    group_by_col = g_tok.value
                    self.optional_newline()
                    continue
                if field == "max_groups":
                    if self.match_value("KEYWORD", "is"):
                        max_groups_expr = self.parse_expression()
                    else:
                        max_groups_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "max_rows_per_group":
                    if self.match_value("KEYWORD", "is"):
                        max_rows_per_group_expr = self.parse_expression()
                    else:
                        max_rows_per_group_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "image_column":
                    if self.match_value("KEYWORD", "is"):
                        i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    image_column = i_tok.value
                    self.optional_newline()
                    continue
                if field == "text_column":
                    if self.match_value("KEYWORD", "is"):
                        t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    text_column = t_tok.value
                    self.optional_newline()
                    continue
                if field == "embedding_model":
                    if self.match_value("KEYWORD", "is"):
                        e_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        e_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    embedding_model = e_tok.value
                    self.optional_newline()
                    continue
                if field == "output_vector_store":
                    if self.match_value("KEYWORD", "is"):
                        o_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        o_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    output_vector_store = o_tok.value
                    self.optional_newline()
                    continue
                if field == "max_items":
                    if self.match_value("KEYWORD", "is"):
                        max_items_expr = self.parse_expression()
                    else:
                        max_items_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "graph":
                    if self.match_value("KEYWORD", "is"):
                        g_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        g_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    graph_name = g_tok.value
                    self.optional_newline()
                    continue
                if field == "graph_summary":
                    if self.match_value("KEYWORD", "is"):
                        gs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        gs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    graph_summary_name = gs_tok.value
                    self.optional_newline()
                    continue
                if field == "top_k":
                    if self.match_value("KEYWORD", "is"):
                        top_k = self.parse_expression()
                    else:
                        top_k = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "max_tokens":
                    if self.match_value("KEYWORD", "is"):
                        max_tokens = self.parse_expression()
                    else:
                        max_tokens = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "where":
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    where_expr = self._parse_expression_block()
                    self.optional_newline()
                    continue
                if field == "choices":
                    if self.peek().value in {"are", "is"}:
                        self.consume_any({"KEYWORD", "IDENT"})
                    start_tok = self.peek()
                    if start_tok.type == "STRING":
                        choices = [self.consume("STRING").value or ""]
                    else:
                        choices = self._parse_string_list_literal(start_tok)
                    self.optional_newline()
                    continue
                if field == "max_queries":
                    if self.match_value("KEYWORD", "is"):
                        max_queries = self.parse_expression()
                    else:
                        max_queries = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "max_subquestions":
                    if self.match_value("KEYWORD", "is"):
                        max_subquestions = self.parse_expression()
                    else:
                        max_subquestions = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "from":
                    next_tok = self.peek()
                    if next_tok.value == "stages":
                        self.consume_any({"KEYWORD", "IDENT"})
                    if self.peek().value in {"are", "is"}:
                        self.consume_any({"KEYWORD", "IDENT"})
                    start_tok = self.peek()
                    if start_tok.type == "STRING":
                        from_stages = [self.consume("STRING").value or ""]
                    else:
                        from_stages = self._parse_string_list_literal(start_tok)
                    self.optional_newline()
                    continue
                if field == "method":
                    if self.match_value("KEYWORD", "is"):
                        method_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        method_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    method = method_tok.value
                    self.optional_newline()
                    continue
                if field == "max_hops":
                    if self.match_value("KEYWORD", "is"):
                        max_hops = self.parse_expression()
                    else:
                        max_hops = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "max_nodes":
                    if self.match_value("KEYWORD", "is"):
                        max_nodes = self.parse_expression()
                    else:
                        max_nodes = self.parse_expression()
                    self.optional_newline()
                    continue
                if field == "strategy":
                    if self.match_value("KEYWORD", "is"):
                        strat_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        strat_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    strategy = strat_tok.value
                    self.optional_newline()
                    continue
                raise self.error(f"Unexpected field '{field}' in stage block", field_tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.RagPipelineStageDecl(
            name=name_tok.value or "",
            type=stage_type or "",
            ai=ai_name,
            vector_store=vector_store,
            frame=stage_frame,
            match_column=match_column,
            max_rows=max_rows_expr,
            group_by=group_by_col,
            max_groups=max_groups_expr,
            max_rows_per_group=max_rows_per_group_expr,
            image_column=image_column,
            text_column=text_column,
            embedding_model=embedding_model,
            output_vector_store=output_vector_store,
            max_items=max_items_expr,
            graph=graph_name,
            graph_summary=graph_summary_name,
            top_k=top_k,
            where=where_expr,
            max_tokens=max_tokens,
            choices=choices,
            max_queries=max_queries,
            max_subquestions=max_subquestions,
            from_stages=from_stages,
            method=method,
            max_hops=max_hops,
            max_nodes=max_nodes,
            strategy=strategy,
            span=self._span(start),
        )

    def parse_tool(self) -> ast_nodes.ToolDeclaration:
        start = self.consume("KEYWORD", "tool")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume_any({"STRING", "IDENT"})
        else:
            tok = self.peek()
            if tok.type in {"STRING", "IDENT"}:
                raise self.error(f'tool "{tok.value}": is not supported. Use tool is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'tool'", tok)
        name = name_tok.value or ""
        kind = None
        method = None
        url_template = None
        url_expr: ast_nodes.Expr | None = None
        query_template: ast_nodes.Expr | None = None
        headers: dict[str, ast_nodes.Expr] = {}
        query_params: dict[str, ast_nodes.Expr] = {}
        body_fields: dict[str, ast_nodes.Expr] = {}
        body_template: ast_nodes.Expr | None = None
        variables: dict[str, ast_nodes.Expr] = {}
        input_fields: list[str] = []
        timeout_expr: ast_nodes.Expr | None = None
        retry_cfg: ast_nodes.ToolRetryConfig | None = None
        auth_cfg: ast_nodes.ToolAuthConfig | None = None
        response_schema: ast_nodes.ResponseSchema | None = None
        logging_level: str | None = None
        rate_limit_cfg: ast_nodes.ToolRateLimitConfig | None = None
        multipart_expr: ast_nodes.Expr | None = None
        query_encoding: str | None = None
        function_path: str | None = None
        self.consume("COLON")
        self.consume("NEWLINE")
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                tok = self.peek()
                if tok.value == "kind":
                    self.consume("KEYWORD", "kind")
                    if self.match_value("KEYWORD", "is"):
                        kind_tok = self.consume_any({"STRING", "IDENT"})
                    else:
                        kind_tok = self.consume_any({"STRING", "IDENT"})
                    kind = kind_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "method":
                    self.consume("KEYWORD", "method")
                    if self.match_value("KEYWORD", "is"):
                        method_tok = self.consume_any({"STRING", "IDENT"})
                    else:
                        method_tok = self.consume_any({"STRING", "IDENT"})
                    method = method_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "url_template":
                    self.consume("KEYWORD", "url_template")
                    if self.match_value("KEYWORD", "is"):
                        url_tok = self.consume_any({"STRING"})
                    else:
                        url_tok = self.consume_any({"STRING"})
                    url_template = url_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "url":
                    self.consume("KEYWORD", "url")
                    if self.match_value("KEYWORD", "is"):
                        url_expr = self.parse_expression()
                    else:
                        url_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if tok.value == "query_template":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        query_template = self.parse_expression()
                    else:
                        query_template = self.parse_expression()
                    self.optional_newline()
                    continue
                if tok.value == "timeout":
                    self.consume("KEYWORD", "timeout")
                    if self.match_value("KEYWORD", "is"):
                        timeout_expr = self._parse_duration_value()
                    else:
                        timeout_expr = self._parse_duration_value()
                    self.optional_newline()
                    continue
                if tok.value == "multipart":
                    self.consume("KEYWORD", "multipart")
                    if self.match_value("KEYWORD", "is"):
                        multipart_expr = self.parse_expression()
                    else:
                        multipart_expr = self.parse_expression()
                    self.optional_newline()
                    continue
                if tok.value == "query_encoding":
                    self.consume("KEYWORD", "query_encoding")
                    if self.match_value("KEYWORD", "is"):
                        q_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        q_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    query_encoding = q_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "function":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "is"):
                        func_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        func_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    function_path = func_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "body_template":
                    self.consume("KEYWORD", "body_template")
                    if self.match_value("KEYWORD", "is"):
                        body_template = self.parse_expression()
                    else:
                        body_template = self.parse_expression()
                    self.optional_newline()
                    continue
                if tok.value == "logging":
                    self.consume("KEYWORD", "logging")
                    if self.match_value("KEYWORD", "is"):
                        log_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    else:
                        log_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    logging_level = log_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "retry":
                    self.consume("KEYWORD", "retry")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    cfg = ast_nodes.ToolRetryConfig()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            field_tok = self.consume_any({"KEYWORD", "IDENT"})
                            field_name = field_tok.value or ""
                            if field_name == "max_attempts":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.max_attempts = self.parse_expression()
                                else:
                                    cfg.max_attempts = self.parse_expression()
                            elif field_name == "backoff":
                                if self.match_value("KEYWORD", "is"):
                                    backoff_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    backoff_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.backoff = backoff_tok.value
                            elif field_name in {"initial_delay", "max_delay"}:
                                if self.match_value("KEYWORD", "is"):
                                    delay_expr = self._parse_duration_value()
                                else:
                                    delay_expr = self._parse_duration_value()
                                if field_name == "initial_delay":
                                    cfg.initial_delay = delay_expr
                                else:
                                    cfg.max_delay = delay_expr
                            elif field_name == "jitter":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.jitter = self.parse_expression()
                                else:
                                    cfg.jitter = self.parse_expression()
                            elif field_name in {"retry_on_status", "retry_on_statuses"}:
                                if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                                    cfg.retry_on_status = self.parse_expression()
                                else:
                                    cfg.retry_on_status = self.parse_expression()
                            elif field_name == "retry_on_exceptions":
                                if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                                    cfg.retry_on_exceptions = self.parse_expression()
                                else:
                                    cfg.retry_on_exceptions = self.parse_expression()
                            elif field_name == "allow_unsafe":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.allow_unsafe = self.parse_expression()
                                else:
                                    cfg.allow_unsafe = self.parse_expression()
                            else:
                                raise self.error(
                                    f"Unexpected field '{field_name}' in retry block",
                                    field_tok,
                                )
                            self.optional_newline()
                        self.consume("DEDENT")
                    retry_cfg = cfg
                    self.optional_newline()
                    continue
                if tok.value == "rate_limit":
                    self.consume("KEYWORD", "rate_limit")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    cfg = ast_nodes.ToolRateLimitConfig()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            field_tok = self.consume_any({"KEYWORD", "IDENT"})
                            field_name = field_tok.value or ""
                            if field_name == "max_calls_per_minute":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.max_calls_per_minute = self.parse_expression()
                                else:
                                    cfg.max_calls_per_minute = self.parse_expression()
                            elif field_name == "max_calls_per_second":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.max_calls_per_second = self.parse_expression()
                                else:
                                    cfg.max_calls_per_second = self.parse_expression()
                            elif field_name == "burst":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.burst = self.parse_expression()
                                else:
                                    cfg.burst = self.parse_expression()
                            else:
                                raise self.error(
                                    f"Unexpected field '{field_name}' in rate_limit block",
                                    field_tok,
                                )
                            self.optional_newline()
                        self.consume("DEDENT")
                    rate_limit_cfg = cfg
                    self.optional_newline()
                    continue
                if tok.value == "response_schema":
                    self.consume("KEYWORD", "response_schema")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    schema = ast_nodes.ResponseSchema()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            field_tok = self.consume_any({"KEYWORD", "IDENT"})
                            field_name = field_tok.value or ""
                            if field_name == "type":
                                if self.match_value("KEYWORD", "is"):
                                    type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                schema.type = type_tok.value
                            elif field_name == "required":
                                if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                                    pass
                                start_list = self.peek()
                                schema.required = self._parse_string_list_literal(start_list)
                            elif field_name == "properties":
                                self.consume("COLON")
                                self.consume("NEWLINE")
                                props: dict[str, ast_nodes.SimpleTypeSchema] = {}
                                if self.check("INDENT"):
                                    self.consume("INDENT")
                                    while not self.check("DEDENT"):
                                        if self.match("NEWLINE"):
                                            continue
                                        prop_name_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                                        self.consume("COLON")
                                        prop_schema = ast_nodes.SimpleTypeSchema()
                                        self.consume("NEWLINE")
                                        if self.check("INDENT"):
                                            self.consume("INDENT")
                                            while not self.check("DEDENT"):
                                                if self.match("NEWLINE"):
                                                    continue
                                                inner_field = self.consume_any({"KEYWORD", "IDENT"})
                                                inner_name = inner_field.value or ""
                                                if inner_name == "type":
                                                    if self.match_value("KEYWORD", "is"):
                                                        type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                                    else:
                                                        type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                                    prop_schema.type = type_tok.value
                                                else:
                                                    raise self.error(
                                                        f"Unexpected field '{inner_name}' in response_schema properties",
                                                        inner_field,
                                                    )
                                                self.optional_newline()
                                            self.consume("DEDENT")
                                        props[prop_name_tok.value or ""] = prop_schema
                                        self.optional_newline()
                                    self.consume("DEDENT")
                                schema.properties = props
                            else:
                                raise self.error(
                                    f"Unexpected field '{field_name}' in response_schema block",
                                    field_tok,
                                )
                            self.optional_newline()
                        self.consume("DEDENT")
                    response_schema = schema
                    self.optional_newline()
                    continue
                if tok.value == "input_fields":
                    self.consume_any({"KEYWORD", "IDENT"})
                    if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                        pass
                    start_tok = self.peek()
                    input_fields = self._parse_string_list_literal(start_tok)
                    self.optional_newline()
                    continue
                if tok.value == "auth":
                    self.consume("KEYWORD", "auth")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    cfg = ast_nodes.ToolAuthConfig()
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            field_tok = self.consume_any({"KEYWORD", "IDENT"})
                            field_name = field_tok.value or ""
                            if field_name == "kind":
                                if self.match_value("KEYWORD", "is"):
                                    kind_tok = self.consume_any({"STRING", "IDENT"})
                                else:
                                    kind_tok = self.consume_any({"STRING", "IDENT"})
                                cfg.kind = kind_tok.value
                            elif field_name == "token":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.token = self.parse_expression()
                                else:
                                    cfg.token = self.parse_expression()
                            elif field_name == "username":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.username = self.parse_expression()
                                else:
                                    cfg.username = self.parse_expression()
                            elif field_name == "password":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.password = self.parse_expression()
                                else:
                                    cfg.password = self.parse_expression()
                            elif field_name == "location":
                                if self.match_value("KEYWORD", "is"):
                                    loc_tok = self.consume_any({"STRING", "IDENT"})
                                else:
                                    loc_tok = self.consume_any({"STRING", "IDENT"})
                                cfg.location = loc_tok.value
                            elif field_name == "name":
                                if self.match_value("KEYWORD", "is"):
                                    name_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    name_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.name = name_tok.value
                            elif field_name == "value":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.value = self.parse_expression()
                                else:
                                    cfg.value = self.parse_expression()
                            elif field_name == "token_url":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.token_url = self.parse_expression()
                                else:
                                    cfg.token_url = self.parse_expression()
                            elif field_name == "client_id":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.client_id = self.parse_expression()
                                else:
                                    cfg.client_id = self.parse_expression()
                            elif field_name == "client_secret":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.client_secret = self.parse_expression()
                                else:
                                    cfg.client_secret = self.parse_expression()
                            elif field_name == "scopes":
                                if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                                    pass
                                start_tok = self.peek()
                                cfg.scopes = self._parse_string_list_literal(start_tok)
                            elif field_name == "audience":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.audience = self.parse_expression()
                                else:
                                    cfg.audience = self.parse_expression()
                            elif field_name == "cache":
                                if self.match_value("KEYWORD", "is"):
                                    cache_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    cache_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.cache = cache_tok.value
                            elif field_name == "issuer":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.issuer = self.parse_expression()
                                else:
                                    cfg.issuer = self.parse_expression()
                            elif field_name == "subject":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.subject = self.parse_expression()
                                else:
                                    cfg.subject = self.parse_expression()
                            elif field_name == "private_key":
                                if self.match_value("KEYWORD", "is"):
                                    cfg.private_key = self.parse_expression()
                                else:
                                    cfg.private_key = self.parse_expression()
                            elif field_name == "algorithm":
                                if self.match_value("KEYWORD", "is"):
                                    alg_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    alg_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                cfg.algorithm = alg_tok.value
                            elif field_name == "claims":
                                self.consume("COLON")
                                self.consume("NEWLINE")
                                if self.check("INDENT"):
                                    self.consume("INDENT")
                                    while not self.check("DEDENT"):
                                        if self.match("NEWLINE"):
                                            continue
                                        claim_key = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                                        self.consume("COLON")
                                        cfg.claims[claim_key.value or ""] = self.parse_expression()
                                        self.optional_newline()
                                    self.consume("DEDENT")
                            else:
                                raise self.error(
                                    f"Unexpected field '{field_name}' in auth block",
                                    field_tok,
                                )
                            self.optional_newline()
                        self.consume("DEDENT")
                    auth_cfg = cfg
                    self.optional_newline()
                    continue
                if tok.value == "headers":
                    self.consume("KEYWORD", "headers")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            self.consume("COLON")
                            expr = self.parse_expression()
                            headers[key_tok.value or ""] = expr
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if tok.value == "query":
                    self.consume("KEYWORD", "query")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            self.consume("COLON")
                            expr = self.parse_expression()
                            query_params[key_tok.value or ""] = expr
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if tok.value == "variables":
                    self.consume_any({"KEYWORD", "IDENT"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            if self.match_value("KEYWORD", "is"):
                                expr = self.parse_expression()
                            else:
                                if self.match("COLON"):
                                    pass
                                expr = self.parse_expression()
                            variables[key_tok.value or ""] = expr
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if tok.value == "body":
                    self.consume("KEYWORD", "body")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            key_tok = self.consume_any({"IDENT", "STRING", "KEYWORD"})
                            self.consume("COLON")
                            expr = self.parse_expression()
                            body_fields[key_tok.value or ""] = expr
                            self.optional_newline()
                        self.consume("DEDENT")
                    self.optional_newline()
                    continue
                if self.match("NEWLINE"):
                    continue
                raise ParseError(f"Unexpected token in tool declaration: {tok.value}")
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.ToolDeclaration(
            name=name,
            kind=kind,
            method=method,
            url_template=url_template,
            url_expr=url_expr,
            query_template=query_template,
            headers=headers,
            query_params=query_params,
            body_fields=body_fields,
            body_template=body_template,
            variables=variables,
            input_fields=input_fields,
            timeout=timeout_expr,
            retry=retry_cfg,
            auth=auth_cfg,
            response_schema=response_schema,
            logging=logging_level,
            rate_limit=rate_limit_cfg,
            multipart=multipart_expr,
            query_encoding=query_encoding,
            function=function_path,
            span=self._span(start),
        )

    def parse_frame(self) -> ast_nodes.FrameDecl:
        start = self.consume("KEYWORD", "frame")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'frame "{tok.value}": is not supported. Use frame is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'frame'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")

        source_kind = None
        source_path = None
        backend = None
        url_expr: ast_nodes.Expr | None = None
        table = None
        primary_key = None
        delimiter = None
        has_headers = False
        select_cols: list[str] = []
        where_expr = None
        seen_source = False
        table_cfg: ast_nodes.FrameTableConfig | None = None

        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                if tok.value == "source":
                    if seen_source:
                        raise self.error("N3F-1001: invalid frame configuration", tok)
                    seen_source = True
                    self.consume("KEYWORD", "source")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        inner = self.peek()
                        if inner.value == "from":
                            self.consume("KEYWORD", "from")
                            if self.peek().value == "file":
                                self.consume("KEYWORD", "file")
                                source_kind = "file"
                            else:
                                raise self.error("N3F-1001: invalid frame configuration", self.peek())
                            path_tok = self.consume("STRING")
                            source_path = path_tok.value
                            self.optional_newline()
                            continue
                        if inner.value == "backend":
                            self.consume("KEYWORD", "backend")
                            if self.match_value("KEYWORD", "is"):
                                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            backend = backend_tok.value
                            source_kind = "backend"
                            self.optional_newline()
                            continue
                        if inner.value == "url":
                            self.consume("KEYWORD", "url")
                            if self.match_value("KEYWORD", "is"):
                                url_expr = self.parse_expression()
                            else:
                                url_expr = self.parse_expression()
                            self.optional_newline()
                            continue
                        if inner.value == "table":
                            self.consume("KEYWORD", "table")
                            if self.match_value("KEYWORD", "is"):
                                table_tok = self.consume("STRING")
                            else:
                                table_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            table = table_tok.value
                            self.optional_newline()
                            continue
                        if inner.value == "primary_key":
                            self.consume("KEYWORD", "primary_key")
                            pk_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            primary_key = pk_tok.value
                            self.optional_newline()
                            continue
                        if inner.value == "delimiter":
                            self.consume("KEYWORD", "delimiter")
                            if self.match_value("KEYWORD", "is"):
                                delim_tok = self.consume("STRING")
                            else:
                                delim_tok = self.consume("STRING")
                            delimiter = delim_tok.value or ","
                            self.optional_newline()
                            continue
                        if inner.value == "has":
                            self.consume("KEYWORD", "has")
                            if self.peek().value != "headers":
                                raise self.error("N3F-1001: invalid frame configuration", self.peek())
                            self.consume("KEYWORD", "headers")
                            has_headers = True
                            self.optional_newline()
                            continue
                        raise self.error("N3F-1001: invalid frame configuration", inner)
                    self.consume("DEDENT")
                    continue
                if tok.value == "table":
                    self.consume("KEYWORD", "table")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    pk_val = None
                    display_cols: list[str] = []
                    time_col = None
                    text_col = None
                    image_col = None
                    if self.check("INDENT"):
                        self.consume("INDENT")
                        while not self.check("DEDENT"):
                            if self.match("NEWLINE"):
                                continue
                            t_field_tok = self.consume_any({"KEYWORD", "IDENT"})
                            t_field = t_field_tok.value or ""
                            if t_field == "primary_key":
                                if self.match_value("KEYWORD", "is"):
                                    pk_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    pk_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                pk_val = pk_tok.value
                                self.optional_newline()
                                continue
                            if t_field == "display_columns":
                                if self.peek().value in {"are", "is"}:
                                    self.consume_any({"KEYWORD", "IDENT"})
                                start_tok = self.peek()
                                display_cols = self._parse_string_list_literal(start_tok)
                                self.optional_newline()
                                continue
                            if t_field == "time_column":
                                if self.match_value("KEYWORD", "is"):
                                    t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                time_col = t_tok.value
                                self.optional_newline()
                                continue
                            if t_field == "text_column":
                                if self.match_value("KEYWORD", "is"):
                                    t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    t_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                text_col = t_tok.value
                                self.optional_newline()
                                continue
                            if t_field == "image_column":
                                if self.match_value("KEYWORD", "is"):
                                    i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                else:
                                    i_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                image_col = i_tok.value
                                self.optional_newline()
                                continue
                            raise self.error(f"Unexpected field '{t_field}' in table block", t_field_tok)
                        self.consume("DEDENT")
                    table_cfg = ast_nodes.FrameTableConfig(
                        primary_key=pk_val,
                        display_columns=display_cols,
                        time_column=time_col,
                        text_column=text_col,
                        image_column=image_col,
                        span=self._span(tok),
                    )
                    self.optional_newline()
                    continue
                if tok.value == "select":
                    self.consume("KEYWORD", "select")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    self.consume("KEYWORD", "columns")
                    if self.peek().value in {"are", "is"}:
                        self.consume_any({"KEYWORD", "IDENT"})
                    start_list_token = self.peek()
                    select_cols = self._parse_string_list_literal(start_list_token)
                    self.optional_newline()
                    self.consume("DEDENT")
                    continue
                if tok.value == "where":
                    self.consume("KEYWORD", "where")
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    where_expr = self._parse_expression_block()
                    self.optional_newline()
                    continue
                raise self.error("N3F-1001: invalid frame configuration", tok)
            self.consume("DEDENT")
        self.optional_newline()

        return ast_nodes.FrameDecl(
            name=name_tok.value or "",
            source_kind=source_kind,
            source_path=source_path,
            backend=backend,
            url=url_expr,
            table=table,
            primary_key=primary_key or (table_cfg.primary_key if table_cfg else None),
            delimiter=delimiter,
            has_headers=has_headers,
            select_cols=select_cols,
            where=where_expr,
            table_config=table_cfg,
            span=self._span(start),
        )

    def _parse_string_list_literal(self, start_token) -> list[str]:
        lit = self.parse_list_literal()
        values: list[str] = []
        for item in lit.items:
            if isinstance(item, ast_nodes.Literal) and isinstance(item.value, str):
                values.append(item.value)
            elif isinstance(item, ast_nodes.Identifier):
                values.append(item.name)
            else:
                raise self.error("Columns must be specified as a list of strings.", start_token)
        return values

    def _parse_expression_block(self) -> ast_nodes.Expr:
        start_tok = self.peek()
        tokens: list[Token] = []
        depth = 1
        while depth > 0:
            tok = self.advance()
            if tok.type == "INDENT":
                depth += 1
                continue
            if tok.type == "DEDENT":
                depth -= 1
                if depth == 0:
                    break
                continue
            if tok.type == "NEWLINE":
                continue
            tokens.append(tok)
        if not tokens:
            raise self.error("I expected an expression inside this block.", start_tok)
        tokens.append(Token("EOF", None, tokens[-1].line, tokens[-1].column))
        sub_parser = Parser(tokens)
        return sub_parser.parse_expression()

    def parse_macro(self) -> ast_nodes.MacroDecl:
        start = self.consume("KEYWORD", "macro")
        name_tok = self.consume("STRING")
        self.consume("KEYWORD", "using")
        self.consume("KEYWORD", "ai")
        model_tok = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        description = None
        version = None
        sample = None
        params: list[str] = []
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.consume_any({"KEYWORD"})
                if tok.value == "description":
                    desc_tok = self.consume("STRING")
                    description = desc_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "version":
                    if self.match_value("KEYWORD", "is"):
                        pass
                    ver_tok = self.consume("STRING")
                    version = ver_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "sample":
                    sample_tok = self.consume("STRING")
                    sample = sample_tok.value
                    self.optional_newline()
                    continue
                if tok.value == "parameters":
                    params = []
                    while True:
                        p_tok = self.consume_any({"IDENT", "KEYWORD"})
                        params.append(p_tok.value or "")
                        if self.match("COMMA"):
                            continue
                        break
                    self.optional_newline()
                    continue
                raise self.error("N3M-1002: invalid macro clause", tok)
            self.consume("DEDENT")
        self.optional_newline()
        if not description:
            raise self.error("N3M-1000: macro missing description", start)
        return ast_nodes.MacroDecl(
            name=name_tok.value or "",
            ai_model=model_tok.value or "",
            version=version,
            description=description,
            sample=sample,
            parameters=params,
            span=self._span(start),
        )

    def parse_macro_test(self) -> ast_nodes.MacroTestDecl:
        start = self.consume("KEYWORD", "macro")
        self.consume("KEYWORD", "test")
        if self.match_value("KEYWORD", "is"):
            name_tok = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'macro test "{tok.value}": is not supported. Use macro test is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'macro test'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")
        uses: list[ast_nodes.MacroUse] = []
        expects: list[ast_nodes.MacroExpectation] = []
        if self.check("INDENT"):
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                if tok.value == "use":
                    use_tok = self.consume("KEYWORD", "use")
                    uses.append(self.parse_macro_use(use_tok))
                    continue
                if tok.value == "expect":
                    self.consume("KEYWORD", "expect")
                    kind_tok = self.consume_any({"KEYWORD", "IDENT"})
                    kind = (kind_tok.value or "").lower()
                    if kind not in {"record", "flow", "page"}:
                        raise self.error("Expected record, flow, or page after expect", kind_tok)
                    name_tok = self.consume("STRING")
                    expects.append(
                        ast_nodes.MacroExpectation(
                            kind=kind,
                            name=name_tok.value or "",
                            span=self._span(kind_tok),
                        )
                    )
                    self.optional_newline()
                    continue
                raise self.error("Invalid statement inside macro test block", tok)
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.MacroTestDecl(
            name=name_tok.value or "",
            uses=uses,
            expects=expects,
            span=self._span(start),
        )

    def parse_macro_use(self, start_tok) -> ast_nodes.MacroUse:
        self.consume("KEYWORD", "macro")
        name_tok = self.consume("STRING")
        args: dict[str, ast_nodes.Expr | Any] = {}
        if self.peek().value == "with":
            self.consume("KEYWORD", "with")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                if key_tok.value == "fields" and self.peek().type == "COLON":
                    args[key_tok.value or "fields"] = self._parse_macro_fields_block()
                else:
                    if not self.match_value("KEYWORD", "is") and not self.match_value("KEYWORD", "are"):
                        raise self.error(
                            f"Expected 'is' after {key_tok.value} in macro arguments. Use '{key_tok.value} is \"value\"' instead.",
                            self.peek(),
                        )
                    value_expr = self.parse_expression()
                    args[key_tok.value or ""] = value_expr
                self.optional_newline()
            self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.MacroUse(macro_name=name_tok.value or "", args=args, span=self._span(start_tok))

    def _parse_macro_fields_block(self) -> list[ast_nodes.MacroFieldSpec]:
        fields: list[ast_nodes.MacroFieldSpec] = []
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            start_tok = self.consume("KEYWORD")
            if start_tok.value != "field":
                raise self.error("Expected 'field is \"name\":' inside fields block.", start_tok)
            if not self.match_value("KEYWORD", "is"):
                raise self.error("Expected 'is' after field in fields block.", self.peek())
            name_tok = self.consume("STRING")
            if not self.match("COLON"):
                raise self.error("Expected ':' after field name.", self.peek())
            self.consume("NEWLINE")
            if not self.check("INDENT"):
                raise self.error("Field block must be indented.", self.peek())
            self.consume("INDENT")
            field_type = None
            required = None
            min_expr = None
            max_expr = None
            default_expr = None
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                inner_tok = self.consume_any({"KEYWORD", "IDENT"})
                if inner_tok.value == "type":
                    if self.match_value("KEYWORD", "is"):
                        type_tok = self.consume_any({"STRING", "IDENT"})
                    else:
                        type_tok = self.consume_any({"STRING", "IDENT"})
                    field_type = type_tok.value
                elif inner_tok.value == "required":
                    self.consume("KEYWORD", "is")
                    val_tok = self.consume_any({"IDENT", "KEYWORD"})
                    if val_tok.value not in {"true", "false"}:
                        raise self.error("required must be true or false", val_tok)
                    required = True if val_tok.value == "true" else False
                elif inner_tok.value == "min":
                    self.consume("KEYWORD", "is")
                    min_expr = self.parse_expression()
                elif inner_tok.value == "max":
                    self.consume("KEYWORD", "is")
                    max_expr = self.parse_expression()
                elif inner_tok.value == "default":
                    self.consume("KEYWORD", "is")
                    default_expr = self.parse_expression()
                else:
                    raise self.error(f"Unexpected field property '{inner_tok.value}'", inner_tok)
                self.optional_newline()
            self.consume("DEDENT")
            self.optional_newline()
            fields.append(
                ast_nodes.MacroFieldSpec(
                    name=name_tok.value or "",
                    field_type=field_type,
                    required=required,
                    min_expr=min_expr,
                    max_expr=max_expr,
                    default_expr=default_expr,
                    span=self._span(start_tok),
                )
            )
        self.consume("DEDENT")
        return fields

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

    def parse_layout_section(self) -> ast_nodes.SectionDecl:
        if self.peek().value == "section":
            start = self.consume("KEYWORD", "section")
        else:
            # Allow callers that have already consumed the 'section' keyword.
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

    def parse_component_call(self) -> ast_nodes.UIComponentCall:
        name_tok = self.consume_any({"IDENT"})
        args: list[ast_nodes.Expr] = []
        named_args: dict[str, list[ast_nodes.Statement | ast_nodes.FlowAction]] = {}
        class_name = None
        style_map: dict[str, str] = {}
        # optional positional expression before colon
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

    def parse_flow(self) -> ast_nodes.FlowDecl:
        start = self.consume("KEYWORD", "flow")
        if self.match_value("KEYWORD", "is"):
            name = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'flow "{tok.value}": is not supported. Use flow is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'flow'", tok)
        self.consume("COLON")
        self.consume("NEWLINE")
        description = None
        steps: List[ast_nodes.FlowStepDecl | ast_nodes.FlowLoopDecl | ast_nodes.FlowTransactionBlock] = []
        if self.check("INDENT"):
            self.consume("INDENT")
        allowed_fields: Set[str] = {"description", "step", "on", "for", "transaction"}
        error_steps: List[ast_nodes.FlowStepDecl] = []
        on_error_seen = False
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
                    if self.peek().value == "for":
                        steps.append(self.parse_flow_loop())
                    elif self.peek().value == "transaction":
                        steps.append(self.parse_transaction_block())
                    else:
                        steps.append(self.parse_english_flow_step(prefix))
                self.consume("DEDENT")
                self.optional_newline()
                continue

            if field_token.value in {"first", "then", "finally"}:
                prefix = self.consume("KEYWORD").value
                if self.peek().value == "for":
                    steps.append(self.parse_flow_loop())
                elif self.peek().value == "transaction":
                    steps.append(self.parse_transaction_block())
                else:
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
            elif field_token.value == "for":
                steps.append(self.parse_flow_loop(start_token=field_token))
            elif field_token.value == "transaction":
                steps.append(self.parse_transaction_block(start_token=field_token))
            elif field_token.value == "on":
                if on_error_seen:
                    raise self.error("N3L-980: multiple 'on error' blocks are not allowed", field_token)
                if not self.match_value("KEYWORD", "error"):
                    raise self.error("Expected 'error' after 'on' in flow block", self.peek())
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    if not self.match_value("KEYWORD", "step"):
                        raise self.error("Unexpected content inside 'on error' block; expected step", self.peek())
                    error_steps.append(self.parse_flow_step())
                self.consume("DEDENT")
                self.optional_newline()
                on_error_seen = True
                # after on error block, no more fields are allowed
                allowed_fields = set()
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
            error_steps=error_steps,
            span=self._span(start),
        )

    def parse_plugin(self) -> ast_nodes.PluginDecl:
        start = self.consume("KEYWORD", "plugin")
        if self.match_value("KEYWORD", "is"):
            name = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'plugin "{tok.value}": is not supported. Use plugin is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'plugin'", tok)
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
        theme_entries: list[ast_nodes.ThemeEntry] = []
        seen_theme: set[str] = set()
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            if self.peek().value == "theme":
                self.consume("KEYWORD", "theme")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    key_tok = self.consume_any({"IDENT", "KEYWORD"})
                    if self.peek().value != "color":
                        raise self.error("N3U-3001: invalid color literal", self.peek())
                    self.consume("KEYWORD", "color")
                    self.consume("KEYWORD", "be")
                    if not self.check("STRING"):
                        raise self.error("N3U-3001: invalid color literal", self.peek())
                    val_tok = self.consume("STRING")
                    key = key_tok.value or ""
                    if key in seen_theme:
                        raise self.error("N3U-3002: duplicate theme key", key_tok)
                    seen_theme.add(key)
                    theme_entries.append(ast_nodes.ThemeEntry(key=key, value=val_tok.value or "", span=self._span(val_tok)))
                    self.optional_newline()
                self.consume("DEDENT")
                self.optional_newline()
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
        return ast_nodes.SettingsDecl(envs=envs, theme=theme_entries, span=self._span(start))

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
        if self.match_value("KEYWORD", "is"):
            step_name_token = self.consume("STRING")
        else:
            tok = self.peek()
            if tok.type == "STRING":
                raise self.error(f'step "{tok.value}": is not supported. Use step is "{tok.value}": instead.', tok)
            raise self.error("Expected 'is' after 'step'", tok)
        alias: str | None = None
        if self.match_value("KEYWORD", "as"):
            alias_tok = self.consume_any({"IDENT", "KEYWORD"})
            alias = alias_tok.value or ""
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        (
            kind,
            target,
            message,
            extra_params,
            statements,
            conditional_branches,
            goto_action,
            when_expr,
            timeout_expr,
        ) = self._parse_step_body(allow_fields=True)
        self.consume("DEDENT")
        self.optional_newline()
        return self._build_flow_step_decl(
            step_name_token,
            alias,
            kind,
            target,
            message,
            extra_params,
            statements,
            conditional_branches,
            goto_action,
            when_expr,
            timeout_expr,
        )

    def parse_flow_loop(self, start_token: Token | None = None) -> ast_nodes.FlowLoopDecl:
        start = start_token or self.consume("KEYWORD", "for")
        if self.match_value("KEYWORD", "each"):
            pass
        if self.match_value("KEYWORD", "is"):
            pass
        if self.peek().type not in {"IDENT", "KEYWORD"}:
            tok = self.peek()
            raise self.error(
                f"N3L-900: Invalid loop variable name '{tok.value}' in flow.",
                tok,
            )
        var_tok = self.consume_any({"IDENT", "KEYWORD"})
        var_name = var_tok.value or ""
        if not var_name.isidentifier():
            raise self.error(
                f"N3L-900: Invalid loop variable name '{var_name}' in flow.",
                var_tok,
            )
        if not self.match_value("KEYWORD", "in"):
            raise self.error("Expected 'in' after loop variable", self.peek())
        iterable_expr = self.parse_expression()
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        steps: list[ast_nodes.FlowStepDecl | ast_nodes.FlowLoopDecl | ast_nodes.FlowTransactionBlock] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            tok = self.peek()
            if tok.value == "for":
                steps.append(self.parse_flow_loop())
            elif tok.value == "step":
                self.consume("KEYWORD", "step")
                steps.append(self.parse_flow_step())
            elif tok.value == "transaction":
                steps.append(self.parse_transaction_block())
            else:
                raise self.error("Unexpected content inside loop; expected step, transaction, or nested loop", tok)
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.FlowLoopDecl(
            name=f"for_each_{var_name}",
            var_name=var_name,
            iterable=iterable_expr,
            steps=[
                s
                for s in steps
                if isinstance(s, ast_nodes.FlowStepDecl)
                or isinstance(s, ast_nodes.FlowLoopDecl)
                or isinstance(s, ast_nodes.FlowTransactionBlock)
            ],
            span=self._span(start),
        )

    def parse_transaction_block(self, start_token: Token | None = None) -> ast_nodes.FlowTransactionBlock:
        start = start_token or self.consume("KEYWORD", "transaction")
        if self._transaction_depth > 0:
            raise self.error(
                "Nested transactions are not supported yet. Remove the inner transaction: block or merge its steps into the outer one.",
                start,
            )
        self._transaction_depth += 1
        try:
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            steps: list[ast_nodes.FlowStepDecl | ast_nodes.FlowLoopDecl | ast_nodes.FlowTransactionBlock] = []
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                tok = self.peek()
                if tok.value == "for":
                    steps.append(self.parse_flow_loop())
                elif tok.value == "step":
                    self.consume("KEYWORD", "step")
                    steps.append(self.parse_flow_step())
                elif tok.value == "transaction":
                    raise self.error(
                        "Nested transactions are not supported yet. Remove the inner transaction: block or move its steps outside.",
                        tok,
                    )
                else:
                    raise self.error(
                        "transaction: blocks can only contain steps or for each loops.",
                        tok,
                    )
            self.consume("DEDENT")
            self.optional_newline()
            if not steps:
                raise self.error("A transaction block must include at least one step.", start)
            return ast_nodes.FlowTransactionBlock(steps=steps, span=self._span(start))
        finally:
            self._transaction_depth = max(0, self._transaction_depth - 1)

    def parse_english_flow_step(self, prefix: str | None) -> ast_nodes.FlowStepDecl:
        if prefix:
            self.consume("KEYWORD", "step")
        else:
            self.consume("KEYWORD", "step")
        if self.match_value("KEYWORD", "is"):
            step_name_token = self.consume("STRING")
        else:
            step_name_token = self.consume("STRING")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        (
            kind,
            target,
            message,
            extra_params,
            statements,
            conditional_branches,
            goto_action,
            when_expr,
            timeout_expr,
        ) = self._parse_step_body(allow_fields=True)
        self.consume("DEDENT")
        self.optional_newline()
        return self._build_flow_step_decl(
            step_name_token,
            None,
            kind,
            target,
            message,
            extra_params,
            statements,
            conditional_branches,
            goto_action,
            when_expr,
            timeout_expr,
        )

    def _parse_where_conditions(self) -> ast_nodes.BooleanCondition:
        """Parse English-style WHERE conditions into a boolean condition tree."""
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        conditions: list[ast_nodes.BooleanCondition] = []
        connectors: list[str | None] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            leading: str | None = None
            if self.peek().value in {"and", "or"}:
                leading_tok = self.consume("KEYWORD")
                leading = leading_tok.value
            cond = self._parse_condition_expr()
            conditions.append(cond)
            connectors.append(leading)
            self.optional_newline()
        self.consume("DEDENT")
        if not conditions:
            raise self.error("A WHERE block needs at least one condition.", self.peek())
        if connectors[0] is not None:
            raise self.error(
                "I expected a condition before this connector. Write something like 'is_active is true and status is \"vip\"'.",
                self.peek(),
            )
        return self._combine_conditions(conditions, connectors)

    def _combine_conditions(
        self, conditions: list[ast_nodes.BooleanCondition], connectors: list[str | None]
    ) -> ast_nodes.BooleanCondition:
        if not conditions:
            raise self.error("A WHERE block needs at least one condition.", self.peek())
        # Default connector is AND when omitted.
        segments: list[ast_nodes.BooleanCondition] = []
        current = conditions[0]
        for idx in range(1, len(conditions)):
            op = connectors[idx] or "and"
            right = conditions[idx]
            if op == "and":
                current = ast_nodes.ConditionAnd(left=current, right=right, span=self._span(self.peek()))
            elif op == "or":
                segments.append(current)
                current = right
            else:
                raise self.error("I don't understand this connector. Use 'and' or 'or'.", self.peek())
        segments.append(current)
        result = segments[0]
        for seg in segments[1:]:
            result = ast_nodes.ConditionOr(left=result, right=seg, span=self._span(self.peek()))
        return result

    def _parse_condition_expr(self) -> ast_nodes.BooleanCondition:
        left = self._parse_condition_and()
        while not (self.check("NEWLINE") or self.check("DEDENT")) and self.match_value("KEYWORD", "or"):
            right = self._parse_condition_and()
            left = ast_nodes.ConditionOr(left=left, right=right, span=self._span(self.peek()))
        return left

    def _parse_condition_and(self) -> ast_nodes.BooleanCondition:
        left = self._parse_condition_primary()
        while not (self.check("NEWLINE") or self.check("DEDENT")) and self.match_value("KEYWORD", "and"):
            right = self._parse_condition_primary()
            left = ast_nodes.ConditionAnd(left=left, right=right, span=self._span(self.peek()))
        return left

    def _parse_condition_primary(self) -> ast_nodes.BooleanCondition:
        tok = self.peek()
        # Grouping: all of / any of
        if tok.value in {"all", "any"} and self.peek_offset(1).value == "of":
            is_all = tok.value == "all"
            self.advance()  # consume all/any
            self.consume("KEYWORD", "of")
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            children: list[ast_nodes.BooleanCondition] = []
            connectors: list[str | None] = []
            while not self.check("DEDENT"):
                if self.match("NEWLINE"):
                    continue
                leading: str | None = None
                if self.peek().value in {"and", "or"}:
                    leading = self.consume("KEYWORD").value
                child = self._parse_condition_expr()
                children.append(child)
                connectors.append(leading)
                self.optional_newline()
            self.consume("DEDENT")
            if not children:
                raise self.error(
                    f"'{'all' if is_all else 'any'} of:' needs at least one condition inside.",
                    tok,
                )
            return (
                ast_nodes.ConditionAllGroup(children=children, span=self._span(tok))
                if is_all
                else ast_nodes.ConditionAnyGroup(children=children, span=self._span(tok))
            )

        field_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
        field_name = field_tok.value or ""
        start_span = self._span(field_tok)
        if not field_name:
            raise self.error("Field name missing in WHERE condition.", field_tok)
        if not self.match_value("KEYWORD", "is"):
            raise self.error(
                "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks.",
                self.peek(),
            )
        next_tok = self.peek()
        if next_tok.type == "KEYWORD" and next_tok.value not in {
            "not",
            "null",
            "greater",
            "less",
            "at",
            "one",
            "true",
            "false",
        }:
            raise self.error(
                "I don't understand this condition in a WHERE block. Use is, is not, is greater than, is at least, is one of, or null checks.",
                next_tok,
            )
        op = "eq"
        value_expr: ast_nodes.Expr | None = None
        if self.match_value("KEYWORD", "not"):
            if self.match_value("KEYWORD", "null") or self.match_value("IDENT", "null"):
                op = "is_not_null"
            else:
                op = "neq"
                value_expr = self.parse_expression()
        elif self.match_value("KEYWORD", "null") or self.match_value("IDENT", "null"):
            op = "is_null"
        elif self.match_value("KEYWORD", "greater"):
            self.consume("KEYWORD", "than")
            op = "gt"
            value_expr = self.parse_expression()
        elif self.match_value("KEYWORD", "less"):
            self.consume("KEYWORD", "than")
            op = "lt"
            value_expr = self.parse_expression()
        elif self.match_value("KEYWORD", "at"):
            limiter = self.consume("KEYWORD")
            if limiter.value == "least":
                op = "ge"
            elif limiter.value == "most":
                op = "le"
            else:
                raise self.error(
                    "I don't understand this condition in a WHERE block. Use 'at least' or 'at most'.",
                    limiter,
                )
            value_expr = self.parse_expression()
        elif self.peek().value == "one":
            self.advance()
            self.consume("KEYWORD", "of")
            op = "in"
            value_expr = self.parse_expression()
        else:
            value_expr = self.parse_expression()
        if op in {"eq", "neq", "gt", "lt", "ge", "le", "in"} and value_expr is None:
            raise self.error(
                "I don't understand this condition in a WHERE block. Use 'field is value', 'field is greater than value', or 'field is one of [...]'.",
                self.peek(),
            )
        return self._expr_to_condition(field_name, op, value_expr, start_span)

    def _expr_to_condition(
        self, field_name: str, op: str, expr: ast_nodes.Expr | None, span: ast_nodes.Span | None
    ) -> ast_nodes.BooleanCondition:
        if isinstance(expr, ast_nodes.BinaryOp) and expr.op in {"and", "or"}:
            left_cond = self._expr_to_condition(field_name, op, expr.left, span)
            right_cond = self._expr_to_condition(field_name, op, expr.right, span)
            if expr.op == "and":
                return ast_nodes.ConditionAnd(left=left_cond, right=right_cond, span=span)
            return ast_nodes.ConditionOr(left=left_cond, right=right_cond, span=span)
        if isinstance(expr, ast_nodes.BinaryOp) and expr.op == "==" and isinstance(expr.left, ast_nodes.VarRef):
            return ast_nodes.ConditionLeaf(field_name=expr.left.name, op="eq", value_expr=expr.right, span=span)
        return ast_nodes.ConditionLeaf(field_name=field_name, op=op, value_expr=expr, span=span)

    def _parse_duration_value(self) -> ast_nodes.Expr:
        tok = self.peek()
        if tok.type == "NUMBER":
            num_tok = self.consume("NUMBER")
            raw_val = num_tok.value or "0"
            try:
                number: float | int | str
                if "." in raw_val:
                    number = float(raw_val)
                else:
                    number = int(raw_val)
            except Exception:
                number = raw_val
            unit_tok = self.peek()
            if unit_tok.type in {"IDENT", "KEYWORD"}:
                unit_val = (unit_tok.value or "").lower()
                if unit_val in {"second", "seconds", "sec", "s", "millisecond", "milliseconds", "ms"}:
                    self.advance()
                    if unit_val.startswith("ms") or unit_val.startswith("millisecond"):
                        try:
                            number = float(number) / 1000.0
                        except Exception:
                            pass
            return ast_nodes.Literal(value=number, span=self._span(num_tok))
        return self.parse_expression()

    def _parse_step_body(
        self, allow_fields: bool = True
    ) -> tuple[
        str | None,
        str | None,
        str | None,
        dict[str, object],
        list[ast_nodes.Statement | ast_nodes.FlowAction],
        list[ast_nodes.ConditionalBranch] | None,
        ast_nodes.FlowAction | None,
        ast_nodes.Expr | None,
        ast_nodes.Expr | None,
    ]:
        kind = None
        target = None
        message = None
        extra_params: dict[str, object] = {}
        statements: list[ast_nodes.Statement | ast_nodes.FlowAction] = []
        conditional_branches: list[ast_nodes.ConditionalBranch] | None = None
        goto_action: ast_nodes.FlowAction | None = None
        when_expr: ast_nodes.Expr | None = None
        timeout_expr: ast_nodes.Expr | None = None
        allowed_fields: Set[str] = {
            "kind",
            "target",
            "tool",
            "tools",
            "message",
            "frame",
            "record",
            "vector_store",
            "values",
            "where",
            "set",
            "query_text",
            "top_k",
            "pipeline",
            "question",
            "args",
            "input",
            "by",
            "limit",
            "when",
            "timeout",
            "streaming",
            "stream_channel",
            "stream_role",
            "stream_label",
            "stream_mode",
        } if allow_fields else set()
        script_mode = False
        find_query: ast_nodes.RecordQuery | None = None
        def _aliases_match(candidate: str, base: str) -> bool:
            if candidate == base:
                return True
            if candidate.endswith("s") and candidate[:-1] == base:
                return True
            if base.endswith("s") and base[:-1] == candidate:
                return True
            return False

        def _alias_from_token(alias_token: Token) -> tuple[str, str | None]:
            alias_value = alias_token.value or ""
            if not alias_value:
                raise self.error("I expected a record name or alias here.", alias_token)
            explicit_record = alias_value if alias_token.type == "STRING" else None
            return alias_value, explicit_record

        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            token = self.peek()
            if token.value == "create":
                next_token = self.peek_offset(1)
                if next_token.value == "many":
                    self.advance()  # consume create
                    self.advance()  # consume many
                    if kind and kind not in {"db_bulk_create"}:
                        raise self.error("This step already declares a kind. Remove 'kind is ...' when using 'create many ...'.", token)
                    if "bulk_create" in extra_params:
                        raise self.error("I already saw a create many ... helper in this step. Keep only one bulk create helper per step.", token)
                    alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    alias, explicit_record = _alias_from_token(alias_tok)
                    if not self.match_value("KEYWORD", "from"):
                        raise self.error("I expected 'create many <record> from <values>'.", self.peek())
                    source_expr = self.parse_expression()
                    record_override = extra_params.get("record") if isinstance(extra_params.get("record"), str) else None
                    record_name = explicit_record or record_override
                    bulk_spec = ast_nodes.BulkCreateSpec(
                        alias=alias,
                        record_name=record_name,
                        source_expr=source_expr,
                        span=self._span(alias_tok),
                    )
                    default_target = record_name or alias
                    extra_params.setdefault("record", default_target)
                    extra_params["bulk_create"] = bulk_spec
                    kind = "db_bulk_create"
                    target = target or default_target
                    self.optional_newline()
                    continue
            if token.value == "update":
                next_token = self.peek_offset(1)
                if next_token.value == "many":
                    self.advance()  # consume update
                    self.advance()  # consume many
                    if kind and kind not in {"db_bulk_update"}:
                        raise self.error("This step already declares a different kind. Remove 'kind is ...' when using 'update many ...'.", token)
                    if "bulk_update" in extra_params:
                        raise self.error("I already saw an update many ... helper in this step. Keep only one bulk update helper per step.", token)
                    alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    alias, explicit_record = _alias_from_token(alias_tok)
                    if not self.match_value("KEYWORD", "where"):
                        raise self.error("update many ... must include a 'where:' block.", self.peek())
                    where_conditions = self._parse_where_conditions()
                    record_override = extra_params.get("record") if isinstance(extra_params.get("record"), str) else None
                    record_name = explicit_record or record_override
                    bulk_spec = ast_nodes.BulkUpdateSpec(
                        alias=alias,
                        where_condition=where_conditions,
                        record_name=record_name,
                        span=self._span(alias_tok),
                    )
                    default_target = record_name or alias
                    extra_params.setdefault("record", default_target)
                    extra_params["bulk_update"] = bulk_spec
                    kind = "db_bulk_update"
                    target = target or default_target
                    self.optional_newline()
                    continue
            if token.value == "delete":
                next_token = self.peek_offset(1)
                if next_token.value == "many":
                    self.advance()  # consume delete
                    self.advance()  # consume many
                    if kind and kind not in {"db_bulk_delete"}:
                        raise self.error("This step already declares a different kind. Remove 'kind is ...' when using 'delete many ...'.", token)
                    if "bulk_delete" in extra_params:
                        raise self.error("I already saw a delete many ... helper in this step. Keep only one bulk delete helper per step.", token)
                    alias_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    alias, explicit_record = _alias_from_token(alias_tok)
                    if not self.match_value("KEYWORD", "where"):
                        raise self.error("delete many ... must include a 'where:' block.", self.peek())
                    where_conditions = self._parse_where_conditions()
                    record_override = extra_params.get("record") if isinstance(extra_params.get("record"), str) else None
                    record_name = explicit_record or record_override
                    bulk_spec = ast_nodes.BulkDeleteSpec(
                        alias=alias,
                        where_condition=where_conditions,
                        record_name=record_name,
                        span=self._span(alias_tok),
                    )
                    default_target = record_name or alias
                    extra_params.setdefault("record", default_target)
                    extra_params["bulk_delete"] = bulk_spec
                    kind = "db_bulk_delete"
                    target = target or default_target
                    self.optional_newline()
                    continue
            if token.value == "find":
                self.advance()
                alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = alias_tok.value or ""
                if find_query is not None:
                    raise self.error(
                        "Only one find ... where block is allowed per step.",
                        alias_tok,
                    )
                if not self.match_value("KEYWORD", "where"):
                    raise self.error(
                        "find ... where ... must include a where block using 'find <alias> where:'.",
                        self.peek(),
                    )
                conds = self._parse_where_conditions()
                find_query = ast_nodes.RecordQuery(alias=alias, where_condition=conds, span=self._span(alias_tok))
                kind = kind or "find"
                target = target or alias
                extra_params["query"] = find_query
                self.optional_newline()
                continue
            if token.value == "order":
                self.advance()
                alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = alias_tok.value or ""
                if find_query is None or find_query.alias != alias:
                    raise self.error(
                        f"I don't know what {alias} refers to here. Use find {alias} where: before order {alias} by ....",
                        alias_tok,
                    )
                self.consume("KEYWORD", "by")
                order_items: list[ast_nodes.RecordOrderBy] = []
                while True:
                    field_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    field_name = field_tok.value or ""
                    direction = "asc"
                    if self.match_value("KEYWORD", "ascending"):
                        direction = "asc"
                    elif self.match_value("KEYWORD", "descending"):
                        direction = "desc"
                    elif self.peek().type == "KEYWORD" and self.peek().value in {"asc", "desc"}:
                        dir_tok = self.consume_any({"KEYWORD"})
                        if dir_tok.value == "asc":
                            direction = "asc"
                        elif dir_tok.value == "desc":
                            direction = "desc"
                        else:
                            raise self.error(
                                "I don't understand this sort direction. Use ascending or descending.",
                                dir_tok,
                            )
                    if direction not in {"asc", "desc"}:
                        raise self.error(
                            "I don't understand this sort direction. Use ascending or descending.",
                            field_tok,
                        )
                    order_items.append(
                        ast_nodes.RecordOrderBy(field_name=field_name, direction=direction, span=self._span(field_tok))
                    )
                    if not self.match("COMMA"):
                        break
                find_query.order_by = order_items
                extra_params["query"] = find_query
                self.optional_newline()
                continue
            if token.value == "limit":
                self.advance()
                alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = alias_tok.value or ""
                if find_query is None or find_query.alias != alias:
                    raise self.error(
                        f"I don't know what {alias} refers to here. Use find {alias} where: before limit {alias} to ....",
                        alias_tok,
                    )
                if not self.match_value("KEYWORD", "to"):
                    raise self.error("Use 'limit <alias> to <number>' to set a limit.", self.peek())
                expr = self.parse_expression()
                find_query.limit_expr = expr
                extra_params["query"] = find_query
                self.optional_newline()
                continue
            if token.value == "offset":
                self.advance()
                alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = alias_tok.value or ""
                if find_query is None or find_query.alias != alias:
                    raise self.error(
                        f"I don't know what {alias} refers to here. Use find {alias} where: before offset {alias} by ....",
                        alias_tok,
                    )
                if not self.match_value("KEYWORD", "by"):
                    raise self.error("Use 'offset <alias> by <number>' to set an offset.", self.peek())
                expr = self.parse_expression()
                find_query.offset_expr = expr
                extra_params["query"] = find_query
                self.optional_newline()
                continue
            if token.value == "with":
                if find_query is None:
                    raise self.error(
                        "I can’t attach a relationship until you declare a find <alias> where: block.",
                        token,
                    )
                self.advance()
                related_alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                related_alias = related_alias_tok.value or ""
                if not related_alias:
                    raise self.error("I expected an alias after with.", related_alias_tok)
                if not self.match_value("KEYWORD", "for"):
                    raise self.error("Use 'with <alias> for each <base alias> by <field>'.", self.peek())
                self.consume("KEYWORD", "each")
                base_alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                base_alias_raw = base_alias_tok.value or ""
                if not base_alias_raw:
                    raise self.error("I expected the base alias after 'for each'.", base_alias_tok)
                canonical_alias = find_query.alias or ""
                if not _aliases_match(base_alias_raw, canonical_alias):
                    raise self.error(
                        f"I can’t attach this relationship because I don’t know what {base_alias_raw} refers to here. Use the alias from find {canonical_alias} where: first.",
                        base_alias_tok,
                    )
                if not self.match_value("KEYWORD", "by"):
                    raise self.error("Relationship joins must specify the field to use, e.g. 'by user_id'.", self.peek())
                via_field_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                via_field = via_field_tok.value or ""
                if not via_field:
                    raise self.error("I expected a field name after 'by'.", via_field_tok)
                find_query.relationships.append(
                    ast_nodes.RecordRelationshipJoin(
                        related_alias=related_alias,
                        base_alias=canonical_alias,
                        via_field=via_field,
                        display_base_alias=base_alias_raw,
                        span=self._span(related_alias_tok),
                    )
                )
                self.optional_newline()
                continue
            if token.value == "set" and allow_fields and kind in {"frame_update", "db_update", "db_bulk_update"} and not script_mode:
                field_token = self.consume("KEYWORD")
                if field_token.value not in allowed_fields:
                    raise self.error(
                        f"Unexpected field '{field_token.value}' in step block",
                        field_token,
                    )
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                entries: dict[str, ast_nodes.Expr] = {}
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    key_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    self.consume("COLON")
                    expr = self.parse_expression()
                    entries[key_tok.value or ""] = expr
                    self.optional_newline()
                self.consume("DEDENT")
                extra_params[field_token.value] = entries
                self.optional_newline()
                continue
            if token.value == "go" and allow_fields and not script_mode and not statements and conditional_branches is None:
                goto_action = self.parse_goto_action()
                self.optional_newline()
                continue
            if token.value in {"let", "set", "do", "repeat", "match", "retry", "ask", "form", "log", "note", "checkpoint", "return", "try", "guard"} or (token.value == "go" and script_mode):
                if token.value == "match":
                    script_mode = True
                    statements.append(self.parse_match_statement())
                    continue
                if token.value == "retry":
                    script_mode = True
                    statements.append(self.parse_retry_statement())
                    continue
                if token.value == "try":
                    script_mode = True
                    statements.append(self.parse_try_catch_statement())
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
            if token.value == "when":
                raise self.error(
                    "when is only supported inside a match block. Use if for standalone conditions.",
                    token,
                )
            if token.value in {"if", "otherwise", "unless", "else"} or (
                token.value == "when" and not allow_fields
            ):
                # Top-level conditional branches (if/when/otherwise/unless) when no script content yet
                if not script_mode and not statements and token.value in {"if", "when", "otherwise", "unless"}:
                    conditional_branches = conditional_branches or []
                    self.parse_conditional_into(conditional_branches)
                else:
                    script_mode = True
                    statements.append(self.parse_if_statement())
                continue
            if token.value == "all":
                raise self.error(
                    "The legacy 'all ...' data syntax is no longer supported. Use a collection pipeline instead (e.g. keep rows where ...).",
                    token,
                )
            if not allow_fields:
                raise self.error(
                    f"Unexpected field '{token.value}' in step block",
                    token,
                )
            field_token = self.consume_any({"KEYWORD", "IDENT"})
            if field_token.value not in allowed_fields:
                if field_token.value == "navigate":
                    raise self.error(
                        "N3L-PARSE-NAVIGATE: 'navigate' is only supported in UI click handlers; in flows use 'go to page \"...\"' or 'go to flow \"...\"'.",
                        field_token,
                    )
                if field_token.value == "output":
                    raise self.error(
                        "N3L-PARSE-OUTPUT: 'output to' is not part of the language yet; use let/set and step.<name>.output to route outputs.",
                        field_token,
                    )
                raise self.error(
                    f"Unexpected field '{field_token.value}' in step block",
                    field_token,
                )
            if field_token.value == "kind":
                if self.match_value("KEYWORD", "is"):
                    kind_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    kind_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                kind = kind_token.value
                if kind == "db_get":
                    raise self.error(
                        "db_get is no longer supported. Write find <alias> where: instead, for example:\nfind users where:\n  is_active is true",
                        kind_token,
                    )
                if kind_token.value == "script":
                    script_mode = True
            elif field_token.value == "target":
                if self.match_value("KEYWORD", "is"):
                    target_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    target_token = self.consume_string_value(field_token, "target")
                target = target_token.value
            elif field_token.value == "tool":
                if kind is None:
                    kind = "tool"
                elif kind != "tool":
                    raise self.error(
                        "Field 'tool' may only be used on steps where kind is 'tool'.",
                        field_token,
                    )
                if self.match_value("KEYWORD", "is"):
                    tool_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    tool_token = self.consume_string_value(field_token, "tool")
                target = tool_token.value
            elif field_token.value == "streaming":
                if self.match_value("KEYWORD", "is"):
                    bool_token = self.consume_any({"KEYWORD", "IDENT"})
                else:
                    bool_token = self.consume_any({"KEYWORD", "IDENT"})
                streaming_val = bool_token.value
                if streaming_val not in {"true", "false"}:
                    raise self.error(
                        "N3L-990: Field 'streaming' must be a boolean literal (true/false).",
                        bool_token,
                    )
                extra_params["streaming"] = streaming_val == "true"
            elif field_token.value == "stream_channel":
                if self.match_value("KEYWORD", "is"):
                    channel_tok = self.consume("STRING")
                else:
                    channel_tok = self.consume_string_value(field_token, "stream_channel")
                extra_params["stream_channel"] = channel_tok.value or ""
            elif field_token.value == "stream_role":
                if self.match_value("KEYWORD", "is"):
                    role_tok = self.consume("STRING")
                else:
                    role_tok = self.consume_string_value(field_token, "stream_role")
                extra_params["stream_role"] = role_tok.value or ""
            elif field_token.value == "stream_label":
                if self.match_value("KEYWORD", "is"):
                    label_tok = self.consume("STRING")
                else:
                    label_tok = self.consume_string_value(field_token, "stream_label")
                extra_params["stream_label"] = label_tok.value or ""
            elif field_token.value == "stream_mode":
                if self.match_value("KEYWORD", "is"):
                    mode_tok = self.consume("STRING")
                else:
                    mode_tok = self.consume_string_value(field_token, "stream_mode")
                mode_val = (mode_tok.value or "").lower()
                if mode_val and mode_val not in {"tokens", "sentences", "full"}:
                    raise self.error(
                        "N3L-995: Field 'stream_mode' must be one of 'tokens', 'sentences', or 'full'.",
                        mode_tok,
                    )
                extra_params["stream_mode"] = mode_val
            elif field_token.value == "message":
                if self.match_value("KEYWORD", "is"):
                    msg_token = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    msg_token = self.consume_string_value(field_token, "message")
                message = msg_token.value
            elif field_token.value == "when":
                if self.match_value("KEYWORD", "is"):
                    when_expr = self.parse_expression()
                else:
                    when_expr = self.parse_expression()
            elif field_token.value == "timeout":
                if self.match_value("KEYWORD", "is"):
                    timeout_expr = self._parse_duration_value()
                else:
                    timeout_expr = self._parse_duration_value()
            elif field_token.value == "frame":
                if self.match_value("KEYWORD", "is"):
                    frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    frame_tok = self.consume_string_value(field_token, "frame")
                extra_params["frame"] = frame_tok.value
            elif field_token.value == "record":
                if self.match_value("KEYWORD", "is"):
                    record_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    record_tok = self.consume_string_value(field_token, "record")
                extra_params["record"] = record_tok.value
            elif field_token.value == "vector_store":
                if self.match_value("KEYWORD", "is"):
                    vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    vs_tok = self.consume_string_value(field_token, "vector_store")
                extra_params["vector_store"] = vs_tok.value
            elif field_token.value == "pipeline":
                if self.match_value("KEYWORD", "is"):
                    pipe_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    pipe_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                extra_params["pipeline"] = pipe_tok.value
            elif field_token.value == "question":
                if self.match_value("KEYWORD", "is"):
                    question_expr = self.parse_expression()
                else:
                    question_expr = self.parse_expression()
                extra_params["question"] = question_expr
            elif field_token.value == "tools":
                if self.match_value("KEYWORD", "is"):
                    mode_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    mode_tok = self.consume_string_value(field_token, "tools")
                mode_val = (mode_tok.value or "").strip().lower()
                if mode_val not in {"auto", "none"}:
                    raise self.error(
                        "Field 'tools' must be set to 'auto' or 'none'.",
                        mode_tok,
                    )
                extra_params["tools_mode"] = mode_val
            elif field_token.value == "query_text":
                if self.match_value("KEYWORD", "is"):
                    expr = self.parse_expression()
                else:
                    expr = self.parse_expression()
                extra_params["query_text"] = expr
            elif field_token.value == "top_k":
                if self.match_value("KEYWORD", "is"):
                    expr = self.parse_expression()
                else:
                    expr = self.parse_expression()
                extra_params["top_k"] = expr
            elif field_token.value == "limit":
                if self.match_value("KEYWORD", "is"):
                    expr = self.parse_expression()
                else:
                    expr = self.parse_expression()
                extra_params["limit"] = expr
            elif field_token.value == "by":
                if self.peek().value != "id":
                    raise self.error("Expected 'id' after 'by' in step block", self.peek())
                self.consume("KEYWORD", "id")
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                entries: dict[str, ast_nodes.Expr] = {}
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    key_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    self.consume("COLON")
                    expr = self.parse_expression()
                    entries[key_tok.value or ""] = expr
                    self.optional_newline()
                self.consume("DEDENT")
                extra_params["by_id"] = entries
                self.optional_newline()
            elif field_token.value == "where":
                if kind == "vector_index_frame":
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    extra_params[field_token.value] = self._parse_expression_block()
                    self.optional_newline()
                else:
                    extra_params[field_token.value] = self._parse_where_conditions()
            elif field_token.value in {"values", "set", "args", "input"}:
                self.consume("COLON")
                self.consume("NEWLINE")
                self.consume("INDENT")
                entries: dict[str, ast_nodes.Expr] = {}
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    key_tok = self.consume_any({"IDENT", "KEYWORD", "STRING"})
                    self.consume("COLON")
                    expr = self.parse_expression()
                    entries[key_tok.value or ""] = expr
                    self.optional_newline()
                self.consume("DEDENT")
                extra_params[field_token.value] = entries
            self.optional_newline()
        # Auto-wrap frame_* actions into a FlowAction to preserve params
        if kind in {
            "frame_insert",
            "frame_query",
            "frame_update",
            "frame_delete",
            "vector_index_frame",
            "vector_query",
            "db_create",
            "db_update",
            "db_delete",
            "db_bulk_create",
            "db_bulk_update",
            "db_bulk_delete",
            "find",
            "auth_register",
            "auth_login",
            "auth_logout",
        } and not statements:
            action = ast_nodes.FlowAction(
                kind=kind,
                target=(extra_params.get("frame") or extra_params.get("record") or extra_params.get("vector_store") or target or "") or "",
                args={
                    k: v
                    for k, v in extra_params.items()
                    if k
                    in {
                        "values",
                        "where",
                        "set",
                        "vector_store",
                        "query_text",
                        "top_k",
                        "by_id",
                        "limit",
                        "input",
                        "query",
                        "offset",
                        "order_by",
                        "bulk_create",
                        "bulk_update",
                        "bulk_delete",
                    }
                },
                span=None,
            )
            statements.append(action)
        return kind, target, message, extra_params, statements, conditional_branches, goto_action, when_expr, timeout_expr

    def _build_flow_step_decl(
        self,
        step_name_token,
        alias,
        kind,
        target,
        message,
        extra_params,
        statements,
        conditional_branches,
        goto_action,
        when_expr,
        timeout_expr,
    ) -> ast_nodes.FlowStepDecl:
        streaming_flag = bool(extra_params.get("streaming"))
        stream_channel = extra_params.get("stream_channel") or None
        stream_role = extra_params.get("stream_role") or None
        stream_label = extra_params.get("stream_label") or None
        stream_mode = extra_params.get("stream_mode") or None
        if stream_mode is not None:
            allowed_modes = {"tokens", "sentences", "full"}
            if stream_mode not in allowed_modes:
                raise self.error(
                    f"N3L-995: Field 'stream_mode' on AI step '{step_name_token.value}' must be one of 'tokens', 'sentences', or 'full'.",
                    step_name_token,
                )
        stream_kwargs = {
            "streaming": streaming_flag,
            "stream_channel": stream_channel,
            "stream_role": stream_role,
            "stream_label": stream_label,
            "stream_mode": stream_mode,
        }
        if kind in {"db_create", "db_get", "db_update", "db_delete", "db_bulk_create", "db_bulk_update", "db_bulk_delete"}:
            record_name = extra_params.get("record") or target
            if not record_name:
                raise self.error(
                    f"Step '{step_name_token.value}' with kind '{kind}' must specify a record.",
                    step_name_token,
                )
            target = record_name
            extra_params.pop("record", None)
        tools_mode = extra_params.pop("tools_mode", None)
        if statements:
            only_actions = all(isinstance(stmt, ast_nodes.FlowAction) for stmt in statements)
            if only_actions and len(statements) == 1 and not conditional_branches:
                action = statements[0]
                return ast_nodes.FlowStepDecl(
                    name=step_name_token.value or "",
                    alias=alias,
                    kind=action.kind,
                    target=action.target,
                    message=action.message,
                    params=action.args or extra_params or {},
                    statements=[],
                    when_expr=when_expr,
                    timeout=timeout_expr,
                    **stream_kwargs,
                    tools_mode=tools_mode,
                    span=self._span(step_name_token),
                )
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                alias=alias,
                kind="script",
                target=target or "",
                message=message,
                params=extra_params or {},
                statements=statements,
                when_expr=when_expr,
                timeout=timeout_expr,
                **stream_kwargs,
                tools_mode=tools_mode,
                span=self._span(step_name_token),
            )
        if conditional_branches:
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                alias=alias,
                kind="condition",
                target=step_name_token.value or "",
                params=extra_params or {},
                conditional_branches=conditional_branches,
                when_expr=when_expr,
                timeout=timeout_expr,
                **stream_kwargs,
                tools_mode=tools_mode,
                span=self._span(step_name_token),
            )
        if goto_action:
            return ast_nodes.FlowStepDecl(
                name=step_name_token.value or "",
                alias=alias,
                kind="goto_flow",
                target=goto_action.target,
                when_expr=when_expr,
                timeout=timeout_expr,
                **stream_kwargs,
                tools_mode=tools_mode,
                span=self._span(step_name_token),
            )
        if kind == "tool" and not target:
            raise self.error("N3L-963: Tool call step must specify a target tool.", step_name_token)
        if kind is None:
            raise self.error("Missing 'kind' in step", step_name_token)
        if target is None and kind in {"vector_query", "vector_index_frame", "rag_query"}:
            target = step_name_token.value or ""
        if target is None:
            raise self.error("Missing 'target' in step", step_name_token)
        return ast_nodes.FlowStepDecl(
            name=step_name_token.value or "",
            alias=alias,
            kind=kind,
            target=target,
            message=message,
            params=extra_params or {},
            when_expr=when_expr,
            timeout=timeout_expr,
            **stream_kwargs,
            tools_mode=tools_mode,
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
        if token.value == "guard":
            return self.parse_guard_statement()
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
        if token.value == "try":
            return self.parse_try_catch_statement()
        if token.value == "do":
            return self._parse_do_action()
        if token.value == "go":
            return self.parse_goto_action()
        if token.value == "navigate":
            raise self.error(
                "N3L-PARSE-NAVIGATE: 'navigate' is only supported in UI click handlers; in flows use 'go to page \"...\"' or 'go to flow \"...\"'.",
                token,
            )
        if token.value == "output":
            raise self.error(
                "N3L-PARSE-OUTPUT: 'output to' is not part of the language yet; use let/set and step.<name>.output to route outputs.",
                token,
            )
        if token.value in {"if", "when", "otherwise", "unless", "else"}:
            return self.parse_if_statement()
        if token.value == "let":
            return self.parse_let_statement()
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
            if token.value in {"otherwise", "else"}:
                raise self.error("Found 'otherwise/else' without preceding if/when", token)
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
        while self.peek().value in {"otherwise", "else"}:
            other_tok = self.consume("KEYWORD")
            label = other_tok.value
            cond = None
            binding = None
            if other_tok.value == "otherwise" and self.peek().value == "if":
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
                binding = self._parse_optional_binding()
                if not self.check("COLON"):
                    raise self.error(
                        "N3CF-900: I expected ':' after 'when success'. If you want to bind the value, write 'when success as value:'.",
                        self.peek(),
                    )
                pattern = ast_nodes.SuccessPattern(binding=binding, span=self._span(pat_token))
            elif pat_token.value == "error":
                self.consume("KEYWORD", "error")
                binding = self._parse_optional_binding()
                if not self.check("COLON"):
                    raise self.error(
                        "N3CF-901: I expected ':' after 'when error'. If you want to bind the error, write 'when error as err:'.",
                        self.peek(),
                    )
                pattern = ast_nodes.ErrorPattern(binding=binding, span=self._span(pat_token))
            else:
                pattern = self.parse_expression()
                if not isinstance(pattern, ast_nodes.Literal) or not isinstance(
                    pattern.value, (str, int, float, bool, type(None))
                ):
                    raise self.error(
                        "This match pattern form is not supported in Control Flow v1. Use literal patterns or rewrite this as an if / otherwise if / else chain.",
                        pat_token,
                    )
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            actions = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            branches.append(ast_nodes.MatchBranch(pattern=pattern, actions=actions, label="when"))
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.MatchStatement(target=target_expr, branches=branches, span=self._span(start_tok))

    def parse_guard_statement(self) -> ast_nodes.GuardStatement:
        start_tok = self.consume("KEYWORD", "guard")
        if self.check("COLON"):
            raise self.error("Expected a condition after guard.", self.peek())
        condition = self.parse_condition_expr()
        if not self.match("COLON"):
            raise self.error("Expected ':' after the guard condition.", self.peek())
        self.consume("NEWLINE")
        self.consume("INDENT")
        body = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.GuardStatement(condition=condition, body=body, span=self._span(start_tok))

    def parse_try_catch_statement(self) -> ast_nodes.TryCatchStatement:
        start_tok = self.consume("KEYWORD", "try")
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        try_block = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        # Expect catch
        catch_tok = self.consume("KEYWORD", "catch")
        if self.peek().type != "IDENT" and self.peek().type != "KEYWORD":
            raise self.error("N3L-601: catch must specify an error identifier (e.g. 'catch err:').", self.peek())
        err_tok = self.consume_any({"IDENT", "KEYWORD"})
        error_ident = err_tok.value or ""
        self.consume("COLON")
        self.consume("NEWLINE")
        self.consume("INDENT")
        catch_block = self.parse_statement_block()
        self.consume("DEDENT")
        self.optional_newline()
        return ast_nodes.TryCatchStatement(
            try_block=try_block,
            error_identifier=error_ident,
            catch_block=catch_block,
            span=self._span(start_tok),
        )

    def _parse_destructuring_pattern(self) -> ast_nodes.DestructuringPattern | None:
        if self.match("LBRACE"):
            fields: list[ast_nodes.DestructuringField] = []
            while not self.check("RBRACE"):
                field_tok = self.consume_any({"IDENT", "KEYWORD"})
                alias = None
                if self.match_value("KEYWORD", "as"):
                    alias_tok = self.consume_any({"IDENT", "KEYWORD"})
                    alias = alias_tok.value or None
                fields.append(ast_nodes.DestructuringField(name=field_tok.value or "", alias=alias))
                if self.match("COMMA"):
                    continue
                if self.check("RBRACE"):
                    break
                raise self.error("Expected ',' or '}' in destructuring pattern", self.peek())
            self.consume("RBRACE")
            return ast_nodes.DestructuringPattern(kind="record", fields=fields)
        if self.match("LBRACKET"):
            elements: list[str] = []
            while not self.check("RBRACKET"):
                elt_tok = self.consume_any({"IDENT", "KEYWORD"})
                elements.append(elt_tok.value or "")
                if self.match("COMMA"):
                    continue
                if self.check("RBRACKET"):
                    break
                raise self.error("Expected ',' or ']' in list destructuring pattern", self.peek())
            self.consume("RBRACKET")
            return ast_nodes.DestructuringPattern(kind="list", fields=elements)
        return None

    def _split_field_access_expr(self, expr: ast_nodes.Expr) -> tuple[ast_nodes.Expr | None, str | None]:
        if isinstance(expr, ast_nodes.RecordFieldAccess):
            return expr.target, expr.field
        if isinstance(expr, ast_nodes.VarRef) and expr.path:
            base_path = expr.path[:-1]
            field = expr.path[-1]
            dotted = ".".join([expr.root] + base_path) if base_path else expr.root
            base_expr = ast_nodes.VarRef(
                name=dotted,
                root=expr.root,
                path=base_path,
                kind=expr.kind,
                span=expr.span,
            )
            return base_expr, field
        return None, None

    def parse_let_statement(self) -> ast_nodes.LetStatement:
        start = self.consume("KEYWORD", "let")
        is_constant = False
        if self.peek().value == "constant":
            self.advance()
            is_constant = True
        pattern = self._parse_destructuring_pattern()
        name_tok = None
        if not pattern:
            name_tok = self.consume_any({"IDENT", "KEYWORD"})
        if self.match_value("KEYWORD", "be"):
            expr = self.parse_expression()
        elif self.peek().type == "OP" and self.peek().value == "=":
            tok = self.peek()
            raise self.error("let x = ... is not supported. Write let x be ... instead.", tok)
        else:
            raise self.error("Expected 'be' after variable name", self.peek())
        if self.match_value("KEYWORD", "if"):
            raise self.error(
                "Inline conditional expressions like value if condition else other are not supported. Use an if / otherwise if / else block instead.",
                self.peek(),
            )
        if self.match("COLON"):
            self.consume("NEWLINE")
            self.consume("INDENT")
            pipeline_steps = self.parse_collection_pipeline_steps()
            self.consume("DEDENT")
            expr = ast_nodes.CollectionPipeline(source=expr, steps=pipeline_steps, span=self._span(start))
            self.optional_newline()
        return ast_nodes.LetStatement(
            name=name_tok.value if name_tok else "",
            expr=expr,
            uses_equals=False,
            is_constant=is_constant,
            pattern=pattern,
            span=self._span(start),
        )

    def parse_collection_pipeline_steps(self) -> list[ast_nodes.CollectionPipelineStep]:
        steps: list[ast_nodes.CollectionPipelineStep] = []
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            token = self.peek()
            if token.value == "keep":
                keep_tok = self.consume("KEYWORD", "keep")
                if not self.match_value("KEYWORD", "rows"):
                    raise self.error("Expected 'rows' after keep in collection pipeline.", self.peek())
                if not self.match_value("KEYWORD", "where"):
                    raise self.error("Expected 'where' in keep rows pipeline step.", self.peek())
                condition = self.parse_expression()
                steps.append(ast_nodes.CollectionKeepRowsStep(condition=condition, span=self._span(keep_tok)))
                self.optional_newline()
                continue
            if token.value == "drop":
                drop_tok = self.consume("KEYWORD", "drop")
                if not self.match_value("KEYWORD", "rows"):
                    raise self.error("Expected 'rows' after drop in collection pipeline.", self.peek())
                if not self.match_value("KEYWORD", "where"):
                    raise self.error("Expected 'where' in drop rows pipeline step.", self.peek())
                condition = self.parse_expression()
                steps.append(ast_nodes.CollectionDropRowsStep(condition=condition, span=self._span(drop_tok)))
                self.optional_newline()
                continue
            if token.value == "group":
                group_tok = self.consume("KEYWORD", "group")
                if not self.match_value("KEYWORD", "by"):
                    raise self.error("Expected 'by' after group in collection pipeline.", self.peek())
                key_expr = self.parse_expression()
                if not self.match("COLON"):
                    raise self.error("Expected ':' after group by key.", self.peek())
                self.consume("NEWLINE")
                self.consume("INDENT")
                body = self.parse_statement_block()
                self.consume("DEDENT")
                steps.append(ast_nodes.CollectionGroupByStep(key=key_expr, body=body, span=self._span(group_tok)))
                self.optional_newline()
                continue
            if token.value == "sort":
                sort_tok = self.consume("KEYWORD", "sort")
                kind_token = self.consume("KEYWORD")
                if kind_token.value not in {"rows", "groups"}:
                    raise self.error("sort must specify 'rows' or 'groups' before 'by'.", kind_token)
                if not self.match_value("KEYWORD", "by"):
                    raise self.error("Expected 'by' in sort pipeline step.", self.peek())
                key_expr = self.parse_expression()
                direction = "asc"
                if self.peek().value in {"descending", "ascending"}:
                    dir_tok = self.consume("KEYWORD")
                    direction = "desc" if dir_tok.value == "descending" else "asc"
                steps.append(
                    ast_nodes.CollectionSortStep(kind=kind_token.value, key=key_expr, direction=direction, span=self._span(sort_tok))
                )
                self.optional_newline()
                continue
            if token.value == "take":
                take_tok = self.consume("KEYWORD", "take")
                if not self.match_value("KEYWORD", "first"):
                    raise self.error("Expected 'first' after take in collection pipeline.", self.peek())
                count_expr = self.parse_expression()
                steps.append(ast_nodes.CollectionTakeStep(count=count_expr, span=self._span(take_tok)))
                self.optional_newline()
                continue
            if token.value == "skip":
                skip_tok = self.consume("KEYWORD", "skip")
                if not self.match_value("KEYWORD", "first"):
                    raise self.error("Expected 'first' after skip in collection pipeline.", self.peek())
                count_expr = self.parse_expression()
                steps.append(ast_nodes.CollectionSkipStep(count=count_expr, span=self._span(skip_tok)))
                self.optional_newline()
                continue
            raise self.error("Unexpected statement in collection pipeline.", token)
        return steps

    def parse_set_statement(self) -> ast_nodes.SetStatement:
        start = self.consume("KEYWORD", "set")
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
        full_name = name_tok.value or ""
        if self.match_value("OP", "."):
            field_tok = self.consume_any({"IDENT", "KEYWORD"})
            full_name = f"{name_tok.value}.{field_tok.value}"
        if self.match_value("KEYWORD", "be") or self.match_value("KEYWORD", "to"):
            expr = self.parse_expression()
        elif self.peek().type == "OP" and self.peek().value == "=":
            tok = self.peek()
            raise self.error("set state.x = ... is not supported. Write set state.x be ... instead.", tok)
        else:
            raise self.error("Expected 'be' or 'to' after target in set statement", self.peek())
        if self.match_value("KEYWORD", "if"):
            raise self.error(
                "Inline conditional expressions like value if condition else other are not supported. Use an if / otherwise if / else block instead.",
                self.peek(),
            )
        return ast_nodes.SetStatement(name=full_name, expr=expr, span=self._span(start))

    def parse_repeat_statement(self) -> ast_nodes.Statement:
        repeat_tok = self.consume("KEYWORD", "repeat")
        if self.peek().value == "for":
            self.consume("KEYWORD", "for")
            self.consume("KEYWORD", "each")
            pattern = self._parse_destructuring_pattern()
            var_tok = None
            if not pattern:
                var_tok = self.consume_any({"IDENT", "KEYWORD"})
            self.consume("KEYWORD", "in")
            if self.peek().value == "step" and self.peek_offset(1).type == "STRING":
                step_tok = self.consume("KEYWORD", "step")
                name_tok = self.consume("STRING")
                if self.peek().type in {"IDENT", "KEYWORD"} and self.peek().value == "output":
                    self.consume_any({"IDENT", "KEYWORD"})
                iterable_expr = ast_nodes.Identifier(name=f"step.{name_tok.value}.output", span=self._span(step_tok))
            else:
                iterable_expr = self.parse_expression()
            self.consume("COLON")
            self.consume("NEWLINE")
            self.consume("INDENT")
            body = self.parse_statement_block()
            self.consume("DEDENT")
            self.optional_newline()
            return ast_nodes.ForEachLoop(
                var_name=var_tok.value if var_tok else "item",
                pattern=pattern,
                iterable=iterable_expr,
                body=body,
                span=self._span(repeat_tok),
            )
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
        if kind_tok.value not in {"ai", "agent", "tool", "flow"}:
            raise self.error(f"Unsupported action kind '{kind_tok.value}'", kind_tok)
        target_tok = self.consume("STRING")
        message = None
        args: dict[str, ast_nodes.Expr] = {}
        if kind_tok.value == "flow" and self.peek().value == "with":
            self.consume("KEYWORD", "with")
            while True:
                key_tok = self.consume_any({"IDENT", "KEYWORD"})
                self.consume("COLON")
                val_expr = self.parse_expression()
                args[key_tok.value or ""] = val_expr
                if self.peek().type == "COMMA":
                    self.consume("COMMA")
                    continue
                break
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
            args=args,
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
        name_tok = self.consume_any({"IDENT", "KEYWORD"})
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
            if self.peek().value in {"let", "set", "if", "when", "otherwise", "unless", "match", "retry", "ask", "form", "log", "note", "checkpoint", "return", "guard"}:
                actions.append(self.parse_statement_or_action())
                continue
            actions.append(self._parse_do_action())
            self.optional_newline()
        return actions

    def parse_goto_action(self, allow_page: bool = False) -> ast_nodes.FlowAction:
        go_tok = self.consume("KEYWORD", "go")
        self.consume("KEYWORD", "to")
        target_kind_tok = self.consume_any({"KEYWORD", "IDENT"})
        if target_kind_tok.value not in {"flow", "page"}:
            raise self.error("Expected 'flow' or 'page' after 'go to'.", target_kind_tok)
        if not self.check("STRING"):
            raise self.error("Expected a string literal name after go to.", self.peek())
        target_tok = self.consume("STRING")
        kind = "goto_flow" if target_kind_tok.value == "flow" else "goto_page"
        if target_kind_tok.value == "page" and not allow_page:
            raise self.error("Unexpected 'go to page' in this context.", target_kind_tok)
        return ast_nodes.FlowAction(kind=kind, target=target_tok.value or "", span=self._span(go_tok))

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
        if token.value == "get":
            start = self.consume_any({"IDENT", "KEYWORD"})
            target_expr = self.parse_expression()
            self.consume("KEYWORD", "otherwise")
            default_expr = self.parse_expression()
            record_expr, field_name = self._split_field_access_expr(target_expr)
            if not field_name or record_expr is None:
                raise self.error(
                    "get ... otherwise ... requires a field access like record.field",
                    start,
                )
            return ast_nodes.GetRecordFieldWithDefault(record=record_expr, field=field_name, default=default_expr, span=self._span(start))
        if token.value == "has" and self.peek_offset(1).value == "key":
            start = self.consume_any({"IDENT", "KEYWORD"})
            self.consume("KEYWORD", "key")
            key_tok = self.consume("STRING")
            self.consume("KEYWORD", "on")
            record_expr = self.parse_expression()
            return ast_nodes.HasKeyOnRecord(record=record_expr, key=key_tok.value or "", span=self._span(start))
        builtin_call_names = {
            "length",
            "first",
            "last",
            "sorted",
            "reverse",
            "unique",
            "sum",
            "count",
            "append",
            "remove",
            "insert",
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
        if token.type == "KEYWORD" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "count", "append", "remove", "insert", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "round", "absolute", "current", "random"}:
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
            if self.peek_offset(1).type == "LPAREN" and token.value in {"length", "first", "last", "sorted", "reverse", "unique", "sum", "count", "append", "remove", "insert", "filter", "map", "trim", "lowercase", "uppercase", "replace", "split", "join", "slugify", "minimum", "maximum", "mean", "min", "max", "average", "round", "abs", "current_timestamp", "current_date", "random_uuid", "any", "all"}:
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
                    expr = ast_nodes.VarRef(name=value, root=parts[0], path=parts[1:], kind=ast_nodes.VarRefKind.UNKNOWN, span=self._span(tok))
                else:
                    expr = ast_nodes.VarRef(name=value, root=value, path=[], kind=ast_nodes.VarRefKind.UNKNOWN, span=self._span(tok))
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
        elif name in {"length", "first", "last", "reverse", "sum", "count"}:
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
        elif name == "append":
            list_expr = self.parse_expression()
            self.consume("KEYWORD", "with")
            value_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="append", args=[list_expr, value_expr])
        elif name == "remove":
            value_expr = self.parse_expression()
            self.consume("KEYWORD", "from")
            list_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="remove", args=[list_expr, value_expr])
        elif name == "insert":
            value_expr = self.parse_expression()
            self.consume("KEYWORD", "at")
            index_expr = self.parse_expression()
            self.consume("KEYWORD", "into")
            list_expr = self.parse_expression()
            return ast_nodes.BuiltinCall(name="insert", args=[list_expr, index_expr, value_expr])
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
            return ast_nodes.ListBuiltinCall(name=name, expr=operand)
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
        start = self.consume("KEYWORD", "all")
        # Legacy data syntax is no longer supported; guide users to pipelines.
        raise self.error(
            "The legacy 'all ...' data syntax is no longer supported. Use a collection pipeline instead, for example:\n"
            "let filtered be <source>:\n"
            "  keep rows where ...",
            start,
        )

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
            raise self.error(
                "filter(...) / map(...) are no longer supported. Use a collection pipeline instead (for example: keep rows where ...).",
                name_tok,
            )
        if name in {"any", "all"}:
            raise self.error(
                f"The legacy '{name}(...)' data syntax is no longer supported. Rewrite this as a collection pipeline with keep rows where ....",
                name_tok,
            )
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
