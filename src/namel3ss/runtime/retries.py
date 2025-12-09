from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional, Tuple

from ..errors import ProviderCircuitOpenError, ProviderRetryError, ProviderTimeoutError
from .circuit_breaker import CircuitBreaker, default_circuit_breaker


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 0.5


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class RetryConfig:
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_base: float = DEFAULT_BACKOFF_BASE


def get_default_retry_config() -> RetryConfig:
    """
    Build a RetryConfig using environment overrides with sensible defaults.
    """

    return RetryConfig(
        timeout=_env_float("N3_PROVIDER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS),
        max_retries=_env_int("N3_PROVIDER_MAX_RETRIES", DEFAULT_MAX_RETRIES),
        backoff_base=_env_float("N3_PROVIDER_BACKOFF_BASE", DEFAULT_BACKOFF_BASE),
    )


async def with_retries_and_timeout(
    fn: Callable[[], Awaitable[Any]],
    *,
    config: RetryConfig | None = None,
    error_types: Tuple[type[BaseException], ...] | tuple = (),
    on_error: Callable[[BaseException, int], None] | None = None,
    circuit_breaker: CircuitBreaker | None = None,
    provider_key: Optional[str] = None,
) -> Any:
    """
    Execute an async callable with timeout, retries, and an optional circuit breaker.
    """

    cfg = config or get_default_retry_config()
    breaker = circuit_breaker or default_circuit_breaker
    retry_errors: tuple[type[BaseException], ...] = tuple(error_types) if error_types else tuple()
    attempts = cfg.max_retries + 1
    last_exc: BaseException | None = None

    for attempt in range(attempts):
        if provider_key and breaker and not breaker.should_allow_call(provider_key):
            raise ProviderCircuitOpenError(f"Circuit open for provider '{provider_key}'.")

        try:
            result = await asyncio.wait_for(fn(), timeout=cfg.timeout)
        except ProviderCircuitOpenError:
            raise
        except asyncio.TimeoutError:
            timeout_exc = ProviderTimeoutError(f"Provider call timed out after {cfg.timeout} seconds.")
            last_exc = timeout_exc
            if breaker and provider_key:
                breaker.record_failure(provider_key, timeout_exc)
            if on_error:
                try:
                    on_error(timeout_exc, attempt)
                except Exception:
                    pass
            if not retry_errors or not isinstance(timeout_exc, retry_errors):
                raise timeout_exc
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if breaker and provider_key:
                breaker.record_failure(provider_key, exc)
            if retry_errors and isinstance(exc, retry_errors):
                if on_error:
                    try:
                        on_error(exc, attempt)
                    except Exception:
                        pass
            else:
                raise
        else:
            if breaker and provider_key:
                breaker.record_success(provider_key)
            return result

        if attempt < cfg.max_retries:
            backoff = cfg.backoff_base * (2**attempt)
            await asyncio.sleep(backoff)
    raise ProviderRetryError(
        f"Provider call failed after {attempts} attempts.",
        attempts=attempts,
        last_error=last_exc,
    )


def run_with_retries_and_timeout(
    fn: Callable[[], Any],
    *,
    config: RetryConfig | None = None,
    error_types: Tuple[type[BaseException], ...] | tuple = (),
    on_error: Callable[[BaseException, int], None] | None = None,
    circuit_breaker: CircuitBreaker | None = None,
    provider_key: Optional[str] = None,
) -> Any:
    """
    Synchronous helper that delegates to the async implementation.
    """

    async def _runner() -> Any:
        return await with_retries_and_timeout(
            lambda: asyncio.to_thread(fn),
            config=config,
            error_types=error_types,
            on_error=on_error,
            circuit_breaker=circuit_breaker,
            provider_key=provider_key,
        )

    return asyncio.run(_runner())

