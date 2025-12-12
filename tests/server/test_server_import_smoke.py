import namel3ss.server as server
from fastapi import FastAPI


def test_server_imports_and_app_creation(tmp_path):
    app = server.create_app(project_root=tmp_path)
    assert isinstance(app, FastAPI)
    assert callable(server.create_app)
