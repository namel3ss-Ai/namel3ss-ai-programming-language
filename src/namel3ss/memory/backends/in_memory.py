from __future__ import annotations

from typing import Dict, List, Optional

from ..models import MemoryItem
from .base import MemoryStore


class InMemoryMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._items: Dict[str, List[MemoryItem]] = {}

    def add(self, item: MemoryItem) -> MemoryItem:
        self._items.setdefault(item.space, []).append(item)
        return item

    def list(self, space: Optional[str] = None) -> List[MemoryItem]:
        if space is None:
            all_items: List[MemoryItem] = []
            for items in self._items.values():
                all_items.extend(items)
            return list(all_items)
        return list(self._items.get(space, []))

    def query(self, space: str, text: str) -> List[MemoryItem]:
        return [
            item
            for item in self._items.get(space, [])
            if text.lower() in item.content.lower()
        ]

    def clear_space(self, space: str) -> None:
        self._items.pop(space, None)
