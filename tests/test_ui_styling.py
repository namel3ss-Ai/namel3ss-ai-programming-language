import pytest

from namel3ss import ast_nodes
from namel3ss.errors import ParseError
from namel3ss.ir import IRSection, IRUIComponentCall, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.ui.runtime import UIPresenter
from namel3ss.ui.manifest import build_ui_manifest


def test_theme_settings_ir():
    src = (
        "settings:\n"
        "  theme:\n"
        '    primary color be "#111111"\n'
        '    accent color be "#222222"\n'
    )
    program = ast_to_ir(parse_source(src))
    assert program.settings
    assert program.settings.theme["primary"] == "#111111"


def test_styles_on_section_and_heading():
    src = (
        'page "styled" at "/":\n'
        '  section "hero":\n'
        '    layout is row\n'
        '    padding is small\n'
        '    heading "Hi"\n'
        '      color is "blue"\n'
    )
    program = ast_to_ir(parse_source(src))
    section = program.pages["styled"].layout[0]
    assert isinstance(section, IRSection)
    assert any(s.kind == "layout" for s in section.styles)
    heading = section.layout[0]
    assert heading.styles[0].kind == "color"
    assert heading.styles[0].value == "blue"


def test_invalid_spacing_raises():
    src = (
        'page "bad" at "/":\n'
        "  padding is huge\n"
        '  heading "X"\n'
    )
    with pytest.raises(ParseError):
        parse_source(src)


def test_component_decl_and_call():
    src = (
        'component "PrimaryButton":\n'
        "  takes label, action\n"
        "  render:\n"
        "    button label:\n"
        "      on click:\n"
        '        do flow "save" with name: label\n'
        '\n'
        'page "home" at "/":\n'
        '  PrimaryButton "Save changes":\n'
        "    action:\n"
        '      do flow "save"\n'
    )
    program = ast_to_ir(parse_source(src))
    assert "PrimaryButton" in program.ui_components
    call = next(el for el in program.pages["home"].layout if isinstance(el, IRUIComponentCall))
    assert call.name == "PrimaryButton"


def test_runtime_theme_resolution():
    src = (
        'page "colors" at "/":\n'
        '  heading "Hello"\n'
        "    color is primary\n"
    )
    program = ast_to_ir(parse_source(src))
    manifest = build_ui_manifest(program)
    assert manifest["theme"] == {}
    presenter = UIPresenter(program.pages["colors"], theme={"primary": "#ffffff"})
    heading = next(node for node in presenter.rendered if node["type"] == "heading")
    assert heading["styles"][0]["value"] == "#ffffff"
