from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from namel3ss.observability.metrics import default_metrics
from namel3ss.observability.tracing import default_tracer
from namel3ss.security.oauth import get_oauth_context
from namel3ss.security.context import SecurityContext
from namel3ss.security.rbac import require_permissions


def build_app():
    app = FastAPI()

    # seed metrics and spans
    default_metrics.record_flow("flowX", duration_seconds=1.0, cost=0.1)
    default_metrics.record_step("stepY", duration_seconds=0.5, cost=0.05)
    with default_tracer.span("http.test") as s:
        trace_id = s.context.trace_id

    def fake_ctx():
        return SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["admin"], scopes=[], auth_scheme="api_key")

    app.dependency_overrides[get_oauth_context] = fake_ctx

    @app.get("/api/observability/metrics/flows")
    def flows(_ctx=Depends(require_permissions(["metrics:read"]))):
        flows_data = [
            {
                "flow_name": name,
                "total_runs": snap.total_runs,
                "avg_duration_seconds": snap.avg_duration_seconds,
                "avg_cost": snap.avg_cost,
            }
            for name, snap in default_metrics.get_flow_metrics().items()
        ]
        return {"flows": flows_data}

    @app.get("/api/observability/metrics/steps")
    def steps(_ctx=Depends(require_permissions(["metrics:read"]))):
        steps_data = [
            {
                "step_id": name,
                "count": snap.count,
                "total_duration_seconds": snap.total_duration_seconds,
                "total_cost": snap.total_cost,
            }
            for name, snap in default_metrics.get_step_metrics().items()
        ]
        return {"steps": steps_data}

    @app.get("/api/observability/traces/{trace_id}")
    def trace(trace_id: str, _ctx=Depends(require_permissions(["metrics:read"]))):
        spans = default_tracer.get_trace(trace_id)
        return {
            "trace_id": trace_id,
            "spans": [
                {
                    "name": span.name,
                    "span_id": span.context.span_id,
                    "parent_span_id": span.context.parent_span_id,
                    "start_time": span.start_time,
                    "end_time": span.end_time,
                    "attributes": span.attributes,
                }
                for span in spans
            ],
        }

    return app, trace_id


def test_observability_endpoints():
    app, trace_id = build_app()
    client = TestClient(app)
    res = client.get("/api/observability/metrics/flows")
    assert res.status_code == 200
    assert res.json()["flows"]

    res = client.get("/api/observability/metrics/steps")
    assert res.status_code == 200
    assert res.json()["steps"]

    res = client.get(f"/api/observability/traces/{trace_id}")
    assert res.status_code == 200
    assert res.json()["trace_id"] == trace_id
