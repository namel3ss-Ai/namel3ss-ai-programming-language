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


def test_studio_rag_endpoints(tmp_path: Path):
    rag_source = textwrap.dedent(
        """
        model is "deterministic":
          provider is "openai:gpt-4.1-mini"

        frame is "docs":
          file is "docs.csv"
          has headers

        vector_store is "docs_vs":
          backend is "memory"
          frame is "docs"
          text_column is "content"
          id_column is "id"
          embedding_model is "deterministic"

        rag pipeline is "support_rag":
          use vector_store "docs_vs"
          stage is "retrieve":
            type is "vector_retrieve"
            top_k is 3
        """
    )
    (tmp_path / "main.ai").write_text(rag_source, encoding="utf-8")
    client = _client(tmp_path)

    listing = client.get("/api/studio/rag/pipelines", headers={"X-API-Key": "dev-key"})
    assert listing.status_code == 200
    pipelines = listing.json()["pipelines"]
    assert pipelines
    pid = pipelines[0]["id"]

    detail = client.get(f"/api/studio/rag/pipelines/{pid}", headers={"X-API-Key": "dev-key"})
    assert detail.status_code == 200
    detail_body = detail.json()["pipeline"]
    assert detail_body["stages"]

    update = client.post(
        f"/api/studio/rag/pipelines/{pid}/update_stage",
        json={"stage": detail_body["stages"][-1]["name"], "changes": {"top_k": 10}},
        headers={"X-API-Key": "dev-key"},
    )
    assert update.status_code == 200
    assert update.json()["stage"]["top_k"] == 10

    preview = client.post(
        f"/api/studio/rag/pipelines/{pid}/preview",
        json={"query": "hello world"},
        headers={"X-API-Key": "dev-key"},
    )
    assert preview.status_code == 200
    preview_body = preview.json()
    assert len(preview_body["stages"]) == len(detail_body["stages"])
