import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.config import settings


def get_db_file_path(database_url: str) -> str:
    """Parse sqlite URL into an absolute or relative filesystem path."""
    if database_url.startswith("sqlite:///"):
        # e.g., sqlite:////data/app.db -> /data/app.db, sqlite:///./app.db -> ./app.db
        path = database_url.replace("sqlite:///", "", 1)
        return path
    parsed = urlparse(database_url)
    return parsed.path or "./app.db"


class Database:
    """SQLite database manager for sessions and message history."""

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or settings.DATABASE_URL
        self.db_path = get_db_file_path(self.db_url)
        self._ensure_dir()
        self.init_schema()

    def _ensure_dir(self):
        parent_dir = os.path.dirname(os.path.abspath(self.db_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a new SQLite connection."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10.0)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_schema(self):
        """Create tables and indexes if they do not exist."""
        self._ensure_dir()
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, id);

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    system_prompt TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cache_usage (
                    cache_key TEXT PRIMARY KEY,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS cached_responses (
                    cache_key TEXT PRIMARY KEY,
                    reply TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def check_health(self) -> bool:
        """Verify database reachability with SELECT 1."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT 1;")
                return cursor.fetchone() is not None
        except Exception:
            return False

    def session_exists(self, session_id: str) -> bool:
        """A session exists if it has at least one stored message."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM messages WHERE session_id = ? LIMIT 1;",
                (session_id,),
            )
            return cursor.fetchone() is not None

    def get_session_system_prompt(self, session_id: str) -> Optional[str]:
        """Fetch custom system prompt for a session if registered."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT system_prompt FROM sessions WHERE session_id = ?;",
                (session_id,),
            )
            row = cursor.fetchone()
            return row["system_prompt"] if row else None

    def set_session_system_prompt(self, session_id: str, system_prompt: str):
        """Register or update system prompt for a session."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (session_id, system_prompt, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt;
                """,
                (session_id, system_prompt, now_iso),
            )

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Return stored messages for a session ordered by id ascending (oldest first).
        Without system prompt.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT role, content, metadata FROM messages WHERE session_id = ? ORDER BY id ASC;",
                (session_id,),
            )
            rows = cursor.fetchall()
            messages = []
            for row in rows:
                meta = None
                if row["metadata"]:
                    try:
                        meta = json.loads(row["metadata"])
                    except Exception:
                        meta = None
                item: Dict[str, Any] = {
                    "role": row["role"],
                    "content": row["content"],
                }
                if row["role"] == "assistant":
                    item["metadata"] = meta
                else:
                    item["metadata"] = None
                messages.append(item)
            return messages

    def save_turn(
        self,
        session_id: str,
        user_content: str,
        assistant_content: str,
        assistant_metadata: Dict[str, Any],
        system_prompt: Optional[str] = None,
    ):
        """
        Save user message and assistant message atomically in one transaction.
        Also record system prompt if provided.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        metadata_json = json.dumps(assistant_metadata)

        with self.get_connection() as conn:
            if system_prompt:
                conn.execute(
                    """
                    INSERT INTO sessions (session_id, system_prompt, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET system_prompt = excluded.system_prompt;
                    """,
                    (session_id, system_prompt, now_iso),
                )

            # Insert user message
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'user', ?, NULL, ?);
                """,
                (session_id, user_content, now_iso),
            )

            # Insert assistant message
            conn.execute(
                """
                INSERT INTO messages (session_id, role, content, metadata, created_at)
                VALUES (?, 'assistant', ?, ?, ?);
                """,
                (session_id, assistant_content, metadata_json, now_iso),
            )

    def save_cache_usage(self, cache_key: str, input_tokens: int, output_tokens: int):
        """Record usage tokens for a cache key to guarantee exact tokens on cache hits."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cache_usage (cache_key, input_tokens, output_tokens, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens;
                """,
                (cache_key, input_tokens, output_tokens, now_iso),
            )

    def save_cached_response(
        self,
        cache_key: str,
        reply: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ):
        """Persist cached response and token usage in SQLite for restart durability."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO cached_responses (cache_key, reply, model, input_tokens, output_tokens, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    reply = excluded.reply,
                    model = excluded.model,
                    input_tokens = excluded.input_tokens,
                    output_tokens = excluded.output_tokens;
                """,
                (cache_key, reply, model, input_tokens, output_tokens, now_iso),
            )

    def get_cached_response(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored cached response from SQLite if available."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT reply, model, input_tokens, output_tokens FROM cached_responses WHERE cache_key = ?;",
                (cache_key,),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "reply": row["reply"],
                    "model": row["model"],
                    "input_tokens": int(row["input_tokens"]),
                    "output_tokens": int(row["output_tokens"]),
                }
            return None


db = Database()
