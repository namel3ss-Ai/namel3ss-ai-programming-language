"""Agent declaration parsing extracted from the legacy parser."""

from __future__ import annotations

from difflib import get_close_matches

from namel3ss import ast_nodes

__all__ = ["parse_agent", "parse_agent_evaluation"]


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
    allowed_fields: set[str] = {"goal", "personality", "system", "system_prompt", "memory", "role", "can_delegate_to"}
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
