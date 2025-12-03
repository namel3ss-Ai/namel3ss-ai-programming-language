from namel3ss import ast_nodes
from namel3ss.parser import parse_source


def test_parse_program_ast_structure():
    program = parse_source(
        'use "common.ai"\n'
        'app "support_portal":\n'
        '  description "Support portal for customer questions"\n'
        '  entry_page "home"\n'
        'page "home":\n'
        '  title "Home"\n'
        '  route "/"\n'
        'model "default":\n'
        '  provider "openai:gpt-4.1-mini"\n'
        'ai "summarise_message":\n'
        '  model "default"\n'
        '  input from user_message\n'
    )

    assert isinstance(program, ast_nodes.Module)
    assert len(program.declarations) == 5
    app = next(d for d in program.declarations if isinstance(d, ast_nodes.AppDecl))
    assert app.name == "support_portal"
    assert app.entry_page == "home"
    page = next(d for d in program.declarations if isinstance(d, ast_nodes.PageDecl))
    assert page.title == "Home"
    ai_call = next(
        d for d in program.declarations if isinstance(d, ast_nodes.AICallDecl)
    )
    assert ai_call.model_name == "default"
    assert ai_call.input_source == "user_message"
