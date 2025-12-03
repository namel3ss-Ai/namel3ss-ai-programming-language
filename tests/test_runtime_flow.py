from namel3ss.runtime.engine import Engine


PROGRAM_TEXT = (
    'flow "pipeline":\n'
    '  step "classify":\n'
    '    kind "ai"\n'
    '    target "summarise_message"\n'
    '  step "delegate":\n'
    '    kind "agent"\n'
    '    target "helper"\n'
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
)


def test_execute_flow_returns_steps():
    engine = Engine.from_source(PROGRAM_TEXT)
    result = engine.execute_flow("pipeline")
    assert result["flow_name"] == "pipeline"
    assert result["steps"][0]["success"] is True
