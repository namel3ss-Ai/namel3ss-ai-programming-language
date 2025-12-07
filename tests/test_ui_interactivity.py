import pytest

from namel3ss import ast_nodes
from namel3ss.errors import IRError, ParseError
from namel3ss.ir import IRUIButton, IRUIConditional, ast_to_ir
from namel3ss.parser import parse_source
from namel3ss.ui.runtime import UIPresenter


def test_parse_state_input_button():
    src = (
        'page "signup" at "/signup":\n'
        '  state name is ""\n'
        '  input "Your name" as name\n'
        '  button "Continue":\n'
        '    on click:\n'
        '      do flow "register" with name: name\n'
    )
    module = parse_source(src)
    page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
    assert isinstance(page.layout[0], ast_nodes.UIStateDecl)
    assert isinstance(page.layout[1], ast_nodes.UIInputNode)
    program = ast_to_ir(module)
    ir_page = program.pages["signup"]
    assert len(ir_page.ui_states) == 1
    button = next(el for el in ir_page.layout if isinstance(el, IRUIButton))
    assert button.actions[0].kind == "flow"
    assert "name" in button.actions[0].args


def test_invalid_state_outside_page():
    with pytest.raises(ParseError):
        parse_source('state name is ""\n')


def test_invalid_input_type():
    src = 'page "bad" at "/":\n  input "X" as x type is weird\n'
    module = parse_source(src)
    with pytest.raises(IRError):
        ast_to_ir(module)


def test_conditional_runtime_updates():
    src = (
        'page "greeting" at "/hello":\n'
        '  state name is ""\n'
        '  when name is not "":\n'
        '    show:\n'
        '      text "Hello"\n'
        '  otherwise:\n'
        '    show:\n'
        '      text "Enter your name"\n'
    )
    program = ast_to_ir(parse_source(src))
    ir_page = program.pages["greeting"]
    presenter = UIPresenter(ir_page)
    assert any(node.get("text") == "Enter your name" for node in presenter.rendered)
    presenter.set_state("name", "Ada")
    assert any(node.get("text") == "Hello" for node in presenter.rendered)


def test_button_dispatch_uses_state_snapshot():
    src = (
        'page "action" at "/":\n'
        '  state counter is 0\n'
        '  button "Run":\n'
        '    on click:\n'
        '      do flow "increment" with value: counter\n'
    )
    program = ast_to_ir(parse_source(src))
    ir_page = program.pages["action"]
    presenter = UIPresenter(ir_page)
    captured = []

    def dispatcher(action, state):
        captured.append((action.target, state["counter"]))

    presenter.click("Run", dispatcher=dispatcher)
    assert captured == [("increment", 0)]
