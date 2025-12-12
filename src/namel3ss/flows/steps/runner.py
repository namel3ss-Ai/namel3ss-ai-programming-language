from __future__ import annotations
import asyncio
from dataclasses import asdict, is_dataclass
from ... import ast_nodes
from typing import Any, Optional
from uuid import uuid4
from ...errors import Namel3ssError
from ...observability.tracing import default_tracer
from ..graph import FlowNode, FlowRuntimeContext, FlowState, flow_ir_to_graph
from ..models import FlowStepResult
from ..state.context import ExecutionContext
from .runner_ai import _run_ai_step
__all__ = ["_execute_node"]

async def _execute_node(
    self, node: FlowNode, state: FlowState, runtime_ctx: FlowRuntimeContext, resolved_kind: str | None = None
) -> Optional[FlowStepResult]:
    tracer = runtime_ctx.tracer
    resolved_kind = resolved_kind or self._resolve_step_kind(node)
    target = node.config.get("target")
    target_label = target or node.id
    step_name = node.config.get("step_name", node.id)
    output: Any = None
    base_context = runtime_ctx.execution_context
    if base_context is None:
        base_context = ExecutionContext(
            app_name="__flow__",
            request_id=str(uuid4()),
            memory_engine=runtime_ctx.memory_engine,
            memory_stores=runtime_ctx.memory_stores,
            rag_engine=runtime_ctx.rag_engine,
            tracer=runtime_ctx.tracer,
            tool_registry=runtime_ctx.tool_registry,
            metrics=runtime_ctx.metrics,
            secrets=runtime_ctx.secrets,
        )

    params = node.config.get("params") or {}
    with default_tracer.span(
        f"flow.step.{resolved_kind}", attributes={"step": step_name, "flow_target": target_label, "kind": resolved_kind}
    ):
        if resolved_kind == "noop":
            output = node.config.get("output")
        elif resolved_kind == "ai":
            output = await _run_ai_step(
                self,
                node,
                state,
                runtime_ctx,
                base_context,
                step_name,
                target,
                params,
            )
        elif resolved_kind == "agent":
            if not target:
                raise Namel3ssError("This agent step needs a target (the agent to run), but none was provided.")
            if target not in runtime_ctx.program.agents:
                raise Namel3ssError(f'I couldn\'t find an agent named "{target}". Check your configuration or plugin setup.')
            raw_output = await asyncio.to_thread(runtime_ctx.agent_runner.run, target, base_context)
            output = asdict(raw_output) if is_dataclass(raw_output) else raw_output
        elif resolved_kind == "tool":
            if not target:
                raise Namel3ssError("This tool step needs a target (the tool name), but none was provided.")
            tool_cfg = runtime_ctx.tool_registry.get(target)
            if not tool_cfg:
                raise Namel3ssError(f'I couldn\'t find a tool named "{target}". Check your configuration or plugin setup.')
            output = await self._execute_tool_call(node, state, runtime_ctx, tool_override=tool_cfg)
        elif resolved_kind in {"frame_insert", "frame_query", "frame_update", "frame_delete"}:
            params = node.config.get("params") or {}
            frame_name = params.get("frame") or target
            if not frame_name:
                raise Namel3ssError(
                    "N3L-831: frame_insert/frame_query/frame_update/frame_delete requires a frame name."
                )
            evaluator = self._build_evaluator(state, runtime_ctx)
            operation = resolved_kind.replace("frame_", "")
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "frame",
                            "event_type": "start",
                            "operation": operation,
                            "frame_name": frame_name,
                            "flow_name": state.context.get("flow_name"),
                            "step_name": step_name,
                            "status": "running",
                        }
                    )
                except Exception:
                    pass
            if resolved_kind == "frame_insert":
                values_expr = params.get("values") or {}
                if not isinstance(values_expr, dict) or not values_expr:
                    raise Namel3ssError("N3L-832: frame_insert requires non-empty values.")
                row: dict[str, Any] = {}
                for k, v in values_expr.items():
                    row[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                runtime_ctx.frames.insert(frame_name, row)
                output = row
            elif resolved_kind == "frame_query":
                filters_expr = params.get("where") or {}
                filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
                output = runtime_ctx.frames.query(frame_name, filters)
            elif resolved_kind == "frame_update":
                set_expr = params.get("set") or {}
                if not isinstance(set_expr, dict) or not set_expr:
                    raise Namel3ssError("N3L-840: frame_update step must define a non-empty 'set' block.")
                filters_expr = params.get("where") or {}
                filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
                updates: dict[str, Any] = {}
                for k, v in set_expr.items():
                    updates[k] = evaluator.evaluate(v) if isinstance(v, ast_nodes.Expr) else v
                output = runtime_ctx.frames.update(frame_name, filters, updates)
            else:  # frame_delete
                filters_expr = params.get("where") or {}
                filters = self._evaluate_where_conditions(filters_expr, evaluator, step_name, record=None)
                output = runtime_ctx.frames.delete(frame_name, filters)
            if runtime_ctx.event_logger:
                try:
                    payload = {
                        "kind": "frame",
                        "event_type": "end",
                        "operation": operation,
                        "frame_name": frame_name,
                        "flow_name": state.context.get("flow_name"),
                        "step_name": step_name,
                        "status": "success",
                    }
                    if resolved_kind in {"frame_query", "frame_update", "frame_delete"}:
                        payload["row_count"] = output if isinstance(output, (int, float)) else (len(output) if isinstance(output, list) else None)
                    runtime_ctx.event_logger.log(payload)
                except Exception:
                    pass
        elif resolved_kind in {"db_create", "db_update", "db_delete", "db_bulk_create", "db_bulk_update", "db_bulk_delete", "find"}:
            params = node.config.get("params") or {}
            record_name = target or target_label
            if not record_name:
                raise Namel3ssError(
                    f"N3L-1500: Step '{step_name}' must specify a record target."
                )
            records = getattr(runtime_ctx, "records", {}) or getattr(runtime_ctx.program, "records", {})
            record = records.get(record_name)
            if not record:
                raise Namel3ssError(
                    f"N3L-1500: Record '{record_name}' is not declared."
                )
            evaluator = self._build_evaluator(state, runtime_ctx)
            output = self._execute_record_step(
                kind=resolved_kind,
                record=record,
                params=params,
                evaluator=evaluator,
                runtime_ctx=runtime_ctx,
                step_name=step_name,
            )
        elif resolved_kind in {"auth_register", "auth_login", "auth_logout"}:
            params = node.config.get("params") or {}
            auth_cfg = getattr(runtime_ctx, "auth_config", None)
            if not auth_cfg:
                raise Namel3ssError("N3L-1600: Auth configuration is not declared.")
            records = getattr(runtime_ctx, "records", {}) or getattr(runtime_ctx.program, "records", {})
            record = records.get(getattr(auth_cfg, "user_record", None))
            if not record:
                raise Namel3ssError("N3L-1600: Auth configuration references unknown user_record.")
            evaluator = self._build_evaluator(state, runtime_ctx)
            output = self._execute_auth_step(
                kind=resolved_kind,
                auth_config=auth_cfg,
                record=record,
                params=params,
                evaluator=evaluator,
                runtime_ctx=runtime_ctx,
                step_name=step_name,
                state=state,
            )
        elif resolved_kind == "vector_index_frame":
            params = node.config.get("params") or {}
            vector_store_name = params.get("vector_store") or target
            if not vector_store_name:
                raise Namel3ssError(
                    f"Step '{step_name}' must specify a 'vector_store'. Add 'vector_store is \"kb\"' to the step."
                )
            if not runtime_ctx.vectorstores:
                raise Namel3ssError("Vector store registry unavailable.")
            evaluator = self._build_evaluator(state, runtime_ctx)
            cfg = runtime_ctx.vectorstores.get(vector_store_name)
            filters_expr = params.get("where")
            use_expr = filters_expr is not None and not isinstance(filters_expr, (dict, list))
            filters = None if use_expr else self._evaluate_where_conditions(filters_expr or {}, evaluator, step_name, record=None)
            base_rows = runtime_ctx.frames.query(cfg.frame, filters) if not use_expr else runtime_ctx.frames.query(cfg.frame)
            rows: list[dict] = []
            if use_expr:
                for row in base_rows:
                    if not isinstance(row, dict):
                        continue
                    row_env = VariableEnvironment({"row": row, **dict(row)})
                    row_evaluator = ExpressionEvaluator(
                        row_env,
                        resolver=lambda name, r=row: (True, r)
                        if name == "row"
                        else ((True, r.get(name)) if isinstance(r, dict) and name in r else evaluator.resolver(name)),
                    )
                    try:
                        keep = row_evaluator.evaluate(filters_expr)
                    except EvaluationError as exc:
                        raise Namel3ssError(str(exc)) from exc
                    if not isinstance(keep, bool):
                        raise Namel3ssError(
                            f"N3F-1003: The 'where' clause on frame '{cfg.frame}' must be a boolean expression."
                        )
                    if keep:
                        rows.append(row)
            else:
                rows = base_rows
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "vector",
                            "event_type": "start",
                            "operation": "index_frame",
                            "vector_store": vector_store_name,
                            "frame": cfg.frame,
                            "flow_name": state.context.get("flow_name"),
                            "step_name": step_name,
                            "status": "running",
                        }
                    )
                except Exception:
                    pass
            try:
                ids: list[str] = []
                texts: list[str] = []
                metadata: list[dict] = []
                metadata_cols = getattr(cfg, "metadata_columns", []) or []
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        id_val = row.get(cfg.id_column)
                        text_val = row.get(cfg.text_column)
                        if id_val is None or text_val is None:
                            continue
                        ids.append(str(id_val))
                        texts.append(str(text_val))
                        if metadata_cols:
                            meta_entry: dict[str, object] = {}
                            for col in metadata_cols:
                                meta_entry[col] = row.get(col)
                            metadata.append(meta_entry)
                runtime_ctx.vectorstores.index_texts(
                    vector_store_name,
                    ids,
                    texts,
                    metadata if metadata_cols else None,
                )
                output = len(ids)
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "end",
                                "operation": "index_frame",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "success",
                                "row_count": output,
                            }
                        )
                    except Exception:
                        pass
            except Exception as exc:
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "error",
                                "operation": "index_frame",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "error",
                                "message": str(exc),
                            }
                        )
                    except Exception:
                        pass
                raise
        elif resolved_kind == "vector_query":
            params = node.config.get("params") or {}
            vector_store_name = params.get("vector_store") or target
            if not vector_store_name:
                raise Namel3ssError(
                    f"Step '{step_name}' must specify a 'vector_store'. Add 'vector_store is \"kb\"' to the step."
                )
            if not runtime_ctx.vectorstores:
                raise Namel3ssError("Vector store registry unavailable.")
            evaluator = self._build_evaluator(state, runtime_ctx)
            cfg = runtime_ctx.vectorstores.get(vector_store_name)
            query_expr = params.get("query_text")
            if query_expr is None:
                raise Namel3ssError(
                    f"Step '{step_name}' must define 'query_text'. Add 'query_text is ...' inside the step."
                )
            query_text = evaluator.evaluate(query_expr) if isinstance(query_expr, ast_nodes.Expr) else query_expr
            if not isinstance(query_text, str):
                raise Namel3ssError(
                    f"The 'query_text' for step '{step_name}' must be a string value."
                )
            top_k_expr = params.get("top_k")
            top_k_val = 5
            if top_k_expr is not None:
                top_k_val = evaluator.evaluate(top_k_expr) if isinstance(top_k_expr, ast_nodes.Expr) else top_k_expr
            try:
                top_k_int = int(top_k_val)
            except Exception:
                raise Namel3ssError(
                    f"Top_k for step '{step_name}' must be a positive integer (for example, 3, 5, or 10)."
                )
            if top_k_int < 1:
                raise Namel3ssError(
                    f"Top_k for step '{step_name}' must be a positive integer (for example, 3, 5, or 10)."
                )
            if runtime_ctx.event_logger:
                try:
                    runtime_ctx.event_logger.log(
                        {
                            "kind": "vector",
                            "event_type": "start",
                            "operation": "query",
                            "vector_store": vector_store_name,
                            "frame": cfg.frame,
                            "flow_name": state.context.get("flow_name"),
                            "step_name": step_name,
                            "status": "running",
                        }
                    )
                except Exception:
                    pass
            try:
                matches = runtime_ctx.vectorstores.query(vector_store_name, str(query_text), top_k_int, frames=runtime_ctx.frames)
                # Build context string
                context_parts: list[str] = []
                enriched: list[dict] = []
                for idx, m in enumerate(matches, start=1):
                    text_val = m.get("text")
                    enriched.append(m)
                    if text_val:
                        context_parts.append(f"Document {idx}:\n{text_val}")
                context = "\n\n".join(context_parts)
                output = {"matches": enriched, "context": context}
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "end",
                                "operation": "query",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "success",
                                "match_count": len(matches),
                            }
                        )
                    except Exception:
                        pass
            except Exception as exc:
                if runtime_ctx.event_logger:
                    try:
                        runtime_ctx.event_logger.log(
                            {
                                "kind": "vector",
                                "event_type": "error",
                                "operation": "query",
                                "vector_store": vector_store_name,
                                "frame": cfg.frame,
                                "flow_name": state.context.get("flow_name"),
                                "step_name": step_name,
                                "status": "error",
                                "message": str(exc),
                            }
                        )
                    except Exception:
                        pass
                raise
        elif resolved_kind == "rag_query":
            params = node.config.get("params") or {}
            pipeline_name = params.get("pipeline")
            question_expr = params.get("question")
            if not pipeline_name:
                raise Namel3ssError(
                    f"Step '{step_name}' refers to a RAG pipeline, but no pipeline is specified. Add 'pipeline is \"...\"'."
                )
            evaluator = self._build_evaluator(state, runtime_ctx)
            question_val = evaluator.evaluate(question_expr) if isinstance(question_expr, ast_nodes.Expr) else question_expr
            if not isinstance(question_val, str):
                raise Namel3ssError(
                    f"The 'question' expression for step '{step_name}' must evaluate to a string."
                )
            output = await self._run_rag_pipeline(
                pipeline_name,
                question_val,
                state,
                runtime_ctx,
                base_context,
                flow_name=state.context.get("flow_name") or "",
                step_name=step_name,
            )
        elif resolved_kind == "rag":
            if not runtime_ctx.rag_engine:
                raise Namel3ssError("RAG engine unavailable for rag step")
            query = node.config.get("query") or state.get("last_output") or ""
            results = await runtime_ctx.rag_engine.a_retrieve(query, index_names=[target])
            output = [
                {"text": r.item.text, "score": r.score, "source": r.source, "metadata": r.item.metadata}
                for r in results
            ]
            if runtime_ctx.metrics:
                runtime_ctx.metrics.record_rag_query(backends=[target])
        elif resolved_kind == "branch":
            output = {"branch": True}
        elif resolved_kind == "join":
            output = {"join": True}
        elif resolved_kind == "subflow":
            subflow = runtime_ctx.program.flows.get(target)
            if not subflow:
                raise Namel3ssError(f"Subflow '{target}' not found")
            graph = flow_ir_to_graph(subflow)
            sub_state = state.copy()
            result = await self.a_run_flow(graph, sub_state, runtime_ctx, flow_name=target)
            output = {"subflow": target, "state": result.state.data if result.state else {}}
        elif resolved_kind == "script":
            statements = node.config.get("statements") or []
            output = await self._execute_script(statements, state, runtime_ctx, node.id)
        elif resolved_kind == "condition":
            output = await self._run_condition_node(node, state, runtime_ctx)
        elif resolved_kind == "function":
            func = node.config.get("callable")
            if not callable(func):
                raise Namel3ssError(f"Function node '{node.id}' missing callable")
            output = func(state)
        elif resolved_kind == "parallel":
            output = await self._execute_parallel_block(node, state, runtime_ctx)
        elif resolved_kind == "transaction":
            output = await self._execute_transaction_block(node, state, runtime_ctx)
        elif resolved_kind == "for_each":
            output = await self._execute_for_each(node, state, runtime_ctx)
        elif resolved_kind == "try":
            output = await self._execute_try_catch(node, state, runtime_ctx)
        elif resolved_kind == "goto_flow":
            target_flow = node.config.get("target")
            reason = node.config.get("reason", "unconditional")
            if not target_flow:
                raise Namel3ssError("'go to flow' requires a target flow name")
            state.context["__redirect_flow__"] = target_flow
            output = {"goto_flow": target_flow}
            if tracer:
                tracer.record_flow_event(
                    "flow.goto",
                    {
                        "from_flow": state.context.get("flow_name"),
                        "to_flow": target_flow,
                        "step": node.config.get("step_name", node.id),
                        "reason": reason,
                    },
                )
        else:
            raise Namel3ssError(f"Unsupported flow step kind '{resolved_kind}'")

    state.set(f"step.{node.id}.output", output)
    state.set("last_output", output)
    if tracer:
        tracer.record_flow_step(
            step_name=step_name,
            kind=resolved_kind,
            target=target_label,
            success=True,
            output_preview=str(output)[:200] if output is not None else None,
            node_id=node.id,
        )
    return FlowStepResult(
        step_name=step_name,
        kind=resolved_kind,
        target=target_label,
        success=True,
        output=output,
        node_id=node.id,
        redirect_to=state.context.get("__redirect_flow__"),
    )
