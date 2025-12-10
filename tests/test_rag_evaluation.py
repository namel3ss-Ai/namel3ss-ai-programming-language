import json
from pathlib import Path

import pytest

from namel3ss import parser
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import IRError, Namel3ssError
from namel3ss.ir import (
    IRFrame,
    IRProgram,
    IRRagEvaluation,
    IRRagPipeline,
    ast_to_ir,
)
from namel3ss.rag.eval import (
    RagEvaluationResult,
    RagEvaluationRow,
    run_rag_evaluation,
    run_rag_evaluation_by_name,
)
from namel3ss.tools.registry import ToolRegistry
from namel3ss.flows.engine import FlowEngine
from namel3ss.cli import main as cli_main


def _build_stub_engine(rows):
    program = IRProgram()
    frame = IRFrame(name="eval_questions", backend="memory", table="eval_questions", select_cols=[])
    program.frames[frame.name] = frame
    pipeline = IRRagPipeline(name="pipe", stages=[])
    program.rag_pipelines[pipeline.name] = pipeline
    eval_cfg = IRRagEvaluation(
        name="eval1",
        pipeline="pipe",
        dataset_frame=frame.name,
        question_column="question",
        answer_column="expected",
        metrics=["context_relevance", "answer_faithfulness", "answer_completeness"],
    )
    program.rag_evaluations[eval_cfg.name] = eval_cfg

    model_registry = ModelRegistry()
    model_registry.register_model("default", provider_name=None)
    tool_registry = ToolRegistry()
    router = ModelRouter(model_registry)
    agent_runner = AgentRunner(program, model_registry, tool_registry, router)
    flow_engine = FlowEngine(program, model_registry, tool_registry, agent_runner, router)
    flow_engine.frame_registry._store[frame.name] = rows

    async def fake_run(pipeline_name, question, state, runtime_ctx, base_context, flow_name, step_name):
        return {"answer": "static answer", "context": "context only"}

    flow_engine._run_rag_pipeline = fake_run
    return program, eval_cfg, flow_engine


def test_rag_evaluation_runner_computes_metrics():
    rows = [
        {"question": "What is Namel3ss?", "expected": "Namel3ss is great"},
        {"question": "How to use frames?", "expected": "Use frames for tables"},
    ]
    program, eval_cfg, engine = _build_stub_engine(rows)

    result = run_rag_evaluation(program, eval_cfg, engine)

    assert result.num_rows == 2
    assert len(result.rows) == 2
    for row in result.rows:
        assert row.answer is not None
        assert set(row.metrics.keys()) == set(eval_cfg.metrics)
    assert result.aggregates["context_relevance"]["mean"] == 0.0
    assert result.aggregates["answer_faithfulness"]["mean"] == 0.0
    assert result.aggregates["answer_completeness"]["mean"] == 0.0


def test_run_by_name_unknown_evaluation():
    program, eval_cfg, engine = _build_stub_engine([{"question": "q", "expected": "a"}])
    with pytest.raises(Namel3ssError):
        run_rag_evaluation_by_name(program, engine, "missing")


def test_invalid_pipeline_reference_errors():
    source = '''
rag evaluation is "bad":
  pipeline is "missing"
  dataset:
    from frame "eval_questions"
    question_column is "question"

frame is "eval_questions":
  source:
    backend is "memory"
    table is "eval"
'''
    mod = parser.parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(mod)
    assert "refers to pipeline 'missing'" in str(excinfo.value)


def test_invalid_frame_reference_errors():
    source = '''
rag pipeline is "pipe":
  stage is "retrieve":
    type is "vector_retrieve"
    vector_store is "kb"

rag evaluation is "bad":
  pipeline is "pipe"
  dataset:
    from frame "unknown_frame"
    question_column is "question"
'''
    mod = parser.parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(mod)
    assert "refers to frame 'unknown_frame'" in str(excinfo.value)


