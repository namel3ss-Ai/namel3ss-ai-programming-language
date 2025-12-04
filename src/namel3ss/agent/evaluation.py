"""
Lightweight agent self-evaluation using the model router.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from ..ai.router import ModelRouter
from ..runtime.context import ExecutionContext
from .planning import AgentGoal


@dataclass
class AgentEvaluation:
    score: float  # normalized 0.0-1.0
    reasons: str
    rubric: Optional[str] = None
    raw_output: str = ""


class AgentEvaluator:
    def __init__(self, router: ModelRouter) -> None:
        self.router = router

    def evaluate_answer(
        self, goal: AgentGoal, answer: str, context: ExecutionContext, agent_id: str
    ) -> AgentEvaluation:
        prompt = self._build_prompt(goal, answer)
        response = self.router.generate(messages=[{"role": "user", "content": prompt}])
        raw_text = self._extract_response_text(response)
        parsed = self._parse_output(raw_text)
        evaluation = AgentEvaluation(
            score=parsed.get("score", 0.0),
            reasons=parsed.get("reasons", "").strip(),
            rubric=parsed.get("rubric"),
            raw_output=raw_text,
        )
        self._record_memory_event(context, agent_id, goal, evaluation)
        return evaluation

    def _build_prompt(self, goal: AgentGoal, answer: str) -> str:
        constraints_block = "\n".join(f"- {k}: {v}" for k, v in goal.constraints.items()) or "None."
        return (
            "You are an evaluator. Score the candidate answer against the goal and constraints.\n"
            "Respond in JSON with keys: score (0-1), reasons, rubric.\n"
            f"Goal: {goal.description}\n"
            f"Constraints:\n{constraints_block}\n"
            f"Answer:\n{answer}\n"
            'Return JSON like {"score":0.8,"reasons":"...","rubric":"correctness, completeness, clarity"}'
        )

    def _parse_output(self, raw_text: str) -> dict[str, Any]:
        cleaned = raw_text.strip()
        # Strip code fences if present
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
        json_text = self._extract_json(cleaned)
        if json_text:
            try:
                data = json.loads(json_text)
                return {
                    "score": self._normalize_score(data.get("score")),
                    "reasons": str(data.get("reasons", "")),
                    "rubric": data.get("rubric"),
                }
            except Exception:
                pass
        # Fallback to pattern-based parsing
        score = self._normalize_score(self._extract_number(cleaned))
        reasons = self._extract_section(cleaned, "reasons") or cleaned
        rubric = self._extract_section(cleaned, "rubric")
        return {"score": score, "reasons": reasons, "rubric": rubric}

    def _extract_json(self, text: str) -> Optional[str]:
        if text.startswith("{") and text.endswith("}"):
            return text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return match.group(0)
        return None

    def _extract_number(self, text: str) -> Optional[float]:
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)", text)
        if match:
            try:
                return float(match.group(1))
            except Exception:
                return None
        return None

    def _extract_section(self, text: str, label: str) -> Optional[str]:
        pattern = re.compile(rf"{label}[:\s]+(.+)", re.IGNORECASE | re.DOTALL)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return None

    def _normalize_score(self, score: Any) -> float:
        try:
            value = float(score)
        except Exception:
            return 0.0
        if value > 1.0:
            value = value / 10.0
        return max(0.0, min(1.0, value))

    def _extract_response_text(self, response: Any) -> str:
        if response is None:
            return ""
        if hasattr(response, "text"):
            try:
                return str(getattr(response, "text"))
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

    def _record_memory_event(
        self, context: ExecutionContext, agent_id: str, goal: AgentGoal, evaluation: AgentEvaluation
    ) -> None:
        memory_engine = getattr(context, "memory_engine", None)
        if not memory_engine:
            return
        message = (
            f"agent_evaluation | agent={agent_id} | goal={goal.description} | "
            f"score={evaluation.score:.2f} | reasons={evaluation.reasons[:100]}"
        )
        try:
            memory_engine.record_conversation(agent_id, message, role="system")
        except Exception:
            pass
