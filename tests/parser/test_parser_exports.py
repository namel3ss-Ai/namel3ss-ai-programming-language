from __future__ import annotations


def test_parser_exports() -> None:
    from namel3ss.parser import ParseError, Parser, parse, parse_source

    assert Parser is not None
    assert callable(parse)
    assert callable(parse_source)
    assert ParseError is not None
