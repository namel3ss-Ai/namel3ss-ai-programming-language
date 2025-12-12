from pathlib import Path
import sys
import os
import textwrap

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from namel3ss.server import create_app


def _client(tmp_path: Path) -> TestClient:
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        return TestClient(create_app())
    finally:
        os.chdir(prev)


def test_studio_macro_inspector(tmp_path: Path):
    macro_source = textwrap.dedent(
        '''
        use macro is "crud_ui" with:
          entity is "Task"
          fields:
            field is "name":
              type is "string"
        '''
    )
    (tmp_path / "macros.ai").write_text(macro_source, encoding="utf-8")
    client = _client(tmp_path)

    listing = client.get("/api/studio/macros", headers={"X-API-Key": "dev-key"})
    assert listing.status_code == 200
    macros = listing.json()["macros"]
    assert macros

    macro_id = macros[0]["id"]
    detail = client.get(f"/api/studio/macros/{macro_id}", headers={"X-API-Key": "dev-key"})
    assert detail.status_code == 200
    artifacts = detail.json()["macro"]["artifacts"]
    assert "flows" in artifacts and isinstance(artifacts["flows"], list)
