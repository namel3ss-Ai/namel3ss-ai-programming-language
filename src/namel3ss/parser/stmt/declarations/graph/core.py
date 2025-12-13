"""Graph and graph summary parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_graph", "parse_graph_summary"]


def parse_graph(self) -> ast_nodes.GraphDecl:
    start = self.consume("KEYWORD", "graph")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'graph "{tok.value}": is not supported. Use graph is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'graph'", tok)
    source_frame: str | None = None
    id_column: str | None = None
    text_column: str | None = None
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
                self.consume_any({"KEYWORD", "IDENT"})  # frame
                if self.match_value("KEYWORD", "is"):
                    frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                source_frame = frame_tok.value
            elif field == "id_column":
                if self.match_value("KEYWORD", "is"):
                    pass
                id_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                id_column = id_tok.value
            elif field == "text_column":
                if self.match_value("KEYWORD", "is"):
                    pass
                text_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                text_column = text_tok.value
            elif field == "entities":
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    model_name = None
                    max_entities = None
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        ent_field = self.consume_any({"KEYWORD", "IDENT"})
                        if ent_field.value == "model":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            model_name = model_tok.value
                        elif ent_field.value == "max_entities_per_doc":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            max_entities = self.parse_expression()
                        else:
                            raise self.error(f"Unexpected field '{ent_field.value}' in entities block.", ent_field)
                        self.optional_newline()
                    self.consume("DEDENT")
                    entities_cfg = ast_nodes.GraphEntitiesConfig(
                        model=model_name,
                        max_entities_per_doc=max_entities,
                        span=self._span(field_tok),
                    )
            elif field == "relations":
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    model_name = None
                    max_rel = None
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        rel_field = self.consume_any({"KEYWORD", "IDENT"})
                        if rel_field.value == "model":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            model_name = model_tok.value
                        elif rel_field.value == "max_relations_per_entity":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            max_rel = self.parse_expression()
                        else:
                            raise self.error(f"Unexpected field '{rel_field.value}' in relations block.", rel_field)
                        self.optional_newline()
                    self.consume("DEDENT")
                    relations_cfg = ast_nodes.GraphRelationsConfig(
                        model=model_name,
                        max_relations_per_entity=max_rel,
                        span=self._span(field_tok),
                    )
            elif field == "storage":
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    nodes_frame = None
                    edges_frame = None
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        stor_field = self.consume_any({"KEYWORD", "IDENT"})
                        if stor_field.value == "nodes_frame":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            nf_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            nodes_frame = nf_tok.value
                        elif stor_field.value == "edges_frame":
                            if self.match_value("KEYWORD", "is"):
                                pass
                            ef_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            edges_frame = ef_tok.value
                        else:
                            raise self.error(f"Unexpected field '{stor_field.value}' in storage block.", stor_field)
                        self.optional_newline()
                    self.consume("DEDENT")
                    storage_cfg = ast_nodes.GraphStorageConfig(
                        nodes_frame=nodes_frame,
                        edges_frame=edges_frame,
                        span=self._span(field_tok),
                    )
            else:
                raise self.error(f"Unexpected field '{field}' in graph block", field_tok)
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.GraphDecl(
        name=name.value or "",
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
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'graph_summary "{tok.value}": is not supported. Use graph_summary is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'graph_summary'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    graph = None
    method = None
    max_nodes_per_summary = None
    model_name = None
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field = field_tok.value or ""
            if field == "graph":
                if self.match_value("KEYWORD", "is"):
                    pass
                graph_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                graph = graph_tok.value
            elif field == "method":
                if self.match_value("KEYWORD", "is"):
                    pass
                method_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                method = method_tok.value
            elif field == "max_nodes_per_summary":
                if self.match_value("KEYWORD", "is"):
                    pass
                max_nodes_per_summary = self.parse_expression()
            elif field == "model":
                if self.match_value("KEYWORD", "is"):
                    pass
                model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                model_name = model_tok.value
            else:
                raise self.error(f"Unexpected field '{field}' in graph_summary block", field_tok)
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.GraphSummaryDecl(
        name=name.value or "",
        graph=graph,
        method=method,
        max_nodes_per_summary=max_nodes_per_summary,
        model=model_name,
        span=self._span(start),
    )
