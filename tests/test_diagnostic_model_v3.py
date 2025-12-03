from namel3ss.diagnostics.models import Diagnostic, has_effective_errors


def test_diagnostic_fields_and_defaults():
    diag = Diagnostic(
        code="N3-TEST-001",
        severity="warning",
        category="semantic",
        message="Test message",
        location="page:home",
        hint="Do a thing",
        auto_fix={"action": "add", "field": "route"},
    )
    data = diag.to_dict()
    assert data["code"] == "N3-TEST-001"
    assert data["severity"] == "warning"
    assert data["category"] == "semantic"
    assert data["message"] == "Test message"
    assert data["hint"] == "Do a thing"
    assert data["auto_fix"] == {"action": "add", "field": "route"}


def test_backward_compatibility_level_sets_severity():
    diag = Diagnostic(level="error", message="Legacy")
    assert diag.severity == "error"
    assert diag.level == "error"
    assert has_effective_errors([diag], strict=False)
    warn = Diagnostic(level="warning", message="Warn")
    assert has_effective_errors([warn], strict=True)
