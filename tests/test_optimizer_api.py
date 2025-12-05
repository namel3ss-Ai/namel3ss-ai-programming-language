from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from namel3ss.optimizer.evaluator import OptimizerEvaluator
from namel3ss.optimizer.models import (
    EvaluationCase,
    EvaluationRun,
    Suggestion,
    SuggestionStatus,
    TargetType,
)
from namel3ss.optimizer.store import OptimizerStore
from namel3ss.optimizer.suggestions import SuggestionEngine
from namel3ss.security.context import SecurityContext
from namel3ss.security.oauth import get_oauth_context
from namel3ss.security.rbac import require_permissions


def build_app(evaluator: OptimizerEvaluator, suggestion_engine: SuggestionEngine, store: OptimizerStore):
    app = FastAPI()

    def fake_ctx():
        return SecurityContext(subject_id="s", app_id=None, tenant_id=None, roles=["admin"], scopes=[], auth_scheme="api_key")

    app.dependency_overrides[get_oauth_context] = fake_ctx

    @app.post("/api/optimizer/evaluate/agent")
    async def eval_agent(payload: dict, _ctx=Depends(require_permissions(["optimizer:run"]))):
        cases = [EvaluationCase(id=c["id"], input=c["input"], expected=c.get("expected")) for c in payload["cases"]]
        run = await evaluator.evaluate_agent(payload["agent_name"], cases)
        store.save_evaluation(run)
        return {"id": run.id, "metrics_summary": run.metrics_summary}

    @app.get("/api/optimizer/evaluations")
    def list_evals(_ctx=Depends(require_permissions(["optimizer:read"]))):
        return {"evaluations": [ {"id": r.id, "target": r.target_name} for r in store.list_evaluations() ]}

    @app.post("/api/optimizer/suggestions/{run_id}")
    async def suggest(run_id: str, _ctx=Depends(require_permissions(["optimizer:run"]))):
        run = store.get_evaluation(run_id)
        suggestions = await suggestion_engine.generate_suggestions_for_evaluation(run)
        store.save_suggestions(suggestions)
        return {"suggestions": [s.id for s in suggestions]}

    @app.post("/api/optimizer/suggestions/{suggestion_id}/decide")
    def decide(suggestion_id: str, payload: dict, _ctx=Depends(require_permissions(["optimizer:run"]))):
        store.update_suggestion_status(suggestion_id, SuggestionStatus(payload["status"]))
        return {"status": payload["status"]}

    @app.get("/api/optimizer/suggestions")
    def list_suggestions(status: str | None = None, _ctx=Depends(require_permissions(["optimizer:read"]))):
        filt = SuggestionStatus(status) if status else None
        sugs = store.list_suggestions(filt)
        return {"suggestions": [s.id for s in sugs]}

    return app


def test_optimizer_api_flow():
    class StubEval:
        async def evaluate_agent(self, agent_name, cases):
            return EvaluationRun(
                id="run1",
                target_type=TargetType.AGENT,
                target_name=agent_name,
                created_at=datetime.now(timezone.utc),
                cases=cases,
                metrics_summary={},
                raw_results=[],
            )

    class StubSuggestionEngine:
        async def generate_suggestions_for_evaluation(self, run):
            return [
                Suggestion(
                    id="sug1",
                    target_type=run.target_type,
                    target_name=run.target_name,
                    created_at=datetime.now(timezone.utc),
                    status=SuggestionStatus.PENDING,
                    description="d",
                    change_spec={},
                    evaluation_run_id=run.id,
                    metadata={},
                )
            ]

    evaluator = StubEval()
    sugg_engine = StubSuggestionEngine()
    store = OptimizerStore()
    app = build_app(evaluator, sugg_engine, store)
    client = TestClient(app)

    res = client.post("/api/optimizer/evaluate/agent", json={"agent_name": "agent", "cases": []})
    assert res.status_code == 200
    run_id = res.json()["id"]

    res = client.get("/api/optimizer/evaluations")
    assert res.status_code == 200
    assert res.json()["evaluations"]

    res = client.post(f"/api/optimizer/suggestions/{run_id}")
    assert res.status_code == 200
    sug_id = res.json()["suggestions"][0]

    res = client.post(f"/api/optimizer/suggestions/{sug_id}/decide", json={"status": "accepted"})
    assert res.status_code == 200

    res = client.get("/api/optimizer/suggestions?status=accepted")
    assert res.status_code == 200
