import pytest
from textwrap import dedent

from namel3ss import parser, ast_nodes
from namel3ss.errors import ParseError


def test_rag_evaluation_metrics_mixed():
    src = dedent(
        """
    rag evaluation is "rag_eval":
      pipeline is "pipe"
      dataset:
        from frame "cases"
        question_column is "question"
      metrics:
        measure is "latency_seconds"
        measures are ["answer_correctness", "latency_seconds", "error_rate"]
    """
    )
    module = parser.parse_source(src)
    decl = next(d for d in module.declarations if isinstance(d, ast_nodes.RagEvaluationDecl))
    assert decl.metrics == ["latency_seconds", "answer_correctness", "error_rate"]


def test_tool_evaluation_metrics_list():
    src = dedent(
        """
    tool evaluation is "t_eval":
      tool is "weather"
      dataset_frame is "cases"
      metrics:
        measures are ["success_rate", "error_rate", "latency_ms"]

    """
    )
    module = parser.parse_source(src)
    decl = next(d for d in module.declarations if isinstance(d, ast_nodes.ToolEvaluationDecl))
    assert decl.metrics == ["success_rate", "error_rate", "latency_ms"]


def test_agent_evaluation_metrics_list():
    src = dedent(
        """
    agent evaluation is "a_eval":
      agent is "support"
      dataset_frame is "cases"
      metrics:
        measure is "latency_seconds"
        measures are ["answer_correctness", "tool_usage_correctness"]
    """
    )
    module = parser.parse_source(src)
    decl = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentEvaluationDecl))
    assert decl.metrics == ["latency_seconds", "answer_correctness", "tool_usage_correctness"]


def test_invalid_measures_syntax_errors():
    src = dedent(
        """
    rag evaluation is "bad":
      pipeline is "p"
      dataset:
        from frame "cases"
        question_column is "q"
      metrics:
        measures are "answer_correctness"
    """
    )
    with pytest.raises(ParseError):
        parser.parse_source(src)
