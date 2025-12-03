"""
Bundle generation utilities.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict

from .models import AppBundle


class Bundler:
    def from_ir(self, ir_program) -> AppBundle:
        app_name = next(iter(ir_program.apps.keys()), "")
        bundle = AppBundle(
            app_name=app_name,
            pages=list(ir_program.pages.keys()),
            flows=list(ir_program.flows.keys()),
            agents=list(ir_program.agents.keys()),
            plugins=list(ir_program.plugins.keys()),
            models=list(ir_program.models.keys()),
            metadata=self._build_metadata(ir_program),
        )
        return bundle

    def _build_metadata(self, ir_program) -> Dict[str, Any]:
        return {
            "version": "0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "pages": len(ir_program.pages),
                "flows": len(ir_program.flows),
                "agents": len(ir_program.agents),
                "plugins": len(ir_program.plugins),
            },
        }


def make_server_bundle(bundle: AppBundle) -> Dict[str, Any]:
    return {"type": "server", "bundle": asdict(bundle)}


def make_worker_bundle(bundle: AppBundle) -> Dict[str, Any]:
    return {"type": "worker", "bundle": asdict(bundle)}
