from textwrap import dedent

from namel3ss import parser
from namel3ss.ast_nodes import FlowDecl, PageDecl, RecordDecl
from namel3ss.macros import MacroExpander


def test_app_scaffold_expands_full_stack():
    source = dedent(
        """
        use macro is "app_scaffold" with:
          entity is "Product"
          fields:
            field is "name":
              type is "string"
              required is true

            field is "price":
              type is "float"
              required is true
              min is 0

            field is "is_active":
              type is "bool"
              default is true
        """
    )
    module = parser.parse_source(source)
    expanded = MacroExpander(ai_callback=None).expand_module(module)
    decls = expanded.declarations

    assert any(isinstance(d, RecordDecl) and d.name == "Product" for d in decls)
    assert any(isinstance(d, FlowDecl) and d.name == "list_products" for d in decls)
    assert any(isinstance(d, PageDecl) and d.name == "products_list" for d in decls)
