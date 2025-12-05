"""
Suggestion engine that inspects evaluation runs and proposes improvements.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List

from .models import EvaluationRun, Suggestion, SuggestionStatus


class SuggestionEngine:
    def __init__(self, model_router) -> None:
        self.model_router = model_router

    async def generate_suggestions_for_evaluation(self, run: EvaluationRun) -> List[Suggestion]:
        prompt = self._build_prompt(run)
        response = self.model_router.generate(messages=[{"role": "user", "content": prompt}])
        raw_text = getattr(response, "text", None) or str(response)
        parsed = self._parse_suggestions(raw_text)
        if not parsed:
            parsed = [
                {
                    "description": "Reduce latency by tuning concurrency",
                    "change_spec": {"type": "flow_param_tweak", "parameter": "concurrency", "value": 2},
                }
            ]
        suggestions: List[Suggestion] = []
        for entry in parsed:
            suggestions.append(
                Suggestion(
                    id=str(uuid.uuid4()),
                    target_type=run.target_type,
                    target_name=run.target_name,
                    created_at=datetime.now(timezone.utc),
                    status=SuggestionStatus.PENDING,
                    description=entry.get("description") or "Improvement",
                    change_spec=entry.get("change_spec") or {},
                    evaluation_run_id=run.id,
                    metadata={"metrics": run.metrics_summary},
                )
            )
        return suggestions

    def _build_prompt(self, run: EvaluationRun) -> str:
        return (
            "You are an optimization assistant. Given evaluation metrics, propose specific changes.\n"
            f"Target: {run.target_type} {run.target_name}\n"
            f"Metrics: {json.dumps(run.metrics_summary)}\n"
            "Return JSON: {\"suggestions\":[{\"description\":\"...\",\"change_spec\":{...}}]}"
        )

    def _parse_suggestions(self, text: str) -> List[dict]:
        try:
            data = json.loads(text)
            return data.get("suggestions") or []
        except Exception:
            return []
