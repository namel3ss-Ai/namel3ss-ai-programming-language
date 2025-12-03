from namel3ss import ast_nodes
from namel3ss.parser import parse_source


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    '  route "/"\n'
    'page "ask":\n'
    '  title "Ask AI"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'agent "helper":\n'
    '  goal "Assist users"\n'
    '  personality "friendly"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
    '  input from user_message\n'
)


def test_parse_program_with_agent_and_ai_call_ref():
    module = parse_source(PROGRAM_TEXT)
    agent = next(d for d in module.declarations if isinstance(d, ast_nodes.AgentDecl))
    assert agent.name == "helper"
    assert agent.goal == "Assist users"
    page = next(
        d for d in module.declarations if isinstance(d, ast_nodes.PageDecl) and d.name == "ask"
    )
    assert len(page.ai_calls) == 1
    assert page.ai_calls[0].name == "summarise_message"
    assert page.agents[0].name == "helper"
    assert page.memories[0].name == "short_term"
    assert any(isinstance(d, ast_nodes.MemoryDecl) for d in module.declarations)
