from pathlib import Path

import pytest

from namel3ss.cli import main
from namel3ss.errors import ParseError


def test_cli_fmt_write(tmp_path):
    file_path = tmp_path / "app.ai"
    file_path.write_text('app "demo":\n description "Hi"\n', encoding="utf-8")
    main(["fmt", str(file_path)])
    content = file_path.read_text(encoding="utf-8")
    assert '  description "Hi"' in content
    assert content.endswith("\n")


def test_cli_fmt_check_detects_changes(tmp_path):
    file_path = tmp_path / "app.ai"
    file_path.write_text('app "demo":\n description "Hi"\n', encoding="utf-8")
    with pytest.raises(SystemExit):
        main(["fmt", str(file_path), "--check"])


def test_cli_fmt_check_clean(tmp_path):
    file_path = tmp_path / "app.ai"
    file_path.write_text('app "demo":\n  description "Hi"\n', encoding="utf-8")
    main(["fmt", str(file_path), "--check"])


def test_cli_fmt_parse_error(tmp_path):
    file_path = tmp_path / "bad.ai"
    file_path.write_text('app "demo"\n  description "Hi"\n', encoding="utf-8")  # missing colon
    with pytest.raises(SystemExit):
        main(["fmt", str(file_path)])
