from namel3ss import ast_nodes
from namel3ss.tools.registry import ToolConfig, ToolRegistry, build_ai_tool_specs


def test_build_ai_tool_specs_with_placeholder():
    registry = ToolRegistry()
    registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_expr=ast_nodes.Literal(value="https://api.example.com/weather"),
            query_params={"city": ast_nodes.Identifier(name="input.city")},
            input_fields=["city"],
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


def test_build_ai_tool_specs_with_alias_object():
    registry = ToolRegistry()
    registry.register(
        ToolConfig(
            name="get_weather",
            kind="http_json",
            method="GET",
            url_expr=ast_nodes.Literal(value="https://api.example.com/weather"),
            query_params={"city": ast_nodes.Identifier(name="input.city")},
            input_fields=["city"],
        )
    )

    class Binding:
        internal_name = "get_weather"
        exposed_name = "weather_lookup"

    specs = build_ai_tool_specs([Binding()], registry)
    assert specs[0].name == "weather_lookup"
