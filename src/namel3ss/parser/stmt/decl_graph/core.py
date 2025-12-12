"""Graph and graph summary parsing extracted from the legacy parser."""

from __future__ import annotations

from .... import ast_nodes

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
    description = None
    if self.match_value("KEYWORD", "description"):
        desc_tok = self.consume("STRING")
        description = desc_tok.value
    nodes: list[ast_nodes.GraphNodeDecl] = []
    relationships: list[ast_nodes.GraphRelationshipDecl] = []
    vector_store = None
    self.consume("COLON")
    self.consume("NEWLINE")
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field = field_tok.value or ""
            if field == "vector_store":
                self.consume("KEYWORD", "is")
                vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                vector_store = vs_tok.value
            elif field == "nodes":
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        ent_field = self.consume_any({"KEYWORD", "IDENT"})
                        if ent_field.value != "entity":
                            raise self.error("Expected 'entity' in nodes block.", ent_field)
                        if self.match_value("KEYWORD", "is"):
                            node_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        else:
                            node_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        node_name = node_tok.value or ""
                        model_name = None
                        if self.match_value("KEYWORD", "model"):
                            if self.match_value("KEYWORD", "is"):
                                model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            model_name = model_tok.value
                        nodes.append(
                            ast_nodes.GraphNodeDecl(
                                name=node_name,
                                model=model_name,
                                span=self._span(node_tok),
                            )
                        )
                        self.optional_newline()
                    self.consume("DEDENT")
            elif field == "relationships":
                self.consume("COLON")
                self.consume("NEWLINE")
                if self.check("INDENT"):
                    self.consume("INDENT")
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        rel_field = self.consume_any({"KEYWORD", "IDENT"})
                        if rel_field.value != "relationship":
                            raise self.error("Expected 'relationship' in relationships block.", rel_field)
                        if self.match_value("KEYWORD", "is"):
                            rel_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        else:
                            rel_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        rel_name = rel_tok.value or ""
                        model_name = None
                        if self.match_value("KEYWORD", "model"):
                            if self.match_value("KEYWORD", "is"):
                                model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            model_name = model_tok.value
                        relationships.append(
                            ast_nodes.GraphRelationshipDecl(
                                name=rel_name,
                                model=model_name,
                                span=self._span(rel_tok),
                            )
                        )
                        self.optional_newline()
                    self.consume("DEDENT")
            else:
                raise self.error(f"Unexpected field '{field}' in graph block", field_tok)
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.GraphDecl(
        name=name.value or "",
        description=description,
        vector_store=vector_store,
        nodes=nodes,
        relationships=relationships,
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
    vector_store = None
    model_name = None
    description = None
    max_nodes = None
    span_nodes = None
    if self.check("INDENT"):
        self.consume("INDENT")
        while not self.check("DEDENT"):
            if self.match("NEWLINE"):
                continue
            field_tok = self.consume_any({"KEYWORD", "IDENT"})
            field = field_tok.value or ""
            if field == "vector_store":
                if self.match_value("KEYWORD", "is"):
                    vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    vs_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                vector_store = vs_tok.value
            elif field == "model":
                if self.match_value("KEYWORD", "is"):
                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    model_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                model_name = model_tok.value
            elif field == "description":
                if self.match_value("KEYWORD", "is"):
                    desc_tok = self.consume("STRING")
                else:
                    desc_tok = self.consume("STRING")
                description = desc_tok.value
            elif field == "max_nodes":
                if self.match_value("KEYWORD", "is"):
                    max_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    max_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                max_nodes = max_tok.value
            elif field == "span_nodes":
                if self.match_value("KEYWORD", "is"):
                    span_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                else:
                    span_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                span_nodes = span_tok.value
            else:
                raise self.error(f"Unexpected field '{field}' in graph_summary block", field_tok)
            self.optional_newline()
        self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.GraphSummaryDecl(
        name=name.value or "",
        vector_store=vector_store,
        model=model_name,
        description=description,
        max_nodes=max_nodes,
        span_nodes=span_nodes,
        span=self._span(start),
    )
