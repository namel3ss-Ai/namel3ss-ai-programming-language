import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest

from namel3ss import cli


class _MockResponse:
    def __init__(self, payload):
        self.payload = payload

    def read(self):  # pragma: no cover - trivial
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_example_list_outputs_names(capsys):
    with patch(
        "namel3ss.cli.list_examples",
        return_value=["hello_world", "multi_agent_debate", "rag_qa", "support_bot"],
    ):
        cli.main(["example", "list"])
    out = capsys.readouterr().out
    assert "hello_world" in out
    assert "multi_agent_debate" in out
    assert "rag_qa" in out
    assert "support_bot" in out


def test_example_run_success(tmp_path: Path, capsys):
    example_file = tmp_path / "demo.ai"
    example_file.write_text('app "demo":\n  entry_page "home"\npage "home":\n  route "/"', encoding="utf-8")
    payload = {"result": {"app": {"message": "ok"}, "trace": {"id": "trace-123"}}}

    def _fake_urlopen(req):
        return _MockResponse(payload)

    with patch("namel3ss.cli.resolve_example_path", return_value=example_file):
        with patch("namel3ss.cli.urlopen", _fake_urlopen):
            cli.main(["example", "run", "demo", "--api-base", "http://localhost:8000"])
    out = capsys.readouterr().out
    assert "trace-123" in out
    assert "Open in Studio" in out


def test_example_run_missing():
    with patch("namel3ss.cli.resolve_example_path", side_effect=FileNotFoundError("missing")):
        with pytest.raises(SystemExit):
            cli.main(["example", "run", "missing"])  # type: ignore[arg-type]
