import json
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from namel3ss.plugins.registry import PluginRegistry
from namel3ss.examples.catalog import ExamplesCatalog
from namel3ss.security.context import SecurityContext
from namel3ss.security.oauth import get_oauth_context
from namel3ss.security.rbac import require_permissions


def build_app(tmp_path: Path):
    # setup plugin manifest
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "p1").mkdir()
    manifest = {
        "name": "p1",
        "version": "1.0.0",
        "description": "P1",
        "entry_point": "demo:Plugin",
        "tags": ["demo"],
    }
    (plugins_dir / "p1" / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    # setup example
    examples_dir = tmp_path / "examples"
    (examples_dir / "ex1").mkdir(parents=True)
    (examples_dir / "ex1" / "meta.json").write_text(
        json.dumps({"name": "Ex1", "category": "agents", "description": "Example", "tags": []}), encoding="utf-8"
    )

    registry = PluginRegistry(builtins_dir=tmp_path / "none", user_dir=plugins_dir)
    catalog = ExamplesCatalog(examples_dir)

    app = FastAPI()

    def fake_ctx():
        return SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["admin"], scopes=[], auth_scheme="api_key")

    app.dependency_overrides[get_oauth_context] = fake_ctx

    @app.get("/api/ecosystem/plugins")
    def list_plugins(_ctx=Depends(require_permissions(["ecosystem:read"]))):
        return {
            "plugins": [
                {"name": p.name, "version": p.version, "description": p.description, "tags": p.tags}
                for p in registry.list_plugins()
            ]
        }

    @app.get("/api/ecosystem/examples")
    def list_examples(_ctx=Depends(require_permissions(["ecosystem:read"]))):
        return {
            "examples": [
                {"id": ex.id, "name": ex.name, "category": ex.category, "description": ex.description}
                for ex in catalog.list_examples()
            ]
        }

    return app


def test_ecosystem_api(tmp_path: Path):
    app = build_app(tmp_path)
    client = TestClient(app)
    assert client.get("/api/ecosystem/plugins").status_code == 200
    assert client.get("/api/ecosystem/examples").status_code == 200
