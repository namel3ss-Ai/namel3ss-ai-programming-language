from namel3ss.observability.metrics import MetricsRegistry


def test_metrics_registry_aggregates_steps_and_flows():
    reg = MetricsRegistry()
    reg.record_step("s1", duration_seconds=1.0, cost=0.1)
    reg.record_step("s1", duration_seconds=2.0, cost=0.2)
    reg.record_flow("flowA", duration_seconds=3.0, cost=0.3)
    reg.record_flow("flowA", duration_seconds=1.0, cost=0.1)

    step_snapshot = reg.get_step_metrics()["s1"]
    assert step_snapshot.count == 2
    assert abs(step_snapshot.total_duration_seconds - 3.0) < 1e-6
    assert abs(step_snapshot.total_cost - 0.3) < 1e-6

    flow_snapshot = reg.get_flow_metrics()["flowA"]
    assert flow_snapshot.total_runs == 2
    assert abs(flow_snapshot.avg_duration_seconds - 2.0) < 1e-6
    assert abs(flow_snapshot.avg_cost - 0.2) < 1e-6
