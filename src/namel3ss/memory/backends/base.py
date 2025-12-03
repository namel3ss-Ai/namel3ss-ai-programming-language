from __future__ import annotations

from typing import Protocol, runtime_checkable, List, Optional

from ..models import MemoryItem


@runtime_checkable
class MemoryStore(Protocol):
    def add(self, item: MemoryItem) -> MemoryItem:
        ...

    def list(self, space: Optional[str] = None) -> List[MemoryItem]:
        ...

    def query(self, space: str, text: str) -> List[MemoryItem]:
        ...

    def clear_space(self, space: str) -> None:
        ...
