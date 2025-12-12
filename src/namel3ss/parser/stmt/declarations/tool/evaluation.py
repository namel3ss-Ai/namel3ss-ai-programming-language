"""Tool evaluation parsing helpers extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_tool_evaluation"]


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
                        elif inner_tok.value == "measures":
                            while True:
                                item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                                _append_metric(item_tok.value or "")
                                if not self.match("COMMA"):
                                    break
                        else:
                            raise self.error(f"Unexpected field '{inner_tok.value}' in metrics", inner_tok)
                        self.optional_newline()
                    metrics = m_list
                    self.consume("DEDENT")
                else:
                    metrics = []
                    while True:
                        item_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        if item_tok.value:
                            if item_tok.value not in metrics:
                                metrics.append(item_tok.value)
                        if not self.match("COMMA"):
                            break
                self.optional_newline()
                continue
            raise self.error(f"Unexpected field '{field}' in tool evaluation block", tok)
        self.consume("DEDENT")
    self.optional_newline()

    return ast_nodes.ToolEvaluationDecl(
        name=name_tok.value or "",
        tool=tool_name,
        dataset_frame=dataset_frame,
        input_mapping=input_mapping,
        expected=expected_cfg,
        metrics=metrics,
        span=self._span(start),
    )
