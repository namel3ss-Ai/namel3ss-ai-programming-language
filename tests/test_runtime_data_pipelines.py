from __future__ import annotations

import pytest

from namel3ss.ir import IRFrame, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment
from namel3ss.runtime.frames import FrameRegistry


def _eval_pipeline(source: str, *, resolver=None, env: VariableEnvironment | None = None):
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    flow = ir_prog.flows["f"]
    let_stmt = flow.steps[0].statements[0]
    env = env or VariableEnvironment()
    evaluator = ExpressionEvaluator(env, resolver=resolver or (lambda name: (False, None)))
    return evaluator.evaluate(let_stmt.expr)


def test_keep_and_drop_lists():
    keep_source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3, 4, 5]:\n"
        "      keep rows where row is greater than 2\n"
    )
    assert _eval_pipeline(keep_source) == [3, 4, 5]

    drop_source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3, 4, 5]:\n"
        "      drop rows where row % 2 is 0\n"
    )
    assert _eval_pipeline(drop_source) == [1, 3, 5]


def test_keep_over_records():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let users be [{ name: "Alice", is_active: true }, { name: "Bob", is_active: false }]:\n'
        "      keep rows where row.is_active is true\n"
    )
    result = _eval_pipeline(source)
    assert len(result) == 1
    assert result[0]["name"] == "Alice"


def test_group_by_and_sort_groups():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let sales be [{ customer_id: "c1", amount: 10 }, { customer_id: "c1", amount: 20 }, { customer_id: "c2", amount: 5 }]:\n'
        "      group by row.customer_id:\n"
        "        let total_spent be sum of row.amount\n"
        "        let orders_count be count of rows\n"
        "      sort groups by total_spent descending\n"
    )
    result = _eval_pipeline(source)
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["key"] == "c1"
    assert result[0]["total_spent"] == 30
    assert result[0]["orders_count"] == 2
    assert result[1]["key"] == "c2"
    assert result[1]["total_spent"] == 5
    assert result[1]["orders_count"] == 1


def test_take_and_skip():
    take_source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3, 4, 5]:\n"
        "      take first 3\n"
    )
    skip_source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3, 4, 5]:\n"
        "      skip first 2\n"
    )
    assert _eval_pipeline(take_source) == [1, 2, 3]
    assert _eval_pipeline(skip_source) == [3, 4, 5]


def test_pipeline_over_memory_frame():
    registry = FrameRegistry({"users": IRFrame(name="users", backend="memory", table="users")})
    registry.insert("users", {"name": "Alice", "is_active": True})
    registry.insert("users", {"name": "Bob", "is_active": False})
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let active be users:\n"
        "      keep rows where row.is_active is true\n"
    )
    resolver = lambda name: (True, registry.query(name)) if name in registry.frames else (False, None)
    result = _eval_pipeline(source, resolver=resolver)
    assert result == [{"name": "Alice", "is_active": True}]


def test_pipeline_errors():
    bad_source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be 123:\n"
        "      keep rows where row is greater than 0\n"
    )
    with pytest.raises(EvaluationError) as excinfo:
        _eval_pipeline(bad_source)
    assert "list or frame" in str(excinfo.value)

    non_boolean = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3]:\n"
        "      keep rows where 123\n"
    )
    with pytest.raises(EvaluationError) as excinfo2:
        _eval_pipeline(non_boolean)
    assert "true or false" in str(excinfo2.value)

    negative_take = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3]:\n"
        "      take first -1\n"
    )
    with pytest.raises(EvaluationError) as excinfo3:
        _eval_pipeline(negative_take)
    assert "non-negative number" in str(excinfo3.value)

    negative_skip = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let xs be [1, 2, 3]:\n"
        "      skip first -2\n"
    )
    with pytest.raises(EvaluationError) as excinfo4:
        _eval_pipeline(negative_skip)
    assert "non-negative number" in str(excinfo4.value)
