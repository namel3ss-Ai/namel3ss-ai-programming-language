import pytest

from namel3ss import ast_nodes
from namel3ss.parser import parse_source


def _first_flow(source: str) -> ast_nodes.FlowDecl:
    module = parse_source(source)
    return next(decl for decl in module.declarations if isinstance(decl, ast_nodes.FlowDecl))


def test_parse_let_with_be_and_equals():
    source = (
        'flow "scores":\n'
        '  step "init":\n'
        '    let score be 1\n'
        '    let bonus = 2\n'
        '    set score to score + bonus\n'
    )
    flow = _first_flow(source)
    step = flow.steps[0]
    assert step.kind == "script"
    let_one = step.statements[0]
    assert isinstance(let_one, ast_nodes.LetStatement)
    assert let_one.name == "score"
    let_two = step.statements[1]
    assert isinstance(let_two, ast_nodes.LetStatement)
    assert let_two.name == "bonus"
    set_stmt = step.statements[2]
    assert isinstance(set_stmt, ast_nodes.SetStatement)
    assert set_stmt.name == "score"
    assert isinstance(set_stmt.expr, ast_nodes.BinaryOp)
    assert set_stmt.expr.op == "+"


def test_arithmetic_precedence_and_parentheses():
    source = (
        'flow "calc":\n'
        '  step "compute":\n'
        '    let total be 1 plus 2 times 3\n'
        '    let nested be (1 + 2) * 3\n'
    )
    flow = _first_flow(source)
    total_expr = flow.steps[0].statements[0].expr
    assert isinstance(total_expr, ast_nodes.BinaryOp)
    assert total_expr.op == "+"
    assert isinstance(total_expr.right, ast_nodes.BinaryOp)
    assert total_expr.right.op == "*"
    nested_expr = flow.steps[0].statements[1].expr
    assert isinstance(nested_expr, ast_nodes.BinaryOp)
    assert nested_expr.op == "*"
    assert isinstance(nested_expr.left, ast_nodes.BinaryOp)
    assert nested_expr.left.op == "+"


def test_boolean_comparisons_and_not():
    source = (
        'flow "logic":\n'
        '  step "check":\n'
        '    if score is greater than 10 and not false:\n'
        '      do tool "echo"\n'
    )
    flow = _first_flow(source)
    step = flow.steps[0]
    if step.statements:
        if_stmt = step.statements[0]
        cond = if_stmt.branches[0].condition
    else:
        cond = step.conditional_branches[0].condition
    assert isinstance(cond, ast_nodes.BinaryOp)
    assert cond.op == "and"
    left = cond.left
    assert isinstance(left, ast_nodes.BinaryOp)
    assert left.op == ">"
    right = cond.right
    assert isinstance(right, ast_nodes.UnaryOp)
    assert right.op == "not"
