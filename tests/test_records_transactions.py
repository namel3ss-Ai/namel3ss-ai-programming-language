import pytest
from textwrap import dedent

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import ParseError
from namel3ss.flows.engine import FlowEngine
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.ir import ast_to_ir


def _build_engine(program):
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


def _parse_program(source: str):
    module = parse_source(source)
    program = ast_to_ir(module)
    assert program.flows, "expected at least one flow"
    return program


BASE_DEFS = dedent(
    """
    frame is "users":
      backend "memory"
      table "users"

    frame is "orders":
      backend "memory"
      table "orders"

    frame is "logs":
      backend "memory"
      table "logs"

    record "User":
      frame is "users"
      fields:
        id:
          type "string"
          primary_key true
        email:
          type "string"
          must be unique
        name:
          type "string"

    record "Order":
      frame is "orders"
      fields:
        id:
          type "string"
          primary_key true
        user_id:
          type "string"
          references "User"
        total:
          type "float"

    record "Log":
      frame is "logs"
      fields:
        id:
          type "string"
          primary_key true
        reason:
          type "string"
    """
).strip() + "\n"


def test_transaction_commits_all_steps():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_success":
          transaction:
            step is "create_user":
              kind is "db_create"
              record "User"
              values:
                id: "user-1"
                email: "success@example.com"
            step is "create_order":
              kind is "db_create"
              record "Order"
              values:
                id: "order-1"
                user_id: "user-1"
                total: 42
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["transaction_success"], runtime_ctx.execution_context, initial_state={})
    assert not result.errors
    users = engine.frame_registry.query("users")
    orders = engine.frame_registry.query("orders")
    assert len(users) == 1
    assert users[0]["email"] == "success@example.com"
    assert len(orders) == 1
    assert orders[0]["user_id"] == "user-1"


def test_transaction_uniqueness_failure_rolls_back_all_rows():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_unique_failure":
          transaction:
            step is "first_user":
              kind is "db_create"
              record "User"
              values:
                id: "user-1"
                email: "duplicate@example.com"
            step is "second_user":
              kind is "db_create"
              record "User"
              values:
                id: "user-2"
                email: "duplicate@example.com"
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["transaction_unique_failure"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "transaction" in result.errors[0].error.lower()
    assert "rolled back" in result.errors[0].error.lower()
    rows = engine.frame_registry.query("users")
    assert rows == []


def test_transaction_foreign_key_failure_restores_previous_inserts():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_fk_failure":
          transaction:
            step is "create_user":
              kind is "db_create"
              record "User"
              values:
                id: "user-rollback"
                email: "fk@example.com"
            step is "create_invalid_order":
              kind is "db_create"
              record "Order"
              values:
                id: "order-missing"
                user_id: "missing-user"
                total: 5
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["transaction_fk_failure"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    users = engine.frame_registry.query("users")
    assert users == []
    orders = engine.frame_registry.query("orders")
    assert orders == []


def test_transaction_bulk_create_violation_leaves_no_rows():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_bulk_seed":
          transaction:
            step is "bulk_insert":
              create many users from state.new_users
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    initial_state = {
        "new_users": [
            {"id": "user-a", "email": "bulk@example.com"},
            {"id": "user-b", "email": "bulk@example.com"},
        ]
    }
    result = engine.run_flow(program.flows["transaction_bulk_seed"], runtime_ctx.execution_context, initial_state=initial_state)
    assert result.errors
    rows = engine.frame_registry.query("users")
    assert rows == []


def test_transaction_rollback_restores_previous_updates():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_update_rollback":
          step is "seed_one":
            kind is "db_create"
            record "User"
            values:
              id: "user-a"
              email: "alpha@example.com"
          step is "seed_two":
            kind is "db_create"
            record "User"
            values:
              id: "user-b"
              email: "bravo@example.com"
          transaction:
            step is "update_first":
              kind is "db_update"
              record "User"
              by id:
                id: "user-a"
              set:
                email: "shared@example.com"
            step is "update_second":
              kind is "db_update"
              record "User"
              by id:
                id: "user-b"
              set:
                email: "shared@example.com"
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["transaction_update_rollback"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    users = {row["id"]: row["email"] for row in engine.frame_registry.query("users")}
    # seed steps ran before the transaction, so both users should still exist with original emails
    assert users["user-a"] == "alpha@example.com"
    assert users["user-b"] == "bravo@example.com"


def test_transaction_on_error_runs_after_rollback():
    source = BASE_DEFS + dedent(
        '''
        flow is "transaction_with_handler":
          transaction:
            step is "create_user":
              kind is "db_create"
              record "User"
              values:
                id: "user-log"
                email: "log@example.com"
            step is "force_duplicate":
              kind is "db_create"
              record "User"
              values:
                id: "user-log-2"
                email: "log@example.com"
          on error:
            step is "log_failure":
              kind is "db_create"
              record "Log"
              values:
                id: "log-entry"
                reason: "duplicate email"
        '''
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["transaction_with_handler"], runtime_ctx.execution_context, initial_state={})
    # The on error handler surfaces as a successful run after rolling back the failed transaction.
    assert not result.errors
    logs = engine.frame_registry.query("logs")
    assert len(logs) == 1
    assert logs[0]["reason"] == "duplicate email"
    assert engine.frame_registry.query("users") == []


def test_parser_rejects_nested_transactions():
    source = BASE_DEFS + dedent(
        '''
        flow is "nested_transactions":
          transaction:
            transaction:
              step is "broken":
                kind is "db_create"
                record "User"
                values:
                  id: "broken"
                  email: "broken@example.com"
        '''
    )
    with pytest.raises(ParseError):
        parse_source(source)
