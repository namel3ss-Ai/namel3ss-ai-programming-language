import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source
from namel3ss.ir import (
    IRAuth,
    IRAgent,
    IRFlow,
    IRFlowStep,
    IRFrame,
    IRModel,
    IRProgram,
    IRRecord,
    IRRecordField,
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


def _engine_and_context(program: IRProgram):
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
    ctx = ExecutionContext(
        app_name="test",
        request_id="req",
        tracer=None,
        tool_registry=tool_registry,
        metrics=metrics,
    )
    return engine, ctx


def test_parse_auth_config():
    module = parse_source(
        'frame "users":\n'
        '  backend "memory"\n'
        '  table "users"\n'
        "\n"
        'record "User":\n'
        '  frame "users"\n'
        "  fields:\n"
        '    id:\n'
        '      type "uuid"\n'
        '      primary_key true\n'
        '    email:\n'
        '      type "string"\n'
        '      required true\n'
        '    password_hash:\n'
        '      type "string"\n'
        '      required true\n'
        "\n"
        "auth:\n"
        '  backend "default_auth"\n'
        '  user_record "User"\n'
        '  id_field "id"\n'
        '  identifier_field "email"\n'
        '  password_hash_field "password_hash"\n'
    )
    auths = [d for d in module.declarations if isinstance(d, ast_nodes.AuthDecl)]
    assert auths
    auth = auths[0]
    assert auth.user_record == "User"
    assert auth.identifier_field == "email"
    assert auth.password_hash_field == "password_hash"


def test_ir_validation_auth_errors():
    auth_decl = ast_nodes.AuthDecl(
        backend="default_auth",
        user_record="Missing",
        id_field="id",
        identifier_field="email",
        password_hash_field="password_hash",
    )
    module = ast_nodes.Module(declarations=[auth_decl])
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1600" in str(exc.value)

    frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="uuid", primary_key=True),
            ast_nodes.RecordFieldDecl(name="email", type="string", required=True),
            ast_nodes.RecordFieldDecl(name="password_hash", type="string", required=True),
        ],
    )
    bad_auth = ast_nodes.AuthDecl(
        backend="default_auth",
        user_record="User",
        id_field="email",  # not primary key
        identifier_field="email",
        password_hash_field="password_hash",
    )
    module = ast_nodes.Module(declarations=[frame, record, bad_auth])
    with pytest.raises(IRError) as exc2:
        ast_to_ir(module)
    assert "N3L-1600" in str(exc2.value)


def test_runtime_register_login_logout_and_user_binding():
    user_record = IRRecord(
        name="User",
        frame="users",
        fields={
            "id": IRRecordField(name="id", type="uuid", primary_key=True, required=True),
            "email": IRRecordField(name="email", type="string", required=True),
            "password_hash": IRRecordField(name="password_hash", type="string", required=True),
        },
        primary_key="id",
    )
    project_record = IRRecord(
        name="Project",
        frame="projects",
        fields={
            "id": IRRecordField(name="id", type="uuid", primary_key=True, required=True),
            "owner_id": IRRecordField(name="owner_id", type="string", required=False),
            "name": IRRecordField(name="name", type="string", required=True),
        },
        primary_key="id",
    )
    auth_cfg = IRAuth(
        backend="default_auth",
        user_record="User",
        id_field="id",
        identifier_field="email",
        password_hash_field="password_hash",
    )
    program = IRProgram(
        models={"default": IRModel(name="default")},
        agents={"helper": IRAgent(name="helper")},
        frames={
            "users": IRFrame(name="users", backend="memory", table="users"),
            "projects": IRFrame(name="projects", backend="memory", table="projects"),
        },
        records={"User": user_record, "Project": project_record},
        auth=auth_cfg,
    )
    engine, ctx = _engine_and_context(program)

    register_flow = IRFlow(
        name="register",
        description=None,
        steps=[
            IRFlowStep(
                name="register",
                kind="auth_register",
                target="",
                params={"input": {"email": ast_nodes.Literal(value="person@example.com"), "password": ast_nodes.Literal(value="pw123")}},
            )
        ],
    )
    result = engine.run_flow(register_flow, ctx, initial_state={})
    reg_output = result.state.get("step.register.output")
    assert reg_output["ok"] is True
    stored_user = engine.frame_registry._store["users"][0]
    assert stored_user["password_hash"] != "pw123"

    # Second registration with same email should fail
    result_dup = engine.run_flow(register_flow, ctx, initial_state={})
    dup_output = result_dup.state.get("step.register.output")
    assert dup_output["ok"] is False
    assert dup_output["code"] == "AUTH_USER_EXISTS"

    wrong_login_flow = IRFlow(
        name="login_fail",
        description=None,
        steps=[
            IRFlowStep(
                name="login",
                kind="auth_login",
                target="",
                params={"input": {"email": ast_nodes.Literal(value="person@example.com"), "password": ast_nodes.Literal(value="wrong")}},
            )
        ],
    )
    wrong_result = engine.run_flow(wrong_login_flow, ctx, initial_state={})
    wrong_output = wrong_result.state.get("step.login.output")
    assert wrong_output["ok"] is False
    assert ctx.user_context.get("is_authenticated") is False

    login_flow = IRFlow(
        name="login",
        description=None,
        steps=[
            IRFlowStep(
                name="login",
                kind="auth_login",
                target="",
                params={"input": {"email": ast_nodes.Literal(value="person@example.com"), "password": ast_nodes.Literal(value="pw123")}},
            )
        ],
    )
    login_result = engine.run_flow(login_flow, ctx, initial_state={})
    login_output = login_result.state.get("step.login.output")
    assert login_output["ok"] is True
    assert ctx.user_context.get("is_authenticated") is True
    user_id = ctx.user_context.get("id")

    create_flow = IRFlow(
        name="create_project",
        description=None,
        steps=[
            IRFlowStep(
                name="create",
                kind="db_create",
                target="Project",
                params={
                    "values": {
                        "id": ast_nodes.Literal(value="proj-1"),
                        "owner_id": ast_nodes.Identifier(name="user.id"),
                        "name": ast_nodes.Literal(value="Test Project"),
                    }
                },
            )
        ],
    )
    create_result = engine.run_flow(create_flow, ctx, initial_state={})
    create_output = create_result.state.get("step.create.output")
    assert create_output["owner_id"] == user_id

    logout_flow = IRFlow(
        name="logout",
        description=None,
        steps=[IRFlowStep(name="logout", kind="auth_logout", target="", params={})],
    )
    logout_result = engine.run_flow(logout_flow, ctx, initial_state={})
    logout_output = logout_result.state.get("step.logout.output")
    assert logout_output["ok"] is True
    assert ctx.user_context.get("is_authenticated") is False
    assert ctx.user_context.get("id") is None
