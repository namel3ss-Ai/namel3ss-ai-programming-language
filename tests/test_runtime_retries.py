import asyncio
import time

import pytest

from namel3ss.errors import ProviderCircuitOpenError, ProviderRetryError, ProviderTimeoutError
from namel3ss.runtime.circuit_breaker import CircuitBreaker
from namel3ss.runtime.retries import RetryConfig, with_retries_and_timeout


def test_with_retries_retries_on_error() -> None:
    calls = 0

    async def _sometimes_fails():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("retry me")
        return "ok"

    cfg = RetryConfig(timeout=0.1, max_retries=3, backoff_base=0.0)
    result = asyncio.run(
        with_retries_and_timeout(
            _sometimes_fails,
            config=cfg,
            error_types=(ValueError,),
            circuit_breaker=CircuitBreaker(failure_threshold=5, reset_seconds=0.01),
        )
    )
    assert result == "ok"
    assert calls == 3


def test_with_retries_exhausts_and_raises_retry_error() -> None:
    calls = 0

    async def _always_fails():
        nonlocal calls
        calls += 1
        raise ValueError("boom")

    cfg = RetryConfig(timeout=0.05, max_retries=1, backoff_base=0.0)
    with pytest.raises(ProviderRetryError) as excinfo:
        asyncio.run(
            with_retries_and_timeout(
                _always_fails,
                config=cfg,
                error_types=(ValueError,),
                circuit_breaker=CircuitBreaker(failure_threshold=5, reset_seconds=0.01),
            )
        )
    assert calls == cfg.max_retries + 1
    assert excinfo.value.attempts == cfg.max_retries + 1


def test_timeout_raises_timeout_error() -> None:
    cfg = RetryConfig(timeout=0.01, max_retries=0, backoff_base=0.0)

    async def _slow():
        await asyncio.sleep(0.05)

    with pytest.raises(ProviderTimeoutError):
        asyncio.run(
            with_retries_and_timeout(
                _slow,
                config=cfg,
                error_types=(),
                circuit_breaker=CircuitBreaker(failure_threshold=5, reset_seconds=0.01),
            )
        )


def test_circuit_breaker_blocks_calls_when_open() -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_seconds=10.0)
    provider_key = "model:test"
    breaker.record_failure(provider_key, RuntimeError("fail fast"))

    async def _never_called():
        return "should not run"

    with pytest.raises(ProviderCircuitOpenError):
        asyncio.run(
            with_retries_and_timeout(
                _never_called,
                config=RetryConfig(timeout=0.1, max_retries=0, backoff_base=0.0),
                error_types=(RuntimeError,),
                circuit_breaker=breaker,
                provider_key=provider_key,
            )
        )


def test_circuit_breaker_recovers_after_cooldown() -> None:
    breaker = CircuitBreaker(failure_threshold=1, reset_seconds=0.01)
    provider_key = "model:recover"
    breaker.record_failure(provider_key, RuntimeError("fail"))
    assert breaker.should_allow_call(provider_key) is False
    time.sleep(0.02)
    assert breaker.should_allow_call(provider_key) is True
    breaker.record_success(provider_key)
    assert breaker.should_allow_call(provider_key) is True
