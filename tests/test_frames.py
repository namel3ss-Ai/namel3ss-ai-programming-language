import pytest

from namel3ss.errors import Namel3ssError
from namel3ss.ir import ast_to_ir, IRError
from namel3ss.parser import parse_source
from namel3ss.runtime.expressions import ExpressionEvaluator, VariableEnvironment
from namel3ss.runtime.frames import FrameRegistry
from namel3ss import ast_nodes


FIXTURE_PATH = "tests/fixtures/sales.csv"


def _resolver_from_env(env: VariableEnvironment):
    return lambda name: (env.has(name), env.resolve(name) if env.has(name) else None)


def test_parse_frame_minimal():
    src = (
        'frame is "sales":\n'
        "  source:\n"
        f'    from file "{FIXTURE_PATH}"\n'
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
        'frame is "sales":\n'
        "  source:\n"
        f'    from file "{FIXTURE_PATH}"\n'
        '    has headers\n'
        '    delimiter is ","\n'
        "  select:\n"
        '    columns are ["region", "revenue", "country"]\n'
        "  where:\n"
        '    row.country is \"BE\"\n'
    )
    module = parse_source(src)
    frame = next(d for d in module.declarations if isinstance(d, ast_nodes.FrameDecl))
    assert frame.delimiter == ","
    assert frame.has_headers is True
    assert frame.select_cols == ["region", "revenue", "country"]
    assert isinstance(frame.where, ast_nodes.Expr)


def test_frame_missing_source_errors():
    src = (
        'frame is "missing_source":\n'
        "  select:\n"
        '    columns are ["id"]\n'
    )
    with pytest.raises(IRError) as exc:
        ast_to_ir(parse_source(src))
    assert "needs a data source" in str(exc.value)


def test_frame_rejects_unsupported_backend():
    src = (
        'frame is "bad_backend":\n'
        "  source:\n"
        '    backend is "oracle"\n'
        '    table is "t1"\n'
    )
    with pytest.raises(IRError) as exc:
        ast_to_ir(parse_source(src))
    assert "not supported" in str(exc.value)


def test_frame_loading_and_aggregate_sum():
    src = (
        'frame is "sales_data":\n'
        "  source:\n"
        f'    from file \"{FIXTURE_PATH}\"\n'
        "    has headers\n"
        "  select:\n"
        '    columns are ["region", "revenue", "country"]\n'
        "  where:\n"
        '    row.country is \"BE\"\n'
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    rows = registry.get_rows("sales_data")
    assert len(rows) == 2
    env = VariableEnvironment({"sales_data": rows})
    resolver = _resolver_from_env(env)
    pipeline_src = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let filtered be sales_data:\n'
        '      keep rows where row.country is "BE"\n'
    )
    pipeline_module = parse_source(pipeline_src)
    pipeline_ir = ast_to_ir(pipeline_module)
    pipeline_expr = pipeline_ir.flows["f"].steps[0].statements[0].expr
    evaluator = ExpressionEvaluator(env, resolver=resolver)
    filtered_rows = evaluator.evaluate(pipeline_expr)
    assert len(filtered_rows) == 2
    revenues = [r["revenue"] for r in filtered_rows]
    sum_expr = ast_nodes.ListBuiltinCall(name="sum", expr=ast_nodes.Literal(value=revenues))
    assert evaluator.evaluate(sum_expr) == 150


def test_all_expression_with_frame_where():
    src = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let filtered be sales_data:\n'
        '      keep rows where row.country is "BE"\n'
    )
    module = parse_source(src)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    let_stmt = flow.steps[0].statements[0]
    program = ast_to_ir(parse_source(
        'frame is "sales_data":\n'
        "  source:\n"
        f'    from file "{FIXTURE_PATH}"\n'
        "    has headers\n"
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
        'frame is "bad":\n'
        "  source:\n"
        f'    from file "{FIXTURE_PATH}"\n'
        "    has headers\n"
        "  select:\n"
        '    columns are ["missing"]\n'
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    with pytest.raises(Namel3ssError) as excinfo:
        registry.get_rows("bad")
    assert "N3F-1002" in str(excinfo.value)


def test_where_clause_must_be_boolean():
    src = (
        'frame is "bad_where":\n'
        "  source:\n"
        f'    from file "{FIXTURE_PATH}"\n'
        "    has headers\n"
        "  where:\n"
        "    revenue plus 1\n"
    )
    program = ast_to_ir(parse_source(src))
    registry = FrameRegistry(program.frames)
    with pytest.raises(Namel3ssError) as excinfo:
        registry.get_rows("bad_where")
    assert "N3F-1003" in str(excinfo.value)
