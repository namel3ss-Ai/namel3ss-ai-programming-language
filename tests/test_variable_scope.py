import pytest

from namel3ss import ast_nodes
from namel3ss.ir import (
    IRFlow,
    IRFlowLoop,
    IRFlowStep,
    IRProgram,
    IRRecord,
    IRRecordField,
    IRFrame,
    IRModel,
    IRAgent,
    IRLet,
    IRSet,
    IRAction,
    IRError,
)
from namel3ss.ir import ast_to_ir


def _simple_program(flow: ast_nodes.FlowDecl) -> ast_nodes.Module:
    frame = ast_nodes.FrameDecl(name="users", backend="memory", table="users")
    record = ast_nodes.RecordDecl(
        name="User",
        frame="users",
        fields=[
            ast_nodes.RecordFieldDecl(name="id", type="uuid", primary_key=True),
            ast_nodes.RecordFieldDecl(name="email", type="string"),
        ],
    )
    return ast_nodes.Module(declarations=[frame, record, flow])


def test_valid_scope_with_state_user_and_steps():
    flow = ast_nodes.FlowDecl(
        name="ok",
        steps=[
            ast_nodes.FlowStepDecl(
                name="load",
                kind="db_get",
                target="User",
                params={"by_id": {"id": ast_nodes.VarRef(name="state.user_id", root="state", path=["user_id"], kind=ast_nodes.VarRefKind.UNKNOWN)}},
            ),
            ast_nodes.FlowStepDecl(
                name="compute",
                kind="set",
                target="state.email",
                params={},
                statements=[
                    ast_nodes.FlowAction(
                        kind="set",
                        target="state.email",
                        args={"value": ast_nodes.VarRef(name="step.load.output.email", root="step", path=["load", "output", "email"], kind=ast_nodes.VarRefKind.UNKNOWN)},
                    )
                ],
            ),
        ],
    )
    module = _simple_program(flow)
    ast_to_ir(module)  # should not raise


def test_unknown_variable_diagnostic():
    flow = ast_nodes.FlowDecl(
        name="bad",
        steps=[
            ast_nodes.FlowStepDecl(
                name="x",
                kind="set",
                target="state.value",
                params={},
                statements=[
                    ast_nodes.FlowAction(
                        kind="set",
                        target="state.value",
                        args={"value": ast_nodes.VarRef(name="foo", root="foo", path=[], kind=ast_nodes.VarRefKind.UNKNOWN)},
                    )
                ],
            )
        ],
    )
    module = _simple_program(flow)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1700" in str(exc.value)


def test_step_before_definition():
    flow = ast_nodes.FlowDecl(
        name="bad_order",
        steps=[
            ast_nodes.FlowStepDecl(
                name="second",
                kind="db_get",
                target="User",
                params={
                    "by_id": {
                        "id": ast_nodes.VarRef(
                            name="step.first.output.foo",
                            root="step",
                            path=["first", "output", "foo"],
                            kind=ast_nodes.VarRefKind.UNKNOWN,
                        )
                    }
                },
            ),
            ast_nodes.FlowStepDecl(
                name="first",
                kind="db_get",
                target="User",
                params={"by_id": {"id": ast_nodes.Literal(value="1")}},
            ),
        ],
    )
    module = _simple_program(flow)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1701" in str(exc.value)


def test_missing_step_reference():
    flow = ast_nodes.FlowDecl(
        name="missing_step",
        steps=[
            ast_nodes.FlowStepDecl(
                name="x",
                kind="set",
                target="state.value",
                params={},
                statements=[
                    ast_nodes.FlowAction(
                        kind="set",
                        target="state.value",
                        args={
                            "value": ast_nodes.VarRef(
                                name="step.load.output.foo",
                                root="step",
                                path=["load", "output", "foo"],
                                kind=ast_nodes.VarRefKind.UNKNOWN,
                            )
                        },
                    )
                ],
            )
        ],
    )
    module = _simple_program(flow)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1702" in str(exc.value)


def test_loop_variable_leak():
    loop = ast_nodes.FlowLoopDecl(
        name="loop",
        var_name="item",
        iterable=ast_nodes.VarRef(name="state.values", root="state", path=["values"], kind=ast_nodes.VarRefKind.UNKNOWN),
        steps=[
            ast_nodes.FlowStepDecl(
                name="inner",
                kind="db_get",
                target="User",
                params={"by_id": {"id": ast_nodes.VarRef(name="item", root="item", path=[], kind=ast_nodes.VarRefKind.UNKNOWN)}},
            )
        ],
    )
    flow = ast_nodes.FlowDecl(
        name="loop_flow",
        steps=[
            loop,
            ast_nodes.FlowStepDecl(
                name="after",
                kind="db_get",
                target="User",
                params={"by_id": {"id": ast_nodes.VarRef(name="item", root="item", path=[], kind=ast_nodes.VarRefKind.UNKNOWN)}},
            ),
        ],
    )
    module = _simple_program(flow)
    with pytest.raises(IRError) as exc:
        ast_to_ir(module)
    assert "N3L-1703" in str(exc.value)
