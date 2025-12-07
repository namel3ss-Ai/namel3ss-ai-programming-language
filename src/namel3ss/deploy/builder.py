"""
Deployment builder for multiple targets.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import List

from .models import BuildArtifact, DeployTargetConfig, DeployTargetKind


class DeployBuilder:
    def __init__(self, source: str, output_root: Path) -> None:
        self.source = source
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def build(self, targets: List[DeployTargetConfig]) -> List[BuildArtifact]:
        artifacts: List[BuildArtifact] = []
        for target in targets:
            if target.kind == DeployTargetKind.SERVER:
                artifacts.append(self._build_server(target))
            elif target.kind == DeployTargetKind.WORKER:
                artifacts.append(self._build_worker(target))
            elif target.kind == DeployTargetKind.DOCKER:
                artifacts.append(self._build_docker(target))
            elif target.kind == DeployTargetKind.SERVERLESS_AWS:
                artifacts.append(self._build_lambda(target))
            elif target.kind == DeployTargetKind.SERVERLESS_CLOUDFLARE:
                artifacts.append(self._build_cloudflare(target))
            elif target.kind == DeployTargetKind.DESKTOP:
                artifacts.append(self._build_desktop(target))
            elif target.kind == DeployTargetKind.MOBILE:
                artifacts.append(self._build_mobile(target))
            else:
                raise ValueError(f"Unsupported target {target.kind}")
        return artifacts

    def _write_source(self, dir_path: Path) -> Path:
        dir_path.mkdir(parents=True, exist_ok=True)
        source_path = dir_path / "app.ai"
        source_path.write_text(self.source, encoding="utf-8")
        return source_path

    def _build_server(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_source(out_dir)
        entry = out_dir / "server_entry.py"
        # copy template from package
        from importlib.resources import files

        entry.write_text(files("namel3ss.deploy").joinpath("server_entry.py").read_text(encoding="utf-8"), encoding="utf-8")
        metadata = {"entrypoint": "namel3ss.deploy.server_entry:app"}
        (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return BuildArtifact(kind=target.kind, path=entry, metadata=metadata)

    def _build_worker(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_source(out_dir)
        from importlib.resources import files

        entry = out_dir / "worker_entry.py"
        entry.write_text(files("namel3ss.deploy").joinpath("worker_entry.py").read_text(encoding="utf-8"), encoding="utf-8")
        metadata = {"entrypoint": str(entry)}
        (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return BuildArtifact(kind=target.kind, path=entry, metadata=metadata)

    def _build_docker(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        self._write_source(out_dir)
        server_docker = out_dir / "Dockerfile.server"
        worker_docker = out_dir / "Dockerfile.worker"
        server_docker.write_text(
            self._dockerfile_content("server_entry.py", target.options.get("base_image", "python:3.11-slim")), encoding="utf-8"
        )
        worker_docker.write_text(
            self._dockerfile_content("worker_entry.py", target.options.get("base_image", "python:3.11-slim")), encoding="utf-8"
        )
        return BuildArtifact(kind=target.kind, path=server_docker, metadata={"worker_dockerfile": str(worker_docker)})

    def _dockerfile_content(self, entry_name: str, base: str) -> str:
        return f"""
