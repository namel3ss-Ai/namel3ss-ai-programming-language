from namel3ss.runtime.engine import Engine


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    '  ai_call "summarise_message"\n'
    '  section "hero":\n'
    '    component "text":\n'
    '      value "Welcome"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
)


def test_ui_trace_has_section_count():
    engine = Engine.from_source(PROGRAM_TEXT)
    result = engine.run_app("support_portal", include_trace=True)
    assert result["trace"]
    page_trace = result["trace"]["pages"][0]
    assert page_trace["ui_section_count"] == 1
    assert page_trace["ai_calls"][0]["provider_name"] is not None
