"""
Agent execution engine with reflection, planning, and retries.
"""

from __future__ import annotations

from typing import Any, Optional

from .. import ast_nodes
from ..ai.registry import ModelRegistry
from ..errors import Namel3ssError
from ..ir import IRAgent, IRProgram
from ..observability.metrics import default_metrics
from ..observability.tracing import default_tracer
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..tools.registry import ToolRegistry
from .evaluation import AgentEvaluation, AgentEvaluator
from .evaluators import AgentStepEvaluator, DeterministicEvaluator, OpenAIEvaluator
from .models import AgentConfig
from .plan import AgentExecutionPlan, AgentPlanResult, AgentStep, AgentStepResult
from .planning import AgentGoal, AgentPlanner, AgentStepPlan
from .reflection import (
    ReflectionConfig,
    build_critique_prompt,
    build_improvement_prompt,
)


class AgentRunner:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        router,
        evaluator: Optional[AgentStepEvaluator] = None,
        config: Optional[AgentConfig] = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.router = router
        self.evaluator = evaluator or DeterministicEvaluator(max_retries=1)
        self.config = config or AgentConfig()
        self._planner = AgentPlanner(router=self.router, agent_config=self.config)
        self._evaluator = AgentEvaluator(router=self.router)

    def build_plan(self, agent: IRAgent, page_ai_fallback: Optional[str] = None) -> AgentExecutionPlan:
        steps: list[AgentStep] = []
        target_ai = page_ai_fallback or next(iter(self.program.ai_calls), None)
        if target_ai:
            steps.append(
                AgentStep(
                    id="call_model",
                    kind="ai",
                    target=target_ai,
                    description="Invoke AI call",
                    max_retries=1,
                )
            )
        if "echo" in self.tool_registry.list_names():
            steps.append(
                AgentStep(
                    id="echo_result",
                    kind="tool",
                    target="echo",
                    description="Echo last output",
                )
            )
        return AgentExecutionPlan(steps=steps, current_index=0, max_retries_per_step=1)

    def run(
        self,
        agent_name: str,
        context: ExecutionContext,
        page_ai_fallback: Optional[str] = None,
    ) -> AgentPlanResult:
        span_attrs = {"agent": agent_name, "app": getattr(context, "app_name", None)}
        with default_tracer.span("agent.run", attributes=span_attrs):
            if agent_name not in self.program.agents:
                raise Namel3ssError(f"Unknown agent '{agent_name}'")
            agent = self.program.agents[agent_name]
            plan = self.build_plan(agent, page_ai_fallback=page_ai_fallback)
            results: list[AgentStepResult] = []
            reflection_cfg = self.config.reflection if self.config else None

            if context.tracer:
                if not context.tracer.last_trace:
                    context.tracer.start_app(context.app_name or "unknown")
                context.tracer.start_agent(agent.name)

        # Allow OpenAI-backed evaluator when secrets configured.
        if isinstance(self.evaluator, DeterministicEvaluator) and context.secrets:
            if context.secrets.get("N3_OPENAI_API_KEY"):
                self.evaluator = OpenAIEvaluator(
                    registry=self.model_registry,
                    router=self.router,
                    secrets=context.secrets,
                )

        last_output: Optional[dict] = None
        stopped = False
        while True:
            if getattr(agent, "conditional_branches", None):
                cond_result = self._run_agent_conditions(agent, context)
                branch_label = cond_result.get("branch")
                branch_condition = cond_result.get("condition_text")
                summary = f"Agent {agent.name} ran conditional branch {branch_label}"
                if branch_condition:
                    summary = f"{summary} ({branch_condition})"
                result = AgentPlanResult(
                    agent_name=agent.name,
                    steps=cond_result.get("steps", []),
                    summary=summary,
                    final_output=cond_result.get("last_output"),
                    final_answer=self._stringify_answer(cond_result.get("last_output")),
                )
                if context.tracer:
                    context.tracer.end_agent(summary=summary)
                return result
            step = plan.next_step()
            if not step or stopped:
                break
            attempt = 0
            success = False
            output = None
            error: Optional[str] = None
            last_result: Optional[AgentStepResult] = None
            while attempt <= max(step.max_retries, plan.max_retries_per_step) and not stopped:
                try:
                    output = self._run_step(step, last_output, context)
                    success = True
                except Exception as exc:  # pragma: no cover - retry path
                    error = str(exc)
                    success = False
                result = AgentStepResult(
                    step_id=step.id,
                    input={"previous": last_output},
                    output=output if isinstance(output, dict) else {"value": output},
                    success=success,
                    error=error,
                    retries=attempt,
                )
                evaluation = self.evaluator.evaluate(result, context)
                result.evaluation = evaluation
                last_result = result
                if context.metrics:
                    context.metrics.record_evaluation()
                if context.tracer:
                    context.tracer.record_agent_step(
                        step_name=step.id,
                        kind=step.kind,
                        target=step.target,
                        success=success,
                        retries=attempt,
                        output_preview=str(output)[:200] if output is not None else None,
                        evaluation_score=evaluation.score,
                        verdict=evaluation.verdict,
                    )
                if context.tracer:
                    pass
                if evaluation.verdict == "accept":
                    break
                if evaluation.verdict == "retry" and attempt < max(step.max_retries, plan.max_retries_per_step):
                    attempt += 1
                    if context.metrics:
                        context.metrics.record_retry()
                    continue
                if evaluation.verdict in {"stop", "escalate"}:
                    stopped = True
                break
            if last_result:
                results.append(last_result)
            last_output = output
            if stopped:
                break

        summary = f"Agent {agent.name} finished {len(results)} steps."
        if stopped:
            summary = f"Agent {agent.name} halted after {len(results)} steps."
        if context.tracer:
            context.tracer.end_agent(summary=summary)
        if context.metrics:
            context.metrics.record_agent_run()
        if getattr(context, "trigger_manager", None):
            context.trigger_manager.notify_agent_signal(agent.name, {"summary": summary})
        result = AgentPlanResult(
            agent_name=agent.name,
            steps=results,
            summary=summary,
            final_output=last_output,
            final_answer=self._stringify_answer(last_output),
        )
        result = self._apply_reflection(agent, context, result, reflection_cfg)
        default_metrics.record_flow(f"agent:{agent_name}", duration_seconds=len(results), cost=0.0)
        return result

    def plan(self, goal: AgentGoal, context: ExecutionContext, agent_id: Optional[str] = None) -> AgentStepPlan:
        agent_identifier = agent_id or goal.description
        return self._planner.plan(goal, context, agent_identifier)

    def evaluate_answer(
        self, goal: AgentGoal, answer: str, context: ExecutionContext, agent_id: Optional[str] = None
    ) -> AgentEvaluation:
        agent_identifier = agent_id or goal.description
        return self._evaluator.evaluate_answer(goal, answer, context, agent_identifier)

    def _apply_reflection(
        self,
        agent: IRAgent,
        context: ExecutionContext,
        result: AgentPlanResult,
        config: Optional[ReflectionConfig],
    ) -> AgentPlanResult:
        if not config or not config.enabled:
            return result
        rounds = max(config.max_rounds, 0)
        answer_text = result.final_answer or ""
        request_text = context.user_input or agent.goal or ""
        executed_rounds = 0

        self._record_memory_event(context, agent.name, "agent_initial_answer", answer_text, round_idx=None)
        if rounds == 0:
            result.reflection_rounds = 0
            result.final_output = answer_text
            result.final_answer = answer_text
            return result

        for idx in range(rounds):
            critique_prompt = build_critique_prompt(request_text, answer_text, config)
            critique_resp = self._invoke_reflection_call(critique_prompt, context)
            critique_text = self._extract_response_text(critique_resp)
            result.critiques.append(critique_text)
            self._record_memory_event(context, agent.name, "agent_critique", critique_text, round_idx=idx)

            improvement_prompt = build_improvement_prompt(request_text, answer_text, critique_text, config)
            improvement_resp = self._invoke_reflection_call(improvement_prompt, context)
            improvement_text = self._extract_response_text(improvement_resp)
            result.improvements.append(improvement_text)
            self._record_memory_event(context, agent.name, "agent_improved_answer", improvement_text, round_idx=idx)

            answer_text = improvement_text
            executed_rounds += 1

        result.final_output = answer_text
        result.final_answer = answer_text
        result.reflection_rounds = executed_rounds
        return result

    def _invoke_reflection_call(self, prompt: str, context: ExecutionContext):
        response = self.router.generate(messages=[{"role": "user", "content": prompt}])
        self._record_metrics_for_response(response, context)
        if context.tracer:
            context.tracer.record_ai(
                model_name="reflection",
                prompt=prompt,
                response_preview=self._extract_response_text(response),
                provider_name=getattr(response, "provider", None),
                logical_model_name="reflection",
            )
        return response

    def _record_metrics_for_response(self, response: Any, context: ExecutionContext) -> None:
        if not context.metrics:
            return
        provider = getattr(response, "provider", None) or "reflection"
        cost = getattr(response, "cost", None) or 0.0
        context.metrics.record_ai_call(provider=provider, cost=cost, tokens_in=0, tokens_out=0)

    def _record_memory_event(
        self,
        context: ExecutionContext,
        agent_name: str,
        event_type: str,
        content: str,
        round_idx: Optional[int],
    ) -> None:
        memory_engine = getattr(context, "memory_engine", None)
        if not memory_engine:
            return
        segments = [event_type]
        if round_idx is not None:
            segments.append(f"round={round_idx}")
        message = " | ".join(segments)
        if content:
            message = f"{message} | {content}"
        try:
            memory_engine.record_conversation(agent_name, message, role="system")
        except Exception:
            # Memory hooks should never break agent execution.
            pass

    def _extract_response_text(self, response: Any) -> str:
        if response is None:
            return ""
        if hasattr(response, "text"):
            try:
                return str(response.text)
            except Exception:
                return str(response)
        if isinstance(response, dict):
            if response.get("text") is not None:
                return str(response["text"])
            if response.get("result") is not None:
                return str(response["result"])
        if hasattr(response, "get"):
            candidate = response.get("result")
            if candidate is not None:
                return str(candidate)
        return str(response)

    def _stringify_answer(self, answer: Any) -> Optional[str]:
        if answer is None:
            return None
        if isinstance(answer, dict):
            provider_result = answer.get("provider_result")
            if provider_result is not None:
                extracted = self._extract_response_text(provider_result)
                if extracted:
                    return extracted
            if "value" in answer:
                return str(answer["value"])
        return str(answer)

    def _run_step(self, step: AgentStep, last_output: Optional[dict], context: ExecutionContext):
        if step.kind == "tool":
            tool = self.tool_registry.get(step.target)
            if not tool:
                raise Namel3ssError(f"Tool '{step.target}' not found")
            result = tool.run(message=str(last_output) if last_output else "", **step.config)
            if context.metrics:
                context.metrics.record_tool_call(provider=step.target, cost=0.0005)
            return result
        if step.kind == "ai":
            if step.target not in self.program.ai_calls:
                raise Namel3ssError(f"AI call '{step.target}' not found")
            ai_call = self.program.ai_calls[step.target]
            return execute_ai_call_with_registry(ai_call, self.model_registry, self.router, context)
        if step.kind == "subagent":
            if step.target not in self.program.agents:
                raise Namel3ssError(f"Sub-agent '{step.target}' not found")
            return {"subagent": step.target}
        raise Namel3ssError(f"Unsupported step kind '{step.kind}'")

    # ---------- Conditional execution for agents ----------
    def _expr_to_str(self, expr: ast_nodes.Expr | None) -> str:
        if expr is None:
            return "<otherwise>"
        if isinstance(expr, ast_nodes.Identifier):
            return expr.name
        if isinstance(expr, ast_nodes.Literal):
            return repr(expr.value)
        if isinstance(expr, ast_nodes.UnaryOp):
            return f"{expr.op} {self._expr_to_str(expr.operand)}"
        if isinstance(expr, ast_nodes.BinaryOp):
            return f"{self._expr_to_str(expr.left)} {expr.op} {self._expr_to_str(expr.right)}"
        if isinstance(expr, ast_nodes.PatternExpr):
            pairs = ", ".join(f"{p.key}: {self._expr_to_str(p.value)}" for p in expr.pairs)
            return f"{expr.subject.name} matches {{{pairs}}}"
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            if expr.condition_name:
                return f"{expr.group_name}.{expr.condition_name}"
            return expr.group_name
        return str(expr)

    def _resolve_identifier(self, name: str, context: ExecutionContext) -> Any:
        parts = name.split(".")
        current: Any = None
        meta = getattr(context, "metadata", None) or {}
        if parts[0] in meta:
            current = meta.get(parts[0])
        elif hasattr(context, parts[0]):
            current = getattr(context, parts[0], None)
        for part in parts[1:]:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
        return current

    def _eval_rulegroup(self, expr: ast_nodes.RuleGroupRefExpr, context: ExecutionContext) -> tuple[bool, Any]:
        groups = getattr(self.program, "rulegroups", {}) if self.program else {}
        rules = groups.get(expr.group_name) or {}
        tracer = context.tracer
        if expr.condition_name:
            rule_expr = rules.get(expr.condition_name)
            if rule_expr is None:
                return False, None
            result = bool(self._eval_expr(rule_expr, context))
            if tracer:
                tracer.record_agent_condition_eval(
                    agent_name=getattr(context, "agent_name", ""),
                    condition=f"{expr.group_name}.{expr.condition_name}",
                    result=result,
                    branch_label=None,
                    macro=None,
                    pattern=None,
                    binding=None,
                    event="agent.condition.rulegroup.eval",
                )
            return result, result
        results_map: dict[str, bool] = {}
        all_true = True
        for name, rule_expr in rules.items():
            val = bool(self._eval_expr(rule_expr, context))
            results_map[name] = val
            if not val:
                all_true = False
        if tracer:
            tracer.record_agent_condition_eval(
                agent_name=getattr(context, "agent_name", ""),
                condition=expr.group_name,
                result=all_true,
                branch_label=None,
                macro=None,
                pattern=None,
                binding=None,
                results=results_map,
                event="agent.condition.rulegroup.eval",
            )
        return all_true, all_true

    def _eval_expr(self, expr: ast_nodes.Expr, context: ExecutionContext) -> Any:
        if isinstance(expr, ast_nodes.Literal):
            return expr.value
        if isinstance(expr, ast_nodes.Identifier):
            return self._resolve_identifier(expr.name, context)
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            res, _ = self._eval_rulegroup(expr, context)
            return res
        if isinstance(expr, ast_nodes.UnaryOp):
            val = self._eval_expr(expr.operand, context) if expr.operand else None
            if expr.op == "not":
                return not bool(val)
            raise Namel3ssError(f"Unsupported unary operator '{expr.op}'")
        if isinstance(expr, ast_nodes.BinaryOp):
            left = self._eval_expr(expr.left, context) if expr.left else None
            right = self._eval_expr(expr.right, context) if expr.right else None
            try:
                if expr.op == "and":
                    return bool(left) and bool(right)
                if expr.op == "or":
                    return bool(left) or bool(right)
                if expr.op == "is":
                    return left == right
                if expr.op == "is not":
                    return left != right
                if expr.op == "<":
                    return left < right
                if expr.op == ">":
                    return left > right
                if expr.op == "<=":
                    return left <= right
                if expr.op == ">=":
                    return left >= right
            except Exception:
                return False
            raise Namel3ssError(f"Unsupported operator '{expr.op}'")
        raise Namel3ssError("Unsupported expression")

    def _match_pattern(self, pattern: ast_nodes.PatternExpr, context: ExecutionContext) -> tuple[bool, Any]:
        subject = self._resolve_identifier(pattern.subject.name, context)
        if not isinstance(subject, dict):
            return False, None
        for pair in pattern.pairs:
            subject_val = subject.get(pair.key)
            val_expr = pair.value
            if isinstance(val_expr, ast_nodes.BinaryOp) and isinstance(val_expr.left, ast_nodes.Identifier):
                left_val = subject_val if val_expr.left.name == pair.key else self._eval_expr(val_expr.left, context)
                right_val = self._eval_expr(val_expr.right, context) if val_expr.right else None
                op = val_expr.op
                try:
                    if op == "and":
                        if not (bool(left_val) and bool(right_val)):
                            return False, None
                    elif op == "or":
                        if not (bool(left_val) or bool(right_val)):
                            return False, None
                    elif op == "is":
                        if left_val != right_val:
                            return False, None
                    elif op == "is not":
                        if left_val == right_val:
                            return False, None
                    elif op == "<":
                        if not (left_val < right_val):
                            return False, None
                    elif op == ">":
                        if not (left_val > right_val):
                            return False, None
                    elif op == "<=":
                        if not (left_val <= right_val):
                            return False, None
                    elif op == ">=":
                        if not (left_val >= right_val):
                            return False, None
                except Exception:
                    return False, None
                continue
            expected = self._eval_expr(val_expr, context)
            if subject_val != expected:
                return False, None
        return True, subject

    def _eval_condition_with_binding(self, expr: ast_nodes.Expr | None, context: ExecutionContext) -> tuple[bool, Any]:
        if expr is None:
            return True, None
        if isinstance(expr, ast_nodes.PatternExpr):
            return self._match_pattern(expr, context)
        if isinstance(expr, ast_nodes.RuleGroupRefExpr):
            return self._eval_rulegroup(expr, context)
        if isinstance(expr, ast_nodes.BinaryOp):
            left = self._eval_expr(expr.left, context) if expr.left else None
            right = self._eval_expr(expr.right, context) if expr.right else None
            result = False
            try:
                if expr.op == "and":
                    result = bool(left) and bool(right)
                elif expr.op == "or":
                    result = bool(left) or bool(right)
                elif expr.op == "is":
                    result = left == right
                elif expr.op == "is not":
                    result = left != right
                elif expr.op == "<":
                    result = left < right
                elif expr.op == ">":
                    result = left > right
                elif expr.op == "<=":
                    result = left <= right
                elif expr.op == ">=":
                    result = left >= right
            except Exception:
                result = False
            return result, right
        if isinstance(expr, ast_nodes.UnaryOp) and expr.op == "not":
            val = self._eval_expr(expr.operand, context) if expr.operand else None
            return (not bool(val)), not bool(val)
        value = self._eval_expr(expr, context)
        return bool(value), value

    def _run_agent_conditions(self, agent: IRAgent, context: ExecutionContext) -> dict:
        branches = agent.conditional_branches or []
        selected = None
        selected_label = None
        selected_expr_display = None
        binding_value = None
        binding_name = None
        for idx, br in enumerate(branches):
            cond = br.condition
            result, candidate_binding = self._eval_condition_with_binding(cond, context)
            expr_display = self._expr_to_str(cond)
            if br.label == "unless":
                result = not result
                expr_display = f"unless {expr_display}"
            if context.tracer:
                event_name = "agent.condition.pattern.eval" if isinstance(cond, ast_nodes.PatternExpr) else "agent.condition.eval"
                context.tracer.record_agent_condition_eval(
                    agent_name=agent.name,
                    condition=expr_display,
                    result=result,
                    branch_label=br.label or f"branch-{idx}",
                    binding={"name": getattr(br, "binding", None), "value": candidate_binding} if result and getattr(br, "binding", None) else None,
                    pattern={"subject": cond.subject.name, "pattern": {p.key: self._expr_to_str(p.value) for p in cond.pairs}} if isinstance(cond, ast_nodes.PatternExpr) else None,
                    macro=getattr(br, "macro_origin", None),
                    event=event_name,
                )
            if result:
                selected = br
                selected_label = br.label or f"branch-{idx}"
                selected_expr_display = expr_display
                binding_name = getattr(br, "binding", None)
                binding_value = candidate_binding
                break
        if selected is None:
            return {"branch": "none", "steps": [], "last_output": None, "condition_text": None}

        steps_results: list[AgentStepResult] = []
        last_output = None
        cond_text = selected_expr_display or (self._expr_to_str(selected.condition) if selected and selected.condition else None)
        previous_binding = None
        had_prev = False
        if binding_name:
            if binding_name in context.metadata:
                had_prev = True
                previous_binding = context.metadata.get(binding_name)
            context.metadata[binding_name] = binding_value
        for action in selected.actions:
            step = AgentStep(kind=action.kind if action.kind != "agent" else "subagent", target=action.target)
            output = self._run_step(step, last_output if isinstance(last_output, dict) else None, context)
            steps_results.append(
                AgentStepResult(
                    step_id=step.id,
                    input={"previous": last_output},
                    output=output if isinstance(output, dict) else {"value": output},
                    success=True,
                    error=None,
                )
            )
            last_output = output
        if binding_name:
            if had_prev:
                context.metadata[binding_name] = previous_binding
            else:
                context.metadata.pop(binding_name, None)
        return {
            "branch": selected_label,
            "steps": steps_results,
            "last_output": last_output,
            "condition_text": cond_text,
        }
