import pytest

from namel3ss import ast_nodes
from namel3ss.ir import IRCollectionPipeline, IRCollectionGroupByStep, IRCollectionSortStep, IRCollectionTakeStep, ast_to_ir
from namel3ss.parser import ParseError, parse_source


def _get_first_let(source: str) -> ast_nodes.LetStatement:
    module = parse_source(source)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    step = flow.steps[0]
    let_stmt = next(s for s in step.statements if isinstance(s, ast_nodes.LetStatement))
    return let_stmt


def test_pipeline_parses_keep_and_take():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let filtered be orders:\n"
        "      keep rows where row.status is \"paid\"\n"
        "      drop rows where row.country is \"FR\"\n"
        "      take first 10\n"
    )
    let_stmt = _get_first_let(source)
    assert isinstance(let_stmt.expr, ast_nodes.CollectionPipeline)
    steps = let_stmt.expr.steps
    assert isinstance(steps[0], ast_nodes.CollectionKeepRowsStep)
    assert isinstance(steps[1], ast_nodes.CollectionDropRowsStep)
    assert isinstance(steps[2], ast_nodes.CollectionTakeStep)


def test_pipeline_parses_group_and_sort():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let grouped be sales_data:\n"
        "      group by row.customer_id:\n"
        "        let total_spent be row.amount\n"
        "        let orders_count be row.count\n"
        "      sort groups by total_spent descending\n"
    )
    let_stmt = _get_first_let(source)
    pipeline = let_stmt.expr
    assert isinstance(pipeline, ast_nodes.CollectionPipeline)
    assert isinstance(pipeline.steps[0], ast_nodes.CollectionGroupByStep)
    assert isinstance(pipeline.steps[1], ast_nodes.CollectionSortStep)
    group_step = pipeline.steps[0]
    assert any(isinstance(s, ast_nodes.LetStatement) for s in group_step.body)


def test_pipeline_missing_colon_errors():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let x be orders\n"
        "      keep rows where row.status is \"paid\"\n"
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "Expected" in str(excinfo.value)


def test_pipeline_missing_where_errors():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let x be orders:\n"
        "      keep rows\n"
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "Expected 'where' in keep rows pipeline step." in str(excinfo.value)


def test_pipeline_ir_shape():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let grouped be sales_data:\n"
        "      group by row.customer_id:\n"
        "        let total_spent be row.amount\n"
        "      sort groups by total_spent descending\n"
        "      take first 50\n"
    )
    module = parse_source(source)
    ir_prog = ast_to_ir(module)
    ir_let = ir_prog.flows["f"].steps[0].statements[0]
    assert isinstance(ir_let.expr, IRCollectionPipeline)
    steps = ir_let.expr.steps
    assert isinstance(steps[0], IRCollectionGroupByStep)
    assert isinstance(steps[1], IRCollectionSortStep)
    assert isinstance(steps[2], IRCollectionTakeStep)
