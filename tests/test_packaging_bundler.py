from namel3ss.packaging.bundler import Bundler
from namel3ss.parser import parse_source
from namel3ss import ir


PROGRAM_TEXT = (
    'app "support_portal":\n'
    '  entry_page "home"\n'
    'page "home":\n'
    '  title "Home"\n'
    'flow "pipeline":\n'
    '  step "call":\n'
    '    kind "ai"\n'
    '    target "summarise_message"\n'
    'agent "helper":\n'
    '  goal "Assist"\n'
    'plugin "stripe":\n'
    '  description "payments"\n'
    'model "default":\n'
    '  provider "openai:gpt-4.1-mini"\n'
    'ai "summarise_message":\n'
    '  model "default"\n'
)


def test_bundler_from_ir_collects_entities():
    module = parse_source(PROGRAM_TEXT)
    program = ir.ast_to_ir(module)
    bundler = Bundler()
    bundle = bundler.from_ir(program)
    assert bundle.app_name == "support_portal"
    assert "home" in bundle.pages
    assert "pipeline" in bundle.flows
    assert "helper" in bundle.agents
    assert "stripe" in bundle.plugins
    assert "default" in bundle.models
    assert "version" in bundle.metadata
