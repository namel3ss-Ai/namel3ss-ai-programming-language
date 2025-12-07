import pytest

from namel3ss.errors import Namel3ssError
from namel3ss.ir import ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.runtime.expressions import ExpressionEvaluator, VariableEnvironment
from namel3ss.runtime.frames import FrameRegistry
from namel3ss import ast_nodes


FIXTURE_PATH = "tests/fixtures/sales.csv"


def _resolver_from_env(env: VariableEnvironment):
    return lambda name: (env.has(name), env.resolve(name) if env.has(name) else None)


def test_parse_frame_minimal():
    src = (
        'frame "sales":\n'
        f'  from file "{FIXTURE_PATH}"\n'
    )
    module = parse_source(src)
    frame = next(d for d in module.declarations if isinstance(d, ast_nodes.FrameDecl))
    assert frame.name == "sales"
    assert frame.source_kind == "file"
    assert frame.source_path == FIXTURE_PATH
    assert frame.delimiter is None
    assert frame.has_headers is False


def test_parse_frame_full_config():
    src = (
        'frame "sales":\n'
        f'  from file "{FIXTURE_PATH}"\n'
        '  with delimiter ","\n'
        "  has headers\n"
        "  select region, revenue, country\n"
        '  where country is "BE"\n'
    )
    module = parse_source(src)
    frame = next(d for d in module.declarations if isinstance(d, ast_nodes.FrameDecl))
    assert frame.delimiter == ","
    assert frame.has_headers is True
    assert frame.select_cols == ["region", "revenue", "country"]
    assert isinstance(frame.where, ast_nodes.Expr)


def test_frame_loading_and_aggregate_sum():
    src = (
        'frame "sales_data":\n'
        f'  from file "{FIXTURE_PATH}"\n'
        "  has headers\n"
        "  select region, revenue, country\n"
        '  where country is "BE"\n'
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    rows = registry.get_rows("sales_data")
    assert len(rows) == 2
    env = VariableEnvironment({"sales_data": rows})
    resolver = _resolver_from_env(env)
    predicate = ast_nodes.BinaryOp(
        left=ast_nodes.RecordFieldAccess(target=ast_nodes.Identifier(name="row"), field="country"),
        op="==",
        right=ast_nodes.Literal(value="BE"),
    )
    filter_expr = ast_nodes.FilterExpression(
        source=ast_nodes.Identifier(name="sales_data"),
        var_name="row",
        predicate=predicate,
    )
    map_expr = ast_nodes.MapExpression(
        source=filter_expr,
        var_name="row",
        mapper=ast_nodes.RecordFieldAccess(target=ast_nodes.Identifier(name="row"), field="revenue"),
    )
    sum_call = ast_nodes.ListBuiltinCall(name="sum", expr=map_expr)
    evaluator = ExpressionEvaluator(env, resolver=resolver)
    total = evaluator.evaluate(sum_call)
    assert total == 150


def test_all_expression_with_frame_where():
    src = (
        'flow "f":\n'
        '  step "s":\n'
        '    let filtered be all row from sales_data where row.country is "BE"\n'
    )
    module = parse_source(src)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    let_stmt = flow.steps[0].statements[0]
    assert isinstance(let_stmt.expr, (ast_nodes.FilterExpression, ast_nodes.MapExpression))
    program = ast_to_ir(parse_source(
        'frame "sales_data":\n'
        f'  from file "{FIXTURE_PATH}"\n'
        "  has headers\n"
    ))
    registry = FrameRegistry(program.frames)
    rows = registry.get_rows("sales_data")
    env = VariableEnvironment({"sales_data": rows})
    evaluator = ExpressionEvaluator(env, resolver=_resolver_from_env(env))
    result = evaluator.evaluate(let_stmt.expr)
    assert isinstance(result, list)
    assert len(result) == 2


def test_unknown_select_column_raises():
    src = (
        'frame "bad":\n'
        f'  from file "{FIXTURE_PATH}"\n'
        "  has headers\n"
        "  select missing\n"
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    with pytest.raises(Namel3ssError) as excinfo:
        registry.get_rows("bad")
    assert "N3F-1002" in str(excinfo.value)


def test_where_clause_must_be_boolean():
    src = (
        'frame "bad_where":\n'
        f'  from file "{FIXTURE_PATH}"\n'
        "  has headers\n"
        "  where revenue plus 1\n"
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    with pytest.raises(Namel3ssError) as excinfo:
        registry.get_rows("bad_where")
    assert "N3F-1003" in str(excinfo.value)
