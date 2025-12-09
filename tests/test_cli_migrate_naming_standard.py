import shutil
import tempfile
from pathlib import Path

from namel3ss.cli import main


def _write_sample(tmp: Path) -> Path:
    sample = (
        'flow "legacy":\n'
        '  step "s":\n'
        "    let total = base + bonus\n"
        "    set state.total = total\n"
    )
    path = tmp / "sample.ai"
    path.write_text(sample, encoding="utf-8")
    return path


def test_cli_migrate_dry_run_does_not_modify():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sample = _write_sample(tmp)
        before = sample.read_text(encoding="utf-8")
        main(["migrate", "naming-standard", "--path", str(tmp), "--dry-run"])
        after = sample.read_text(encoding="utf-8")
        assert before == after


def test_cli_migrate_write_creates_backup_and_rewrites():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        sample = _write_sample(tmp)
        main(["migrate", "naming-standard", "--path", str(tmp), "--write"])
        updated = sample.read_text(encoding="utf-8")
        backup = sample.with_suffix(".ai.bak")
        assert backup.exists()
        assert 'flow is "legacy":' in updated
        assert "let total be base + bonus" in updated
