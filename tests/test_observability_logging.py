import logging
from namel3ss.observability.logging import get_logger
from namel3ss.observability.tracing import default_tracer


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_logs_include_trace_and_span_ids():
    logger = get_logger("test_logger")
    logger.setLevel(logging.INFO)
    handler = ListHandler()
    logger.addHandler(handler)
    with default_tracer.span("log-span"):
        logger.info("hello")
    assert handler.records
    rec = handler.records[0]
    assert hasattr(rec, "trace_id")
    assert rec.trace_id is not None
    assert rec.span_id is not None
