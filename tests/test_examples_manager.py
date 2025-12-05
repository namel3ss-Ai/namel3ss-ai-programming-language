from namel3ss.examples.manager import list_examples, resolve_example_path


def test_list_examples_includes_defaults():
    examples = list_examples()
    assert "hello_world" in examples
    assert "multi_agent_debate" in examples
    assert "rag_qa" in examples
    assert "support_bot" in examples


def test_resolve_example_path_exists():
    path = resolve_example_path("hello_world")
    assert path.exists()
    assert path.name == "hello_world.ai"
    assert resolve_example_path("rag_qa").exists()
    assert resolve_example_path("support_bot").exists()


def test_resolve_example_path_missing():
    try:
        resolve_example_path("does_not_exist")
    except FileNotFoundError as exc:
        assert "does_not_exist" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected FileNotFoundError")
