import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext


def _make_engine(ir_prog):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def get(self, name):
            return None

    class DummyAgentRunner:
        def __init__(self):
            self.calls = []

        def run(self, name, context):
            self.calls.append(name)
            return {"agent": name}

    runner = DummyAgentRunner()
    engine = FlowEngine(
        program=ir_prog,
        model_registry=DummyModelRegistry(),
        tool_registry=DummyToolRegistry(),
        agent_runner=runner,
        router=DummyRouter(),
        metrics=None,
        secrets=None,
    )
    return engine, runner


def test_helper_call_with_return():
    source = (
        'define helper "double":\n'
        "  takes x\n"
        "  returns result\n"
        "  let result be x * 2\n"
        "  return result\n"
        '\n'
        'flow "f":\n'
        '  step "s":\n'
        "    let val be double(3)\n"
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, runner = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-helper")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert runner.calls == ["done"]
    assert result.state and result.state.variables.resolve("val") == 6


def test_helper_return_none():
    source = (
        'define helper "noop":\n'
        "  return\n"
        '\n'
        'flow "f":\n'
        '  step "s":\n'
        "    let val be noop()\n"
        '    do agent "done"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, runner = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-helper-none")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert not result.errors
    assert runner.calls == ["done"]
    assert result.state and result.state.variables.resolve("val") is None


def test_return_outside_helper_errors():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    return 5\n"
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-return-error")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert result.errors


def test_unknown_helper_call_errors():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    let val be missing_helper(1)\n"
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _ = _make_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-unknown-helper")
    result = engine.run_flow(ir_prog.flows["f"], ctx)
    assert result.errors


def test_settings_and_imports_parsed():
    source = (
        'use module "common"\n'
        'from "helpers" use helper "normalize"\n'
        "\n"
        "settings:\n"
        '  env "prod":\n'
        "    model_provider be \"openai\"\n"
        "    retries be 3\n"
    )
    ir_prog = ast_to_ir(parse_source(source))
    assert ir_prog.imports and ir_prog.imports[0].module == "common"
    assert any(imp.kind == "helper" and imp.name == "normalize" for imp in ir_prog.imports)
    assert ir_prog.settings
    prod = ir_prog.settings.envs.get("prod")
    assert prod is not None
    assert "model_provider" in prod.entries
    assert "retries" in prod.entries
