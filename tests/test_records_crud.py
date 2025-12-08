import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import (
    IRFlow,
    IRFlowStep,
    IRFrame,
    IRModel,
    IRProgram,
    IRRecord,
    IRRecordField,
    IRAgent,
    ast_to_ir,
    IRError,
)
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext


def _build_engine(program: IRProgram):
    registry = ModelRegistry()
    registry.register_model("default", provider_name=None)
    router = ModelRouter(registry)
    tool_registry = ToolRegistry()
    agent_runner = AgentRunner(program, registry, tool_registry, router)
    metrics = MetricsTracker()
    engine = FlowEngine(
        program=program,
        model_registry=registry,
        tool_registry=tool_registry,
        agent_runner=agent_runner,
        router=router,
        metrics=metrics,
    )
    exec_ctx = ExecutionContext(
        app_name="test",
        request_id="req",
        tracer=None,
        tool_registry=tool_registry,
        metrics=metrics,
    )
    runtime_ctx = engine._build_runtime_context(exec_ctx)
    return engine, runtime_ctx


def test_parse_record_decl_fields():
    module = parse_source(
        'frame "documents":\n'
        '  backend "memory"\n'
        '  table "documents"\n'
        '\n'
        'record "Document":\n'
        '  frame "documents"\n'
        "  fields:\n"
        '    id:\n'
        '      type "uuid"\n'
        '      primary_key true\n'
        '    title:\n'
        '      type "string"\n'
        '      required true\n'
        '      default "Untitled"\n'
    )
    records = [d for d in module.declarations if isinstance(d, ast_nodes.RecordDecl)]
    assert records and records[0].frame == "documents"
    fields = {f.name: f for f in records[0].fields}
    assert fields["id"].primary_key is True
    assert fields["title"].required is True
    assert isinstance(fields["title"].default_expr, ast_nodes.Literal)


def test_ir_validation_missing_frame_for_record():
    record = ast_nodes.RecordDecl(
        name="Doc",
        frame="missing",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="uuid", primary_key=True),
        ],
    )
    module = ast_nodes.Module(declarations=[record])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1500" in str(exc.value)


def test_ir_validation_missing_required_field_in_create():
    frame = ast_nodes.FrameDecl(name="documents", backend="memory", table="documents")
    record = ast_nodes.RecordDecl(
        name="Document",
        frame="documents",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="uuid", primary_key=True),
            ast_nodes.RecordFieldDecl(name="title", type="string", required=True),
        ],
    )
    flow = ast_nodes.FlowDecl(
        name="create_doc",
        steps=[
            ast_nodes.FlowStepDecl(
                name="create",
                kind="db_create",
                target="Document",
                params={"values": {"id": ast_nodes.Literal(value="1")}},
            )
        ],
    )
    module = ast_nodes.Module(declarations=[frame, record, flow])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1502" in str(exc.value)


def test_ir_validation_missing_record_reference():
    frame = ast_nodes.FrameDecl(name="documents", backend="memory", table="documents")
    flow = ast_nodes.FlowDecl(
        name="create_doc",
        steps=[
            ast_nodes.FlowStepDecl(
                name="create",
                kind="db_create",
                target="Missing",
                params={"values": {"id": ast_nodes.Literal(value="1")}},
            )
        ],
    )
    module = ast_nodes.Module(declarations=[frame, flow])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1500" in str(exc.value)


def test_runtime_record_crud_flow():
    record = IRRecord(
        name="Document",
        frame="documents",
        fields={
            "id": IRRecordField(name="id", type="uuid", primary_key=True, required=True),
            "project_id": IRRecordField(name="project_id", type="string", required=True),
            "title": IRRecordField(name="title", type="string", required=True),
            "content": IRRecordField(name="content", type="text", required=False),
        },
        primary_key="id",
    )
    flow = IRFlow(
        name="crud",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target="Document",
                params={
                    "values": {
                        "id": ast_nodes.Literal(value="doc-1"),
                        "project_id": ast_nodes.Literal(value="proj-1"),
                        "title": ast_nodes.Literal(value="Doc 1"),
                    }
                },
            ),
            IRFlowStep(
                name="fetch_one",
                kind="db_get",
                target="Document",
                params={"by_id": {"id": ast_nodes.Literal(value="doc-1")}},
            ),
            IRFlowStep(
                name="fetch_project",
                kind="db_get",
                target="Document",
                params={"where": {"project_id": ast_nodes.Literal(value="proj-1")}},
            ),
            IRFlowStep(
                name="rename",
                kind="db_update",
                target="Document",
                params={
                    "by_id": {"id": ast_nodes.Literal(value="doc-1")},
                    "set": {"title": ast_nodes.Literal(value="Doc 1 Updated")},
                },
            ),
            IRFlowStep(
                name="remove",
                kind="db_delete",
                target="Document",
                params={"by_id": {"id": ast_nodes.Literal(value="doc-1")}},
            ),
        ],
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={"documents": IRFrame(name="documents", backend="memory", table="documents")},
        records={"Document": record},
    )
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})

    created = result.state.get("step.create.output")
    assert created["title"] == "Doc 1"

    fetched = result.state.get("step.fetch_one.output")
    assert fetched and fetched["id"] == "doc-1"

    listed = result.state.get("step.fetch_project.output")
    assert isinstance(listed, list) and listed[0]["project_id"] == "proj-1"

    updated = result.state.get("step.rename.output")
    assert updated["title"] == "Doc 1 Updated"

    deleted = result.state.get("step.remove.output")
    assert deleted["ok"] is True and deleted["deleted"] == 1
