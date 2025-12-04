import asyncio
from datetime import datetime

from namel3ss.optimizer.evaluator import OptimizerEvaluator
from namel3ss.optimizer.models import EvaluationCase, TargetType
from namel3ss.agent.engine import AgentRunner
from namel3ss.agent.plan import AgentExecutionPlan, AgentStep
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.ir import IRAgent, IRAiCall, IRFlow, IRFlowStep, IRModel, IRProgram
from namel3ss.runtime.context import ExecutionContext
from namel3ss.tools.registry import ToolRegistry
from namel3ss.flows.engine import FlowEngine


def build_flow_engine():
    program = IRProgram(
        flows={"demo": IRFlow(name="demo", description=None, steps=[IRFlowStep(name="noop", kind="tool", target="echo")])},
        agents={},
        models={},
    )
    registry = ModelRegistry()
    tools = ToolRegistry()

    class EchoTool:
        name = "echo"

        def run(self, **kwargs):
            return "ok"

    tools.register(EchoTool())
    router = ModelRouter(registry)
    agent_runner = AgentRunner(program, registry, tools, router)
    engine = FlowEngine(program, registry, tools, agent_runner, router)
    return engine, agent_runner


def test_evaluate_flow_runs_cases():
    flow_engine, agent_runner = build_flow_engine()
    evaluator = OptimizerEvaluator(flow_engine, agent_runner)
    cases = [EvaluationCase(id="c1", input={"foo": "bar"})]
    run = asyncio.run(evaluator.evaluate_flow("demo", cases))
    assert run.target_type == TargetType.FLOW
    assert run.metrics_summary["error_rate"] == 0
    assert len(run.raw_results) == 1


def test_evaluate_agent_scores():
    program = IRProgram(
        agents={"helper": IRAgent(name="helper")},
        ai_calls={"ask": IRAiCall(name="ask", model_name="model")},
        models={"model": IRModel(name="model", provider=None)},
    )
    registry = ModelRegistry()
    registry.register_model("model", provider_name=None)
    tools = ToolRegistry()
    router = ModelRouter(registry)
    runner = AgentRunner(program, registry, tools, router)
    evaluator = OptimizerEvaluator(None, runner)
    cases = [EvaluationCase(id="c1", input={}, expected={"goal": "test goal"})]
    run = asyncio.run(evaluator.evaluate_agent("helper", cases))
    assert run.target_type == TargetType.AGENT
    assert len(run.raw_results) == 1
