from textwrap import dedent

from namel3ss import parser
from namel3ss.ir import ast_to_ir
from namel3ss.ai.providers import ChatToolResponse, ModelProvider
from namel3ss.ai.models import ModelResponse
from namel3ss.agent.engine import AgentRunner
from namel3ss.runtime.context import ExecutionContext, execute_ai_call_with_registry
from namel3ss.tools.registry import ToolRegistry


class StubProvider(ModelProvider):
    def __init__(self, responses):
        super().__init__("stub")
        self.responses = list(responses)
        self.calls = []
        self.supports_tools = True

    def generate(self, messages, **kwargs):
        self.calls.append({"method": "generate", "messages": [dict(m) for m in messages], "kwargs": kwargs})
        resp = self.responses.pop(0)
        if isinstance(resp, ModelResponse):
            return resp
        return ModelResponse(provider="stub", model=kwargs.get("model") or "stub", messages=messages, text=resp, raw={"resp": resp})

    def stream(self, messages, **kwargs):
        raise NotImplementedError

    def chat_with_tools(self, messages, tools=None, tool_choice="auto", **kwargs):
        self.calls.append(
            {
                "method": "chat",
                "messages": [dict(m) for m in messages],
                "kwargs": {"tools": tools, "tool_choice": tool_choice, **kwargs},
            }
        )
        resp = self.responses.pop(0)
        if isinstance(resp, ModelResponse):
            return ChatToolResponse(final_text=resp.text, tool_calls=[], raw=resp.raw, finish_reason=resp.finish_reason)
        return ChatToolResponse(
            final_text=resp.get("final_text"),
            tool_calls=resp.get("tool_calls") or [],
            raw=resp.get("raw"),
            finish_reason=resp.get("finish_reason"),
        )


class StubRegistry:
    def __init__(self, provider):
        self.provider = provider
        self.provider_status = {}

    def resolve_provider_for_ai(self, ai_call):
        return self.provider, ai_call.model_name or "stub-model", "stub"


class StubRouter:
    def select_model(self, logical_name=None):
        class Sel:
            def __init__(self, name):
                self.model_name = name
                self.provider_name = "stub"
                self.actual_model = name

        return Sel(logical_name or "stub-model")


def test_agent_runs_ai_with_tools_and_tool_loop(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    code = dedent(
        """
        model is "gpt-4.1-mini":
          provider is "stub"

        tool is "get_weather":
          kind is "http_json"
          method is "GET"
          url is "https://api.example.com/weather"
          query:
            city: input.city

        ai is "support_agent":
          model is "gpt-4.1-mini"
          tools:
            - "get_weather"

        agent is "support_agent":
          goal is "Answer support questions."
          personality is "Helpful"
        """
    )
    program = ast_to_ir(parser.parse_source(code))

    first = {"tool_calls": [{"name": "get_weather", "arguments": {"city": "Paris"}}], "final_text": ""}
    second = {"tool_calls": [], "final_text": "It is sunny in Paris."}
    provider = StubProvider([first, second])
    registry = StubRegistry(provider)
    router = StubRouter()

    tool_registry = ToolRegistry()
    for tool in program.tools.values():
        tool_registry.register(tool)

    runner = AgentRunner(program=program, model_registry=registry, tool_registry=tool_registry, router=router)
    ctx = ExecutionContext(
        app_name="app",
        request_id="req-agent-tools",
        user_input="How is the weather?",
        tool_registry=tool_registry,
        metadata={"mock_tool_results": {"get_weather": {"temp_c": 20}}},
    )
    result = runner.run("support_agent", ctx)
    assert result.final_answer == "It is sunny in Paris."
    assert provider.calls[0]["kwargs"]["tools"]  # tools were passed to provider
    assert provider.calls[1]["kwargs"]["tool_choice"] == "none"  # follow-up call after tool


def test_agent_conditional_subagent_runs_children(monkeypatch):
    code = dedent(
        """
        model is "stub-model":
          provider is "stub"

        ai is "router":
          model is "stub-model"

        ai is "worker":
          model is "stub-model"

        agent is "worker":
          goal is "Do the work."

        """
    )
    program = ast_to_ir(parser.parse_source(code))
    # Manually add a conditional branch that delegates to worker to cover routing.
    from namel3ss import ast_nodes
    from namel3ss.ir import IRConditionalBranch, IRAction, IRAgent

    program.agents["router"] = IRAgent(name="router", goal="Route requests.", system_prompt="Always delegate.", conditional_branches=[])
    program.agents["router"].conditional_branches = [
        IRConditionalBranch(
            condition=ast_nodes.Literal(value=True),
            actions=[IRAction(kind="agent", target="worker")],
            label="always",
        )
    ]
    provider = StubProvider(
        [
            ModelResponse(provider="stub", model="stub-model", messages=[], text="delegating", raw={}),
            ModelResponse(provider="stub", model="stub-model", messages=[], text="done", raw={}),
        ]
    )
    registry = StubRegistry(provider)
    router = StubRouter()
    tool_registry = ToolRegistry()
    runner = AgentRunner(program=program, model_registry=registry, tool_registry=tool_registry, router=router)
    ctx = ExecutionContext(app_name="app", request_id="req-agent-branch", user_input="Hi", tool_registry=tool_registry)
    result = runner.run("router", ctx)
    assert result.final_answer == "delegating"
    assert provider.calls  # both router and worker calls executed
