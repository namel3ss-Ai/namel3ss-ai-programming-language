from namel3ss.secrets.manager import SecretsManager


def test_secrets_manager_get_and_list():
    env = {"API_KEY": "123", "OTHER": "456"}
    mgr = SecretsManager(env)
    assert mgr.get("API_KEY") == "123"
    all_secrets = mgr.list()
    names = {s.name for s in all_secrets}
    assert "API_KEY" in names and "OTHER" in names
