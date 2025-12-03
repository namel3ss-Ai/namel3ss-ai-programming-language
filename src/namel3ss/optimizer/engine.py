"""
Optimizer engine that scans metrics/traces and generates suggestions.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from ..metrics.tracker import MetricsTracker
from ..memory.engine import MemoryEngine
from ..obs.tracer import Tracer
from ..ai.router import ModelRouter
from .models import OptimizationKind, OptimizationStatus, OptimizationSuggestion
from .storage import OptimizerStorage
from ..secrets.manager import SecretsManager


class OptimizerEngine:
    def __init__(
        self,
        storage: OptimizerStorage,
        metrics: MetricsTracker,
        memory_engine: Optional[MemoryEngine] = None,
        tracer: Optional[Tracer] = None,
        router: Optional[ModelRouter] = None,
        secrets: Optional[SecretsManager] = None,
    ) -> None:
        self.storage = storage
        self.metrics = metrics
        self.memory_engine = memory_engine
        self.tracer = tracer
        self.router = router
        self.secrets = secrets or SecretsManager()

    def scan(self, snapshot: Optional[dict] = None, auto_apply: bool = False) -> List[OptimizationSuggestion]:
        snap = snapshot or self.metrics.snapshot()
        suggestions: List[OptimizationSuggestion] = []
        suggestions.extend(self._scan_flows(snap))
        suggestions.extend(self._scan_memory())
        suggestions.extend(self._scan_ai_assistant(snap))
        for s in suggestions:
            self.storage.save(s)
        return suggestions

    def _scan_flows(self, snap: dict) -> List[OptimizationSuggestion]:
        results: List[OptimizationSuggestion] = []
        flow_metrics = snap.get("flow_metrics", {})
        for key, value in flow_metrics.items():
            if key.startswith("flow:") and key.endswith(":runs"):
                flow_name = key.split(":")[1]
                runs = value
                errors = flow_metrics.get(f"flow:{flow_name}:errors", 0)
                if runs and errors / runs > 0.3:
                    results.append(
                        self._make_suggestion(
                            kind=OptimizationKind.FLOW_OPTIMIZATION,
                            severity="warning",
                            title=f"Reduce errors in flow {flow_name}",
                            description="High error rate detected; consider adding retries and timeouts.",
                            reason="error_rate_high",
                            target={"flow": flow_name},
                            actions=[
                                {
                                    "type": "set_flow_timeout",
                                    "target": {"flow_name": flow_name},
                                    "params": {"timeout": 30},
                                },
                                {
                                    "type": "tool_retry",
                                    "target": {"tool_name": "echo"},
                                    "params": {"retries": 2},
                                },
                            ],
                            metrics_snap={"runs": runs, "errors": errors},
                        )
                    )
        return results

    def _scan_memory(self) -> List[OptimizationSuggestion]:
        results: List[OptimizationSuggestion] = []
        if not self.memory_engine:
            return results
        for space in self.memory_engine.spaces.keys():
            items = self.memory_engine.list_all(space)
            if len(items) > 50:
                results.append(
                    self._make_suggestion(
                        kind=OptimizationKind.MEMORY_POLICY,
                        severity="info",
                        title=f"Prune memory space {space}",
                        description="Memory space is large; consider pruning.",
                        reason="memory_bloat",
                        target={"memory": space},
                        actions=[
                            {
                                "type": "memory_policy",
                                "target": {"memory": space},
                                "params": {"strategy": "fifo", "limit": 50},
                            }
                        ],
                        metrics_snap={"items": len(items)},
                    )
                )
        return results

    def _scan_ai_assistant(self, snap: dict) -> List[OptimizationSuggestion]:
        results: List[OptimizationSuggestion] = []
        # Optional AI-based analyzer: only if enabled and router available.
        if not self.secrets.is_enabled("N3_OPTIMIZER_AI"):
            return results
        if not self.router:
            return results
        try:
            selected = self.router.select_model()
            # Use selected model info as part of suggestion
            results.append(
                self._make_suggestion(
                    kind=OptimizationKind.MODEL_SELECTION,
                    severity="info",
                    title="AI-assisted model review",
                    description="AI suggests reviewing model selection for cost efficiency.",
                    reason="ai_review",
                    target={"model": selected.model_name},
                    actions=[
                        {
                            "type": "set_model",
                            "target": {"model_name": selected.model_name},
                            "params": {"provider": selected.provider_name},
                        }
                    ],
                    metrics_snap=snap,
                )
            )
        except Exception:
            # ignore if selection fails
            pass
        return results

    def _make_suggestion(
        self,
        kind: OptimizationKind,
        severity: str,
        title: str,
        description: str,
        reason: str,
        target: dict,
        actions: list[dict],
        metrics_snap: dict,
    ) -> OptimizationSuggestion:
        return OptimizationSuggestion(
            id=str(uuid.uuid4()),
            kind=kind,
            created_at=datetime.now(timezone.utc),
            status=OptimizationStatus.PENDING,
            severity=severity,
            title=title,
            description=description,
            reason=reason,
            target=target,
            actions=actions,
            metrics_snapshot=metrics_snap,
        )
