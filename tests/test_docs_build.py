import subprocess
import sys
from pathlib import Path
import pytest


def test_mkdocs_build(tmp_path):
    try:
        import mkdocs  # noqa: F401
    except ImportError:
        pytest.skip("mkdocs not installed in environment")
    site_dir = tmp_path / "site"
    cmd = [sys.executable, "-m", "mkdocs", "build", "--config-file", "mkdocs.yml", "--site-dir", str(site_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert site_dir.exists()
