"""
Multi-agent debate coordinator built on top of AgentRunner and the model router.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .engine import AgentRunner
from .models import AgentConfig
from ..ai.registry import ModelRegistry
from ..ai.router import ModelRouter
from ..ir import IRProgram
from ..tools.registry import ToolRegistry
from ..runtime.context import ExecutionContext


@dataclass
class DebateTurn:
    agent_id: str
    message: str
    round_index: int


@dataclass
class DebateOutcome:
    transcript: List[DebateTurn]
    consensus_summary: str
    chosen_answer: str
    scores: Dict[str, float]
    final_answers: Dict[str, str] = field(default_factory=dict)


@dataclass
class DebateAgentConfig:
    id: str
    config: AgentConfig = field(default_factory=AgentConfig)


@dataclass
class DebateConfig:
    max_rounds: int = 2
    enable_reflection: bool = False
    judge_agent_id: Optional[str] = None
    judge_prompt: Optional[str] = None


class DebateEngine:
    def __init__(
        self,
        program: IRProgram,
        model_registry: ModelRegistry,
        tool_registry: ToolRegistry,
        router: ModelRouter,
        base_agent_config: Optional[AgentConfig] = None,
    ) -> None:
        self.program = program
        self.model_registry = model_registry
        self.tool_registry = tool_registry
        self.router = router
        self.base_agent_config = base_agent_config or AgentConfig()

    def run_debate(
        self,
        question: str,
        agents: List[DebateAgentConfig],
        context: ExecutionContext,
        config: Optional[DebateConfig] = None,
    ) -> DebateOutcome:
        cfg = config or DebateConfig()
        transcript: List[DebateTurn] = []
        final_answers: Dict[str, str] = {}

        original_user_input = getattr(context, "user_input", None)
        context.user_input = question
        try:
            # Initial answers
            for agent in agents:
                agent_config = self._prepare_agent_config(agent.config, cfg)
                runner = self._build_runner(agent_config)
                result = runner.run(agent.id, context)
                answer_text = result.final_answer or ""
                final_answers[agent.id] = answer_text
                turn = DebateTurn(agent_id=agent.id, message=answer_text, round_index=0)
                transcript.append(turn)
                self._record_memory_turn(context, question, turn)

            # Debate rounds
            for round_idx in range(1, cfg.max_rounds + 1):
                for agent in agents:
                    own_answer = final_answers.get(agent.id, "")
                    others = {aid: ans for aid, ans in final_answers.items() if aid != agent.id}
                    prompt = self._build_debate_prompt(question, agent.id, own_answer, others)
                    response = self.router.generate(messages=[{"role": "user", "content": prompt}])
                    updated_answer = self._extract_response_text(response)
                    final_answers[agent.id] = updated_answer
                    turn = DebateTurn(agent_id=agent.id, message=updated_answer, round_index=round_idx)
                    transcript.append(turn)
                    self._record_memory_turn(context, question, turn)

            outcome = self._compute_consensus(question, final_answers, transcript, cfg, context)
            return outcome
        finally:
            context.user_input = original_user_input

    def _build_runner(self, config: AgentConfig) -> AgentRunner:
        return AgentRunner(
            program=self.program,
            model_registry=self.model_registry,
            tool_registry=self.tool_registry,
            router=self.router,
            config=config,
        )

    def _prepare_agent_config(self, agent_config: Optional[AgentConfig], debate_config: DebateConfig) -> AgentConfig:
        agent_config = agent_config or self.base_agent_config
        if debate_config.enable_reflection and not agent_config.reflection:
            from .reflection import ReflectionConfig

            agent_config = AgentConfig(reflection=ReflectionConfig(enabled=True, max_rounds=1))
        return agent_config

    def _build_debate_prompt(
        self,
        question: str,
        agent_id: str,
        own_answer: str,
        others: Dict[str, str],
    ) -> str:
        other_lines = [f"{aid}: {ans}" for aid, ans in others.items()]
        others_block = "\n".join(other_lines) if other_lines else "None provided."
        return (
            f"You are agent '{agent_id}' participating in a debate.\n"
            f"Question: {question}\n"
            f"Your previous answer: {own_answer}\n"
            f"Other agents' latest answers:\n{others_block}\n"
            "Provide a revised answer or argument."
        )

    def _compute_consensus(
        self,
        question: str,
        final_answers: Dict[str, str],
        transcript: List[DebateTurn],
        cfg: DebateConfig,
        context: ExecutionContext,
    ) -> DebateOutcome:
        judge_prompt = cfg.judge_prompt or self._default_judge_prompt(question, final_answers, transcript)
        response = self.router.generate(messages=[{"role": "user", "content": judge_prompt}])
        parsed = self._parse_judge_response(response, final_answers)
        outcome = DebateOutcome(
            transcript=transcript,
            consensus_summary=parsed["consensus_summary"],
            chosen_answer=parsed["chosen_answer"],
            scores=parsed["scores"],
            final_answers=dict(final_answers),
        )
        self._record_memory_consensus(context, question, outcome)
        return outcome

    def _default_judge_prompt(
        self, question: str, final_answers: Dict[str, str], transcript: List[DebateTurn]
    ) -> str:
        answers_block = "\n".join(f"{aid}: {ans}" for aid, ans in final_answers.items())
        rounds_summary = "\n".join(
            f"[Round {t.round_index}] {t.agent_id}: {t.message}" for t in transcript
        )
        return (
            "You are the judge for a multi-agent debate.\n"
            f"Question: {question}\n"
            f"Final answers:\n{answers_block}\n\n"
            "Transcript summary:\n"
            f"{rounds_summary}\n\n"
            "Return a JSON object with fields: "
            "'consensus_summary', 'chosen_answer', and 'scores' (mapping agent_id to score between 0 and 1)."
        )

    def _parse_judge_response(self, response, final_answers: Dict[str, str]) -> Dict[str, object]:
        text = self._extract_response_text(response)
        consensus_summary = text
        chosen_answer = next(iter(final_answers.values()), "")
        scores = {aid: 1.0 for aid in final_answers.keys()}
        try:
            payload = json.loads(text)
            consensus_summary = payload.get("consensus_summary") or consensus_summary
            chosen_answer = payload.get("chosen_answer") or chosen_answer
            scores = payload.get("scores") or scores
        except Exception:
            pass
        return {
            "consensus_summary": consensus_summary,
            "chosen_answer": chosen_answer,
            "scores": scores,
        }

    def _extract_response_text(self, response) -> str:
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

    def _record_memory_turn(self, context: ExecutionContext, question: str, turn: DebateTurn) -> None:
        memory_engine = getattr(context, "memory_engine", None)
        if not memory_engine:
            return
        message = f"agent_debate_turn | agent={turn.agent_id} | round={turn.round_index} | question={question} | message={turn.message}"
        try:
            memory_engine.record_conversation(turn.agent_id, message, role="system")
        except Exception:
            pass

    def _record_memory_consensus(self, context: ExecutionContext, question: str, outcome: DebateOutcome) -> None:
        memory_engine = getattr(context, "memory_engine", None)
        if not memory_engine:
            return
        summary = (
            f"agent_debate_consensus | question={question} | summary={outcome.consensus_summary} | "
            f"chosen={outcome.chosen_answer} | scores={outcome.scores}"
        )
        try:
            memory_engine.record_conversation("debate", summary, role="system")
        except Exception:
            pass
