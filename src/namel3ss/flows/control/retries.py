from __future__ import annotations

import asyncio

__all__ = ["_sleep_backoff"]


async def _sleep_backoff(self, attempt: int) -> None:
    base = getattr(self, "retry_config", None).backoff_base if getattr(self, "retry_config", None) else 0
    delay = base * (2**attempt)
    if delay > 0:
        await asyncio.sleep(delay)
