from textwrap import dedent

from namel3ss import parser
from namel3ss.ast_nodes import AgentDecl, FlowDecl, PageDecl, RecordDecl, VectorStoreDecl
from namel3ss.macros import MacroExpander


def test_app_scaffold_expands_full_stack():
    source = dedent(
        """
        use macro "app_scaffold" with:
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
    assert any(isinstance(d, VectorStoreDecl) and d.name == "product_kb" for d in decls)
    assert any(getattr(d, "name", None) == "product_kb_pipeline" for d in decls)
    assert any(isinstance(d, AgentDecl) and d.name == "product_support_agent" for d in decls)
