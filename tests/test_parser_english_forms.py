import pytest

from namel3ss import lexer, parser, ir
from namel3ss.ast_nodes import DestructuringPattern, LetStatement
from namel3ss.errors import ParseError


def parse_src(source: str):
    tokens = lexer.Lexer(source).tokenize()
    return parser.Parser(tokens).parse_module()


def test_flow_header_english_form_parses():
    module = parse_src('flow is "demo":\n  step is "s":\n    let total be 1\n')
    flow = module.declarations[0]
    assert getattr(flow, "name", "") == "demo"


def test_let_constant_and_be_assignment():
    module = parse_src('flow is "demo":\n  step is "s":\n    let constant tax_rate be 0.21\n')
    step = module.declarations[0].steps[0]
    let_stmt = step.statements[0]
    assert isinstance(let_stmt, LetStatement)
    assert let_stmt.is_constant is True
    assert let_stmt.uses_equals is False


def test_record_and_list_destructuring_parse():
    src = '\n'.join(
        [
            'flow is "demo":',
            '  step is "s":',
            "    let {name, email as user_email} be user_record",
            "    let [first_user, second_user] be users",
        ]
    )
    module = parse_src(src)
    stmts = module.declarations[0].steps[0].statements
    record_stmt = stmts[0]
    list_stmt = stmts[1]
    assert isinstance(record_stmt.pattern, DestructuringPattern)
    assert record_stmt.pattern.kind == "record"
    assert record_stmt.pattern.fields[0].name == "name"
    assert record_stmt.pattern.fields[1].alias == "user_email"
    assert isinstance(list_stmt.pattern, DestructuringPattern)
    assert list_stmt.pattern.kind == "list"
    assert list_stmt.pattern.fields == ["first_user", "second_user"]


def test_legacy_equals_assignment_rejected():
    with pytest.raises(ParseError):
        parse_src('flow "legacy":\n  step "s":\n    let x = 1\n    set state.x = x\n')
