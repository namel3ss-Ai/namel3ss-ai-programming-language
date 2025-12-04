import json
from pathlib import Path

from namel3ss.examples.catalog import ExamplesCatalog


def test_catalog_lists_examples(tmp_path: Path):
    ex_root = tmp_path / "examples"
    (ex_root / "agents").mkdir(parents=True)
    meta = {
        "name": "Agent Demo",
        "category": "agents",
        "description": "Demo agent",
        "tags": ["agent"],
    }
    (ex_root / "agents" / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    catalog = ExamplesCatalog(ex_root)
    examples = catalog.list_examples()
    assert len(examples) == 1
    assert examples[0].category == "agents"
    assert catalog.get_example("agents").name == "Agent Demo"
