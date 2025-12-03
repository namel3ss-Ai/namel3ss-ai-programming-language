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
                raise NotImplementedError("Waiting for Phase 9+ Cloudflare adapter")
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
