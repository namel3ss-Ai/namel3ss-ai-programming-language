from pathlib import Path

from namel3ss.diagnostics.runner import collect_diagnostics


EXAMPLES = [
    "hello_world",
    "multi_agent_debate",
    "rag_qa",
    "support_bot",
]


def test_examples_have_no_errors():
    for name in EXAMPLES:
        path = Path(__file__).resolve().parents[2] / "examples" / name / f"{name}.ai"
        diags, summary = collect_diagnostics([path], strict=False)
        assert summary["errors"] == 0, f"{name} has errors: {diags}"
