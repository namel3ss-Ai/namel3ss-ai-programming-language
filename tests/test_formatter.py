from namel3ss.lang.formatter import format_source


def test_format_source_formats_and_idempotent():
    source = (
        'app is "demo":\n'
        '  description "Sample"\n'
        '\n'
        'page is "home":\n'
        '  route  "/" \n'
        '  section "main":\n'
        '    component "text":\n'
        '      value "Hello"'
    )
    expected = (
        'app is "demo":\n'
        '  description "Sample"\n'
        '\n'
        'page is "home":\n'
        '  route "/"\n'
        '  section "main":\n'
        '    component "text":\n'
        '      value "Hello"\n'
    )
    formatted = format_source(source)
    assert formatted == expected
    # idempotence
    assert format_source(formatted) == formatted


def test_format_source_with_flow_and_ai():
    source = (
        'ai is "greet":\n'
        ' model "m"\n'
        ' input from user\n'
        '\n'
        'flow is "pipeline":\n'
        ' step is "s":\n'
        '  target "greet"\n'
        '  kind "ai"\n'
    )
    expected = (
        'ai is "greet":\n'
        '  model "m"\n'
        '  input from "user"\n'
        '\n'
        'flow is "pipeline":\n'
        '  step is "s":\n'
        '    kind "ai"\n'
        '    target "greet"\n'
    )
    assert format_source(source) == expected
