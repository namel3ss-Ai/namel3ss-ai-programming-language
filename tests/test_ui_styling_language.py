from textwrap import dedent

import pytest

from namel3ss import ast_nodes, parser
from namel3ss.ir import ast_to_ir
from namel3ss.ui.manifest import build_ui_manifest


def _get_page(module: ast_nodes.Module) -> ast_nodes.PageDecl:
    return next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))


def test_parse_component_class_and_style():
    source = dedent(
        """
        page is "home" at "/":
          text is "title":
            value is "Welcome"
            class is "hero-title"
            style:
              color: "#fff"
              background: "#000"
          button is "cta":
            label is "Click"
            class is "primary-cta"
            style:
              color: "#fff"
            on click:
              navigate to "/next"
        """
    )
    module = parser.parse_source(source)
    page = _get_page(module)
    text = next(el for el in page.layout if isinstance(el, ast_nodes.TextNode))
    assert text.class_name == "hero-title"
    assert text.style == {"color": "#fff", "background": "#000"}
    button = next(el for el in page.layout if isinstance(el, ast_nodes.UIButtonNode))
    assert button.class_name == "primary-cta"
    assert button.style == {"color": "#fff"}


def test_manifest_includes_class_and_style():
    source = dedent(
        """
        page is "home" at "/":
          text is "title":
            value is "Welcome"
            class is "hero-title"
          button is "cta":
            label is "Click"
            class is "primary-cta"
            style:
              color: "#fff"
            on click:
              navigate to "/next"
        """
    )
    module = parser.parse_source(source)
    ir_prog = ast_to_ir(module)
    manifest = build_ui_manifest(ir_prog)
    page_manifest = manifest["pages"][0]
    text_el = next(el for el in page_manifest["layout"] if el["type"] == "text")
    button_el = next(el for el in page_manifest["layout"] if el["type"] == "button")
    assert text_el.get("className") == "hero-title"
    assert button_el.get("className") == "primary-cta"
    assert button_el.get("style", {}).get("color") == "#fff"


def test_invalid_class_requires_string_literal():
    source = dedent(
        """
        page is "home" at "/":
          text is "title":
            class is 123
        """
    )
    with pytest.raises(Exception):
        parser.parse_source(source)
