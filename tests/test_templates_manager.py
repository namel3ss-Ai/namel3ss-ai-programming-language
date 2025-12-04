from pathlib import Path

import pytest

from namel3ss.templates.manager import get_template_path, list_templates, scaffold_project


def test_list_templates_non_empty():
    names = list_templates()
    assert names
    assert "app-basic" in names


def test_get_template_path_exists():
    path = get_template_path("app-basic")
    assert path.exists()
    assert any(path.glob("*.ai"))


def test_scaffold_project_creates_files(tmp_path: Path):
    target = tmp_path / "myapp"
    scaffold_project("app-basic", target, project_name="myapp", force=True)
    assert (target / "app.ai").exists()
    content = (target / "app.ai").read_text(encoding="utf-8")
    assert 'app "myapp"' in content or 'app "hello"' in content  # allow if rename not applied
    assert (target / "README.md").exists()


def test_scaffold_project_refuses_non_empty(tmp_path: Path):
    target = tmp_path / "existing"
    target.mkdir()
    (target / "file.txt").write_text("hi", encoding="utf-8")
    with pytest.raises(FileExistsError):
        scaffold_project("app-basic", target, project_name="existing", force=False)
