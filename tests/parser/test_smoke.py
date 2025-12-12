import pytest

from namel3ss import parser


def test_parser_smoke():
    assert hasattr(parser, "parse")
    src = 'app is "a":\n  starts at page "x"\n'
    result = parser.parse_source(src)
    assert result is not None
