import pytest

from namel3ss.diagnostics import all_definitions, create_diagnostic, get_definition


def test_registry_contains_core_codes():
    for code in ["N3-1001", "N3-1002", "N3-1003", "N3-1004", "N3-1005", "N3-0001", "N3-2001"]:
        assert get_definition(code) is not None
    codes = {d.code for d in all_definitions()}
    assert "N3-1001" in codes


def test_create_diagnostic_formats_message_and_defaults():
    diag = create_diagnostic(
        "N3-1001",
        message_kwargs={"field": "route", "kind": "page"},
        file="page:home",
        line=3,
        column=5,
        hint="Add route",
    )
    assert diag.code == "N3-1001"
    assert diag.category == "lang-spec"
    assert diag.severity == "error"
    assert "route" in diag.message
    assert diag.file == "page:home"
    assert diag.line == 3
    assert diag.column == 5
    assert diag.hint == "Add route"


def test_create_diagnostic_unknown_code_raises():
    with pytest.raises(ValueError):
        create_diagnostic("N3-9999")
