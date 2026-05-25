import sqlite3
import stat
from contextlib import contextmanager

from secretary.config import settings

DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL DEFAULT (datetime('now')),
    summary    TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    role       TEXT    NOT NULL CHECK(role IN ('user', 'assistant', 'tool')),
    content    TEXT    NOT NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);

CREATE TABLE IF NOT EXISTS user_context (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


@contextmanager
def _conn():
    con = sqlite3.connect(settings.db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with _conn() as con:
        con.executescript(DDL)
    # Restrict DB file to owner only (mode 600)
    settings.db_path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def create_session() -> int:
    with _conn() as con:
        cur = con.execute("INSERT INTO sessions DEFAULT VALUES")
        return cur.lastrowid


def save_message(session_id: int, role: str, content: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def update_session_summary(session_id: int, summary: str) -> None:
    with _conn() as con:
        con.execute("UPDATE sessions SET summary=? WHERE id=?", (summary, session_id))


def list_sessions(n: int = 10) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (n,)
        ).fetchall()


def get_session_messages(session_id: int) -> list[sqlite3.Row]:
    with _conn() as con:
        return con.execute(
            "SELECT * FROM messages WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()


def set_user_context(key: str, value: str) -> None:
    with _conn() as con:
        con.execute(
            "INSERT INTO user_context(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=datetime('now')",
            (key, value),
        )


def get_user_context(key: str) -> str | None:
    with _conn() as con:
        row = con.execute(
            "SELECT value FROM user_context WHERE key=?", (key,)
        ).fetchone()
        return row["value"] if row else None


def get_all_user_context() -> dict[str, str]:
    with _conn() as con:
        rows = con.execute("SELECT key, value FROM user_context").fetchall()
        return {row["key"]: row["value"] for row in rows}
