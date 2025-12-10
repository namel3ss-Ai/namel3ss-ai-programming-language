import pytest
from textwrap import dedent

from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.errors import IRError, ParseError
from namel3ss.flows.engine import FlowEngine
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry


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
    frame is "products":
      backend "memory"
      table "products"

    record "Product":
      frame is "products"
      fields:
        id:
          type is "string"
          primary_key true
        price:
          type is "float"
          must be at least 0
          must be at most 1000
        discount_rate:
          type is "decimal"
          must be at least 0
          must be at most 1
        name:
          type is "string"
          must be present
          must have length at least 3
          must have length at most 32
        status:
          type is "string"
          must be one of ["draft", "published", "archived"]
        slug:
          type is "string"
          must match pattern "^[a-z0-9-]+$"
        tags:
          type is "array"
          must have length at most 2
        subtitle:
          type is "string"
          must have length at most 50
        metadata:
          type is "json"
    """
).strip() + "\n"


def test_create_with_valid_data_passes():
    source = BASE_DEFS + dedent(
        """
        flow is "create_valid":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-1"
              name: "Valid Product"
              price: 25
              discount_rate: 0.1
              status: "draft"
              slug: "valid-slug"
              tags: ["ops", "ai"]
              metadata: { origin: "suite" }
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["create_valid"], runtime_ctx.execution_context, initial_state={})
    assert not result.errors
    rows = engine.frame_registry.query("products")
    assert len(rows) == 1
    assert rows[0]["slug"] == "valid-slug"
    assert rows[0]["tags"] == ["ops", "ai"]
    assert rows[0]["metadata"]["origin"] == "suite"


