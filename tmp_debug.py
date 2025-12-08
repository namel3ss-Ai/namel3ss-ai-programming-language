import sys
sys.path.insert(0, "src")
from namel3ss import ast_nodes
from namel3ss.ir import IRFlow, IRFlowStep, IRFrame, IRModel, IRProgram, IRRecord, IRRecordField, IRAgent
from namel3ss.flows.engine import FlowEngine
from namel3ss.agent.engine import AgentRunner
from namel3ss.ai.registry import ModelRegistry
from namel3ss.ai.router import ModelRouter
from namel3ss.tools.registry import ToolRegistry
from namel3ss.metrics.tracker import MetricsTracker
from namel3ss.runtime.context import ExecutionContext

record = IRRecord(
    name="Document",
    frame="documents",
    fields={
        "id": IRRecordField(name="id", type="uuid", primary_key=True, required=True),
        "project_id": IRRecordField(name="project_id", type="string", required=True),
        "title": IRRecordField(name="title", type="string", required=True),
    },
    primary_key="id",
)
flow = IRFlow(
    name="crud",
    description=None,
    steps=[
        IRFlowStep(
            name="create",
            kind="db_create",
            target="Document",
            params={
                "values": {
                    "id": ast_nodes.Literal(value="doc-1"),
                    "project_id": ast_nodes.Literal(value="proj-1"),
                    "title": ast_nodes.Literal(value="Doc 1"),
                }
            },
        )
    ],
)
program = IRProgram(
    models={"default": IRModel(name="default")},
    agents={"helper": IRAgent(name="helper")},
    frames={"documents": IRFrame(name="documents", backend="memory", table="documents")},
    records={"Document": record},
)
registry = ModelRegistry()
registry.register_model("default", provider_name=None)
router = ModelRouter(registry)
tool_registry = ToolRegistry()
agent_runner = AgentRunner(program, registry, tool_registry, router)
metrics = MetricsTracker()
engine = FlowEngine(program, registry, tool_registry, agent_runner, router, metrics=metrics)
exec_ctx = ExecutionContext(app_name="test", request_id="req", tracer=None, tool_registry=tool_registry, metrics=metrics)
runtime_ctx = engine._build_runtime_context(exec_ctx)
result = engine.run_flow(flow, runtime_ctx.execution_context, initial_state={})
print("data keys", result.state.data.keys())
print("last_output", result.state.get("last_output"))
print("step output", result.state.get("step.create.output"))
