"""
Lightweight tracing inspired by OpenTelemetry primitives.
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import contextvars


@dataclass
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None


@dataclass
class Span:
    name: str
    context: SpanContext
    attributes: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    exception: Optional[str] = None

    def finish(self) -> None:
        if self.end_time is None:
            self.end_time = time.time()


class Tracer:
    def __init__(self) -> None:
        self._spans: Dict[str, List[Span]] = {}
        self._current_ctx: contextvars.ContextVar[Optional[SpanContext]] = contextvars.ContextVar(
            "current_span_ctx", default=None
        )

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None, parent: Optional[SpanContext] = None) -> Span:
        trace_id = parent.trace_id if parent else uuid.uuid4().hex
        span_id = uuid.uuid4().hex
        ctx = SpanContext(trace_id=trace_id, span_id=span_id, parent_span_id=parent.span_id if parent else None)
        span = Span(name=name, context=ctx, attributes=attributes or {}, start_time=time.time())
        self._spans.setdefault(trace_id, []).append(span)
        self._current_ctx.set(ctx)
        return span

    def finish_span(self, span: Span) -> None:
        span.finish()
        # restore parent context if any
        if span.context.parent_span_id:
            parent_ctx = self._find_context(span.context.trace_id, span.context.parent_span_id)
            self._current_ctx.set(parent_ctx)
        else:
            self._current_ctx.set(None)

    def _find_context(self, trace_id: str, span_id: str) -> Optional[SpanContext]:
        for s in self._spans.get(trace_id, []):
            if s.context.span_id == span_id:
                return s.context
        return None

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        parent = self.current_span_context()
        span = self.start_span(name, attributes=attributes, parent=parent)
        try:
            yield span
        except Exception as exc:  # pragma: no cover - simple recording
            span.exception = str(exc)
            raise
        finally:
            self.finish_span(span)

    def current_span_context(self) -> Optional[SpanContext]:
        return self._current_ctx.get()

    def get_trace(self, trace_id: str) -> List[Span]:
        return list(self._spans.get(trace_id, []))

    def all_traces(self) -> Dict[str, List[Span]]:
        return self._spans


default_tracer = Tracer()
