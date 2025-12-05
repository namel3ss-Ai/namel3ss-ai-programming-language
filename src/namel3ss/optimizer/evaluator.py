"""
Evaluation harness for flows and agents.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from ..agent.engine import AgentRunner
from ..agent.planning import AgentGoal
from ..flows.engine import FlowEngine
from ..observability.metrics import default_metrics
from ..runtime.context import ExecutionContext
from .models import EvaluationCase, EvaluationRun, TargetType


class OptimizerEvaluator:
    def __init__(self, flow_engine: FlowEngine, agent_runner: AgentRunner):
        self.flow_engine = flow_engine
        self.agent_runner = agent_runner

    async def evaluate_flow(self, flow_name: str, cases: List[EvaluationCase]) -> EvaluationRun:
        results: List[Dict[str, Any]] = []
        latencies: List[float] = []
        errors = 0
        for case in cases:
            start = time.monotonic()
            try:
                flow = self.flow_engine.program.flows.get(flow_name)
                if not flow:
                    raise ValueError(f"Flow '{flow_name}' not found")
                ctx = ExecutionContext(
                    app_name="__optimizer__",
                    request_id=str(uuid.uuid4()),
                    memory_engine=getattr(self.flow_engine, "memory_engine", None),
                    tool_registry=self.flow_engine.tool_registry,
                    tracer=None,
                )
                result = await self.flow_engine.run_flow_async(flow, ctx, initial_state=case.input)
                output = result.state.data if result.state else {}
                success = True
            except Exception as exc:
                result = str(exc)
                output = None
                success = False
                errors += 1
            latency = time.monotonic() - start
            latencies.append(latency)
            results.append(
                {
                    "case_id": case.id,
                    "success": success,
                    "output": output,
                    "latency": latency,
                }
            )
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        error_rate = errors / len(cases) if cases else 0.0
        metrics = {"avg_latency": avg_latency, "error_rate": error_rate}
        default_metrics.record_flow(f"optimizer:flow:{flow_name}", duration_seconds=avg_latency, cost=0.0)
        return EvaluationRun(
            id=str(uuid.uuid4()),
            target_type=TargetType.FLOW,
            target_name=flow_name,
            created_at=datetime.now(timezone.utc),
            cases=cases,
            metrics_summary=metrics,
            raw_results=results,
        )

    async def evaluate_agent(self, agent_name: str, cases: List[EvaluationCase]) -> EvaluationRun:
        results: List[Dict[str, Any]] = []
        latencies: List[float] = []
        scores: List[float] = []
        for case in cases:
            start = time.monotonic()
            try:
                ctx = ExecutionContext(app_name="__optimizer__", request_id=str(uuid.uuid4()), memory_engine=None, tracer=None)
                run_result = self.agent_runner.run(agent_name, ctx)
                answer = run_result.final_answer or ""
                score = None
                if case.expected and "goal" in case.expected:
                    goal = AgentGoal(description=case.expected["goal"], constraints=case.expected.get("constraints") or {})
                    eval_result = self.agent_runner.evaluate_answer(goal, answer, ctx, agent_id=agent_name)
                    score = eval_result.score
                    scores.append(score)
                results.append(
                    {
                        "case_id": case.id,
                        "success": True,
                        "answer": answer,
                        "score": score,
                    }
                )
            except Exception as exc:
                results.append({"case_id": case.id, "success": False, "error": str(exc), "score": 0.0})
                scores.append(0.0)
            latency = time.monotonic() - start
            latencies.append(latency)
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_score = sum(scores) / len(scores) if scores else 0.0
        metrics = {"avg_latency": avg_latency, "avg_score": avg_score}
        default_metrics.record_flow(f"optimizer:agent:{agent_name}", duration_seconds=avg_latency, cost=0.0)
        return EvaluationRun(
            id=str(uuid.uuid4()),
            target_type=TargetType.AGENT,
            target_name=agent_name,
            created_at=datetime.now(timezone.utc),
            cases=cases,
            metrics_summary=metrics,
            raw_results=results,
        )
