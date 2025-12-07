import pytest

from namel3ss import ast_nodes
from namel3ss.ir import IRPage, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.ui.registry import UIPageRegistry
from namel3ss.errors import IRError, ParseError


def test_parse_page_with_layout():
    src = (
        'page "home" at "/":\n'
        '  heading "Welcome"\n'
        '  text "Hello"\n'
    )
    module = parse_source(src)
    page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
    assert page.route == "/"
    assert len(page.layout) == 2
    assert isinstance(page.layout[0], ast_nodes.HeadingNode)


def test_parse_section_and_image_and_form():
    src = (
        'page "signup" at "/signup":\n'
        '  section "hero":\n'
        '    heading "Create account"\n'
        '    image "https://example.com/logo.png"\n'
        '    use form "Signup"\n'
    )
    module = parse_source(src)
    page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
    sec = page.layout[0]
    assert isinstance(sec, ast_nodes.SectionDecl)
    assert len(sec.layout) == 3
    assert isinstance(sec.layout[-1], ast_nodes.EmbedFormNode)


def test_route_validation():
    src = 'page "bad" at "signup":\n  heading "oops"\n'
    with pytest.raises(ParseError):
        parse_source(src)


def test_duplicate_page_route():
    src = (
        'page "home" at "/":\n'
        '  heading "A"\n'
        '\n'
        'page "home2" at "/":\n'
        '  heading "B"\n'
    )
    module = parse_source(src)
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_layout_outside_page_error():
    src = 'heading "nope"\n'
    with pytest.raises(ParseError):
        parse_source(src)


def test_ir_lowering_and_registry():
    src = (
        'page "home" at "/":\n'
        '  heading "Welcome"\n'
        '  text "Hello"\n'
    )
    program = ast_to_ir(parse_source(src))
    ir_page: IRPage = program.pages["home"]
    assert len(ir_page.layout) == 2
    registry = UIPageRegistry()
    registry.register(ir_page)
    data = registry.to_dict()
    assert data["pages"][0]["route"] == "/"
    assert data["pages"][0]["layout"][0]["type"] == "heading"
