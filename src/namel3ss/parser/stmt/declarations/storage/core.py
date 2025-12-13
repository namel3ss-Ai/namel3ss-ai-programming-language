"""Vector store and frame parsing extracted from the legacy parser."""

from __future__ import annotations

from namel3ss import ast_nodes

__all__ = ["parse_vector_store", "parse_frame"]


def parse_vector_store(self) -> ast_nodes.VectorStoreDecl:
    start = self.consume("KEYWORD", "vector_store")
    if self.match_value("KEYWORD", "is"):
        name = self.consume_any({"STRING", "IDENT"})
    else:
        tok = self.peek()
        if tok.type in {"STRING", "IDENT"}:
            raise self.error(f'vector_store "{tok.value}": is not supported. Use vector_store is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'vector_store'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")
    backend = None
    frame_name = None
    text_column = None
    id_column = None
    embedding_model = None
    metadata_columns = None
    allowed_fields = {
        "backend",
        "frame",
        "text_column",
        "id_column",
        "embedding_model",
        "metadata_columns",
    }
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        field_token = self.consume_any({"KEYWORD", "IDENT"})
        field = field_token.value or ""
        if field not in allowed_fields:
            raise self.error(f"Unexpected field '{field}' in vector_store block", field_token)
        if field == "backend":
            if self.match_value("KEYWORD", "is"):
                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            backend = backend_tok.value
        elif field == "frame":
            if self.match_value("KEYWORD", "is"):
                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            frame_name = frame_tok.value
        elif field == "text_column":
            if self.match_value("KEYWORD", "is"):
                text_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                text_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            text_column = text_tok.value
        elif field == "id_column":
            if self.match_value("KEYWORD", "is"):
                id_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                id_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            id_column = id_tok.value
        elif field == "embedding_model":
            if self.match_value("KEYWORD", "is"):
                emb_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                emb_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            embedding_model = emb_tok.value
        elif field == "metadata_columns":
            if self.match_value("KEYWORD", "are"):
                self.consume_any({"KEYWORD"})
            if not self.match("LBRACKET"):
                raise self.error("Expected '[' after metadata_columns", self.peek())
            cols = []
            if not self.check("RBRACKET"):
                while True:
                    col_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                    cols.append(col_tok.value or "")
                    if self.match("COMMA"):
                        continue
                    break
            self.consume("RBRACKET")
            metadata_columns = cols
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.VectorStoreDecl(
        name=name.value or "",
        backend=backend,
        frame=frame_name,
        text_column=text_column,
        id_column=id_column,
        embedding_model=embedding_model,
        metadata_columns=metadata_columns or [],
        span=self._span(start),
    )


def parse_frame(self) -> ast_nodes.FrameDecl:
    start = self.consume("KEYWORD", "frame")
    if self.match_value("KEYWORD", "is"):
        name = self.consume("STRING")
    else:
        tok = self.peek()
        if tok.type == "STRING":
            raise self.error(f'frame "{tok.value}": is not supported. Use frame is "{tok.value}": instead.', tok)
        raise self.error("Expected 'is' after 'frame'", tok)
    self.consume("COLON")
    self.consume("NEWLINE")
    self.consume("INDENT")

    source = None
    backend = None
    table = None
    primary_key = None
    delimiter = None
    has_headers: bool | None = None
    fields: list[ast_nodes.FrameFieldDecl] = []
    table_config: ast_nodes.FrameTableConfig | None = None
    allowed_fields = {
        "source",
        "backend",
        "url",
        "file",
        "table",
        "primary_key",
        "delimiter",
        "has",
        "headers",
        "fields",
    }
    while not self.check("DEDENT"):
        if self.match("NEWLINE"):
            continue
        tok = self.peek()
        field = tok.value or ""
        if field not in allowed_fields:
            raise self.error(f"Unexpected field '{field}' in frame block", tok)
        if field == "source":
            self.consume("KEYWORD", "source")
            if self.match_value("KEYWORD", "is"):
                src_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                src_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            source = src_tok.value
        elif field == "backend":
            self.consume("KEYWORD", "backend")
            if self.match_value("KEYWORD", "is"):
                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                backend_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            backend = backend_tok.value
        elif field == "url":
            self.consume("KEYWORD", "url")
            if self.match_value("KEYWORD", "is"):
                url_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                url_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            source = url_tok.value
        elif field == "file":
            self.consume("KEYWORD", "file")
            if self.match_value("KEYWORD", "is"):
                file_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                file_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            source = file_tok.value
        elif field == "table":
            self.consume("KEYWORD", "table")
            self.match_value("KEYWORD", "is")
            if self.match("COLON"):
                self.consume("NEWLINE")
                self.consume("INDENT")
                pk = None
                display_columns: list[str] = []
                time_col = None
                text_col = None
                image_col = None
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    prop_tok = self.consume_any({"KEYWORD", "IDENT"})
                    if prop_tok.value == "primary_key":
                        if self.match_value("KEYWORD", "is"):
                            pass
                        pk_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        pk = pk_tok.value
                    elif prop_tok.value == "display_columns":
                        if self.match_value("KEYWORD", "is") or self.match_value("KEYWORD", "are"):
                            pass
                        cols_expr = self.parse_expression()
                        if isinstance(cols_expr, ast_nodes.ListLiteral):
                            display_columns = [
                                el.value for el in cols_expr.items if isinstance(el, ast_nodes.Literal)
                            ]
                    elif prop_tok.value == "time_column":
                        if self.match_value("KEYWORD", "is"):
                            pass
                        time_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        time_col = time_tok.value
                    elif prop_tok.value == "text_column":
                        if self.match_value("KEYWORD", "is"):
                            pass
                        text_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        text_col = text_tok.value
                    elif prop_tok.value == "image_column":
                        if self.match_value("KEYWORD", "is"):
                            pass
                        img_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                        image_col = img_tok.value
                    else:
                        raise self.error(f"Unexpected field '{prop_tok.value}' in table block", prop_tok)
                    self.optional_newline()
                self.consume("DEDENT")
                table_config = ast_nodes.FrameTableConfig(
                    primary_key=pk,
                    display_columns=display_columns,
                    time_column=time_col,
                    text_column=text_col,
                    image_column=image_col,
                    span=self._span(tok),
                )
                if primary_key is None and pk is not None:
                    primary_key = pk
            else:
                table_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                table = table_tok.value
        elif field == "primary_key":
            self.consume("KEYWORD", "primary_key")
            pk_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            primary_key = pk_tok.value
        elif field == "delimiter":
            self.consume("KEYWORD", "delimiter")
            if self.match_value("KEYWORD", "is"):
                delim_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            else:
                delim_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
            delimiter = delim_tok.value
        elif field == "has":
            self.consume("KEYWORD", "has")
            hdr_tok = self.consume("KEYWORD", "headers")
            has_headers = True
        elif field == "headers":
            if has_headers is None:
                has_headers = True
        elif field == "fields":
            self.consume("KEYWORD", "fields")
            self.consume("COLON")
            self.consume("NEWLINE")
            if self.check("INDENT"):
                self.consume("INDENT")
                while not self.check("DEDENT"):
                    if self.match("NEWLINE"):
                        continue
                    field_name_tok = self.consume_any({"KEYWORD", "IDENT", "STRING"})
                    self.consume("COLON")
                    self.consume("NEWLINE")
                    self.consume("INDENT")
                    field_type: str | None = None
                    is_pk = False
                    ref_frame = None
                    ref_field = None
                    while not self.check("DEDENT"):
                        if self.match("NEWLINE"):
                            continue
                        prop_tok = self.consume_any({"KEYWORD", "IDENT"})
                        if prop_tok.value == "type":
                            if self.match_value("KEYWORD", "is"):
                                type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                type_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            field_type = type_tok.value
                        elif prop_tok.value == "key":
                            is_pk = True
                            if self.match_value("KEYWORD", "is"):
                                pass
                        elif prop_tok.value == "ref":
                            if self.match_value("KEYWORD", "is"):
                                ref_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                ref_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            ref_field = ref_tok.value
                        elif prop_tok.value == "frame":
                            if self.match_value("KEYWORD", "is"):
                                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            else:
                                frame_tok = self.consume_any({"STRING", "IDENT", "KEYWORD"})
                            ref_frame = frame_tok.value
                        else:
                            raise self.error(
                                f"Unexpected field '{prop_tok.value}' in frame field",
                                prop_tok,
                            )
                        self.optional_newline()
                    self.consume("DEDENT")
                    fields.append(
                        ast_nodes.FrameFieldDecl(
                            name=field_name_tok.value or "",
                            type=field_type,
                            is_primary_key=is_pk,
                            ref_frame=ref_frame,
                            ref_field=ref_field,
                            span=self._span(field_name_tok),
                        )
                    )
                self.consume("DEDENT")
        self.optional_newline()
    self.consume("DEDENT")
    self.optional_newline()
    return ast_nodes.FrameDecl(
        name=name.value or "",
        source_path=source,
        backend=backend,
        table=table,
        primary_key=primary_key,
        delimiter=delimiter,
        has_headers=has_headers,
        table_config=table_config,
        span=self._span(start),
    )
