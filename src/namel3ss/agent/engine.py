"""
Agent execution engine with reflection, planning, and retries.
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .. import ast_nodes
from ..ai.registry import ModelRegistry
from ..errors import Namel3ssError
from ..ir import (
    IRAction,
    IRAskUser,
    IRCheckpoint,
    IRAgent,
    IRForEach,
    IRForm,
    IRIf,
    IRLet,
    IRLog,
    IRMatch,
    IRMatchBranch,
    IRNote,
    IRProgram,
    IRRepeatUpTo,
    IRRetry,
    IRReturn,
    IRSet,
    IRStatement,
)
from ..observability.metrics import default_metrics
from ..observability.tracing import default_tracer
from ..runtime.context import ExecutionContext, execute_ai_call_with_registry
from ..runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment
from ..runtime.frames import FrameRegistry
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
        self.frame_registry = FrameRegistry(program.frames if program else {})

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

    def _resolve_identifier(self, name: str, context: ExecutionContext) -> tuple[bool, Any]:
        env = getattr(context, "_env", None)
        if env and env.has(name):
            return True, env.resolve(name)
        if env and "." in name:
            parts = name.split(".")
            if env.has(parts[0]):
                value: Any = env.resolve(parts[0])
                for part in parts[1:]:
                    if isinstance(value, dict) and part in value:
                        value = value.get(part)
                    elif hasattr(value, part):
                        value = getattr(value, part, None)
                    else:
                        return False, None
                return True, value
        parts = name.split(".")
        current: Any = None
        meta = getattr(context, "metadata", None) or {}
        if parts[0] in meta:
            current = meta.get(parts[0])
        elif hasattr(context, parts[0]):
            current = getattr(context, parts[0], None)
        elif parts[0] in getattr(context, "variables", {}):
            current = context.variables.get(parts[0])
        elif self.frame_registry and parts[0] in getattr(self.frame_registry, "frames", {}):
            current = self.frame_registry.get_rows(parts[0])
        else:
            return False, None
        for part in parts[1:]:
            if isinstance(current, dict) and part in current:
                current = current.get(part)
            elif hasattr(current, part):
                current = getattr(current, part, None)
            else:
                return False, None
        return True, current

    def _call_helper(self, name: str, args: list[Any], context: ExecutionContext) -> Any:
        helper = self.program.helpers.get(name) if self.program else None
        if not helper:
            raise Namel3ssError(f"N3-6000: unknown helper '{name}'")
        if len(args) != len(helper.params):
            raise Namel3ssError("N3-6001: wrong number of arguments for helper")
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        env = env.clone()
        saved_env = getattr(context, "_env", None)
        for param, arg in zip(helper.params, args):
            if env.has(param):
                env.assign(param, arg)
            else:
                env.declare(param, arg)
            context.metadata[param] = arg
        context._env = env
        context.variables = env.values
        evaluator = self._build_evaluator(context)
        try:
            for stmt in helper.body:
                if isinstance(stmt, IRLet):
                    val = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                    env.declare(stmt.name, val)
                    context.metadata[stmt.name] = val
                    context.variables = env.values
                elif isinstance(stmt, IRSet):
                    if not env.has(stmt.name):
                        raise Namel3ssError(f"Variable '{stmt.name}' is not defined")
                    val = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                    env.assign(stmt.name, val)
                    context.metadata[stmt.name] = val
                    context.variables = env.values
                elif isinstance(stmt, IRReturn):
                    return evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
                else:
                    raise Namel3ssError("Helper bodies support let/set/return statements in this phase")
        finally:
            context._env = saved_env
        return None

    def _is_error_result(self, value: Any) -> bool:
        if isinstance(value, Exception):
            return True
        if isinstance(value, dict):
            if value.get("error") is not None:
                return True
            if "success" in value and value.get("success") is False:
                return True
        return False

    def _extract_success_payload(self, value: Any) -> Any:
        if isinstance(value, dict):
            if "result" in value:
                return value.get("result")
            if "value" in value:
                return value.get("value")
        return value

    def _extract_error_payload(self, value: Any) -> Any:
        if isinstance(value, dict) and "error" in value:
            return value.get("error")
        return value

    def _match_branch(self, br: IRMatchBranch, target_val: Any, evaluator: ExpressionEvaluator, context: ExecutionContext) -> bool:
        pattern = br.pattern
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        if isinstance(pattern, ast_nodes.SuccessPattern):
            if self._is_error_result(target_val):
                return False
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, self._extract_success_payload(target_val))
                else:
                    env.declare(pattern.binding, self._extract_success_payload(target_val))
                context.metadata[pattern.binding] = self._extract_success_payload(target_val)
            return True
        if isinstance(pattern, ast_nodes.ErrorPattern):
            if not self._is_error_result(target_val):
                return False
            if pattern.binding:
                if env.has(pattern.binding):
                    env.assign(pattern.binding, self._extract_error_payload(target_val))
                else:
                    env.declare(pattern.binding, self._extract_error_payload(target_val))
                context.metadata[pattern.binding] = self._extract_error_payload(target_val)
            return True
        if pattern is None:
            return True
        try:
            pat_val = evaluator.evaluate(pattern)
        except Exception as exc:
            raise Namel3ssError(str(exc))
        if isinstance(pat_val, bool):
            return bool(pat_val)
        return target_val == pat_val

    def _resolve_provided_input(self, name: str, context: ExecutionContext) -> Any:
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        if env.has(name):
            try:
                return env.resolve(name)
            except Exception:
                return None
        inputs = {}
        if isinstance(context.metadata.get("inputs"), dict):
            inputs = context.metadata.get("inputs", {})
        if name in inputs:
            return inputs.get(name)
        return None

    def _assign_variable(self, name: str, value: Any, context: ExecutionContext) -> None:
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        if env.has(name):
            env.assign(name, value)
        else:
            env.declare(name, value)
        context.variables[name] = value
        context._env = env

    def _validation_to_dict(self, validation: ast_nodes.InputValidation | None, evaluator: ExpressionEvaluator) -> dict | None:
        if not validation:
            return None
        data: dict[str, Any] = {}
        if validation.field_type:
            data["type"] = validation.field_type
        if validation.min_expr is not None:
            try:
                data["min"] = evaluator.evaluate(validation.min_expr)
            except Exception:
                data["min"] = None
        if validation.max_expr is not None:
            try:
                data["max"] = evaluator.evaluate(validation.max_expr)
            except Exception:
                data["max"] = None
        return data or None

    def _build_log_entry(self, level: str, message: str, metadata: Any) -> dict:
        return {"timestamp": time.time(), "level": level, "message": message, "metadata": metadata}

    def _build_note_entry(self, message: str) -> dict:
        return {"timestamp": time.time(), "message": message}

    def _build_checkpoint_entry(self, label: str) -> dict:
        return {"timestamp": time.time(), "label": label}

    def _build_evaluator(self, context: ExecutionContext) -> ExpressionEvaluator:
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        context._env = env
        return ExpressionEvaluator(
            env,
            resolver=lambda name: self._resolve_identifier(name, context),
            rulegroup_resolver=lambda expr: self._eval_rulegroup(expr, context),
            helper_resolver=lambda name, args: self._call_helper(name, args, context),
        )

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
        if isinstance(expr, ast_nodes.PatternExpr):
            match, _ = self._match_pattern(expr, context)
            return match
        evaluator = self._build_evaluator(context)
        try:
            return evaluator.evaluate(expr)
        except EvaluationError as exc:
            raise Namel3ssError(str(exc))

    def _match_pattern(self, pattern: ast_nodes.PatternExpr, context: ExecutionContext) -> tuple[bool, Any]:
        found, subject = self._resolve_identifier(pattern.subject.name, context)
        if not found or not isinstance(subject, dict):
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
                    elif op in {"is", "==", "="}:
                        if left_val != right_val:
                            return False, None
                    elif op in {"is not", "!="}:
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
        evaluator = self._build_evaluator(context)
        try:
            value = evaluator.evaluate(expr)
        except EvaluationError as exc:
            raise Namel3ssError(str(exc))
        if not isinstance(value, bool):
            raise Namel3ssError("Condition must evaluate to a boolean")
        return bool(value), value

    def _execute_ir_if(self, stmt: IRIf, context: ExecutionContext) -> None:
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        context._env = env
        for idx, br in enumerate(stmt.branches):
            result, candidate_binding = self._eval_condition_with_binding(br.condition, context)
            label = br.label or f"branch-{idx}"
            if br.label == "unless":
                result = not result
            if not result:
                continue
            had_prev = False
            previous_binding = None
            if br.binding:
                if env.has(br.binding):
                    had_prev = True
                    previous_binding = env.resolve(br.binding)
                    env.assign(br.binding, candidate_binding)
                else:
                    env.declare(br.binding, candidate_binding)
                context.variables = env.values
                context.metadata[br.binding] = candidate_binding
            for action in br.actions:
                self._execute_statement(action, context)
            if br.binding:
                if had_prev:
                    env.assign(br.binding, previous_binding)
                    context.metadata[br.binding] = previous_binding
                else:
                    env.remove(br.binding)
                    context.metadata.pop(br.binding, None)
            break

    def _execute_statement(self, stmt: IRStatement, context: ExecutionContext, allow_return: bool = False) -> Any:
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        context._env = env
        evaluator = self._build_evaluator(context)
        if isinstance(stmt, IRLet):
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            env.declare(stmt.name, value)
            context.variables = env.values
            context.metadata[stmt.name] = value
            context.metadata["last_output"] = value
            return value
        if isinstance(stmt, IRSet):
            if not env.has(stmt.name):
                raise Namel3ssError(f"Variable '{stmt.name}' is not defined")
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            env.assign(stmt.name, value)
            context.variables = env.values
            context.metadata[stmt.name] = value
            context.metadata["last_output"] = value
            return value
        if isinstance(stmt, IRIf):
            self._execute_ir_if(stmt, context)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRForEach):
            iterable_val = evaluator.evaluate(stmt.iterable) if stmt.iterable is not None else None
            if not isinstance(iterable_val, list):
                raise Namel3ssError("N3-3400: for-each loop requires a list value")
            had_prev = env.has(stmt.var_name)
            prev_val = env.resolve(stmt.var_name) if had_prev else None
            declared_new = not had_prev
            for idx, item in enumerate(iterable_val):
                if had_prev or not declared_new:
                    env.assign(stmt.var_name, item)
                else:
                    env.declare(stmt.var_name, item)
                    declared_new = False
                context.variables = env.values
                context.metadata[stmt.var_name] = item
                for body_stmt in stmt.body:
                    self._execute_statement(body_stmt, context, allow_return=allow_return)
            if had_prev:
                env.assign(stmt.var_name, prev_val)
                context.metadata[stmt.var_name] = prev_val
            else:
                env.remove(stmt.var_name)
                context.metadata.pop(stmt.var_name, None)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRRepeatUpTo):
            count_val = evaluator.evaluate(stmt.count) if stmt.count is not None else 0
            try:
                count_num = int(count_val)
            except Exception:
                raise Namel3ssError("N3-3401: repeat-up-to requires numeric count")
            if count_num < 0:
                raise Namel3ssError("N3-3402: loop count must be non-negative")
            for idx in range(count_num):
                for body_stmt in stmt.body:
                    self._execute_statement(body_stmt, context, allow_return=allow_return)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRRetry):
            count_val = evaluator.evaluate(stmt.count) if stmt.count is not None else 0
            try:
                attempts = int(count_val)
            except Exception:
                raise Namel3ssError("N3-4500: retry requires numeric max attempts")
            if attempts < 1:
                raise Namel3ssError("N3-4501: retry max attempts must be at least 1")
            last_output = None
            for attempt in range(attempts):
                try:
                    for body_stmt in stmt.body:
                        last_output = self._execute_statement(body_stmt, context)
                    if not self._is_error_result(last_output):
                        break
                    if attempt + 1 == attempts:
                        break
                except Namel3ssError:
                    if attempt + 1 == attempts:
                        raise
                    continue
            context.metadata["last_output"] = last_output
            return last_output
        if isinstance(stmt, IRMatch):
            target_val = evaluator.evaluate(stmt.target) if stmt.target is not None else None
            for br in stmt.branches:
                if self._match_branch(br, target_val, evaluator, context):
                    for action in br.actions:
                        self._execute_statement(action, context, allow_return=allow_return)
                    break
            return context.metadata.get("last_output")
        if isinstance(stmt, IRReturn):
            if not allow_return:
                raise Namel3ssError("N3-6002: return used outside helper")
            value = evaluator.evaluate(stmt.expr) if stmt.expr is not None else None
            raise ReturnSignal(value)
        if isinstance(stmt, IRAskUser):
            provided = self._resolve_provided_input(stmt.var_name, context)
            if provided is not None:
                self._assign_variable(stmt.var_name, provided, context)
                return provided
            pending = context.metadata.setdefault("pending_inputs", [])
            pending.append(
                {
                    "type": "ask",
                    "name": stmt.var_name,
                    "label": stmt.label,
                    "validation": self._validation_to_dict(stmt.validation, evaluator),
                }
            )
            context.metadata["__awaiting_input__"] = True
            return None
        if isinstance(stmt, IRForm):
            provided = self._resolve_provided_input(stmt.name, context)
            if isinstance(provided, dict):
                self._assign_variable(stmt.name, provided, context)
                return provided
            fields = [
                {"label": f.label, "name": f.name, "validation": self._validation_to_dict(f.validation, evaluator)}
                for f in stmt.fields
            ]
            pending = context.metadata.setdefault("pending_inputs", [])
            pending.append({"type": "form", "name": stmt.name, "label": stmt.label, "fields": fields})
            context.metadata["__awaiting_input__"] = True
            return None
        if isinstance(stmt, IRLog):
            meta_val = evaluator.evaluate(stmt.metadata) if stmt.metadata is not None else None
            entry = self._build_log_entry(stmt.level, stmt.message, meta_val)
            context.metadata.setdefault("logs", []).append(entry)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRNote):
            entry = self._build_note_entry(stmt.message)
            context.metadata.setdefault("notes", []).append(entry)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRCheckpoint):
            entry = self._build_checkpoint_entry(stmt.label)
            context.metadata.setdefault("checkpoints", []).append(entry)
            return context.metadata.get("last_output")
        if isinstance(stmt, IRAction):
            step = AgentStep(kind=stmt.kind if stmt.kind != "agent" else "subagent", target=stmt.target)
            output = self._run_step(step, context.metadata.get("last_output") if isinstance(context.metadata.get("last_output"), dict) else None, context)
            context.metadata["last_output"] = output
            return output
        raise Namel3ssError(f"Unsupported statement '{type(stmt).__name__}'")

    def _run_agent_conditions(self, agent: IRAgent, context: ExecutionContext) -> dict:
        branches = agent.conditional_branches or []
        selected = None
        selected_label = None
        selected_expr_display = None
        binding_value = None
        binding_name = None
        env = getattr(context, "_env", None) or VariableEnvironment(context.variables)
        context._env = env
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
            if env.has(binding_name):
                had_prev = True
                previous_binding = env.resolve(binding_name)
                env.assign(binding_name, binding_value)
            else:
                env.declare(binding_name, binding_value)
            context.variables = env.values
            context.metadata[binding_name] = binding_value
        for action in selected.actions:
            if isinstance(action, IRAction):
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
                context.metadata["last_output"] = output
            else:
                last_output = self._execute_statement(action, context)
        if binding_name:
            if had_prev:
                env.assign(binding_name, previous_binding)
                context.metadata[binding_name] = previous_binding
            else:
                env.remove(binding_name)
                context.metadata.pop(binding_name, None)
        return {
            "branch": selected_label,
            "steps": steps_results,
            "last_output": last_output,
            "condition_text": cond_text,
        }
