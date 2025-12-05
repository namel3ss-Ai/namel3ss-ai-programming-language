import pytest

from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.obs.tracer import Tracer
from namel3ss.errors import IRError


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


def test_parse_rulegroup_and_use_whole_group():
    module = parse_source(
        'define rulegroup "vip_rules":\n'
        '  condition "age_ok":\n'
        '    user.age > 25\n'
        '  condition "value_ok":\n'
        '    user.value > 10000\n'
        'flow "f":\n'
        '  step "s":\n'
        '    if vip_rules:\n'
        '      do agent "vip_agent"\n'
    )
    ir_prog = ast_to_ir(module)
    assert "vip_rules" in ir_prog.rulegroups
    flow = ir_prog.flows["f"]
    cond = flow.steps[0].conditional_branches[0].condition
    from namel3ss.ast_nodes import RuleGroupRefExpr
    assert isinstance(cond, RuleGroupRefExpr)
    assert cond.group_name == "vip_rules"
    assert cond.condition_name is None


def test_rulegroup_runtime_whole_group():
    source = (
        'define rulegroup "vip_rules":\n'
        '  condition "age_ok":\n'
        '    user.age > 25\n'
        '  condition "value_ok":\n'
        '    user.value > 10000\n'
        'agent "vip_agent":\n'
        '  the goal is "vip"\n'
        '  the personality is "polite"\n'
        'agent "normal_agent":\n'
        '  the goal is "norm"\n'
        '  the personality is "kind"\n'
        'flow "check":\n'
        '  step "decide":\n'
        '    if vip_rules:\n'
        '      do agent "vip_agent"\n'
        '    otherwise:\n'
        '      do agent "normal_agent"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-rg", tracer=tracer)
    engine = _make_engine(ir_prog)
    engine.run_flow(ir_prog.flows["check"], ctx, initial_state={"user": {"age": 30, "value": 20000}})
    assert engine._agent_calls == ["vip_agent"]
    events = tracer.last_trace.flows[0].events if tracer.last_trace and tracer.last_trace.flows else []
    assert any(evt.get("event") == "condition.rulegroup.eval" for evt in events)


def test_rulegroup_single_rule_reference():
    source = (
        'define rulegroup "vip_rules":\n'
        '  condition "age_ok":\n'
        '    user.age > 25\n'
        'flow "f":\n'
        '  step "s":\n'
        '    when vip_rules.age_ok:\n'
        '      do tool "echo"\n'
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    tracer = Tracer()
    ctx = ExecutionContext(app_name="test", request_id="req-rg2", tracer=tracer)
    engine = _make_engine(ir_prog)
    engine.run_flow(ir_prog.flows["f"], ctx, initial_state={"user": {"age": 40}})
    assert engine._tool_calls == ["echo"]


def test_rulegroup_duplicate_condition_error():
    module = parse_source(
        'define rulegroup "rg":\n'
        '  condition "c1":\n'
        '    user.a\n'
        '  condition "c1":\n'
        '    user.b\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_rulegroup_pattern_value_allows_ref():
    module = parse_source(
        'define rulegroup "rg":\n'
        '  condition "ok":\n'
        '    true\n'
        'flow "f":\n'
        '  step "s":\n'
        '    when obj matches { flag: rg }:\n'
        '      do tool "echo"\n'
    )
    ir_prog = ast_to_ir(module)
    cond = ir_prog.flows["f"].steps[0].conditional_branches[0].condition
    from namel3ss.ast_nodes import PatternExpr, RuleGroupRefExpr
    assert isinstance(cond, PatternExpr)
    assert isinstance(cond.pairs[0].value, RuleGroupRefExpr)


def test_rulegroup_pattern_key_rejected():
    module = parse_source(
        'define rulegroup "rg":\n'
        '  condition "ok":\n'
        '    true\n'
        'flow "f":\n'
        '  step "s":\n'
        '    when obj matches { rg: "x" }:\n'
        '      do tool "echo"\n'
    )
    with pytest.raises(IRError):
        ast_to_ir(module)
