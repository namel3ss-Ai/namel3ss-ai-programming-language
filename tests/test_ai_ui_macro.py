import pytest

from namel3ss import ast_nodes
from namel3ss.errors import Namel3ssError
from namel3ss.macros import MacroExpander, MacroExpansionError
from namel3ss.parser import parse_source
from namel3ss.runtime.engine import Engine


def test_crud_ui_macro_expansion_generates_crud():
    src = (
        'use macro is "crud_ui" with:\n'
        '  entity is "Product"\n'
        "  fields:\n"
        '    field is "name":\n'
        '      type is "string"\n'
        '      required is true\n'
        '    field is "price":\n'
        '      type is "float"\n'
        '      required is true\n'
    )
    module = parse_source(src)
    expander = MacroExpander(lambda m, a: "")
    expanded = expander.expand_module(module)
    flows = {d.name for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)}
    pages = {d.name for d in expanded.declarations if isinstance(d, ast_nodes.PageDecl)}
    assert {"list_products", "create_product", "edit_product", "delete_product", "get_product"} <= flows
    assert {"products_list", "product_create", "product_edit", "product_detail", "product_delete"} <= pages


def test_crud_ui_macro_invalid_fields():
    src = (
        'use macro is "crud_ui" with:\n'
        '  entity is "Product"\n'
        "  fields:\n"
        '    field is "name"\n'
    )
    with pytest.raises(Namel3ssError):
        parse_source(src)


def test_engine_expands_crud_ui():
    src = (
        'use macro is "crud_ui" with:\n'
        '  entity is "Widget"\n'
        "  fields:\n"
        '    field is "title":\n'
        '      type is "string"\n'
    )
    program = Engine._load_program(src, filename="<crud>")
    assert "list_widgets" in program.flows
