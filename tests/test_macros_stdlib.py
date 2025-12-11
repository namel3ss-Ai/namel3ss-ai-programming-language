from namel3ss import ast_nodes
from namel3ss.macros import MacroExpander


def _expand_single_macro(name: str, args: dict | None = None):
    expander = MacroExpander(None)
    module = ast_nodes.Module(declarations=[ast_nodes.MacroUse(macro_name=name, args=args or {})])
    return expander.expand_module(module)


def test_auth_ui_macro_expands_defaults():
    expanded = _expand_single_macro("auth_ui")
    names = [getattr(d, "name", None) for d in expanded.declarations if getattr(d, "name", None)]
    assert "User" in names
    assert any("login" in n for n in names)
    assert any("authenticate" in n.lower() for n in names)


def test_api_endpoints_macro_emits_crud_flows():
    expanded = _expand_single_macro("api_endpoints", {"record": "Widget"})
    flow_names = [d.name for d in expanded.declarations if isinstance(d, ast_nodes.FlowDecl)]
    assert "list_widgets" in flow_names
    assert "get_widget" in flow_names
    assert "create_widget" in flow_names
    assert "update_widget" in flow_names
    assert "delete_widget" in flow_names


def test_analytics_dashboard_macro_includes_rag_and_agent():
    expanded = _expand_single_macro("analytics_dashboard", {"record": "Metric"})
    rag_names = [d.name for d in expanded.declarations if isinstance(d, ast_nodes.RagPipelineDecl)]
    agent_names = [d.name for d in expanded.declarations if isinstance(d, ast_nodes.AgentDecl)]
    assert rag_names
    assert agent_names
