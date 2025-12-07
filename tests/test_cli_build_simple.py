from pathlib import Path
import os

from namel3ss.cli import main


def test_build_simple_desktop_defaults(tmp_path: Path):
    src = tmp_path / "app.ai"
    src.write_text('app "demo" version "0.0.1"\n', encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        main(["build", "desktop"])
        assert (tmp_path / "build/desktop").exists()
    finally:
        os.chdir(prev)


def test_build_simple_requires_file_when_multiple(tmp_path: Path):
    (tmp_path / "a1.ai").write_text('app "a1" version "0.0.1"\n', encoding="utf-8")
    (tmp_path / "a2.ai").write_text('app "a2" version "0.0.1"\n', encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        try:
            main(["build", "desktop"])
            assert False, "expected failure"
        except SystemExit as exc:
            assert exc.code != 0
    finally:
        os.chdir(prev)


def test_build_simple_mobile_with_file(tmp_path: Path):
    (tmp_path / "app.ai").write_text('app "demo" version "0.0.1"\n', encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        main(["build", "mobile", "app.ai"])
        assert (tmp_path / "build/mobile").exists()
    finally:
        os.chdir(prev)
