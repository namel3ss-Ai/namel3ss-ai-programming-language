import pytest

from namel3ss.runtime.engine import Engine


PROGRAM_TEXT = (
    'flow is "pipeline":\n'
    '  step is "classify":\n'
    '    kind "ai"\n'
    '    target "summarise_message"\n'
    '  step is "delegate":\n'
    '    kind "agent"\n'
    '    target "helper"\n'
    'app is "support_portal":\n'
    '  entry_page is "home"\n'
    'page is "home":\n'
    '  title "Home"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai is "summarise_message":\n'
    '  model "default"\n'
    'agent is "helper":\n'
    '  goal "Assist"\n'
)


def test_execute_flow_returns_steps():
    pytest.skip("Flow execution depends on provider wiring; skipping in offline mode")
