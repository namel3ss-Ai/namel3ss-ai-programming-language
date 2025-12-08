from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Literal, Protocol, TypedDict, Tuple
from urllib.parse import unquote, urlparse


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ConversationTurn(TypedDict, total=False):
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: str | None


class SessionInfo(TypedDict, total=False):
    id: str
    last_activity: str | None
    turns: int
    user_id: str | None


class LongTermItem(TypedDict, total=False):
    id: str
    summary: str
    created_at: str | None


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except Exception:
        return None


class ConversationMemoryBackend(Protocol):
    def load_history(self, ai_id: str, session_id: str, window: int) -> List[ConversationTurn]:
        ...

    def append_turns(
        self,
        ai_id: str,
        session_id: str,
        turns: List[ConversationTurn],
        user_id: str | None = None,
    ) -> None:
        ...

    def append_summary(self, ai_id: str, session_id: str, summary: str) -> None:
        ...

    def append_facts(self, ai_id: str, session_id: str, facts: List[str]) -> None:
        ...

    def list_sessions(self, ai_id: str) -> List[SessionInfo]:
        ...

    def get_full_history(self, ai_id: str, session_id: str) -> List[ConversationTurn]:
        ...

    def clear_session(self, ai_id: str, session_id: str) -> None:
        ...

    def list_items(self, ai_id: str, session_id: str) -> List[LongTermItem]:
        ...

    def get_facts(self, ai_id: str, session_id: str) -> List[str]:
        ...

    def cleanup_retention(self, ai_id: str, session_id: str, cutoff_iso: str) -> None:
        ...

    def get_session_user(self, ai_id: str, session_id: str) -> str | None:
        ...


