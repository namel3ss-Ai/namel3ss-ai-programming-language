from fastapi.testclient import TestClient

from src.namel3ss.server import create_app


def _client() -> TestClient:
    app = create_app()
    return TestClient(app)


def test_migrate_endpoint_rewrites_legacy_syntax():
    client = _client()
    legacy = (
        'flow "calculate_total":\n'
        '  step "sum":\n'
        "    let total = base + bonus\n"
        "    set state.total = total\n"
    )
    resp = client.post(
        "/api/migrate/naming-standard",
        json={"source": legacy, "fix_names": False},
    )
    assert resp.status_code == 200
    data = resp.json()
    migrated = data["source"]
    assert 'flow is "calculate_total":' in migrated
    assert "step is \"sum\":" in migrated
    assert "let total be base + bonus" in migrated
    assert "set state.total be total" in migrated
    summary = data["changes_summary"]
    assert summary["headers_rewritten"] == 2
    assert summary["let_rewritten"] == 1
    assert summary["set_rewritten"] == 1


def test_migrate_endpoint_renames_camel_case_when_requested():
    client = _client()
    legacy = (
        'flow "rename_test":\n'
        '  step "s":\n'
        "    let userEmail = input.email\n"
        "    set state.result = userEmail\n"
    )
    resp = client.post(
        "/api/migrate/naming-standard",
        json={"source": legacy, "fix_names": True},
    )
    assert resp.status_code == 200
    data = resp.json()
    migrated = data["source"]
    assert "user_email" in migrated
    assert "userEmail" not in migrated
    summary = data["changes_summary"]
    assert summary["names_renamed"]
    assert summary["names_renamed"][0]["to"] == "user_email"
