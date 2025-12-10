from namel3ss.runtime.engine import Engine
from namel3ss.runtime.graph import NodeType


PROGRAM_TEXT = (
    'app is "support_portal":\n'
    '  entry_page is "home"\n'
    'page is "home":\n'
    '  title "Home"\n'
    '  ai_call "summarise_message"\n'
    '  agent "helper"\n'
    '  memory "short_term"\n'
    'model is "default":\n'
    '  provider is "openai:gpt-4.1-mini"\n'
    'ai is "summarise_message":\n'
    '  model is "default"\n'
    'agent is "helper":\n'
    '  goal "Assist"\n'
    'memory "short_term":\n'
    '  type "conversation"\n'
)


def test_graph_contains_ai_call_ref_and_edges():
    engine = Engine.from_source(PROGRAM_TEXT)
    graph = engine.graph
    assert any(node.type == NodeType.AI_CALL_REF for node in graph.nodes.values())
    assert any(edge.label == "ai_call" for edge in graph.edges)
    assert any(node.type == NodeType.AGENT for node in graph.nodes.values())
    assert any(node.type == NodeType.MEMORY for node in graph.nodes.values())
    assert any(edge.label == "agent" for edge in graph.edges)
    assert any(edge.label == "memory" for edge in graph.edges)