FROM {base}
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir .
ENV N3_SOURCE_PATH=/app/app.ai
CMD ["python", "-m", "namel3ss.deploy.{entry_name.replace('.py','')}"]
""".strip()

    def _build_lambda(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        lambda_dir = out_dir / "lambda"
        lambda_dir.mkdir(parents=True, exist_ok=True)
        source_path = self._write_source(lambda_dir)
        from importlib.resources import files

        handler_path = lambda_dir / "aws_lambda.py"
        handler_path.write_text(files("namel3ss.deploy").joinpath("aws_lambda.py").read_text(encoding="utf-8"), encoding="utf-8")
        zip_path = out_dir / "lambda_bundle.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            for path in [handler_path, source_path]:
                zf.write(path, path.name)
        metadata = {"handler": "aws_lambda.lambda_handler"}
        return BuildArtifact(kind=target.kind, path=zip_path, metadata=metadata)

    def _build_cloudflare(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        source_path = self._write_source(out_dir)
        worker_path = out_dir / "worker.js"
        worker_path.write_text(self._cloudflare_worker_template(), encoding="utf-8")
        wrangler_path = out_dir / "wrangler.toml"
        wrangler_path.write_text(self._wrangler_content(target), encoding="utf-8")
        readme = out_dir / "README.md"
        readme.write_text(
            "\n".join(
                [
                    "# Namel3ss Cloudflare Worker",
                    "",
                    "This bundle was generated for the `serverless-cloudflare` target.",
                    "",
                    "Quick start:",
                    "  1) Install Wrangler: https://developers.cloudflare.com/workers/wrangler/install-and-update/",
                    "  2) Configure account_id/routes in wrangler.toml as needed.",
                    "  3) Run locally: `wrangler dev`",
                    "  4) Deploy: `wrangler publish`",
                    "",
                    "Requests are optionally forwarded to `env.N3_ORIGIN` (configure in wrangler.toml [vars]).",
                ]
            ),
            encoding="utf-8",
        )
        metadata = {
            "handler": "worker.fetch",
            "config": str(wrangler_path),
            "notes": "Run `wrangler dev` or `wrangler publish` inside this directory.",
            "source": str(source_path),
        }
        return BuildArtifact(kind=target.kind, path=worker_path, metadata=metadata)

    def _cloudflare_worker_template(self) -> str:
        return (
            "// Cloudflare Worker entry for Namel3ss\n"
            "export default {\n"
            "  async fetch(request, env, ctx) {\n"
            "    const method = request.method || 'GET';\n"
            "    const forwardOrigin = env && env.N3_ORIGIN;\n"
            "    if (forwardOrigin) {\n"
            "      const url = new URL(request.url);\n"
            "      const upstream = forwardOrigin.replace(/\\/$/, '') + url.pathname + url.search;\n"
            "      const init = { method, headers: request.headers };\n"
            "      if (!['GET','HEAD'].includes(method.toUpperCase())) {\n"
            "        init.body = request.body;\n"
            "      }\n"
            "      return fetch(upstream, init);\n"
            "    }\n"
            "    return new Response('Namel3ss Cloudflare worker is running. Set N3_ORIGIN to forward requests.', { status: 200 });\n"
            "  }\n"
            "};\n"
        )

    def _wrangler_content(self, target: DeployTargetConfig) -> str:
        name = target.options.get("service_name", "namel3ss-worker")
        account_id = target.options.get("account_id", "")
        route = target.options.get("route")
        routes = target.options.get("routes")
        compatibility_date = target.options.get("compatibility_date", "2024-01-01")
        lines = [
            f'name = "{name}"',
            'main = "worker.js"',
            f'compatibility_date = "{compatibility_date}"',
        ]
        if account_id:
            lines.append(f'account_id = "{account_id}"')
        if route:
            lines.append(f'route = "{route}"')
        if routes and isinstance(routes, list):
            quoted = ", ".join([f'"{r}"' for r in routes])
            lines.append(f"routes = [{quoted}]")
        lines.append("\n[vars]")
        env_map = dict(target.env or {})
        env_map.setdefault("N3_ORIGIN", "http://localhost:8000")
        env_map.setdefault("N3_SOURCE_PATH", "./app.ai")
        for k, v in env_map.items():
            lines.append(f'{k} = "{v}"')
        return "\n".join(lines)

    def _build_desktop(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = out_dir / "README.md"
        readme.write_text(
            "# Desktop Skeleton\n\nLoad Namel3ss Studio in a webview. Install Tauri/Electron and wire main.ts to serve localhost API.",
            encoding="utf-8",
        )
        config = out_dir / "electron.config.js"
        config.write_text(
            "module.exports = { appId: 'namel3ss.desktop', productName: 'Namel3ss', directories: { output: 'dist' } };",
            encoding="utf-8",
        )
        main_ts = out_dir / "main.ts"
        main_ts.write_text(
            "import { app, BrowserWindow } from 'electron';\napp.whenReady().then(()=>{const w=new BrowserWindow({width:1280,height:800});w.loadURL('http://localhost:8000');});",
            encoding="utf-8",
        )
        return BuildArtifact(kind=target.kind, path=readme, metadata={"note": "Template only"})

    def _build_mobile(self, target: DeployTargetConfig) -> BuildArtifact:
        out_dir = target.output_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        readme = out_dir / "README.md"
        readme.write_text(
            "# Mobile Skeleton\n\nUse React Native to call Namel3ss backend APIs. This template is a starting point.",
            encoding="utf-8",
        )
        package_json = out_dir / "package.json"
        package_json.write_text(
            json.dumps(
                {"name": "namel3ss-mobile", "version": "0.1.0", "private": True, "scripts": {"start": "expo start"}},
                indent=2,
            ),
            encoding="utf-8",
        )
        app_tsx = out_dir / "App.tsx"
        app_tsx.write_text(
            "import React from 'react'; import { Text, View } from 'react-native';\nexport default function App(){return <View><Text>Namel3ss Mobile</Text></View>;}",
            encoding="utf-8",
        )
        return BuildArtifact(kind=target.kind, path=readme, metadata={"note": "Template only"})
