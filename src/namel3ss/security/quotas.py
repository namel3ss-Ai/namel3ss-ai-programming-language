"""
Simple in-memory quotas and throttling.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Tuple

from fastapi import Depends, HTTPException

from .context import SecurityContext
from .oauth import get_oauth_context
from ..i18n import translate


@dataclass
class QuotaConfig:
    max_requests_per_minute: int
    max_tokens_per_minute: int | None = None


class QuotaExceededError(Exception):
    pass


class InMemoryQuotaTracker:
    def __init__(self, config: QuotaConfig) -> None:
        self.config = config
        self._requests: Dict[Tuple[str, str | None], list[float]] = {}

    def _key(self, ctx: SecurityContext) -> Tuple[str, str | None]:
        return (ctx.tenant_id or ctx.subject_id or "anon", ctx.app_id)

    def check_and_consume(self, ctx: SecurityContext, tokens: int = 0) -> None:
        key = self._key(ctx)
        now = time.monotonic()
        window_start = now - 60
        history = [t for t in self._requests.get(key, []) if t >= window_start]
        if len(history) >= self.config.max_requests_per_minute:
            raise QuotaExceededError("Request quota exceeded")
        history.append(now)
        self._requests[key] = history
        # token-based quota not enforced in detail here but stub for extension
        if self.config.max_tokens_per_minute is not None and tokens > self.config.max_tokens_per_minute:
            raise QuotaExceededError("Token quota exceeded")


def quota_dependency(tracker: InMemoryQuotaTracker):
    def dependency(ctx: SecurityContext = Depends(get_oauth_context)):
        try:
            tracker.check_and_consume(ctx)
            return ctx
        except QuotaExceededError as exc:
            raise HTTPException(status_code=429, detail=translate("error.quota.exceeded", "en"))

    return dependency
