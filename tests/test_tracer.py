from namel3ss.obs.tracer import Tracer


def test_tracer_records_ai_and_pages():
    tracer = Tracer()
    tracer.start_app("demo")
    tracer.start_page("home")
    tracer.record_ai("model-x", "hello", "world")
    trace = tracer.last_trace
    assert trace is not None
    assert trace.app_name == "demo"
    assert trace.pages[0].page_name == "home"
    assert trace.pages[0].ai_calls[0].model_name == "model-x"


def test_tracer_records_agent_steps():
    tracer = Tracer()
    tracer.start_app("demo")
    tracer.start_page("home")
    tracer.start_agent("helper")
    tracer.record_agent_step(
        step_name="call_tool",
        kind="tool",
        target="echo",
        success=True,
        retries=0,
        output_preview="ok",
    )
    tracer.end_agent(summary="done")
    trace = tracer.last_trace
    assert trace.pages[0].agents[0].agent_name == "helper"
    assert trace.pages[0].agents[0].steps[0].success is True


def test_tracer_records_flow_steps():
    tracer = Tracer()
    tracer.start_app("demo")
    tracer.start_flow("pipeline")
    tracer.record_flow_step(
        step_name="s1",
        kind="ai",
        target="call",
        success=True,
        output_preview="ok",
    )
    tracer.end_flow()
    trace = tracer.last_trace
    assert trace.flows[0].flow_name == "pipeline"
    assert trace.flows[0].steps[0].kind == "ai"
