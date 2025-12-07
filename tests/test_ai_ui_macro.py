import pytest

from namel3ss.errors import Namel3ssError
from namel3ss.macros import MacroExpander
from namel3ss.parser import parse_source
from namel3ss.runtime.engine import Engine


def test_crud_ui_macro_expansion_generates_crud():
    src = (
        'use macro "crud_ui" with:\n'
        '  entity "Product"\n'
        '  fields ["name", "price"]\n'
    )
    module = parse_source(src)
    expander = MacroExpander(lambda m, a: "")
    expanded = expander.expand_module(module)
    flow_names = {getattr(d, "name", None) for d in expanded.declarations if d.__class__.__name__ == "FlowDecl"}
    page_names = {getattr(d, "name", None) for d in expanded.declarations if d.__class__.__name__ == "PageDecl"}
    assert "list_products" in flow_names
    assert "create_product" in flow_names
    assert "products_list" in page_names
    assert "create_product" in page_names


def test_crud_ui_macro_invalid_fields():
    src = (
        'use macro "crud_ui" with:\n'
        '  entity "Product"\n'
        '  fields "name"\n'
    )
    module = parse_source(src)
    expander = MacroExpander(lambda m, a: "")
    with pytest.raises(Namel3ssError):
        expander.expand_module(module)


def test_engine_expands_crud_ui():
    src = (
        'use macro "crud_ui" with:\n'
        '  entity "Widget"\n'
        '  fields ["title"]\n'
    )
    program = Engine._load_program(src, filename="<crud>")
    assert "list_widgets" in program.flows
    assert "widgets_list" in program.pages
