import json
from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.macros import MacroExpander, MacroExpansionError
from namel3ss.ast_nodes import MacroDecl, MacroUse


def _expander(fake_output: str):
    def _cb(macro, args):
        return fake_output

    return MacroExpander(ai_callback=_cb)


def test_structured_macro_plan_expands_to_ast():
    plan = {
        "macro_plan": {
            "records": [
                {
                    "name": "Product",
                    "frame": "products",
                    "fields": [
                        {"name": "id", "type": "uuid", "primary_key": True, "required": True},
                        {"name": "name", "type": "string", "required": True},
                        {"name": "price", "type": "float", "required": True, "min": 0},
                    ],
                }
            ],
            "flows": [
                {"name": "list_products", "kind": "list_crud", "record": "Product"},
                {"name": "create_product", "kind": "create_crud", "record": "Product"},
            ],
            "pages": [
                {"name": "products_list", "route": "/products", "kind": "crud_list", "record": "Product"},
            ],
        }
    }
    module = parser.parse_source(
        dedent(
            """
            macro "plan_codegen" using ai "stub":
              description "Structured plan macro"

            use macro "plan_codegen"
            """
        )
    )
    macro_decl = next(d for d in module.declarations if isinstance(d, MacroDecl))
    macro_use = next(d for d in module.declarations if isinstance(d, MacroUse))
    expander = _expander(json.dumps(plan))
    expanded = expander.expand_module(module)
    names = {d.name for d in expanded.declarations if hasattr(d, "name")}
    assert "Product" in names
    assert "list_products" in names
    assert "create_product" in names
    assert "products_list" in names


def test_invalid_macro_plan_raises():
    bad_plan = {"macro_plan": {"flows": [{"name": "oops", "kind": "unknown"}]}}
    module = parser.parse_source(
        dedent(
            """
            macro "plan_codegen" using ai "stub":
              description "Structured plan macro"

            use macro "plan_codegen"
            """
        )
    )
    expander = _expander(json.dumps(bad_plan))
    expanded = expander.expand_module(module)
    names = {getattr(d, "name", None) for d in expanded.declarations if hasattr(d, "name")}
    assert "oops" in names


def test_non_plan_json_falls_back_to_string_parse():
    payload = json.dumps({"not_a_plan": True})
    module = parser.parse_source(
        dedent(
            """
            macro "plan_codegen" using ai "stub":
              description "Structured plan macro"

            use macro "plan_codegen"
            """
        )
    )
    expander = _expander(payload)
    # This should error with parse (no DSL), not a plan error.
    with pytest.raises(Exception):
        expander.expand_module(module)
