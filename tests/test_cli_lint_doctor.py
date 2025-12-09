import json
import os
import subprocess
import sys
from pathlib import Path


def _env():
    env = os.environ.copy()
    src_path = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")
    return env


def test_lint_passes_on_valid_file(tmp_path: Path):
    ai = tmp_path / "ok.ai"
    ai.write_text(
        '\n'.join(
            [
                'flow is "main":',
                '  step is "one":',
                "    return",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "namel3ss.cli", "lint", str(ai)],
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lint_strict_upgrades_warnings(tmp_path: Path):
    ai = tmp_path / "warn.ai"
    ai.write_text(
        '\n'.join(
            [
                'define helper "unused":',
                "  return",
                "",
                'flow is "main":',
                '  step is "one":',
                "    return",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "namel3ss.cli", "lint", str(ai), "--strict"],
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert result.returncode != 0
    assert "unused" in result.stdout.lower()


def test_lint_json_reports_parse_codes(tmp_path: Path):
    ai = tmp_path / "bad.ai"
    ai.write_text(
        '\n'.join(
            [
                'flow is "main":',
                '  step is "one":',
                '    navigate "home"',
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-m", "namel3ss.cli", "lint", str(ai), "--json"],
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    codes = {d.get("code") for d in payload.get("lint", [])}
    assert "N3L-PARSE-NAVIGATE" in codes
    assert payload["summary"]["errors"] >= 1


def test_doctor_reports_versions():
    result = subprocess.run(
        [sys.executable, "-m", "namel3ss.cli", "doctor"],
        capture_output=True,
        text=True,
        env=_env(),
    )
    assert result.returncode == 0
    stdout = result.stdout
    assert "Namel3ss version" in stdout
    assert "IR version" in stdout
