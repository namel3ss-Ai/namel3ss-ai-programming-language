from namel3ss import ir
from namel3ss.parser import parse_source
from namel3ss.diagnostics.engine import DiagnosticEngine


def test_diagnostics_warnings_and_errors():
    source = (
        'page "home":\n'
        '  title "Home"\n'
        'flow "pipeline":\n'
        'plugin "stripe":\n'
        '  description "payments"\n'
        'agent "helper":\n'
        '  goal "Assist"\n'
    )
    module = parse_source(source)
    program = ir.ast_to_ir(module)
    engine = DiagnosticEngine()
    diags = engine.analyze_ir(program, available_plugins=set())
    levels = [d.level for d in diags]
    messages = [d.message for d in diags]
    locations = [d.location for d in diags]
    assert any(m == "Page has no route" for m in messages)
    assert any(m == "Flow has no steps" for m in messages)
    assert any(m == "Agent declared but not referenced" for m in messages)
    assert any(d.level == "error" and d.location == "plugin:stripe" for d in diags)
