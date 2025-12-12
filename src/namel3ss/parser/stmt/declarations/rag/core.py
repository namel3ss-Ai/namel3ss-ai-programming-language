"""RAG pipeline and evaluation parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_rag_pipeline", "parse_rag_evaluation"]


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
                pipe_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                pipeline_name = pipe_tok.value
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
            if field == "question_column":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.peek().value == "is":
                    self.consume_any({"KEYWORD"})
                q_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                question_column = q_tok.value
                self.optional_newline()
                continue
            if field == "answer_column":
                self.consume_any({"KEYWORD", "IDENT"})
                if self.peek().value == "is":
                    self.consume_any({"KEYWORD"})
                a_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                answer_column = a_tok.value
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
