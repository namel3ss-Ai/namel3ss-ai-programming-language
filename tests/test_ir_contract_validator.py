from namel3ss.lang.validator import validate_module
from namel3ss.ir import (
    IRProgram,
    IRApp,
    IRPage,
    IRModel,
    IRAiCall,
    IRAgent,
    IRFlow,
    IRFlowStep,
    IRMemory,
)


def build_valid_program() -> IRProgram:
    program = IRProgram()
    program.models["m"] = IRModel(name="m", provider="dummy")
    program.ai_calls["a"] = IRAiCall(name="a", model_name="m", input_source="user_input")
    program.agents["agent"] = IRAgent(name="agent")
    program.pages["home"] = IRPage(name="home", route="/")
    program.apps["app"] = IRApp(name="app", entry_page="home")
    program.flows["f"] = IRFlow(name="f", description=None, steps=[IRFlowStep(name="s", kind="ai", target="a")])
    program.memories["mem"] = IRMemory(name="mem", memory_type="conversation")
    return program


def test_validate_module_success():
    program = build_valid_program()
    diags = validate_module(program)
    errors = [d for d in diags if d.severity == "error"]
    assert not errors


def test_missing_required_field_reports_error():
    program = build_valid_program()
    program.pages["home"].route = None  # missing required
    diags = validate_module(program)
    codes = {d.code for d in diags if d.severity == "error"}
    assert "N3-1001" in codes


def test_unknown_field_reports_warning():
    program = build_valid_program()
    program.pages["home"].extra = "unknown"
    diags = validate_module(program)
    assert any(d.code == "N3-1002" for d in diags)


def test_unknown_reference_emits_semantic_code():
    program = build_valid_program()
    program.pages["home"].ai_calls.append("missing")
    diags = validate_module(program)
    assert any(d.code == "N3-2001" for d in diags)


def test_adapter_preserves_structured_information():
    program = build_valid_program()
    program.pages["home"].route = None
    diags = validate_module(program)
    # Convert the first error diagnostic back to structured and check key fields.
    from namel3ss.diagnostics import legacy_to_structured

    error_diag = next(d for d in diags if d.code == "N3-1001")
    structured = legacy_to_structured(error_diag)
    assert structured.code == "N3-1001"
    assert structured.category == "lang-spec"
    assert structured.severity == "error"
