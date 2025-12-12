from __future__ import annotations

from typing import Any

from .... import ast_nodes
from ....errors import Namel3ssError
from ....runtime.expressions import EvaluationError, ExpressionEvaluator, VariableEnvironment
from ...graph import FlowRuntimeContext, FlowState
from ...state.context import ExecutionContext

__all__ = ["FlowEngineRagPipelineMixin"]


class FlowEngineRagPipelineMixin:
    async def _run_rag_pipeline(
        self,
        pipeline_name: str,
        question: str,
        state: FlowState,
        runtime_ctx: FlowRuntimeContext,
        base_context: ExecutionContext,
        flow_name: str,
        step_name: str,
    ) -> dict[str, Any]:
        pipeline = getattr(runtime_ctx, "rag_pipelines", {}).get(pipeline_name) or getattr(self.program, "rag_pipelines", {}).get(pipeline_name)
        if not pipeline:
            raise Namel3ssError(
                f"Step '{step_name}' refers to RAG pipeline '{pipeline_name}', but no such pipeline is declared."
            )
        ctx = {
            "original_question": question,
            "current_query": question,
            "queries": [],
            "subquestions": [],
            "chosen_vector_stores": [],
            "matches": [],
            "matches_per_stage": {},
            "context": "",
            "answer": None,
        }
        evaluator = self._build_evaluator(state, runtime_ctx)
        for stage in pipeline.stages:
            st_type = (stage.type or "").lower()
            if st_type == "ai_rewrite":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                ctx["current_query"] = str(result)
            elif st_type == "query_route":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                choices = stage.choices or []
                selected: list[str] = []
                if isinstance(result, list):
                    selected = [str(x) for x in result if str(x)]
                elif isinstance(result, dict):
                    selected = [str(v) for v in result.values() if v]
                elif result is not None:
                    selected = [str(result)]
                selected_filtered = [s for s in selected if not choices or s in choices]
                if not selected_filtered and pipeline.default_vector_store:
                    selected_filtered = [pipeline.default_vector_store]
                if not selected_filtered:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' could not choose a vector_store. Ensure the router AI returns one of: {', '.join(choices)}."
                    )
                ctx["chosen_vector_stores"] = selected_filtered
            elif st_type == "vector_retrieve":
                targets: list[str] = []
                if stage.vector_store:
                    targets = [stage.vector_store]
                elif ctx.get("chosen_vector_stores"):
                    targets = list(ctx.get("chosen_vector_stores") or [])
                elif pipeline.default_vector_store:
                    targets = [pipeline.default_vector_store]
                if not targets:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' must specify a 'vector_store' or set a default with 'use vector_store \"...\"'."
                    )
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=5)
                if top_k_val < 1:
                    top_k_val = 5
                queries_to_run = ctx.get("queries") or ctx.get("subquestions") or []
                if not queries_to_run:
                    queries_to_run = [ctx.get("current_query") or question]
                aggregated_matches: list[dict[str, Any]] = []
                where_expr = stage.where
                for target_vs in targets:
                    for query_text in queries_to_run:
                        matches = runtime_ctx.vectorstores.query(target_vs, query_text, top_k=top_k_val, frames=runtime_ctx.frames)
                        filtered_matches = []
                        if where_expr is None:
                            filtered_matches = matches
                        else:
                            for m in matches:
                                env = VariableEnvironment({"metadata": m.get("metadata") or {}, "match": m})
                                match_eval = ExpressionEvaluator(
                                    env,
                                    resolver=lambda name, meta=m: (
                                        True,
                                        meta.get("metadata", {}).get(name) if isinstance(meta, dict) and isinstance(meta.get("metadata"), dict) and name in meta.get("metadata", {}) else meta.get(name),
                                    ),
                                )
                                try:
                                    keep_val = match_eval.evaluate(where_expr)
                                except EvaluationError as exc:
                                    raise Namel3ssError(str(exc)) from exc
                                if not isinstance(keep_val, bool):
                                    raise Namel3ssError(
                                        f"The 'where' clause on stage '{stage.name}' in pipeline '{pipeline.name}' must be a boolean expression."
                                    )
                                if keep_val:
                                    filtered_matches.append(m)
                        for m in filtered_matches:
                            m = dict(m)
                            m.setdefault("vector_store", target_vs)
                            m.setdefault("query", query_text)
                            aggregated_matches.append(m)
                ctx["matches"] = aggregated_matches
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = aggregated_matches
                ctx["matches_per_stage"] = ctx_matches_per_stage
                texts: list[str] = []
                for m in aggregated_matches:
                    text_val = m.get("text") if isinstance(m, dict) else None
                    if text_val is None and isinstance(m, dict):
                        meta = m.get("metadata") or {}
                        if isinstance(meta, dict):
                            text_val = meta.get("text")
                    if text_val:
                        texts.append(str(text_val))
                ctx["context"] = "\n\n".join(texts).strip()
            elif st_type == "table_lookup":
                frame_name = stage.frame or ""
                if not frame_name:
                    raise Namel3ssError(f"Stage '{stage.name}' in pipeline '{pipeline.name}' must specify a frame.")
                rows = runtime_ctx.frames.query(frame_name, None)
                match_column = stage.match_column
                query_text = (ctx.get("current_query") or question or "") or ""
                filtered: list[dict] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    if match_column and match_column in row:
                        try:
                            if query_text and str(row.get(match_column, "")).lower().find(str(query_text).lower()) != -1:
                                filtered.append(row)
                        except Exception:
                            if str(query_text) in str(row.get(match_column, "")):
                                filtered.append(row)
                    else:
                        filtered.append(row)
                max_rows_val = self._evaluate_stage_number(stage.max_rows, evaluator, default=20)
                filtered = filtered[: max_rows_val or len(filtered)]
                ctx_rows_per_stage = ctx.get("table_rows_per_stage") or {}
                ctx_rows_per_stage[stage.name] = filtered
                ctx["table_rows_per_stage"] = ctx_rows_per_stage
                ctx["table_rows"] = filtered
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = filtered
                ctx["matches_per_stage"] = ctx_matches_per_stage
                existing_matches = ctx.get("matches") or []
                display_cols: list[str] = []
                frame_def = getattr(runtime_ctx.frames, "frames", {}).get(frame_name)
                if frame_def and getattr(frame_def, "table_config", None):
                    display_cols = getattr(frame_def.table_config, "display_columns", []) or []
                lines: list[str] = []
                for row in filtered:
                    entry = dict(row)
                    entry.setdefault("frame", frame_name)
                    existing_matches.append(entry)
                    if not isinstance(row, dict):
                        continue
                    cols = display_cols or list(row.keys())
                    preview = ", ".join(f"{c}={row.get(c)}" for c in cols if c in row)
                    lines.append(preview)
                ctx["matches"] = existing_matches
                combined = "\n\n".join([t for t in [ctx.get("context", ""), "\n".join(lines)] if t]).strip()
                ctx["context"] = combined
            elif st_type == "table_summarise":
                frame_name = stage.frame or ""
                rows = ctx.get("table_rows") or runtime_ctx.frames.query(frame_name, None)
                if not isinstance(rows, list):
                    rows = []
                group_by = stage.group_by
                grouped: dict[str, list[dict]] = {}
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    key = str(row.get(group_by)) if group_by else "all"
                    grouped.setdefault(key, []).append(row)
                max_groups_val = self._evaluate_stage_number(stage.max_groups, evaluator, default=5)
                max_rows_per_group_val = self._evaluate_stage_number(stage.max_rows_per_group, evaluator, default=20)
                display_cols: list[str] = []
                frame_def = getattr(runtime_ctx.frames, "frames", {}).get(frame_name)
                if frame_def and getattr(frame_def, "table_config", None):
                    display_cols = getattr(frame_def.table_config, "display_columns", []) or []
                summaries: list[dict] = []
                for idx, (group_key, group_rows) in enumerate(grouped.items()):
                    if max_groups_val and idx >= max_groups_val:
                        break
                    sample_rows = group_rows[: max_rows_per_group_val or len(group_rows)]
                    preview_parts: list[str] = []
                    for row in sample_rows:
                        cols = display_cols or list(row.keys())
                        preview_parts.append(", ".join(f"{c}={row.get(c)}" for c in cols if c in row))
                    summary_text = f"{len(group_rows)} rows"
                    if group_by:
                        summary_text += f" for {group_by}={group_key}"
                    if preview_parts:
                        summary_text += f": {' | '.join(preview_parts)}"
                    summaries.append({"text": summary_text, "group": group_key, "frame": frame_name})
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = summaries
                ctx["matches_per_stage"] = ctx_matches_per_stage
                existing_matches = ctx.get("matches") or []
                existing_matches.extend(summaries)
                ctx["matches"] = existing_matches
                texts = [s.get("text") for s in summaries if isinstance(s, dict) and s.get("text")]
                combined = "\n\n".join([t for t in [ctx.get("context", ""), "\n".join(texts)] if t]).strip()
                ctx["context"] = combined
            elif st_type == "multimodal_embed":
                frame_name = stage.frame or ""
                if not frame_name:
                    raise Namel3ssError(f"Stage '{stage.name}' in pipeline '{pipeline.name}' must specify a frame.")
                rows = runtime_ctx.frames.query(frame_name, None)
                max_items_val = self._evaluate_stage_number(stage.max_items, evaluator, default=20)
                rows = rows[: max_items_val or len(rows)]
                text_col = stage.text_column
                image_col = stage.image_column
                frame_def = getattr(runtime_ctx.frames, "frames", {}).get(frame_name)
                if frame_def and getattr(frame_def, "table_config", None):
                    text_col = text_col or getattr(frame_def.table_config, "text_column", None)
                    image_col = image_col or getattr(frame_def.table_config, "image_column", None)
                vector_store_name = stage.output_vector_store or stage.vector_store
                metadata: list[dict] = []
                texts: list[str] = []
                ids: list[str] = []
                for idx, row in enumerate(rows):
                    if not isinstance(row, dict):
                        continue
                    base_text = row.get(text_col) if text_col else None
                    img_val = row.get(image_col) if image_col else None
                    combined_text = str(base_text if base_text is not None else row)
                    if img_val is not None:
                        combined_text = f"{combined_text} | image: {img_val}"
                    texts.append(combined_text)
                    metadata.append({"text": base_text, "image": img_val})
                    row_id = row.get(getattr(frame_def, "primary_key", None)) if frame_def else None
                    ids.append(str(row_id or idx))
                if vector_store_name and texts:
                    runtime_ctx.vectorstores.index_texts(vector_store_name, ids, texts, metadata)
            elif st_type == "multimodal_summarise":
                frame_name = stage.frame or ""
                rows = runtime_ctx.frames.query(frame_name, None)
                max_items_val = self._evaluate_stage_number(stage.max_items, evaluator, default=20)
                rows = rows[: max_items_val or len(rows)]
                text_col = stage.text_column
                image_col = stage.image_column
                frame_def = getattr(runtime_ctx.frames, "frames", {}).get(frame_name)
                if frame_def and getattr(frame_def, "table_config", None):
                    text_col = text_col or getattr(frame_def.table_config, "text_column", None)
                    image_col = image_col or getattr(frame_def.table_config, "image_column", None)
                captions: list[dict] = []
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    base_text = row.get(text_col) if text_col else None
                    img_val = row.get(image_col) if image_col else None
                    caption = f"Item: {base_text or row}"
                    if img_val is not None:
                        caption = f"{caption} | image: {img_val}"
                    captions.append({"text": caption, "frame": frame_name, "image": img_val})
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = captions
                ctx["matches_per_stage"] = ctx_matches_per_stage
                existing_matches = ctx.get("matches") or []
                existing_matches.extend(captions)
                ctx["matches"] = existing_matches
                combined = "\n\n".join([t for t in [ctx.get("context", ""), "\n".join([c.get("text", "") for c in captions])] if t]).strip()
                ctx["context"] = combined
            elif st_type == "graph_query":
                graph_engine = getattr(runtime_ctx, "graph_engine", None)
                if graph_engine is None:
                    raise Namel3ssError(f"Stage '{stage.name}' in pipeline '{pipeline.name}' requires graph support, but no graph engine is available.")
                graph_name = stage.graph or ""
                max_hops_val = self._evaluate_stage_number(stage.max_hops, evaluator, default=2)
                max_nodes_val = self._evaluate_stage_number(stage.max_nodes, evaluator, default=25)
                query_text = ctx.get("current_query") or question
                results = graph_engine.query(
                    graph_name,
                    query_text,
                    max_hops=max_hops_val,
                    max_nodes=max_nodes_val,
                    strategy=stage.strategy,
                    frames=runtime_ctx.frames,
                )
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = results
                ctx["matches_per_stage"] = ctx_matches_per_stage
                existing_matches = ctx.get("matches") or []
                for r in results:
                    entry = dict(r)
                    entry.setdefault("graph", graph_name)
                    existing_matches.append(entry)
                ctx["matches"] = existing_matches
                texts = [r.get("text") for r in results if isinstance(r, dict) and r.get("text")]
                combined = "\n\n".join([t for t in [ctx.get("context", ""), "\n".join(texts)] if t]).strip()
                ctx["context"] = combined
            elif st_type == "graph_summary_lookup":
                graph_engine = getattr(runtime_ctx, "graph_engine", None)
                if graph_engine is None:
                    raise Namel3ssError(f"Stage '{stage.name}' in pipeline '{pipeline.name}' requires graph support, but no graph engine is available.")
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=5)
                query_text = ctx.get("current_query") or question
                results = graph_engine.lookup_summary(stage.graph_summary or "", query_text, top_k=top_k_val, frames=runtime_ctx.frames)
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = results
                ctx["matches_per_stage"] = ctx_matches_per_stage
                existing_matches = ctx.get("matches") or []
                for r in results:
                    entry = dict(r)
                    entry.setdefault("graph_summary", stage.graph_summary)
                    existing_matches.append(entry)
                ctx["matches"] = existing_matches
                texts = [r.get("text") for r in results if isinstance(r, dict) and r.get("text")]
                combined = "\n\n".join([t for t in [ctx.get("context", ""), "\n".join(texts)] if t]).strip()
                ctx["context"] = combined
            elif st_type == "ai_rerank":
                matches = ctx.get("matches") or []
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=len(matches) or 0)
                try:
                    await self._run_ai_stage(
                        ai_name=stage.ai or "",
                        payload={"question": question, "matches": matches},
                        runtime_ctx=runtime_ctx,
                        step_name=stage.name,
                        flow_name=flow_name,
                        base_context=base_context,
                    )
                except Exception:
                    pass
                matches_sorted = sorted(matches, key=lambda m: m.get("score", 0), reverse=True)
                if top_k_val > 0:
                    matches_sorted = matches_sorted[:top_k_val]
                ctx["matches"] = matches_sorted
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = matches_sorted
                ctx["matches_per_stage"] = ctx_matches_per_stage
                ctx["context"] = "\n\n".join([str(m.get("text", "")) for m in matches_sorted if m.get("text")]).strip()
            elif st_type == "context_compress":
                max_tokens_val = self._evaluate_stage_number(stage.max_tokens, evaluator, default=None)
                context_text = ctx.get("context") or ""
                if max_tokens_val and max_tokens_val > 0 and len(context_text) > max_tokens_val:
                    ctx["context"] = context_text[:max_tokens_val]
            elif st_type == "multi_query":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context"), "current_query": ctx.get("current_query")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                queries: list[str] = []
                if isinstance(result, list):
                    queries = [str(q) for q in result if str(q)]
                elif isinstance(result, str):
                    queries = [s for s in [r.strip() for r in result.split("\n") if r.strip()] if s]
                elif result is not None:
                    queries = [str(result)]
                max_queries_val = self._evaluate_stage_number(stage.max_queries, evaluator, default=4)
                if max_queries_val > 0:
                    queries = queries[:max_queries_val]
                ctx["queries"] = queries
            elif st_type == "query_decompose":
                result = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                subs: list[str] = []
                if isinstance(result, list):
                    subs = [str(s) for s in result if str(s)]
                elif isinstance(result, str):
                    subs = [s for s in [r.strip() for r in result.split("\n") if r.strip()] if s]
                elif result is not None:
                    subs = [str(result)]
                max_sub_val = self._evaluate_stage_number(stage.max_subquestions, evaluator, default=3)
                if max_sub_val > 0:
                    subs = subs[:max_sub_val]
                ctx["subquestions"] = subs
            elif st_type == "fusion":
                source_matches: list[dict[str, Any]] = []
                missing_sources: list[str] = []
                for ref in stage.from_stages or []:
                    ref_matches = (ctx.get("matches_per_stage") or {}).get(ref)
                    if ref_matches is None:
                        missing_sources.append(ref)
                        continue
                    source_matches.append({"name": ref, "matches": ref_matches})
                if missing_sources:
                    raise Namel3ssError(
                        f"Stage '{stage.name}' in pipeline '{pipeline.name}' cannot fuse missing stages: {', '.join(missing_sources)}."
                    )
                fused_scores: dict[tuple[Any, Any], dict[str, Any]] = {}
                method = (stage.method or "rrf").lower()
                for entry in source_matches:
                    matches_list = entry["matches"]
                    for rank, m in enumerate(matches_list):
                        key = (m.get("id"), m.get("vector_store"))
                        base = fused_scores.setdefault(key, {"score": 0.0, "match": dict(m)})
                        if method == "rrf":
                            base["score"] += 1.0 / float(rank + 1)
                        else:
                            base["score"] += 1.0 / float(rank + 1)
                fused_list = []
                for val in fused_scores.values():
                    match = val["match"]
                    match["score"] = val.get("score", match.get("score", 0))
                    fused_list.append(match)
                fused_list.sort(key=lambda m: m.get("score", 0), reverse=True)
                top_k_val = self._evaluate_stage_number(stage.top_k, evaluator, default=5)
                if top_k_val > 0:
                    fused_list = fused_list[:top_k_val]
                ctx["matches"] = fused_list
                ctx_matches_per_stage = ctx.get("matches_per_stage") or {}
                ctx_matches_per_stage[stage.name] = fused_list
                ctx["matches_per_stage"] = ctx_matches_per_stage
                ctx["context"] = "\n\n".join([str(m.get("text", "")) for m in fused_list if m.get("text")]).strip()
            elif st_type == "ai_answer":
                answer_val = await self._run_ai_stage(
                    ai_name=stage.ai or "",
                    payload={"question": question, "context": ctx.get("context"), "matches": ctx.get("matches")},
                    runtime_ctx=runtime_ctx,
                    step_name=stage.name,
                    flow_name=flow_name,
                    base_context=base_context,
                )
                ctx["answer"] = answer_val if not isinstance(answer_val, dict) else answer_val.get("text") or answer_val
            else:
                raise Namel3ssError(f"Stage type '{stage.type}' is not supported in RAG pipelines.")
        return {
            "answer": ctx.get("answer"),
            "matches": ctx.get("matches"),
            "context": ctx.get("context"),
            "query": ctx.get("current_query"),
        }
