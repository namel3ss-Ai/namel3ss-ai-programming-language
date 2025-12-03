from namel3ss.metrics.tracker import MetricsTracker


def test_metrics_tracker_records_and_summarizes():
    tracker = MetricsTracker()
    tracker.record_ai_call(provider="dummy", tokens_in=10, tokens_out=20, cost=0.5)
    tracker.record_tool_call(provider="echo", cost=0.1)
    tracker.record_agent_run(provider="agent", cost=0.2)
    snap = tracker.snapshot()
    assert snap["total_cost"] == 0.8
    assert snap["by_operation"]["ai_call"]["tokens_out"] == 20
    assert snap["by_operation"]["tool_call"]["count"] == 1
