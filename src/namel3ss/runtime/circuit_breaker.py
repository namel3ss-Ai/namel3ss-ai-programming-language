from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Literal, Optional


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


@dataclass
class CircuitBreakerState:
    failures: int = 0
    last_failure_time: float = 0.0
    state: Literal["closed", "open", "half_open"] = "closed"


class CircuitBreaker:
    """
    Minimal circuit breaker to prevent cascading provider failures.
    """

    def __init__(self, failure_threshold: Optional[int] = None, reset_seconds: Optional[float] = None) -> None:
        self.failure_threshold = failure_threshold if failure_threshold is not None else _env_int(
            "N3_CIRCUIT_FAILURE_THRESHOLD", 5
        )
        self.reset_seconds = reset_seconds if reset_seconds is not None else _env_float("N3_CIRCUIT_RESET_SECONDS", 30.0)
        self._states: Dict[str, CircuitBreakerState] = {}

    def _state_for(self, provider_key: str) -> CircuitBreakerState:
        if provider_key not in self._states:
            self._states[provider_key] = CircuitBreakerState()
        return self._states[provider_key]

    def should_allow_call(self, provider_key: str) -> bool:
        state = self._state_for(provider_key)
        if state.state == "open":
            elapsed = time.monotonic() - state.last_failure_time
            if elapsed >= self.reset_seconds:
                state.state = "half_open"
                self._states[provider_key] = state
                return True
            return False
        return True

    def record_success(self, provider_key: str) -> None:
        state = self._state_for(provider_key)
        state.failures = 0
        state.state = "closed"
        state.last_failure_time = 0.0
        self._states[provider_key] = state

    def record_failure(self, provider_key: str, exc: BaseException | None = None) -> None:
        state = self._state_for(provider_key)
        state.failures += 1
        state.last_failure_time = time.monotonic()
        if state.state == "half_open" or state.failures >= self.failure_threshold:
            state.state = "open"
        self._states[provider_key] = state


default_circuit_breaker = CircuitBreaker()

