"""
Bundle generation utilities.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import json

from .. import ir, lexer, parser
from ..errors import Namel3ssError
from .models import AppBundle, BundleManifest


class Bundler:
    def from_ir(self, ir_program, *, bundle_type: str = "server") -> AppBundle:
        app_name = next(iter(ir_program.apps.keys()), "")
        bundle = AppBundle(
            app_name=app_name,
            pages=list(ir_program.pages.keys()),
            flows=list(ir_program.flows.keys()),
            agents=list(ir_program.agents.keys()),
            plugins=list(ir_program.plugins.keys()),
            models=list(ir_program.models.keys()),
            metadata=self._build_metadata(ir_program, bundle_type=bundle_type),
        )
        return bundle

    def build_bundle(
        self,
        source_path: Path,
        *,
        target: str = "server",
        output_dir: Path,
        name: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        include_studio: bool = False,
    ) -> Path:
        env = env or {}
        output_dir.mkdir(parents=True, exist_ok=True)
        program = self._compile(source_path)
        bundle = self.from_ir(program, bundle_type=target)
        bundle_name = name or (bundle.app_name or source_path.stem)
        bundle_root = output_dir / bundle_name
        bundle_root.mkdir(parents=True, exist_ok=True)

        # copy source for reference
        (bundle_root / "app.ai").write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

        entry_name = "server_entry.py" if target in {"server", "full", "desktop"} else "worker_entry.py"
        from importlib.resources import files

        entry_content = files("namel3ss.deploy").joinpath(entry_name).read_text(encoding="utf-8")
        (bundle_root / entry_name).write_text(entry_content, encoding="utf-8")

        assets: list[str] = []
        if include_studio or target == "desktop":
            studio_dir = Path("studio/dist")
            if studio_dir.exists():
                target_static = bundle_root / "static"
                target_static.mkdir(exist_ok=True)
                for path in studio_dir.rglob("*"):
                    if path.is_file():
                        rel = path.relative_to(studio_dir)
                        dest = target_static / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(path.read_bytes())
                        assets.append(str(dest.relative_to(bundle_root)))

        manifest = BundleManifest.from_bundle(
            app_name=bundle.app_name or bundle_name,
            entrypoint=entry_name,
            bundle_type=target,
            env=env,
            assets=assets,
            metadata=bundle.metadata,
        )
        (bundle_root / "manifest.json").write_text(json.dumps(asdict(manifest), indent=2), encoding="utf-8")
        return bundle_root

    def _compile(self, source_path: Path):
        tokens = lexer.Lexer(source_path.read_text(encoding="utf-8"), filename=str(source_path)).tokenize()
        module = parser.Parser(tokens).parse_module()
        try:
            return ir.ast_to_ir(module)
        except Namel3ssError:
            raise

    def _build_metadata(self, ir_program, bundle_type: str = "server") -> Dict[str, Any]:
        return {
            "version": "0.1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "counts": {
                "pages": len(ir_program.pages),
                "flows": len(ir_program.flows),
                "agents": len(ir_program.agents),
                "plugins": len(ir_program.plugins),
            },
            "bundle_type": bundle_type,
        }


def make_server_bundle(bundle: AppBundle) -> Dict[str, Any]:
    return {"type": "server", "bundle": asdict(bundle)}


def make_worker_bundle(bundle: AppBundle) -> Dict[str, Any]:
    return {"type": "worker", "bundle": asdict(bundle)}
