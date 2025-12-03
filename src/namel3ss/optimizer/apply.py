"""
Applying optimization suggestions to overlays.
"""

from __future__ import annotations

from typing import Optional

from .models import OptimizationSuggestion, OptimizationStatus
from .overlays import OverlayStore, RuntimeOverlay
from .storage import OptimizerStorage
from ..obs.tracer import Tracer


class SuggestionApplier:
    def __init__(self, overlay_store: OverlayStore, storage: OptimizerStorage, tracer: Optional[Tracer] = None) -> None:
        self.overlay_store = overlay_store
        self.storage = storage
        self.tracer = tracer

    def apply(self, suggestion: OptimizationSuggestion) -> None:
        overlay = self.overlay_store.load()
        for action in suggestion.actions:
            atype = action.get("type")
            if atype == "set_model":
                target = action.get("target", {})
                name = target.get("model_name")
                if name:
                    overlay.models[name] = action.get("params", {})
            elif atype == "set_flow_parallelism":
                flow = action.get("target", {}).get("flow_name")
                if flow:
                    overlay.flows.setdefault(flow, {})["parallelism"] = action.get("params", {}).get("parallelism")
            elif atype == "set_flow_timeout":
                flow = action.get("target", {}).get("flow_name")
                if flow:
                    overlay.flows.setdefault(flow, {})["timeout"] = action.get("params", {}).get("timeout")
            elif atype == "update_prompt":
                prompt = action.get("target", {}).get("prompt_id")
                if prompt:
                    overlay.prompts[prompt] = action.get("params", {}).get("content", "")
            elif atype == "memory_policy":
                space = action.get("target", {}).get("memory")
                if space:
                    overlay.memory_policies[space] = action.get("params", {})
            elif atype == "tool_retry":
                tool = action.get("target", {}).get("tool_name")
                if tool:
                    overlay.tools.setdefault(tool, {})["retries"] = action.get("params", {}).get("retries", 1)
            else:
                raise ValueError(f"Unsupported action type {atype}")
        self.overlay_store.save(overlay)
        suggestion.status = OptimizationStatus.APPLIED
        self.storage.update(suggestion)
        if self.tracer:
            self.tracer.record_flow_event("optimizer.apply", {"suggestion_id": suggestion.id})
