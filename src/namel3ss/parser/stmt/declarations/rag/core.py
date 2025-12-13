"""RAG pipeline and evaluation parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_rag_pipeline", "parse_rag_evaluation", "_parse_rag_stage"]


def _parse_rag_stage(self) -> ast_nodes.RagPipelineStageDecl:
    start = self.consume("KEYWORD", "stage")
    if self.match_value("KEYWORD", "is"):
        name_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
    else:
        tok = self.peek()
        if tok.type in {"STRING", "IDENT", "KEYWORD"}:
            raise self.error(
                f'stage "{tok.value}": is not supported. Use stage is "{tok.value}": instead.',
                tok,
            )
        raise self.error("Expected 'is' after 'stage'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    # Defaults
    stage_type: str | None = None
    ai: str | None = None
    vector_store: str | None = None
    frame: str | None = None
    match_column: str | None = None
    text_column: str | None = None
    image_column: str | None = None
    embedding_model: str | None = None
    output_vector_store: str | None = None
    max_items: ast_nodes.Expr | None = None
    graph: str | None = None
    graph_summary: str | None = None
    top_k: ast_nodes.Expr | None = None
    where_expr: ast_nodes.Expr | None = None
    max_rows: ast_nodes.Expr | None = None
    group_by: str | None = None
    max_groups: ast_nodes.Expr | None = None
    max_rows_per_group: ast_nodes.Expr | None = None
    choices: list[str] | None = None
    max_queries: ast_nodes.Expr | None = None
    max_subquestions: ast_nodes.Expr | None = None
    from_stages: list[str] | None = None
    method: str | None = None
    max_hops: ast_nodes.Expr | None = None
    max_nodes: ast_nodes.Expr | None = None
    strategy: str | None = None
    max_tokens: ast_nodes.Expr | None = None

    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        field = tok.value or ""
        self.consume_any({"KEYWORD", "IDENT"})
        if field == "type":
            if self.match_value("KEYWORD", "is"):
                pass
            type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            stage_type = type_tok.value
            self.optional_newline()
            continue
        if field == "ai":
            if self.match_value("KEYWORD", "is"):
                pass
            ai_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            ai = ai_tok.value
            self.optional_newline()
            continue
        if field in {
            "vector_store",
            "frame",
            "match_column",
            "text_column",
            "embedding_model",
            "output_vector_store",
            "graph",
            "graph_summary",
            "group_by",
            "strategy",
            "method",
            "image_column",
        }:
            if self.match_value("KEYWORD", "is"):
                pass
            val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            if field == "vector_store":
                vector_store = val_tok.value
            elif field == "frame":
                frame = val_tok.value
            elif field == "match_column":
                match_column = val_tok.value
            elif field == "text_column":
                text_column = val_tok.value
            elif field == "image_column":
                image_column = val_tok.value
            elif field == "embedding_model":
                embedding_model = val_tok.value
            elif field == "output_vector_store":
                output_vector_store = val_tok.value
            elif field == "graph":
                graph = val_tok.value
            elif field == "graph_summary":
                graph_summary = val_tok.value
            elif field == "group_by":
                group_by = val_tok.value
            elif field == "strategy":
                strategy = val_tok.value
            elif field == "method":
                method = val_tok.value
            self.optional_newline()
            continue
        if field in {"max_items", "top_k", "max_rows", "max_groups", "max_rows_per_group", "max_queries", "max_subquestions", "max_hops", "max_nodes", "max_tokens"}:
            if self.match_value("KEYWORD", "is"):
                pass
            expr_val = self.parse_expression()
            if field == "max_items":
                max_items = expr_val
            elif field == "top_k":
                top_k = expr_val
            elif field == "max_rows":
                max_rows = expr_val
            elif field == "max_groups":
                max_groups = expr_val
            elif field == "max_rows_per_group":
                max_rows_per_group = expr_val
            elif field == "max_queries":
                max_queries = expr_val
            elif field == "max_subquestions":
                max_subquestions = expr_val
            elif field == "max_hops":
                max_hops = expr_val
            elif field == "max_nodes":
                max_nodes = expr_val
            elif field == "max_tokens":
                max_tokens = expr_val
            self.optional_newline()
            continue
        if field == "where":
            if self.match_value("KEYWORD", "is"):
                pass
            where_expr = self.parse_expression()
            self.optional_newline()
            continue
        if field == "choices":
            if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                pass
            if self.peek().type == "LBRACKET":
                choices = self._parse_string_list_literal(self.peek())
            else:
                val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                choices = [val_tok.value or ""]
            self.optional_newline()
            continue
        if field in {"from", "from_stages"}:
            if self.match_value("KEYWORD", "are") or self.match_value("KEYWORD", "is"):
                pass
            if self.peek().type == "LBRACKET":
                from_stages = self._parse_string_list_literal(self.peek())
            else:
                val_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                from_stages = [val_tok.value or ""]
            self.optional_newline()
            continue
        raise self.error(f"Unexpected field '{field}' in rag stage block", tok)
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.RagPipelineStageDecl(
        name=name_tok.value or "",
        type=stage_type or "",
        ai=ai,
        vector_store=vector_store,
        frame=frame,
        match_column=match_column,
        text_column=text_column,
        image_column=image_column,
        embedding_model=embedding_model,
        output_vector_store=output_vector_store,
        max_items=max_items,
        graph=graph,
        graph_summary=graph_summary,
        top_k=top_k,
        where=where_expr,
        max_rows=max_rows,
        group_by=group_by,
        max_groups=max_groups,
        max_rows_per_group=max_rows_per_group,
        choices=choices,
        max_queries=max_queries,
        max_subquestions=max_subquestions,
        from_stages=from_stages,
        method=method,
        max_hops=max_hops,
        max_nodes=max_nodes,
        strategy=strategy,
        max_tokens=max_tokens,
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
