from pathlib import Path

from namel3ss.runtime.engine import Engine
from namel3ss.plugins.registry import PluginRegistry
from namel3ss.plugins.sdk import PluginSDK
from namel3ss.ir import IRProgram


def test_default_tools_plugin_registers_tools():
    plugins_dir = Path("plugins")
    registry = PluginRegistry(plugins_dir)
    program = IRProgram()
    engine = Engine(program, plugin_registry=registry)
    assert "get_time" in engine.tool_registry.tools
    assert "math_eval" in engine.tool_registry.tools


def test_default_rag_plugin_registers_index():
    registry = PluginRegistry(Path("plugins"))
    engine = Engine(IRProgram(), plugin_registry=registry)
    assert "default-rag" in engine.rag_engine.index_registry


def test_default_agents_plugin_registers_agent():
    registry = PluginRegistry(Path("plugins"))
    engine = Engine(IRProgram(), plugin_registry=registry)
    assert "summarizer" in engine.program.agents
