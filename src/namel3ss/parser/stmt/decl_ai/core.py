"""AI declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from difflib import get_close_matches

from .... import ast_nodes

__all__ = ["parse_ai", "parse_ai_called_block", "_parse_ai_tools_block", "_parse_ai_tool_binding_entry"]

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
