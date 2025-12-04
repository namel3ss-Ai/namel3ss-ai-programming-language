"""
Reflection configuration and prompt helpers for agent self-critique loops.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

DEFAULT_CRITIQUE_PROMPT = (
    "You are reviewing an assistant's answer. Identify mistakes, gaps, and unclear reasoning."
)
DEFAULT_IMPROVEMENT_PROMPT = (
    "Improve the assistant's answer using the critique. Be concise and correct any issues."
)


@dataclass
class ReflectionConfig:
    enabled: bool = False
    max_rounds: int = 1
    critique_prompt: Optional[str] = None
    improvement_prompt: Optional[str] = None


def build_critique_prompt(request: str, answer: str, config: ReflectionConfig) -> str:
    instruction = config.critique_prompt or DEFAULT_CRITIQUE_PROMPT
    return (
        f"{instruction}\n\n"
        f"User request:\n{request}\n\n"
        f"Current answer:\n{answer}\n\n"
        "Provide a concise critique of the answer."
    )


def build_improvement_prompt(
    request: str, answer: str, critique: str, config: ReflectionConfig
) -> str:
    instruction = config.improvement_prompt or DEFAULT_IMPROVEMENT_PROMPT
    return (
        f"{instruction}\n\n"
        f"User request:\n{request}\n\n"
        f"Current answer:\n{answer}\n\n"
        f"Critique:\n{critique}\n\n"
        "Return an improved answer that addresses the critique."
    )


__all__ = ["ReflectionConfig", "build_critique_prompt", "build_improvement_prompt"]
