import pytest

from namel3ss import lexer, parser
from namel3ss.errors import ParseError


def parse_source(src: str):
    tokens = lexer.Lexer(src).tokenize()
    return parser.Parser(tokens).parse_module()


def test_missing_newline_between_declarations_has_hint():
    source = 'remember conversation as "chat" page is "home":\n  section "body":\n    text "hi"'
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    msg = str(excinfo.value)
    assert "N3L-PARSE-NEWLINE" in msg
    assert "Top-level blocks must start on a new line" in msg


def test_unknown_ai_field_suggests_close_match():
    source = '\n'.join(
        [
            'ai is "demo":',
            '  model is "gpt-4"',
            '  systm is "bad field"',
        ]
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    msg = str(excinfo.value)
    assert "N3L-PARSE-UNKNOWN-FIELD" in msg
    assert "Did you mean" in msg
    assert "system" in msg


def test_navigate_misuse_has_specific_message():
    source = '\n'.join(
        [
            'flow is "main":',
            '  step is "one":',
            '    navigate "home"',
        ]
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "N3L-PARSE-NAVIGATE" in str(excinfo.value)


def test_output_to_message_is_clear():
    source = '\n'.join(
        [
            'flow is "main":',
            '  step is "one":',
            '    output to record foo',
        ]
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "N3L-PARSE-OUTPUT" in str(excinfo.value)
