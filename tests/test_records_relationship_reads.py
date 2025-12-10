import pytest
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import IRError, ParseError
from namel3ss.flows.engine import FlowEngine
from namel3ss.ir import IRFlow, IRFlowStep, IRFrame, IRModel, IRProgram, IRRecord, IRRecordField, IRAgent, ast_to_ir
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


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


def _run_flow(program: IRProgram, flow_name: str):
    engine, runtime_ctx = _build_engine(program)
    flow = program.flows[flow_name]
    return engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})


def _relationship_source(include_missing_user: bool = False, include_tenant: bool = False) -> str:
    tenant_fields = ""
    tenant_seed = ""
    tenant_join = ""
    if include_tenant:
        tenant_fields = (
            '    tenant_id:\n'
            '      type "string"\n'
            '      references "Tenant"\n'
            '    tenant:\n'
            '      relationship is "Tenant" by tenant_id\n'
        )
        tenant_seed = (
            '  step is "create_tenant_a":\n'
            '    kind is "db_create"\n'
            '    record "Tenant"\n'
            "    values:\n"
            '      id: "t1"\n'
            '      name: "North"\n'
            '  step is "create_tenant_b":\n'
            '    kind is "db_create"\n'
            '    record "Tenant"\n'
            "    values:\n"
            '      id: "t2"\n'
            '      name: "South"\n'
        )
        tenant_join = '    with tenants for each order by tenant_id\n'
    missing_user_block = ""
    if include_missing_user:
        missing_user_block = (
            '  step is "remove_user_a":\n'
            '    kind is "db_delete"\n'
            '    record "User"\n'
            "    by id:\n"
            '      id: "user-a"\n'
        )
    parts = [
        'frame is "users":\n',
        '  source:\n',
        '    backend is "memory"\n',
        '    table is "users"\n',
        'frame is "orders":\n',
        '  source:\n',
        '    backend is "memory"\n',
        '    table is "orders"\n',
    ]
    if include_tenant:
        parts.extend(
            [
                'frame is "tenants":\n',
                '  source:\n',
                '    backend is "memory"\n',
                '    table is "tenants"\n',
            ]
        )
    parts.append("\n")
    parts.extend(
        [
            'record "User":\n',
            '  frame is "users"\n',
            "  fields:\n",
            "    id:\n",
            '      type "string"\n',
            '      primary_key true\n',
            "    email:\n",
            '      type "string"\n',
            "\n",
        ]
    )
    if include_tenant:
        parts.extend(
            [
                'record "Tenant":\n',
                '  frame is "tenants"\n',
                "  fields:\n",
                "    id:\n",
                '      type "string"\n',
                '      primary_key true\n',
                "    name:\n",
                '      type "string"\n',
                "\n",
            ]
        )
    parts.extend(
        [
            'record "Order":\n',
            '  frame is "orders"\n',
            "  fields:\n",
            "    id:\n",
            '      type "string"\n',
            '      primary_key true\n',
            "    status:\n",
            '      type "string"\n',
            "    user_id:\n",
            '      type "string"\n',
            '      references "User"\n',
            "    user:\n",
            '      relationship is "User" by user_id\n',
            tenant_fields,
            "\n",
        ]
    )
    parts.extend(
        [
            'flow is "list_orders_with_users":\n',
            '  step is "create_user_a":\n',
            '    kind is "db_create"\n',
            '    record "User"\n',
            "    values:\n",
            '      id: "user-a"\n',
            '      email: "a@example.com"\n',
            '  step is "create_user_b":\n',
            '    kind is "db_create"\n',
            '    record "User"\n',
            "    values:\n",
            '      id: "user-b"\n',
            '      email: "b@example.com"\n',
            tenant_seed,
            '  step is "create_order_1":\n',
            '    kind is "db_create"\n',
            '    record "Order"\n',
            "    values:\n",
            '      id: "order-1"\n',
            '      status: "open"\n',
            '      user_id: "user-a"\n',
            '      tenant_id: "t1"\n' if include_tenant else "",
            '  step is "create_order_2":\n',
            '    kind is "db_create"\n',
            '    record "Order"\n',
            "    values:\n",
            '      id: "order-2"\n',
            '      status: "pending"\n',
            '      user_id: "user-b"\n',
            '      tenant_id: "t2"\n' if include_tenant else "",
            '  step is "create_order_3":\n',
            '    kind is "db_create"\n',
            '    record "Order"\n',
            "    values:\n",
            '      id: "order-3"\n',
            '      status: "open"\n',
            '      tenant_id: "t2"\n' if include_tenant else "",
            missing_user_block,
            '  step is "list_open":\n',
            '    find orders where:\n',
            '      status is "open"\n',
            '    with users for each order by user_id\n',
            tenant_join,
        ]
    )
    return "".join(parts)


