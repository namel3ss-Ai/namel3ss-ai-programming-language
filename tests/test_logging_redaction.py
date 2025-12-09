import os

from namel3ss.observability.logging_utils import redact_prompt, redact_metadata, redact_event


def test_prompt_redaction_default():
    assert redact_prompt("secret prompt") == "[REDACTED]"


def test_prompt_redaction_disabled(monkeypatch):
    monkeypatch.setenv("N3_LOG_REDACT_PROMPTS", "false")
    assert redact_prompt("secret prompt") == "secret prompt"
    monkeypatch.delenv("N3_LOG_REDACT_PROMPTS", raising=False)


def test_metadata_redaction():
    meta = {"email": "user@example.com", "other": "ok"}
    redacted = redact_metadata(meta)
    assert redacted["email"] == "[REDACTED]"
    assert redacted["other"] == "ok"


def test_redact_event_combines_prompt_and_metadata(monkeypatch):
    event = {"prompt": "hello", "metadata": {"token": "abc", "x": "y"}}
    cleaned = redact_event(event)
    assert cleaned["prompt"] == "[REDACTED]"
    assert cleaned["metadata"]["token"] == "[REDACTED]"
    assert cleaned["metadata"]["x"] == "y"
    monkeypatch.setenv("N3_LOG_REDACT_PROMPTS", "false")
    cleaned2 = redact_event(event)
    assert cleaned2["prompt"] == "hello"
    monkeypatch.delenv("N3_LOG_REDACT_PROMPTS", raising=False)
