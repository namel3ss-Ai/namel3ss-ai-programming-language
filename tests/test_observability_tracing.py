from namel3ss.observability.tracing import Tracer, default_tracer


def test_nested_spans_share_trace_and_parent():
    tracer = Tracer()
    with tracer.span("root") as root:
        root_trace = root.context.trace_id
        with tracer.span("child") as child:
            assert child.context.trace_id == root_trace
            assert child.context.parent_span_id == root.context.span_id
    trace_spans = tracer.get_trace(root_trace)
    assert any(s.name == "root" for s in trace_spans)
    assert any(s.name == "child" for s in trace_spans)


def test_default_tracer_records_spans():
    with default_tracer.span("default-root") as s:
        trace_id = s.context.trace_id
    assert trace_id in default_tracer.all_traces()
