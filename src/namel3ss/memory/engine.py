"""
High-level memory engine.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Optional
from uuid import uuid4

from .backends.in_memory import InMemoryMemoryStore
from .backends.sqlite import SQLiteMemoryStore
from .backends.base import MemoryStore
from .models import MemoryItem, MemorySpaceConfig, MemoryType


class MemoryEngine:
    def __init__(
        self,
        spaces: List[MemorySpaceConfig],
        store: Optional[MemoryStore] = None,
        trigger_manager: Optional[object] = None,
    ) -> None:
        self.store: MemoryStore = store or InMemoryMemoryStore()
        self.spaces: Dict[str, MemorySpaceConfig] = {space.name: space for space in spaces}
        self.trigger_manager = trigger_manager

    def record_conversation(self, space: str, message: str, role: str, namespace=None) -> MemoryItem:
        config = self.spaces.get(space)
        memory_type = config.type if config else MemoryType.CONVERSATION
        item = MemoryItem(
            id=str(uuid4()),
            space=space,
            type=memory_type,
            content=message,
            metadata={"role": role, "namespace": namespace.__dict__ if namespace else None},
        )
        added = self.store.add(item)
        self._notify_triggers(space, added)
        return added

    def add_item(self, space: str, content: str, memory_type: MemoryType) -> MemoryItem:
        item = MemoryItem(
            id=str(uuid4()),
            space=space,
            type=memory_type,
            content=content,
        )
        added = self.store.add(item)
        self._notify_triggers(space, added)
        return added

    def get_recent(self, space: str, limit: int = 10) -> List[MemoryItem]:
        items = self.store.list(space)
        return items[-limit:]

    def query(self, space: str, text: str) -> List[MemoryItem]:
        return self.store.query(space, text)

    def list_all(self, space: str | None = None) -> List[MemoryItem]:
        return self.store.list(space)

    def load_conversation(self, space: str, session_id: str | None = None, limit: int = 50) -> list[dict]:
        session = session_id or "default"
        items = self.store.list(space)
        filtered = [
            item for item in items if item.metadata.get("session_id") in {session, None}
        ]
        return [
            {"role": item.metadata.get("role", "user"), "content": item.content}
            for item in filtered[-limit:]
        ]

    def append_conversation(self, space: str, session_id: str | None, messages: list[dict]) -> None:
        session = session_id or "default"
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            item = MemoryItem(
                id=str(uuid4()),
                space=space,
                type=MemoryType.CONVERSATION,
                content=content,
                metadata={"role": role, "session_id": session},
            )
            added = self.store.add(item)
            self._notify_triggers(space, added)

    def _notify_triggers(self, space: str, item: MemoryItem) -> None:
        if self.trigger_manager:
            try:
                self.trigger_manager.notify_memory_event(space, {"item": item.__dict__})
            except Exception:
                # Triggering should not break memory writes.
                pass


class ShardedMemoryEngine(MemoryEngine):
    def __init__(
        self, spaces: List[MemorySpaceConfig], num_shards: int = 4, trigger_manager: Optional[object] = None
    ) -> None:
        self._stores = [InMemoryMemoryStore() for _ in range(num_shards)]
        self.spaces: Dict[str, MemorySpaceConfig] = {space.name: space for space in spaces}
        self.num_shards = num_shards
        self._counter = 0
        self.trigger_manager = trigger_manager

    def _choose_store(self, key: str) -> InMemoryMemoryStore:
        # round-robin distribution to avoid skew
        shard_idx = self._counter % self.num_shards
        self._counter += 1
        return self._stores[shard_idx]

    def record_conversation(self, space: str, message: str, role: str, namespace=None) -> MemoryItem:
        config = self.spaces.get(space)
        memory_type = config.type if config else MemoryType.CONVERSATION
        item_id = str(uuid4())
        item = MemoryItem(
            id=item_id,
            space=space,
            type=memory_type,
            content=message,
            metadata={"role": role, "namespace": namespace.__dict__ if namespace else None},
        )
        return self._choose_store(item_id).add(item)

    def add_item(self, space: str, content: str, memory_type: MemoryType) -> MemoryItem:
        item_id = str(uuid4())
        item = MemoryItem(
            id=item_id,
            space=space,
            type=memory_type,
            content=content,
        )
        return self._choose_store(item_id).add(item)

    def get_recent(self, space: str, limit: int = 10) -> List[MemoryItem]:
        items: List[MemoryItem] = []
        for store in self._stores:
            items.extend(store.list(space))
        return sorted(items, key=lambda x: x.id)[-limit:]

    def query(self, space: str, text: str) -> List[MemoryItem]:
        results: List[MemoryItem] = []
        for store in self._stores:
            results.extend(store.query(space, text))
        return results

    def list_all(self, space: str | None = None) -> List[MemoryItem]:
        items: List[MemoryItem] = []
        for store in self._stores:
            items.extend(store.list(space))
        return items


class PersistentMemoryEngine(MemoryEngine):
    def __init__(
        self, spaces: List[MemorySpaceConfig], db_path: str, trigger_manager: Optional[object] = None
    ) -> None:
        super().__init__(spaces, store=SQLiteMemoryStore(db_path), trigger_manager=trigger_manager)
