from namel3ss.diagnostics import Diagnostic


def test_diagnostic_to_dict_includes_all_fields():
    diag = Diagnostic(
        code="N3-1001",
        category="lang-spec",
        severity="error",
        message="Missing field",
        hint="Add the field",
        file="main.ai",
        line=10,
        column=5,
        end_line=10,
        end_column=12,
        doc_url="docs/diagnostics.md",
    )
    data = diag.to_dict()
    assert data["code"] == "N3-1001"
    assert data["category"] == "lang-spec"
    assert data["severity"] == "error"
    assert data["message"] == "Missing field"
    assert data["hint"] == "Add the field"
    assert data["file"] == "main.ai"
    assert data["line"] == 10
    assert data["column"] == 5
    assert data["end_line"] == 10
    assert data["end_column"] == 12
    assert data["doc_url"] == "docs/diagnostics.md"


def test_diagnostic_to_dict_handles_optional_nones():
    diag = Diagnostic(
        code="N3-1002",
        category="lang-spec",
        severity="warning",
        message="Unknown field",
        hint=None,
        file=None,
        line=None,
        column=None,
    )
    data = diag.to_dict()
    assert data["hint"] is None
    assert data["file"] is None
    assert data["line"] is None
    assert data["end_line"] is None
    assert data["doc_url"] is None
