"""
Helper utilities for common multi-agent orchestration patterns (router, supervisor/worker, debate).

These helpers sit on top of the existing AgentRunner/AgentTeamRunner so that flows
and Python callers can compose multi-agent behaviours without bespoke plumbing.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .engine import AgentRunner
from .teams import AgentTeamRunner


@dataclass
class RoutingDecision:
    target_agent: str
    reason: str | None = None
    payload: Any | None = None


@dataclass
class WorkerTask:
    agent_name: str
    description: str | None = None
    priority: int | None = None
    parallel: bool = False


@dataclass
class SupervisorOutcome:
    plan: Any
    worker_results: list[dict[str, Any]] = field(default_factory=list)
    synthesizer_result: Any | None = None


def _normalize_result(value: Any) -> dict[str, Any] | None:
    if isinstance(value, Exception):
        return {"ok": False, "value": None, "error": value, "raw": value}
    mapping: dict[str, Any] | None = None
    if isinstance(value, dict):
        mapping = value
    else:
        attrs: dict[str, Any] = {}
        for key in ("ok", "success", "error", "data", "result", "value", "final_answer", "final_output"):
            if hasattr(value, key):
                try:
                    attrs[key] = getattr(value, key)
                except Exception:
                    continue
        mapping = attrs or None
    if mapping is None:
        return None
    has_signal = any(k in mapping for k in ("ok", "success", "error", "data", "result", "value", "final_answer", "final_output"))
    if not has_signal:
        return None
    ok_val = mapping.get("ok", None)
    if ok_val is None and "success" in mapping:
        ok_val = mapping.get("success")
    error_val = mapping.get("error", None)
    payload = None
    for key in ("data", "result", "value", "final_answer", "final_output"):
        if key in mapping:
            payload = mapping.get(key)
            if payload is not None:
                break
    if ok_val is None and error_val is not None:
        ok_val = False
    if ok_val is None and payload is not None:
        ok_val = True
    if ok_val is None:
        return None
    return {"ok": bool(ok_val), "value": payload, "error": error_val, "raw": value}


def extract_routing_decision(result: Any, fallback_agent: str | None = None) -> RoutingDecision:
    normalized = _normalize_result(result) or {}
    value = normalized.get("value")
    target_agent = None
    reason = None
    payload = value
    if isinstance(value, dict):
        target_agent = value.get("target_agent") or value.get("route") or value.get("agent")
        reason = value.get("reason") or value.get("why")
    elif isinstance(value, str):
        target_agent = value
    if not target_agent:
        target_agent = fallback_agent or ""
    return RoutingDecision(target_agent=target_agent, reason=reason, payload=payload)


def route_and_run(router_agent: str, context, agent_runner: AgentRunner, *, fallback_agent: str | None = None):
    """
    Run a router agent, extract its routing decision, then invoke the chosen worker.
    Returns (decision, worker_result, router_result).
    """
    router_result = agent_runner.run(router_agent, context)
    decision = extract_routing_decision(router_result, fallback_agent=fallback_agent)
    worker_result = None
    if decision.target_agent:
        worker_result = agent_runner.run(decision.target_agent, context)
    return decision, worker_result, router_result


def _coerce_tasks(tasks: Any) -> list[WorkerTask]:
    if tasks is None:
        return []
    if isinstance(tasks, WorkerTask):
        return [tasks]
    if isinstance(tasks, Iterable) and not isinstance(tasks, (str, bytes, dict)):
        coerced: list[WorkerTask] = []
        for item in tasks:
            if isinstance(item, WorkerTask):
                coerced.append(item)
            elif isinstance(item, dict):
                coerced.append(
                    WorkerTask(
                        agent_name=item.get("agent_name") or item.get("agent") or item.get("name") or "",
                        description=item.get("description") or item.get("task"),
                        priority=item.get("priority"),
                        parallel=bool(item.get("parallel", False)),
                    )
                )
        return coerced
    if isinstance(tasks, dict):
        return _coerce_tasks(tasks.get("tasks"))
    return []


def run_supervisor_plan(
    planner_agent: str,
    context,
    agent_runner: AgentRunner,
    *,
    plan_value: Any | None = None,
    synthesizer_agent: str | None = None,
) -> SupervisorOutcome:
    """
    Execute a supervisor/worker pattern.
    - planner_agent produces a plan with tasks: [{agent_name, description, priority?, parallel?}]
    - each worker agent is executed sequentially (parallel flag is ignored for now)
    - optionally call a synthesizer agent with worker_results in context.metadata["worker_results"]
    """
    planner_result = plan_value
    if planner_result is None:
        planner_result = agent_runner.run(planner_agent, context)
    normalized = _normalize_result(planner_result) or {}
    plan_payload = normalized.get("value") if normalized else planner_result
    tasks = _coerce_tasks(plan_payload)
    worker_results: list[dict[str, Any]] = []
    for task in tasks:
        if not task.agent_name:
            continue
        if task.description and not getattr(context, "user_input", None):
            context.user_input = str(task.description)
        res = agent_runner.run(task.agent_name, context)
        worker_results.append({"task": asdict(task), "result": res})
    synth_result = None
    if synthesizer_agent:
        try:
            context.metadata = dict(getattr(context, "metadata", {}) or {})
            context.metadata["worker_results"] = [
                asdict(item["result"]) if hasattr(item["result"], "__dict__") else item["result"] for item in worker_results
            ]
        except Exception:
            pass
        synth_result = agent_runner.run(synthesizer_agent, context)
    return SupervisorOutcome(plan=plan_payload, worker_results=worker_results, synthesizer_result=synth_result)


def run_debate_pattern(
    question: str,
    pro_agent: str,
    con_agent: str,
    judge_agent: str | None,
    context,
    agent_runner: AgentRunner,
    team_runner: AgentTeamRunner | None = None,
):
    """
    Simple debate wrapper: run pro/con agents, optionally let a judge decide.
    Falls back to AgentTeamRunner.run_debate if provided.
    """
    if team_runner:
        try:
            return team_runner.run_debate(question, [pro_agent, con_agent], context)
        except Exception:
            # fall through to simple pattern
            pass
    original_input = getattr(context, "user_input", None)
    context.user_input = question
    pro_result = agent_runner.run(pro_agent, context)
    con_result = agent_runner.run(con_agent, context)
    judge_result = None
    if judge_agent:
        try:
            context.metadata = dict(getattr(context, "metadata", {}) or {})
            context.metadata["debate"] = {
                "question": question,
                "pro": getattr(pro_result, "final_answer", None),
                "con": getattr(con_result, "final_answer", None),
            }
        except Exception:
            pass
        judge_result = agent_runner.run(judge_agent, context)
    context.user_input = original_input
    return {
        "pro": pro_result,
        "con": con_result,
        "judge": judge_result,
    }
