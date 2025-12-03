"""
Job scheduler helper.
"""

from __future__ import annotations

from typing import Any

from .models import Job
from .queue import JobQueue


class JobScheduler:
    def __init__(self, queue: JobQueue) -> None:
        self.queue = queue

    def schedule_flow(self, flow_name: str, payload: dict[str, Any] | None = None) -> Job:
        return self.queue.create_and_enqueue("flow", flow_name, payload)

    def schedule_agent(self, agent_name: str, payload: dict[str, Any] | None = None) -> Job:
        return self.queue.create_and_enqueue("agent", agent_name, payload)

    def schedule_page(self, page_name: str, payload: dict[str, Any] | None = None) -> Job:
        return self.queue.create_and_enqueue("page", page_name, payload)

    def schedule_tool(self, tool_name: str, payload: dict[str, Any] | None = None) -> Job:
        return self.queue.create_and_enqueue("tool", tool_name, payload)
