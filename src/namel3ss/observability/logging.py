"""
Correlated logging utilities.
"""

from __future__ import annotations

import logging
from typing import Optional

from .tracing import default_tracer, SpanContext


class TraceLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        ctx: Optional[SpanContext] = default_tracer.current_span_context()
        record.trace_id = ctx.trace_id if ctx else None
        record.span_id = ctx.span_id if ctx else None
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not any(isinstance(f, TraceLogFilter) for f in logger.filters):
        logger.addFilter(TraceLogFilter())
    return logger