class InMemoryConversationMemoryBackend:
    def __init__(self) -> None:
        self._store: Dict[Tuple[str, str], List[ConversationTurn]] = {}
        self._meta: Dict[Tuple[str, str], SessionInfo] = {}

    def load_history(self, ai_id: str, session_id: str, window: int) -> List[ConversationTurn]:
        turns = self._store.get((ai_id, session_id), [])
        if window <= 0:
            return []
        if len(turns) <= window:
            return list(turns)
        return turns[-window:]

    def append_turns(self, ai_id: str, session_id: str, turns: List[ConversationTurn], user_id: str | None = None) -> None:
        key = (ai_id, session_id)
        current = self._store.get(key, [])
        enriched: List[ConversationTurn] = []
        timestamp = _iso_now()
        for turn in turns:
            enriched_turn: ConversationTurn = {
                "role": turn.get("role", "user"),  # type: ignore[arg-type]
                "content": turn.get("content", ""),
                "created_at": turn.get("created_at") or timestamp,
            }
            enriched.append(enriched_turn)
        current.extend(enriched)
        self._store[key] = current
        meta = self._meta.get(key) or {"id": session_id, "last_activity": None, "turns": 0, "user_id": None}
        meta["turns"] = int(meta.get("turns", 0)) + len(enriched)
        meta["last_activity"] = enriched[-1].get("created_at")
        if user_id is not None:
            meta["user_id"] = user_id
        self._meta[key] = meta

    def append_summary(self, ai_id: str, session_id: str, summary: str) -> None:
        summary = (summary or "").strip()
        if not summary:
            return
        self.append_turns(ai_id, session_id, [{"role": "system", "content": summary, "created_at": None}])

    def append_facts(self, ai_id: str, session_id: str, facts: List[str]) -> None:
        turns = [
            {"role": "system", "content": fact.strip(), "created_at": None}
            for fact in facts
            if fact and fact.strip()
        ]
        if turns:
            self.append_turns(ai_id, session_id, turns)

    def list_sessions(self, ai_id: str) -> List[SessionInfo]:
        sessions: List[SessionInfo] = []
        for (stored_ai, session_id), meta in self._meta.items():
            if stored_ai != ai_id:
                continue
            sessions.append(
                {
                    "id": session_id,
                    "last_activity": meta.get("last_activity"),
                    "turns": meta.get("turns", 0),
                    "user_id": meta.get("user_id"),
                }
            )
        sessions.sort(key=lambda entry: entry.get("last_activity") or "", reverse=True)
        return sessions

    def get_full_history(self, ai_id: str, session_id: str) -> List[ConversationTurn]:
        return list(self._store.get((ai_id, session_id), []))

    def clear_session(self, ai_id: str, session_id: str) -> None:
        key = (ai_id, session_id)
        self._store.pop(key, None)
        self._meta.pop(key, None)

    def list_items(self, ai_id: str, session_id: str) -> List[LongTermItem]:
        history = self._store.get((ai_id, session_id), [])
        items: List[LongTermItem] = []
        for idx, turn in enumerate(history):
            items.append(
                {
                    "id": f"{session_id}-{idx}",
                    "summary": turn.get("content", ""),
                    "created_at": turn.get("created_at"),
                }
            )
        return items

    def get_facts(self, ai_id: str, session_id: str) -> List[str]:
        history = self._store.get((ai_id, session_id), [])
        return [turn.get("content", "") for turn in history if (turn.get("role") or "").lower() == "system"]

    def cleanup_retention(self, ai_id: str, session_id: str, cutoff_iso: str) -> None:
        cutoff_dt = _parse_iso(cutoff_iso)
        if cutoff_dt is None:
            return
        key = (ai_id, session_id)
        turns = self._store.get(key)
        if not turns:
            return
        filtered: List[ConversationTurn] = []
        for turn in turns:
            ts = _parse_iso(turn.get("created_at"))
            if ts is None or ts >= cutoff_dt:
                filtered.append(turn)
        if len(filtered) == len(turns):
            return
        if filtered:
            self._store[key] = filtered
            meta = self._meta.get(key)
            if meta:
                meta["turns"] = len(filtered)
                meta["last_activity"] = filtered[-1].get("created_at")
        else:
            self._store.pop(key, None)
            self._meta.pop(key, None)

    def get_session_user(self, ai_id: str, session_id: str) -> str | None:
        meta = self._meta.get((ai_id, session_id))
        return meta.get("user_id") if meta else None


