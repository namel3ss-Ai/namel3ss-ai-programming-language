"""
In-memory store for optimizer evaluations and suggestions.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from .models import EvaluationRun, Suggestion, SuggestionStatus


class OptimizerStore:
    def __init__(self) -> None:
        self._evaluations: Dict[str, EvaluationRun] = {}
        self._suggestions: Dict[str, Suggestion] = {}

    def save_evaluation(self, run: EvaluationRun) -> None:
        self._evaluations[run.id] = run

    def list_evaluations(self) -> List[EvaluationRun]:
        return list(self._evaluations.values())

    def get_evaluation(self, run_id: str) -> Optional[EvaluationRun]:
        return self._evaluations.get(run_id)

    def save_suggestions(self, suggestions: List[Suggestion]) -> None:
        for s in suggestions:
            self._suggestions[s.id] = s

    def list_suggestions(self, status: Optional[SuggestionStatus] = None) -> List[Suggestion]:
        if status is None:
            return list(self._suggestions.values())
        return [s for s in self._suggestions.values() if s.status == status]

    def update_suggestion_status(self, suggestion_id: str, status: SuggestionStatus) -> None:
        if suggestion_id in self._suggestions:
            self._suggestions[suggestion_id].status = status
