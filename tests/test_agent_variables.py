from namel3ss.agent.engine import AgentRunner
from namel3ss.ir import IRAgent, IRProgram, IRConditionalBranch, IRLet, IRSet, IRAction
from namel3ss import ast_nodes
from namel3ss.runtime.context import ExecutionContext
from namel3ss.errors import Namel3ssError


def test_agent_conditional_let_set_and_tool():
    # Agent with a single branch that declares and updates a variable then calls a tool.
    branch = IRConditionalBranch(
        condition=None,
        actions=[
            IRLet(name="score", expr=ast_nodes.Literal(value=1)),
            IRSet(name="score", expr=ast_nodes.BinaryOp(left=ast_nodes.Identifier(name="score"), op="+", right=ast_nodes.Literal(value=1))),
            IRAction(kind="tool", target="echo", message=None),
        ],
        label="if",
    )
    agent = IRAgent(name="var_agent", goal=None, personality=None, conditional_branches=[branch])

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

        def list_names(self):
            return ["echo"]

    program = IRProgram(agents={"var_agent": agent})
    tool_registry = DummyToolRegistry()
    runner = AgentRunner(program, DummyModelRegistry(), tool_registry, DummyRouter())
    ctx = ExecutionContext(app_name="test", request_id="req-agent")

    result = runner.run("var_agent", ctx)
    assert ctx.variables == {"score": 2}  # set executed, variables present
    assert tool_registry.calls  # tool was executed
    assert result.summary.startswith("Agent var_agent ran conditional branch")


def test_agent_variable_errors():
    # Declaring the same variable twice in the same branch should fail.
    branch = IRConditionalBranch(
        condition=None,
        actions=[IRLet(name="x", expr=ast_nodes.Literal(value=1)), IRLet(name="x", expr=ast_nodes.Literal(value=2))],
        label="if",
    )
    agent = IRAgent(name="dup_agent", conditional_branches=[branch])

    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def list_names(self):
            return []

    program = IRProgram(agents={"dup_agent": agent})
    runner = AgentRunner(program, DummyModelRegistry(), DummyToolRegistry(), DummyRouter())
    ctx = ExecutionContext(app_name="test", request_id="req-dup-agent")

    try:
        runner.run("dup_agent", ctx)
    except Namel3ssError as exc:
        assert "already defined" in str(exc)
    else:
        raise AssertionError("Expected Namel3ssError for duplicate variable")


def test_agent_set_undefined_raises():
    branch = IRConditionalBranch(
        condition=None,
        actions=[IRSet(name="missing", expr=ast_nodes.Literal(value=1))],
        label="if",
    )
    agent = IRAgent(name="undef_agent", conditional_branches=[branch])

    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def list_names(self):
            return []

    program = IRProgram(agents={"undef_agent": agent})
    runner = AgentRunner(program, DummyModelRegistry(), DummyToolRegistry(), DummyRouter())
    ctx = ExecutionContext(app_name="test", request_id="req-undef-agent")

    try:
        runner.run("undef_agent", ctx)
    except Namel3ssError as exc:
        assert "not defined" in str(exc)
    else:
        raise AssertionError("Expected Namel3ssError for undefined variable set")


def test_agent_numeric_errors():
    # Non-numeric arithmetic and divide by zero should raise errors.
    mismatch_branch = IRConditionalBranch(
        condition=None,
        actions=[
            IRLet(name="x", expr=ast_nodes.Literal(value="hi")),
            IRSet(
                name="x",
                expr=ast_nodes.BinaryOp(
                    left=ast_nodes.Identifier(name="x"),
                    op="+",
                    right=ast_nodes.Literal(value=1),
                ),
            ),
        ],
        label="if",
    )
    div_zero_branch = IRConditionalBranch(
        condition=None,
        actions=[
            IRLet(name="y", expr=ast_nodes.Literal(value=1)),
            IRSet(
                name="y",
                expr=ast_nodes.BinaryOp(
                    left=ast_nodes.Identifier(name="y"),
                    op="/",
                    right=ast_nodes.Literal(value=0),
                ),
            ),
        ],
        label="if",
    )

    class DummyModelRegistry:
        pass

    class DummyRouter:
        pass

    class DummyToolRegistry:
        def list_names(self):
            return []

    for name, branch in [("mismatch", mismatch_branch), ("divzero", div_zero_branch)]:
        program = IRProgram(agents={name: IRAgent(name=name, conditional_branches=[branch])})
        runner = AgentRunner(program, DummyModelRegistry(), DummyToolRegistry(), DummyRouter())
        ctx = ExecutionContext(app_name="test", request_id=f"req-{name}")
        try:
            runner.run(name, ctx)
        except Namel3ssError as exc:
            # Non-numeric or divide-by-zero messages
            assert "numeric" in str(exc) or "zero" in str(exc)
        else:
            raise AssertionError("Expected Namel3ssError for numeric failure")
