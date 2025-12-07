import pytest

from namel3ss import ast_nodes
from namel3ss.errors import Namel3ssError
from namel3ss.parser import parse_source
from namel3ss.ir import ast_to_ir, IRProgram, IRConditionalBranch, IRLet, IRSet
from namel3ss.flows.engine import FlowEngine
from namel3ss.runtime.context import ExecutionContext
from namel3ss.agent.engine import AgentRunner


def _make_flow_engine(ir_prog: IRProgram):
    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyTool:
        def __init__(self, calls):
            self.calls = calls

        def run(self, **kwargs):
            self.calls.append(kwargs)
            return {"tool": "echo", "args": kwargs}

    class DummyToolRegistry:
        def __init__(self):
            self.calls = []

        def get(self, name):
            return DummyTool(self.calls)

    class DummyAgentRunner:
        def __init__(self):
            self.calls = []

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
    return engine, tool_registry, runner


def test_parse_list_literal_and_index():
    source = (
        'flow "lists":\n'
        '  step "s":\n'
        '    let xs = [1, 2, 3]\n'
        '    set first to xs[0]\n'
    )
    module = parse_source(source)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    let_stmt = flow.steps[0].statements[0]
    assert isinstance(let_stmt.expr, ast_nodes.ListLiteral)
    assert len(let_stmt.expr.items) == 3
    set_stmt = flow.steps[0].statements[1]
    assert isinstance(set_stmt.expr, ast_nodes.IndexExpr)


def test_flow_runtime_index_and_slice():
    source = (
        'flow "lists":\n'
        '  step "s":\n'
        '    let xs = [1, 2, 3]\n'
        '    let tail = xs[1:]\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_flow_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-list")
    result = engine.run_flow(ir_prog.flows["lists"], ctx)
    assert not result.errors
    assert tools.calls
    assert tools.calls[0].get("message") == [2, 3]


def test_flow_index_errors():
    source = (
        'flow "bad":\n'
        '  step "s":\n'
        '    let xs = [1]\n'
        '    let v = 0\n'
        '    set v to xs[2]\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_flow_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-bad-index")
    result = engine.run_flow(ir_prog.flows["bad"], ctx)
    assert result.errors
    assert any("out of bounds" in err.error for err in result.errors)


def test_agent_list_usage():
    branch = IRConditionalBranch(
        condition=None,
        actions=[
            IRLet(name="xs", expr=ast_nodes.ListLiteral(items=[ast_nodes.Literal(value=1), ast_nodes.Literal(value=2)])),
            IRLet(name="val", expr=ast_nodes.Literal(value=0)),
            IRSet(
                name="val",
                expr=ast_nodes.IndexExpr(
                    seq=ast_nodes.Identifier(name="xs"),
                    index=ast_nodes.Literal(value=1),
                ),
            ),
        ],
        label="if",
    )
    from namel3ss.ir import IRAgent  # local import to avoid circular in type hints

    agent = IRAgent(name="agent_list", goal=None, personality=None, conditional_branches=[branch])
    program = IRProgram(agents={"agent_list": agent})

    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def list_names(self):
            return []

    runner = AgentRunner(program, DummyModelRegistry(), DummyToolRegistry(), DummyRouter())
    ctx = ExecutionContext(app_name="test", request_id="req-agent-list")
    runner.run("agent_list", ctx)
    assert ctx.variables["val"] == 2


def test_negative_indices_and_slices():
    source = (
        'flow "lists":\n'
        '  step "s":\n'
        '    let xs = [10, 20, 30, 40]\n'
        '    let last = xs[-1]\n'
        '    let second_last = xs[-2]\n'
        '    let mid = xs[-3:-1]\n'
        '    let head = xs[:-2]\n'
        '    let tail = xs[-2:]\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, tools, _ = _make_flow_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-neg")
    result = engine.run_flow(ir_prog.flows["lists"], ctx)
    assert not result.errors
    assert ctx.variables["last"] == 40
    assert ctx.variables["second_last"] == 30
    assert ctx.variables["mid"] == [20, 30]
    assert ctx.variables["head"] == [10, 20]
    assert ctx.variables["tail"] == [30, 40]


def test_negative_index_out_of_range():
    source = (
        'flow "badneg":\n'
        '  step "s":\n'
        '    let xs = [1, 2]\n'
        '    let v = xs[-5]\n'
        '    do tool "echo"\n'
    )
    ir_prog = ast_to_ir(parse_source(source))
    engine, _, _ = _make_flow_engine(ir_prog)
    ctx = ExecutionContext(app_name="test", request_id="req-badneg")
    result = engine.run_flow(ir_prog.flows["badneg"], ctx)
    assert result.errors
    assert any("out of bounds" in err.error for err in result.errors)


def test_agent_slice_error():
    branch = IRConditionalBranch(
        condition=None,
        actions=[
            IRLet(name="x", expr=ast_nodes.Literal(value=1)),
            IRSet(
                name="y",
                expr=ast_nodes.SliceExpr(seq=ast_nodes.Identifier(name="x"), start=None, end=None),
            ),
        ],
        label="if",
    )
    from namel3ss.ir import IRAgent  # local import

    agent = IRAgent(name="agent_slice", goal=None, personality=None, conditional_branches=[branch])
    program = IRProgram(agents={"agent_slice": agent})

    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def list_names(self):
            return []

    runner = AgentRunner(program, DummyModelRegistry(), DummyToolRegistry(), DummyRouter())
    ctx = ExecutionContext(app_name="test", request_id="req-agent-slice")
    with pytest.raises(Namel3ssError):
        runner.run("agent_slice", ctx)
