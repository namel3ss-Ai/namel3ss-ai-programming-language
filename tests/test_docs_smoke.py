from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _non_empty(path: Path) -> bool:
    return path.exists() and path.read_text(encoding="utf-8").strip() != ""


def test_docs_core_files_exist_and_non_empty():
    assert _non_empty(ROOT / "README.md")
    assert _non_empty(ROOT / "CHANGELOG.md")
    assert _non_empty(ROOT / "MIGRATING.md")
    assert _non_empty(ROOT / "docs" / "index.md")


def test_readme_mentions_quickstart():
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Quickstart" in content
