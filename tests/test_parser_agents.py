from textwrap import dedent

from namel3ss import parser, ast_nodes


def test_parse_agent_metadata_and_evaluation():
    source = dedent(
        """
agent is "router":
  goal is "Route requests"
  role is "router"
  can_delegate_to are ["billing_agent", "tech_agent"]

agent evaluation is "router_eval":
  agent is "router"
  dataset_frame is "cases"
  input_mapping:
    question is "q"
  expected:
    answer_column is "expected"
    allow_llm_judge is true
    judge_model is "judge"
  metrics:
    - "answer_correctness"
    - "latency_seconds"
"""
    ).strip()
    module = parser.parse_source(source)
    agents = [d for d in module.declarations if isinstance(d, ast_nodes.AgentDecl)]
    assert agents[0].role == "router"
    assert agents[0].can_delegate_to == ["billing_agent", "tech_agent"]
    eval_decl = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentEvaluationDecl))
    assert eval_decl.agent == "router"
    assert eval_decl.expected.answer_column == "expected"
    assert eval_decl.expected.allow_llm_judge is True
    assert eval_decl.metrics == ["answer_correctness", "latency_seconds"]