def test_invalid_question_or_answer_column_errors():
    source = '''
frame is "eval":
  source:
    backend is "memory"
    table is "eval"
  select:
    columns are ["prompt", "expected_answer", "id"]

vector_store is "kb":
  backend is "memory"
  frame is "eval"
  text_column is "prompt"
  id_column is "id"
  embedding_model is "fake"

rag pipeline is "pipe":
  stage is "retrieve":
    type is "vector_retrieve"
    vector_store is "kb"

rag evaluation is "bad_eval":
  pipeline is "pipe"
  dataset:
    from frame "eval"
    question_column is "question"
    answer_column is "missing"
'''
    mod = parser.parse_source(source)
    with pytest.raises(IRError) as excinfo:
        ast_to_ir(mod)
    msg = str(excinfo.value)
    assert "Frame 'eval' does not have a column 'question'" in msg


def _write_minimal_eval_file(tmp_path: Path) -> Path:
    content = '''
model is "default":
  provider is "openai_default"

ai is "echo_ai":
  model is "default"

rag pipeline is "kb_qa":
  stage is "answer":
    type is "ai_answer"
    ai is "echo_ai"

frame is "eval_questions":
  source:
    backend is "memory"
    table is "eval_questions"

rag evaluation is "support_eval":
  pipeline is "kb_qa"
  dataset:
    from frame "eval_questions"
    question_column is "question"
    answer_column is "expected_answer"
'''
    path = tmp_path / "prog.ai"
    path.write_text(content, encoding="utf-8")
    return path


def test_cli_rag_eval_outputs_summary(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(
        "N3_PROVIDERS_JSON",
        '{"default": "openai_default", "providers": {"openai_default": {"type": "openai", "api_key": "test-key"}}}',
    )
    eval_result = RagEvaluationResult(
        name="support_eval",
        pipeline="kb_qa",
        dataset_frame="eval_questions",
        question_column="question",
        answer_column="expected_answer",
        metrics=["context_relevance"],
        rows=[
            RagEvaluationRow(question="q1", expected_answer="a1", answer="a1", metrics={"context_relevance": 1.0}),
            RagEvaluationRow(question="q2", expected_answer="a2", answer="a2", metrics={"context_relevance": 0.5}),
        ],
        aggregates={"context_relevance": {"mean": 0.75, "count": 2}},
        num_rows=2,
    )
    called = {}

    def fake_runner(program, flow_engine, evaluation_name, limit=None):
        called["limit"] = limit
        return eval_result

    monkeypatch.setattr("namel3ss.cli.run_rag_evaluation_by_name", fake_runner)
    ai_file = _write_minimal_eval_file(tmp_path)

    cli_main(["rag-eval", "support_eval", "--file", str(ai_file), "--limit", "2"])
    assert called["limit"] == 2
    out = capsys.readouterr().out
    assert "RAG evaluation: support_eval" in out
    assert "Pipeline: kb_qa" in out
    assert 'Dataset: frame "eval_questions"' in out
    assert "context_relevance" in out


def test_cli_rag_eval_json_output(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv(
        "N3_PROVIDERS_JSON",
        '{"default": "openai_default", "providers": {"openai_default": {"type": "openai", "api_key": "test-key"}}}',
    )
    eval_result = RagEvaluationResult(
        name="support_eval",
        pipeline="kb_qa",
        dataset_frame="eval_questions",
        question_column="question",
        answer_column="expected_answer",
        metrics=["context_relevance"],
        rows=[RagEvaluationRow(question="q1", expected_answer="a1", answer="a1", metrics={"context_relevance": 1.0})],
        aggregates={"context_relevance": {"mean": 1.0, "count": 1}},
        num_rows=1,
    )

    def fake_runner(program, flow_engine, evaluation_name, limit=None):
        return eval_result

    monkeypatch.setattr("namel3ss.cli.run_rag_evaluation_by_name", fake_runner)
    ai_file = _write_minimal_eval_file(tmp_path)

    cli_main(["rag-eval", "support_eval", "--file", str(ai_file), "--output", "json"])
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["name"] == "support_eval"
    assert payload["aggregates"]["context_relevance"]["count"] == 1
