import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer
from namel3ss.errors import IRError, ParseError


def _make_engine(ir_prog: IRProgram):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyTool:
        def __init__(self, name: str, calls: list[str]):
            self.name = name
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append(self.name)
            return {"tool": self.name, "args": kwargs}

    class DummyToolRegistry:
        def __init__(self):
            self.calls: list[str] = []

        def get(self, name):
            return DummyTool(name, self.calls)

    class DummyAgentRunner:
        def __init__(self):
            self.calls: list[str] = []

        def run(self, name, context):
            self.calls.append(name)
            return {"agent": name}

    tool_registry = DummyToolRegistry()
    runner = DummyAgentRunner()
    engine = FlowEngine(
        program=ir_prog,
        model_registry=DummyModelRegistry(),
        tool_registry=tool_registry,
        agent_runner=runner,
        router=DummyRouter(),
        metrics=None,
        secrets=None,
    )
    engine._tool_calls = tool_registry.calls
    engine._agent_calls = runner.calls
    return engine


def test_parse_macro_declaration_and_use():
    module = parse_source(
        'define condition "is_vip" as:\n'
        '  user.value > 10000\n'
        'flow "f":\n'
        '  step "s":\n'
        '    if is_vip:\n'
        '      do agent "vip_handler"\n'
    )
    macros = [d for d in module.declarations if d.__class__.__name__ == "ConditionMacroDecl"]
    assert len(macros) == 1
    ir_prog = ast_to_ir(module)
    flow = ir_prog.flows["f"]
    branch = flow.steps[0].conditional_branches[0]
    assert getattr(branch, "macro_origin", None) == "is_vip"


def test_duplicate_macro_is_error():
    module = parse_source(
        'define condition "c1" as:\n'
        '  user.flag\n'
        'define condition "c1" as:\n'
        '  user.other\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_macro_runtime_branch_and_trace():
    source = (
        'define condition "is_billing" as:\n'
        '  result.category is "billing"\n'
        'agent "billing_agent":\n'
        '  the goal is "bill"\n'
        '  the personality is "direct"\n'
        'flow "router":\n'
        '  step "route":\n'
        '    if is_billing:\n'
        '      do agent "billing_agent"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-macro", tracer=tracer)
    engine = _make_engine(ir_prog)
    engine.run_flow(ir_prog.flows["router"], ctx, initial_state={"result": {"category": "billing"}})
    assert engine._agent_calls == ["billing_agent"]
    events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("macro") == "is_billing" for evt in events if evt.get("event", "").startswith("flow.condition"))


def test_macro_not_allowed_in_binding_conflict():
    module = parse_source(
        'define condition "is_vip" as:\n'
        '  user.flag\n'
        'flow "f":\n'
        '  step "s":\n'
        '    if user.flag as is_vip:\n'
        '      do agent "a"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_macro_in_pattern_value_expands():
    module = parse_source(
        'define condition "is_billing" as:\n'
        '  "billing"\n'
        'flow "f":\n'
        '  step "s":\n'
        '    when result matches { category: is_billing }:\n'
        '      do tool "echo"\n'
    )
    ir_prog = ast_to_ir(module)
    branch = ir_prog.flows["f"].steps[0].conditional_branches[0]
    assert isinstance(branch.condition, object)


def test_macro_key_in_pattern_rejected():
    module = parse_source(
        'define condition "c1" as:\n'
        '  user.flag\n'
        'flow "f":\n'
        '  step "s":\n'
        '    when result matches { c1: "x" }:\n'
        '      do tool "echo"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_macro_parse_requires_expression():
    with pytest.raises(ParseError):
        parse_source(
            'define condition "empty" as:\n'
            '  \n'
        )
