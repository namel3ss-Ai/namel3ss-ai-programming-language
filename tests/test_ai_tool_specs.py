from namel3ss.tools.registry import ToolConfig, ToolRegistry, build_ai_tool_specs


def test_build_ai_tool_specs_with_placeholder():
    registry = ToolRegistry()
    registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_template="https://api.example.com/weather?city={city}",
            headers={},
        )
    )
    specs = build_ai_tool_specs(["get_weather"], registry)
    assert len(specs) == 1
    spec = specs[0]
    assert spec.name == "get_weather"
    assert spec.parameters["type"] == "object"
    assert "city" in spec.parameters["properties"]
    assert spec.parameters["properties"]["city"]["type"] == "string"
    assert "city" in spec.parameters["required"]


def test_build_ai_tool_specs_unknown_tool():
    registry = ToolRegistry()
    try:
        build_ai_tool_specs(["unknown"], registry)
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "unknown" in str(exc)