def test_price_below_min_fails():
    source = BASE_DEFS + dedent(
        """
        flow is "price_too_low":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-low"
              name: "Too Cheap"
              price: -5
              discount_rate: 0.2
              status: "draft"
              slug: "cheap"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["price_too_low"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "price must be at least" in result.errors[0].error
    assert engine.frame_registry.query("products") == []


def test_price_above_max_update_fails():
    source = BASE_DEFS + dedent(
        """
        flow is "seed_high":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-high"
              name: "High Price"
              price: 10
              discount_rate: 0.1
              status: "draft"
              slug: "pricey"

        flow is "raise_price":
          step is "update":
            kind is "db_update"
            record "Product"
            by id:
              id: "prod-high"
            set:
              price: 5000
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    assert not engine.run_flow(program.flows["seed_high"], context, initial_state={}).errors
    result = engine.run_flow(program.flows["raise_price"], context, initial_state={})
    assert result.errors
    assert "price must be at most" in result.errors[0].error
    rows = engine.frame_registry.query("products")
    assert rows[0]["price"] == 10


def test_name_length_violations():
    long_name_value = "x" * 40
    source = BASE_DEFS + dedent(
        f"""
        flow is "short_name":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-short"
              name: "ab"
              price: 10
              discount_rate: 0.1
              status: "draft"
              slug: "short-name"

        flow is "long_name":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-long"
              name: "{long_name_value}"
              price: 10
              discount_rate: 0.1
              status: "draft"
              slug: "long-name"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    short_result = engine.run_flow(program.flows["short_name"], context, initial_state={})
    assert short_result.errors
    assert "length at least" in short_result.errors[0].error
    long_result = engine.run_flow(program.flows["long_name"], context, initial_state={})
    assert long_result.errors
    assert "length at most" in long_result.errors[0].error


def test_status_enum_violation():
    source = BASE_DEFS + dedent(
        """
        flow is "bad_status":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-status"
              name: "Invalid Status"
              price: 20
              discount_rate: 0.1
              status: "unknown"
              slug: "stat"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["bad_status"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "must be one of" in result.errors[0].error


def test_slug_pattern_violation():
    source = BASE_DEFS + dedent(
        """
        flow is "bad_slug":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-slug"
              name: "Bad Slug"
              price: 20
              discount_rate: 0.1
              status: "draft"
              slug: "Bad Slug"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["bad_slug"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "must match pattern" in result.errors[0].error


def test_tags_length_constraint():
    source = BASE_DEFS + dedent(
        """
        flow is "too_many_tags":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-tags"
              name: "Too Many Tags"
              price: 25
              discount_rate: 0.1
              status: "draft"
              slug: "taggy"
              tags: ["one", "two", "three"]
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["too_many_tags"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert "length at most" in result.errors[0].error


def test_optional_field_skips_validation_when_missing():
    long_subtitle = "z" * 60
    source = BASE_DEFS + dedent(
        f"""
        flow is "missing_subtitle":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-sub"
              name: "No Subtitle"
              price: 15
              discount_rate: 0.1
              status: "draft"
              slug: "subtitle"

        flow is "long_subtitle":
          step is "db_update":
            kind is "db_update"
            record "Product"
            by id:
              id: "prod-sub"
            set:
              subtitle: "{long_subtitle}"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    assert not engine.run_flow(program.flows["missing_subtitle"], context, initial_state={}).errors
    result = engine.run_flow(program.flows["long_subtitle"], context, initial_state={})
    assert result.errors
    assert "subtitle" in result.errors[0].error


def test_bulk_create_rolls_back_on_validation_error():
    source = BASE_DEFS + dedent(
        """
        flow is "bulk_seed":
          step is "bulk_insert":
            create many products from state.batch
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    initial_state = {
        "batch": [
            {"id": "prod-1", "name": "One", "price": 20, "discount_rate": 0.2, "status": "draft", "slug": "one"},
            {"id": "prod-2", "name": "Two", "price": -1, "discount_rate": 0.1, "status": "draft", "slug": "two"},
        ]
    }
    result = engine.run_flow(program.flows["bulk_seed"], runtime_ctx.execution_context, initial_state=initial_state)
    assert result.errors
    assert engine.frame_registry.query("products") == []


def test_transaction_rolls_back_on_validation_error():
    source = BASE_DEFS + dedent(
        """
        flow is "tx_validation":
          transaction:
            step is "create_one":
              kind is "db_create"
              record "Product"
              values:
                id: "prod-tx-1"
                name: "First"
                price: 10
                discount_rate: 0.1
                status: "draft"
                slug: "first"
            step is "create_two":
              kind is "db_create"
              record "Product"
              values:
                id: "prod-tx-2"
                name: "Second"
                price: 10
                discount_rate: 0.2
                status: "draft"
                slug: "Second With Space"
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    result = engine.run_flow(program.flows["tx_validation"], runtime_ctx.execution_context, initial_state={})
    assert result.errors
    assert engine.frame_registry.query("products") == []


def test_decimal_constraints_enforced():
    source = BASE_DEFS + dedent(
        """
        flow is "seed_discount":
          step is "create":
            kind is "db_create"
            record "Product"
            values:
              id: "prod-disc"
              name: "Discounted"
              price: 10
              discount_rate: 0.5
              status: "draft"
              slug: "disc"

        flow is "bad_discount":
          step is "db_update":
            kind is "db_update"
            record "Product"
            by id:
              id: "prod-disc"
            set:
              discount_rate: 2
        """
    )
    program = _parse_program(source)
    engine, runtime_ctx = _build_engine(program)
    context = runtime_ctx.execution_context
    assert not engine.run_flow(program.flows["seed_discount"], context, initial_state={}).errors
    result = engine.run_flow(program.flows["bad_discount"], context, initial_state={})
    assert result.errors
    assert "discount_rate must be at most" in result.errors[0].error


def test_parser_requires_list_for_enum():
    bad_source = dedent(
        """
        record "Bad":
          frame is "products"
          fields:
            id:
              type is "string"
              primary key true
            status:
              type is "string"
              must be one of "draft"
        """
    )
    with pytest.raises(ParseError):
        parse_source(bad_source)


def test_ir_rejects_length_on_int_field():
    bad_source = dedent(
        """
        frame is "numbers":
          backend "memory"
          table "numbers"

        record "Value":
          frame is "numbers"
          fields:
            id:
              type is "string"
              primary key true
            score:
              type is "int"
              must have length at most 5
        """
    )
    module = parse_source(bad_source)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "length rules" in str(exc.value)


def test_ir_rejects_empty_enum_list():
    bad_source = dedent(
        """
        frame is "statuses":
          backend "memory"
          table "statuses"

        record "Status":
          frame is "statuses"
          fields:
            id:
              type is "string"
              primary key true
            state:
              type is "string"
              must be one of []
        """
    )
    module = parse_source(bad_source)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "at least one value" in str(exc.value)


def test_ir_rejects_pattern_on_non_string():
    bad_source = dedent(
        """
        frame is "data":
          backend "memory"
          table "data"

        record "Sample":
          frame is "data"
          fields:
            id:
              type is "string"
              primary key true
            score:
              type is "int"
              must match pattern "^\\d+$"
        """
    )
    module = parse_source(bad_source)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "must match pattern" in str(exc.value)
