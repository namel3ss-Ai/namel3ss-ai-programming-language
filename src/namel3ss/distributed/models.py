"""
Job models for distributed execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


JobType = Literal["flow", "agent", "page", "tool"]
JobStatus = Literal["queued", "running", "success", "error"]


@dataclass
class Job:
    id: str
    type: JobType
    target: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: JobStatus = "queued"
    result: Any | None = None
    error: str | None = None
