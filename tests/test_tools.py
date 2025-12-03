from namel3ss.tools.builtin import AddNumbersTool, EchoTool, register_builtin_tools
from namel3ss.tools.registry import ToolRegistry


def test_tool_registry_register_and_list():
    registry = ToolRegistry()
    register_builtin_tools(registry)
    assert "echo" in registry.list_names()
    assert "add_numbers" in registry.list_names()


def test_builtin_tools_run():
    echo = EchoTool()
    add = AddNumbersTool()
    assert echo.run(message="hi") == "echo:hi"
    assert add.run(a=2, b=3) == 5
