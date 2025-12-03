import tempfile
from pathlib import Path

from namel3ss.plugins.registry import PluginRegistry
from namel3ss.plugins.sdk import PluginSDK
from namel3ss.runtime.engine import Engine
from namel3ss.ir import IRProgram, IRFlow, IRFlowStep
from namel3ss.ai.router import ModelRouter
from namel3ss.ai.registry import ModelRegistry


PLUGIN_TOML = """
id = "toolkit"
name = "Toolkit"
version = "0.1.0"
description = "demo"
author = "dev"
n3_core_version = ">=3.0.0,<4.0.0"

[entrypoints]
tools = "toolkit:register_tools"
"""

PLUGIN_CODE = """
def register_tools(sdk):
    def plus(**kwargs):
        return 42
    sdk.tools.register_tool("plugin_plus", plus, plugin_id="toolkit")
"""


def _build_engine():
    program = IRProgram(
        flows={
            "use_plugin": IRFlow(
                name="use_plugin",
                description=None,
                steps=[IRFlowStep(name="add", kind="tool", target="plugin_plus")],
            )
        }
    )
    model_registry = ModelRegistry()
    return Engine(program, metrics_tracker=None, trigger_manager=None)


def test_discover_and_load_registers_tool():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        plugin_dir = root / "toolkit"
        plugin_dir.mkdir()
        (plugin_dir / "plugin.toml").write_text(PLUGIN_TOML, encoding="utf-8")
        (plugin_dir / "toolkit.py").write_text(PLUGIN_CODE, encoding="utf-8")
        registry = PluginRegistry(root)
        engine = _build_engine()
        sdk = PluginSDK.from_engine(engine)
        info = registry.load("toolkit", sdk)  # triggers discover implicitly
        assert info.loaded is True
        tool = engine.tool_registry.get("plugin_plus")
        assert tool is not None
        # Flow using plugin tool runs
        ctx = engine._build_default_execution_context()
        result = engine.flow_engine.run_flow(engine.program.flows["use_plugin"], ctx)
        assert result.steps[0].success is True
