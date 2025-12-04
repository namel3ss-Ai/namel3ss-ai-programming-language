import os
import subprocess
import sys
from pathlib import Path

from namel3ss.version import __version__


def test_cli_version_flag():
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
    result = subprocess.run(
        [sys.executable, "-m", "namel3ss.cli", "--version"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    output = result.stdout.strip()
    assert __version__ in output
    assert "Python" in output
    # basic PEP440-ish check
    assert any(part.isdigit() for part in __version__.split("."))
