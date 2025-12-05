from datetime import datetime, timezone

from namel3ss.optimizer.models import (
    EvaluationCase,
    EvaluationRun,
    Suggestion,
    SuggestionStatus,
    TargetType,
)


def test_models_instantiation():
    case = EvaluationCase(id="c1", input={"q": "hi"}, expected={"goal": "answer"})
    run = EvaluationRun(
        id="r1",
        target_type=TargetType.AGENT,
        target_name="helper",
        created_at=datetime.now(timezone.utc),
        cases=[case],
        metrics_summary={"avg_latency": 0.1},
        raw_results=[],
    )
    sugg = Suggestion(
        id="s1",
        target_type=TargetType.AGENT,
        target_name="helper",
        created_at=datetime.now(timezone.utc),
        status=SuggestionStatus.PENDING,
        description="Improve prompt",
        change_spec={"type": "prompt_update"},
        evaluation_run_id=run.id,
        metadata={},
    )
    assert run.target_name == "helper"
    assert sugg.status == SuggestionStatus.PENDING