class SqliteConversationMemoryBackend:
    def __init__(self, url: str | Path) -> None:
        self._db_path = self._resolve_path(url)
        self._ensure_schema()

    def _resolve_path(self, url: str | Path) -> str:
        if isinstance(url, Path):
            candidate = url
        else:
            value = str(url)
            if value.startswith("sqlite:///"):
                value = value[len("sqlite:///") :]
            elif value.startswith("file://"):
                parsed = urlparse(value)
                value = unquote(parsed.path or "")
            candidate = Path(value)
        candidate = candidate.expanduser()
        if not candidate.is_absolute() and candidate != Path(":memory:"):
            candidate = Path.cwd() / candidate
        if candidate != Path(":memory:"):
            candidate.parent.mkdir(parents=True, exist_ok=True)
        return str(candidate)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversation_lookup
                ON conversation_turns (ai_id, session_id, id)
                """
            )
            columns = {row[1] for row in conn.execute("PRAGMA table_info(conversation_turns)").fetchall()}
            if "created_at" not in columns:
                conn.execute("ALTER TABLE conversation_turns ADD COLUMN created_at TEXT")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS session_meta (
                    ai_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    user_id TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (ai_id, session_id)
                )
                """
            )

    def load_history(self, ai_id: str, session_id: str, window: int) -> List[ConversationTurn]:
        if window <= 0:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM conversation_turns
                WHERE ai_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (ai_id, session_id, window),
            ).fetchall()
        rows.reverse()
        return [{"role": role, "content": content, "created_at": created_at} for role, content, created_at in rows]

    def append_turns(
        self,
        ai_id: str,
        session_id: str,
        turns: List[ConversationTurn],
        user_id: str | None = None,
    ) -> None:
        if not turns:
            return
        timestamp = _iso_now()
        payload = [
            (
                ai_id,
                session_id,
                turn.get("role", "user"),
                turn.get("content", ""),
                turn.get("created_at") or timestamp,
            )
            for turn in turns
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO conversation_turns (ai_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                payload,
            )
            if user_id is not None:
                conn.execute(
                    """
                    INSERT INTO session_meta (ai_id, session_id, user_id, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(ai_id, session_id) DO UPDATE SET
                        user_id=excluded.user_id,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (ai_id, session_id, user_id),
                )

    def append_summary(self, ai_id: str, session_id: str, summary: str) -> None:
        summary = (summary or "").strip()
        if not summary:
            return
        self.append_turns(ai_id, session_id, [{"role": "system", "content": summary, "created_at": None}])

    def append_facts(self, ai_id: str, session_id: str, facts: List[str]) -> None:
        turns = [
            {"role": "system", "content": fact.strip(), "created_at": None}
            for fact in facts
            if fact and fact.strip()
        ]
        if turns:
            self.append_turns(ai_id, session_id, turns)

    def list_sessions(self, ai_id: str) -> List[SessionInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT t.session_id, MAX(t.created_at), COUNT(*), MAX(t.id), MAX(m.user_id)
                FROM conversation_turns t
                LEFT JOIN session_meta m ON m.ai_id = t.ai_id AND m.session_id = t.session_id
                WHERE t.ai_id = ?
                GROUP BY t.session_id
                ORDER BY MAX(t.id) DESC
                """,
                (ai_id,),
            ).fetchall()
        return [
            {
                "id": session_id,
                "last_activity": last_activity,
                "turns": turns,
                "user_id": user_id,
            }
            for session_id, last_activity, turns, _, user_id in rows
        ]

    def get_full_history(self, ai_id: str, session_id: str) -> List[ConversationTurn]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, created_at
                FROM conversation_turns
                WHERE ai_id = ? AND session_id = ?
                ORDER BY id
                """,
                (ai_id, session_id),
            ).fetchall()
        return [{"role": role, "content": content, "created_at": created_at} for role, content, created_at in rows]

    def clear_session(self, ai_id: str, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM conversation_turns
                WHERE ai_id = ? AND session_id = ?
                """,
                (ai_id, session_id),
            )
            conn.execute(
                """
                DELETE FROM session_meta
                WHERE ai_id = ? AND session_id = ?
                """,
                (ai_id, session_id),
            )

    def list_items(self, ai_id: str, session_id: str) -> List[LongTermItem]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, content, created_at
                FROM conversation_turns
                WHERE ai_id = ? AND session_id = ?
                ORDER BY id
                """,
                (ai_id, session_id),
            ).fetchall()
        return [{"id": f"{session_id}-{row_id}", "summary": content, "created_at": created_at} for row_id, content, created_at in rows]

    def get_facts(self, ai_id: str, session_id: str) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT content
                FROM conversation_turns
                WHERE ai_id = ? AND session_id = ? AND LOWER(role) = 'system'
                ORDER BY id
                """,
                (ai_id, session_id),
            ).fetchall()
        return [content for (content,) in rows]

    def cleanup_retention(self, ai_id: str, session_id: str, cutoff_iso: str) -> None:
        if not cutoff_iso:
            return
        with self._connect() as conn:
            conn.execute(
                """
                DELETE FROM conversation_turns
                WHERE ai_id = ? AND session_id = ? AND created_at IS NOT NULL AND created_at < ?
                """,
                (ai_id, session_id, cutoff_iso),
            )

    def get_session_user(self, ai_id: str, session_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT user_id FROM session_meta
                WHERE ai_id = ? AND session_id = ?
                """,
                (ai_id, session_id),
            ).fetchone()
        return row[0] if row else None
