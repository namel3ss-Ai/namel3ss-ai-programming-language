from namel3ss.linting import lint_source


def find_rule(source: str, rule_id: str) -> bool:
    return any(f.rule_id == rule_id for f in lint_source(source))


def test_unused_variable_rule():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    let unused be 1\n"
    )
    assert find_rule(source, "N3-L001")


def test_unused_helper_rule():
    source = (
        'define helper "h":\n'
        "  return\n"
    )
    assert find_rule(source, "N3-L002")


def test_unreachable_match_branch():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        '    match intent:\n'
        '      when "a":\n'
        "        return\n"
        '      when "a":\n'
        "        return\n"
    )
    assert find_rule(source, "N3-L003")


def test_excessive_loop_bound():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    repeat up to 1001 times:\n"
        '      let x be 1\n'
    )
    assert find_rule(source, "N3-L004")


def test_shadow_variable():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    let x be 1\n"
        "    repeat for each x in [1]:\n"
        "      let y be x\n"
    )
    assert find_rule(source, "N3-L005")


def test_discouraged_equals():
    source = (
        'flow "f":\n'
        '  step "s":\n'
        "    let x = 1\n"
    )
    assert find_rule(source, "N3-L006")


def test_examples_smoke():
    examples = [
        "examples/gallery/support_chat.ai",
        "examples/gallery/data_processing.ai",
        "examples/gallery/form_flow.ai",
        "examples/gallery/modular_app.ai",
    ]
    for path in examples:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
        findings = lint_source(source)
        assert not findings or all(f.rule_id not in {"N3-L001", "N3-L002"} for f in findings)
