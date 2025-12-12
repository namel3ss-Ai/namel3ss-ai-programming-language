from namel3ss.server import create_app


def test_studio_routes_present(tmp_path):
    app = create_app(project_root=tmp_path)
    route_map = {
        route.path: route.methods
        for route in app.routes
        if hasattr(route, "methods")
    }

    expected = {
        ("/api/studio/canvas", "GET"),
        ("/api/studio/log-note", "POST"),
        ("/api/studio/inspect", "GET"),
        ("/api/studio/ask", "POST"),
        ("/api/studio/flows", "GET"),
        ("/api/studio/run-flow", "POST"),
        ("/api/studio/ai-call", "GET"),
        ("/api/studio/rag/list", "GET"),
        ("/api/studio/rag/pipeline", "GET"),
        ("/api/studio/warnings", "GET"),
        ("/api/studio/reparse", "POST"),
    }

    for path, method in expected:
        assert path in route_map, f"{path} missing from app routes"
        assert method in route_map[path], f"{path} missing method {method}"
