import pytest
from textwrap import dedent

from namel3ss import ast_nodes
from namel3ss.errors import ParseError, IRError
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir


def test_frame_with_table_block_parses():
    src = dedent(
        '''
    frame is "orders":
      file is "tests/fixtures/sales.csv"
      has headers
      table is:
        primary_key is "id"
        display_columns are ["customer_name", "status"]
        time_column is "created_at"
        text_column is "notes"
        image_column is "receipt_image"
    '''
    )
    module = parse_source(src)
    frame = next(d for d in module.declarations if isinstance(d, ast_nodes.FrameDecl))
    assert frame.table_config
    assert frame.table_config.primary_key == "id"
    assert "customer_name" in frame.table_config.display_columns
    program = ast_to_ir(module)
    assert "orders" in program.frames
    assert program.frames["orders"].table_config


def test_top_level_table_errors():
    with pytest.raises(ParseError):
        parse_source('table is "orders":\n  primary_key is "id"\n')


def test_rag_stages_parse_with_table_and_multimodal():
    src = dedent(
        '''
    rag pipeline is "orders_support":
      stage is "lookup":
        type is "table_lookup"
        frame is "orders"
        match_column is "customer_name"
        max_rows is 10
      stage is "summarise":
        type is "table_summarise"
        frame is "orders"
        group_by is "status"
      stage is "embed_images":
        type is "multimodal_embed"
        frame is "orders"
        image_column is "image_url"
        text_column is "description"
        output_vector_store is "media_vectors"
      stage is "captions":
        type is "multimodal_summarise"
        frame is "orders"
        image_column is "image_url"
        text_column is "description"

    frame is "orders":
      file is "tests/fixtures/sales.csv"
      has headers
      table is:
        primary_key is "id"
        display_columns are ["customer_name", "status"]

    vector_store is "media_vectors":
      backend is "memory"
      frame is "orders"
      text_column is "description"
      id_column is "id"
      embedding_model is "default_embedding"
    '''
    )
    module = parse_source(src)
    program = ast_to_ir(module)
    assert "orders_support" in program.rag_pipelines
    stages = program.rag_pipelines["orders_support"].stages
    assert any(st.type == "table_lookup" for st in stages)
    assert any(st.type == "table_summarise" for st in stages)
    assert any(st.type == "multimodal_embed" for st in stages)
    assert any(st.type == "multimodal_summarise" for st in stages)