def test_relationship_join_attaches_related_records():
    module = parse_source(_relationship_source())
    program = ast_to_ir(module)
    result = _run_flow(program, "list_orders_with_users")
    output = result.state.get("step.list_open.output")
    assert output and len(output) == 2
    order_by_id = {row["id"]: row for row in output}
    assert order_by_id["order-1"]["user"]["email"] == "a@example.com"
    assert order_by_id["order-3"]["user"] is None


def test_multiple_relationship_joins_attach_both():
    module = parse_source(_relationship_source(include_tenant=True))
    program = ast_to_ir(module)
    result = _run_flow(program, "list_orders_with_users")
    output = result.state.get("step.list_open.output")
    assert output and len(output) == 2
    order_by_id = {row["id"]: row for row in output}
    assert order_by_id["order-1"]["user"]["email"] == "a@example.com"
    assert order_by_id["order-1"]["tenant"]["name"] == "North"
    # order-3 missing user_id but has tenant
    assert order_by_id["order-3"]["user"] is None
    assert order_by_id["order-3"]["tenant"]["name"] == "South"


def test_missing_related_row_results_in_null_attachment():
    module = parse_source(_relationship_source(include_missing_user=True))
    program = ast_to_ir(module)
    result = _run_flow(program, "list_orders_with_users")
    output = result.state.get("step.list_open.output")
    assert output and len(output) == 2
    order_by_id = {row["id"]: row for row in output}
    assert order_by_id["order-1"]["user"] is None


def test_parser_rejects_unknown_base_alias():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'frame is "orders":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "orders"\n'
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'record "Order":\n'
        '  frame is "orders"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        '    user_id:\n'
        '      type "string"\n'
        '      references "User"\n'
        'flow is "bad_alias":\n'
        '  step is "list":\n'
        '    find orders where:\n'
        '      id is not null\n'
        '    with users for each invoice by user_id\n'
    )
    with pytest.raises(ParseError):
        parse_source(source)


def test_ir_error_when_via_field_missing():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'frame is "orders":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "orders"\n'
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'record "Order":\n'
        '  frame is "orders"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'flow is "missing_field":\n'
        '  step is "list":\n'
        '    find orders where:\n'
        '      id is not null\n'
        '    with users for each order by user_id\n'
    )
    module = parse_source(source)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "has no field named user_id" in str(exc.value)


def test_ir_error_when_field_not_foreign_key():
    source = (
        'frame is "users":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "users"\n'
        'frame is "orders":\n'
        '  source:\n'
        '    backend is "memory"\n'
        '    table is "orders"\n'
        'record "User":\n'
        '  frame is "users"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        'record "Order":\n'
        '  frame is "orders"\n'
        "  fields:\n"
        "    id:\n"
        '      type "string"\n'
        '      primary_key true\n'
        "    status:\n"
        '      type "string"\n'
        'flow is "bad_fk":\n'
        '  step is "list":\n'
        '    find orders where:\n'
        '      id is not null\n'
        '    with users for each order by status\n'
    )
    module = parse_source(source)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "does not reference another record" in str(exc.value)
