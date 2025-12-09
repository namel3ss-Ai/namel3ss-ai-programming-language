from namel3ss.secrets.manager import EnvSecretsManager
import pytest


def test_env_secrets_manager_reads_env(monkeypatch):
    monkeypatch.setenv("N3_TEST_SECRET", "value123")
    mgr = EnvSecretsManager()
    assert mgr.get_secret("N3_TEST_SECRET") == "value123"
    assert mgr.is_enabled("N3_TEST_SECRET") is True


def test_env_secrets_manager_require_secret(monkeypatch):
    mgr = EnvSecretsManager(env={"FOO": "bar"})
    assert mgr.require_secret("FOO") == "bar"
    with pytest.raises(Exception):
        mgr.require_secret("MISSING")

