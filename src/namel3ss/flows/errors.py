from typing import Any


class ReturnSignal(Exception):
    def __init__(self, value: Any = None) -> None:
        self.value = value


class TimedStepError(Exception):
    def __init__(self, original: Exception, duration: float) -> None:
        message = str(original) or "timeout"
        super().__init__(message)
        self.original = original
        self.duration = duration
