from pathlib import Path

from namel3ss.migration.naming import rewrite_source


def test_rewrite_headers_and_assignments():
    legacy = (
        'flow "calculate_total":\n'
        '  step "sum":\n'
        "    let total = base + bonus\n"
        "    let constant taxRate = 0.2\n"
        "    set state.total = total\n"
    )
    result, updated = rewrite_source(legacy, apply_name_fixes=True)
    assert result.header_rewrites == 2
    assert result.let_rewrites == 2
    assert result.set_rewrites == 1
    assert 'flow is "calculate_total":' in updated
    assert 'step is "sum":' in updated
    assert "let total be base + bonus" in updated
    assert "let constant tax_rate be 0.2" in updated
    assert "set state.total be total" in updated


def test_rewrite_other_headers_and_preserve_strings():
    legacy = (
        'page "Home":\n'
        '  step "log":\n'
        '    let msg = "flow \\"name\\" should stay in string"\n'
    )
    _, updated = rewrite_source(legacy, apply_name_fixes=False)
    assert 'page is "Home":' in updated
    assert 'step is "log":' in updated
    assert '\\"name\\"' in updated  # string content untouched


def test_rewrite_removes_old_name():
    legacy = (
        'flow "legacy_names":\n'
        '  step "s":\n'
        "    let userEmail = input.email\n"
        "    let total = userEmail\n"
    )
    _, updated = rewrite_source(legacy, apply_name_fixes=True)
    assert "userEmail" not in updated
    assert "user_email" in updated
