from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Callable, List


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class ConversationSummaryConfig:
    max_messages_before_summary: int = 50
    target_summary_length: int | None = None
    enabled: bool = False


def get_summary_config_from_env() -> ConversationSummaryConfig:
    return ConversationSummaryConfig(
        max_messages_before_summary=_env_int("N3_SUMMARY_MAX_MESSAGES", 50),
        target_summary_length=_env_int("N3_SUMMARY_TARGET_LENGTH", 1),
        enabled=_env_bool("N3_SUMMARY_ENABLED", False),
    )


def summarise_conversation(
    messages: List[dict[str, Any]],
    *,
    config: ConversationSummaryConfig,
    summariser: Callable[[str, ConversationSummaryConfig], str],
    recent_preserve: int = 10,
) -> List[dict[str, Any]]:
    """
    Summarise older messages into a single system message, preserving the most recent turns.
    The summariser callable performs the actual summarisation (AI-backed or heuristic).
    """

    if not config.enabled or len(messages) <= config.max_messages_before_summary:
        return list(messages)
    # Split into older and recent portions
    older = messages[:-recent_preserve] if len(messages) > recent_preserve else []
    recent = messages[-recent_preserve:] if len(messages) > recent_preserve else list(messages)
    if not older:
        return list(messages)
    transcript_lines: list[str] = []
    for msg in older:
        role = msg.get("role", "user")
        content = str(msg.get("content", "")).strip()
        if content:
            transcript_lines.append(f"{role}: {content}")
    transcript = "\n".join(transcript_lines)
    summary_text = summariser(transcript, config)
    summary_msg = {"role": "system", "content": summary_text}
    return [summary_msg] + recent

