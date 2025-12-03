from namel3ss.runtime.engine import Engine


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  description "Support portal for customer questions"\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    '  input from user_message\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_engine_run_returns_summary():
    engine = Engine.from_source(PROGRAM_TEXT)
    result = engine.run_app("support_portal")
    assert result["app"]["status"] == "ok"
    assert result["app"]["entry_page"] == "home"
    assert result["entry_page"]["status"] == "ok"
    assert result["entry_page"]["agents"]
    assert result["entry_page"]["memories"]
    assert result["entry_page"]["memory_items"]["short_term"]
    assert result["entry_page"]["agent_runs"]
    assert result["entry_page"]["ai_calls"]
    assert result["entry_page"]["ui"]
    assert any(edge["label"] == "entry_page" for edge in result["graph"]["edges"])
