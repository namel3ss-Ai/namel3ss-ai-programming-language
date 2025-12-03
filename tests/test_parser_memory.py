from namel3ss import ast_nodes
from namel3ss.parser import parse_source


def test_parse_memory_block_and_page_properties():
    module = parse_source(
        'memory "short_term":\n'
        '  type "conversation"\n'
        'page "home":\n'
        '  title "Home"\n'
        '  route "/"\n'
        '  description "Landing"\n'
    )
    memory = next(d for d in module.declarations if isinstance(d, ast_nodes.MemoryDecl))
    assert memory.memory_type == "conversation"
    page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
    assert page.description == "Landing"
    assert len(page.properties) == 3
