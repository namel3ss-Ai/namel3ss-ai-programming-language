import pytest
from textwrap import dedent

from namel3ss import ast_nodes
from namel3ss.errors import ParseError
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRError


def test_graph_and_summary_parse():
    src = dedent(
        '''
    graph is "support_graph":
      from frame is "docs"
      id_column is "doc_id"
      text_column is "content"
      entities:
        model is "gpt-4o-mini"
        max_entities_per_doc is 5
      relations:
        model is "gpt-4o-mini"
        max_relations_per_entity is 3

    graph_summary is "support_graph_summary":
      graph is "support_graph"
      method is "community"
      max_nodes_per_summary is 50
      model is "gpt-4o-mini"
    '''
    )
    module = parse_source(src)
    graphs = [d for d in module.declarations if isinstance(d, ast_nodes.GraphDecl)]
    summaries = [d for d in module.declarations if isinstance(d, ast_nodes.GraphSummaryDecl)]
    assert graphs and summaries
    g = graphs[0]
    assert g.source_frame == "docs"
    assert g.entities.model == "gpt-4o-mini"
    s = summaries[0]
    assert s.graph == "support_graph"
    assert s.method == "community"


def test_graph_legacy_style_errors():
    bad = dedent('graph "legacy":\n  from frame is "docs"\n')
    with pytest.raises(ParseError):
        parse_source(bad)


def test_graph_pipeline_stage_parses_and_validates():
    src = dedent(
        '''
    rag pipeline is "graph_pipe":
      stage is "graph_stage":
        type is "graph_query"
        graph is "g"
      stage is "summary":
        type is "graph_summary_lookup"
        graph_summary is "gs"

    frame is "f":
      file is "tests/fixtures/sales.csv"
      has headers

    graph is "g":
      from frame is "f"
      text_column is "text"
      id_column is "id"
      entities:
        model is "m"

    graph_summary is "gs":
      graph is "g"
    '''
    )
    module = parse_source(src)
    program = ast_to_ir(module)
    assert "graph_pipe" in program.rag_pipelines
    assert "g" in program.graphs
    assert "gs" in program.graph_summaries


def test_missing_graph_in_stage_raises():
    src = dedent(
        '''
    rag pipeline is "graph_pipe":
      stage is "graph_stage":
        type is "graph_query"
        graph is "unknown"

    frame is "f":
      file is "tests/fixtures/sales.csv"
      has headers
    '''
    )
    module = parse_source(src)
    with pytest.raises(IRError):
        ast_to_ir(module)
