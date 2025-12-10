import pytest

from namel3ss.errors import Namel3ssError
from namel3ss.macros import MacroExpander, MacroExpansionError
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
    with pytest.raises(MacroExpansionError):
        expander.expand_module(module)


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
    with pytest.raises(MacroExpansionError):
        Engine._load_program(src, filename="<crud>")
