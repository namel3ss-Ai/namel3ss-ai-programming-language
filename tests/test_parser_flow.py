from namel3ss import ast_nodes
from namel3ss.parser import parse_source


PROGRAM_TEXT = (
    'flow "support_pipeline":\n'
    '  description "Handle support"\n'
    '  step "classify":\n'
    '    kind "ai"\n'
    '    target "classify_ticket"\n'
    '  step "assign_helper":\n'
    '    kind "agent"\n'
    '    target "helper"\n'
)


def test_parse_flow_and_steps():
    module = parse_source(PROGRAM_TEXT)
    flow = next(d for d in module.declarations if isinstance(d, ast_nodes.FlowDecl))
    assert flow.name == "support_pipeline"
    assert flow.description == "Handle support"
    assert len(flow.steps) == 2
    assert flow.steps[0].kind == "ai"
    assert flow.steps[1].target == "helper"


def test_parse_page_sections_and_components():
    module = parse_source(
        'page "home":\n'
        '  section "hero":\n'
        '    component "text":\n'
        '      value "Welcome"\n'
        '      variant "heading"\n'
    )
    page = next(d for d in module.declarations if isinstance(d, ast_nodes.PageDecl))
    assert page.sections[0].name == "hero"
    assert page.sections[0].components[0].type == "text"
    assert page.sections[0].components[0].props[0].key == "value"


def test_parse_plugin_decl():
    module = parse_source(
        'plugin "stripe":\n'
        '  description "Payments"\n'
    )
    plugin = next(d for d in module.declarations if isinstance(d, ast_nodes.PluginDecl))
    assert plugin.name == "stripe"
    assert plugin.description == "Payments"
