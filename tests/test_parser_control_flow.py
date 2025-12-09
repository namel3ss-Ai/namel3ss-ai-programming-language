import pytest

from namel3ss import ast_nodes
from namel3ss.parser import ParseError, parse_source


def test_if_chain_parses():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let score be 70\n"
        "    if score is greater than 80:\n"
        '      set state.status be \"approved\"\n'
        "    otherwise if score is greater than 60:\n"
        '      set state.status be \"review\"\n'
        "    else:\n"
        '      set state.status be \"rejected\"\n'
    )
    module = parse_source(source)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    assert flow.name == "f"
    assert flow.steps[0].name == "s"


def test_match_when_literal_only():
    source = (
        'flow is "router":\n'
        '  step is "route":\n'
        '    match state.intent:\n'
        '      when "billing":\n'
        '        set state.route be "billing_flow"\n'
        '      when "support":\n'
        '        set state.route be "support_flow"\n'
        "      otherwise:\n"
        '        set state.route be "fallback"\n'
    )
    module = parse_source(source)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    match_stmt = next(s for s in flow.steps[0].statements if isinstance(s, ast_nodes.MatchStatement))
    assert isinstance(match_stmt.target, ast_nodes.VarRef)
    patterns = [b.pattern.value for b in match_stmt.branches if b.pattern is not None]
    assert patterns == ["billing", "support"]


def test_standalone_when_errors():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    when true:\n"
        '      set state.flag be true\n'
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "only supported inside a match" in str(excinfo.value)


def test_match_non_literal_pattern_errors():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    match score:\n"
        "      when score is greater than 10:\n"
        '        set state.flag be true\n'
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "Control Flow v1" in str(excinfo.value)


def test_retry_and_loops_parse():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    repeat for each item in items:\n"
        "      let doubled be item * 2\n"
        "    repeat up to max_attempts times:\n"
        '      do tool "echo"\n'
        "    retry up to 3 times:\n"
        '      do tool "echo"\n'
        "    retry up to 5 times with backoff:\n"
        '      do tool "echo"\n'
    )
    module = parse_source(source)
    assert module


def test_legacy_kind_without_is_errors():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    kind "ai"\n'
        '    target is "bot"\n'
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "kind \"ai\" is not supported" in str(excinfo.value)


def test_legacy_headers_error():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    let x be 1\n"
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "flow \"f\": is not supported" in str(excinfo.value)


def test_inline_ternary_rejected():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    set state.kind be "a" if flag else "b"\n'
    )
    with pytest.raises(ParseError) as excinfo:
        parse_source(source)
    assert "Inline conditional expressions" in str(excinfo.value)
