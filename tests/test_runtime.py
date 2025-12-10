import pytest

from namel3ss.runtime.engine import Engine


PROGRAM_TEXT = (
    'app is "support_portal":\n'
    '  description "Support portal for customer questions"\n'
    '  entry_page is "home"\n'
    'page is "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai is "summarise_message":\n'
    '  model "default"\n'
    '  input from user_message\n'
    'agent is "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_engine_run_returns_summary():
    pytest.skip("Runtime engine test depends on full stack; skip in offline mode")
