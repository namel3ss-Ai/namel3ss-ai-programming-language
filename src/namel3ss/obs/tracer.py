"""
Simple tracer for Namel3ss executions.
"""

from __future__ import annotations

from typing import Optional, List

from .models import (
    AgentStepTrace,
    AgentTrace,
    AITrace,
    AppTrace,
    FlowStepTrace,
    FlowTrace,
    JobTrace,
    TeamTrace,
    RAGTrace,
    PageTrace,
)


class Tracer:
    def __init__(self) -> None:
        self._current_app: Optional[AppTrace] = None
        self._current_page: Optional[PageTrace] = None
        self._current_agent: Optional[AgentTrace] = None
        self._current_flow: Optional[FlowTrace] = None
        self._current_job: Optional[JobTrace] = None
        self._current_team: Optional[TeamTrace] = None

    def start_app(self, app_name: str, role: Optional[str] = None) -> None:
        self._current_app = AppTrace(app_name=app_name, pages=[], role=role)
        self._current_page = None
        self._current_flow = None

    def start_page(self, page_name: str) -> None:
        if not self._current_app:
            self.start_app(app_name="unknown")
        page_trace = PageTrace(page_name=page_name)
        self._current_app.pages.append(page_trace)
        self._current_page = page_trace
        self._current_agent = None

    def record_ai(
        self,
        model_name: str,
        prompt: str,
        response_preview: str,
        provider_name: Optional[str] = None,
        logical_model_name: Optional[str] = None,
    ) -> None:
        if not self._current_page:
            return
        self._current_page.ai_calls.append(
            AITrace(
                model_name=model_name,
                prompt=prompt,
                response_preview=response_preview[:200],
                provider_name=provider_name,
                logical_model_name=logical_model_name,
            )
        )

    def start_agent(self, agent_name: str) -> None:
        if not self._current_page:
            return
        agent_trace = AgentTrace(agent_name=agent_name)
        self._current_page.agents.append(agent_trace)
        self._current_agent = agent_trace

    def record_agent_step(
        self,
        step_name: str,
        kind: str,
        target: str,
        success: bool,
        retries: int,
        output_preview: Optional[str],
        evaluation_score: Optional[float] = None,
        verdict: Optional[str] = None,
    ) -> None:
        if not self._current_agent:
            return
        self._current_agent.steps.append(
            AgentStepTrace(
                step_name=step_name,
                kind=kind,
                target=target,
                success=success,
                retries=retries,
                output_preview=output_preview,
                evaluation_score=evaluation_score,
                verdict=verdict,
            )
        )

    def end_agent(self, summary: Optional[str]) -> None:
        if self._current_agent:
            self._current_agent.summary = summary
        self._current_agent = None

    def start_flow(self, flow_name: str) -> None:
        if not self._current_app:
            self.start_app(app_name="unknown")
        flow_trace = FlowTrace(flow_name=flow_name)
        self._current_app.flows.append(flow_trace)
        self._current_flow = flow_trace

    def record_flow_step(
        self,
        step_name: str,
        kind: str,
        target: str,
        success: bool,
        output_preview: Optional[str],
    ) -> None:
        if not self._current_flow:
            return
        self._current_flow.steps.append(
            FlowStepTrace(
                step_name=step_name,
                kind=kind,
                target=target,
                success=success,
                output_preview=output_preview,
            )
        )

    def end_flow(self) -> None:
        self._current_flow = None

    def record_ui_sections(self, count: int) -> None:
        if self._current_page:
            self._current_page.ui_section_count = count

    def start_job(self, job_id: str, job_type: str, target: str) -> None:
        self._current_job = JobTrace(
            job_id=job_id, job_type=job_type, target=target, status="queued"
        )

    def end_job(self, status: str, result_preview: Optional[str] = None) -> None:
        if self._current_job:
            self._current_job.status = status
            if result_preview:
                self._current_job.steps.append(result_preview)

    def start_team(self, agents: List[str]) -> None:
        team_trace = TeamTrace(agents=agents, messages=[], votes=[])
        if self._current_app:
            self._current_app.teams.append(team_trace)
        self._current_team = team_trace

    def record_agent_message(self, sender: str, role: str, content: str) -> None:
        if self._current_team:
            self._current_team.messages.append({"sender": sender, "role": role, "content": content})

    def record_team_vote(self, votes: List[dict]) -> None:
        if self._current_team:
            self._current_team.votes.extend(votes)

    def end_team(self) -> None:
        self._current_team = None

    def record_rag_query(self, indexes: List[str], hybrid: Optional[bool]) -> None:
        if not self._current_app:
            self.start_app("rag")
        self._current_app.rag_queries.append(
            RAGTrace(query="", indexes=indexes, hybrid=hybrid, result_count=0)
        )

    def update_last_rag_result_count(self, count: int) -> None:
        if self._current_app and self._current_app.rag_queries:
            self._current_app.rag_queries[-1].result_count = count

    @property
    def last_trace(self) -> Optional[AppTrace]:
        return self._current_app
