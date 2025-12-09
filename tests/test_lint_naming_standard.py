from namel3ss.linting import lint_source


def has_rule(source: str, rule_id: str) -> bool:
    return any(f.rule_id == rule_id for f in lint_source(source))


def test_lint_snake_case():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    let UserEmail be input.email\n"
    )
    assert has_rule(source, "N3-L008")


def test_lint_boolean_prefix_suggestion():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let active be status is "active"\n'
    )
    assert has_rule(source, "N3-L009")


def test_lint_plural_loop_variable():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    repeat for each users in users:\n"
        "      let total be 0\n"
    )
    assert has_rule(source, "N3-L010")
