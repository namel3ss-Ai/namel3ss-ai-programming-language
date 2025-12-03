from namel3ss.plugins.models import PluginInfo
from namel3ss.plugins.registry import PluginRegistry


def test_plugin_registry_lists_and_checks():
    plugins = [
        PluginInfo(name="stripe", description="payments"),
        PluginInfo(name="notion", description="notes", enabled=False),
    ]
    registry = PluginRegistry(plugins)
    assert registry.is_enabled("stripe") is True
    assert registry.is_enabled("notion") is False
    names = [p.name for p in registry.list_plugins()]
    assert "stripe" in names and "notion" in names
