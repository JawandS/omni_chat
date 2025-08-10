import os
import sqlite3
from datetime import datetime, UTC
from typing import Optional

from flask import current_app, g, Flask


def init_app(app: Flask) -> None:
    """Configure database path and teardown for the Flask app."""
    # Ensure instance folder exists for sqlite database
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.setdefault("DATABASE", os.path.join(app.instance_path, "omni_chat.db"))

    @app.teardown_appcontext
    def close_db(exception: Optional[BaseException]):  # noqa: ARG001 - Flask signature
        db = g.pop("db", None)
        if db is not None:
            db.close()


def get_db() -> sqlite3.Connection:
    """Get sqlite connection stored on Flask's `g`."""
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        # Ensure foreign key constraints are enforced (for ON DELETE CASCADE)
        try:
            conn.execute("PRAGMA foreign_keys = ON")
        except Exception:
            pass
        g.db = conn
    return g.db  # type: ignore[no-any-return]


def init_db() -> None:
    """Create required tables if they don't exist."""
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()


def commit() -> None:
    get_db().commit()


# Data helpers ---------------------------------------------------------------


def create_chat(title: str, provider: str, model: str, now: Optional[str] = None) -> int:
    db = get_db()
    ts = now or datetime.now(UTC).isoformat()
    cur = db.execute(
        "INSERT INTO chats (title, provider, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, provider, model, ts, ts),
    )
    return int(cur.lastrowid)


def update_chat_meta(chat_id: int, provider: Optional[str], model: Optional[str], now: Optional[str] = None) -> None:
    ts = now or datetime.now(UTC).isoformat()
    get_db().execute(
        "UPDATE chats SET provider = ?, model = ?, updated_at = ? WHERE id = ?",
        (provider, model, ts, chat_id),
    )


def update_chat(chat_id: int, *, title: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None,
                now: Optional[str] = None) -> None:
    db = get_db()
    ts = now or datetime.now(UTC).isoformat()
    if title:
        db.execute("UPDATE chats SET title = ?, updated_at = ? WHERE id = ?", (title, ts, chat_id))
    if provider is not None or model is not None:
        db.execute(
            "UPDATE chats SET provider = COALESCE(?, provider), model = COALESCE(?, model), updated_at = ? WHERE id = ?",
            (provider, model, ts, chat_id),
        )


def insert_message(chat_id: int, role: str, content: str, now: Optional[str] = None) -> None:
    ts = now or datetime.now(UTC).isoformat()
    get_db().execute(
        "INSERT INTO messages (chat_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (chat_id, role, content, ts),
    )


def touch_chat(chat_id: int, now: Optional[str] = None) -> None:
    ts = now or datetime.now(UTC).isoformat()
    get_db().execute("UPDATE chats SET updated_at = ? WHERE id = ?", (ts, chat_id))


def list_chats():
    return get_db().execute(
        "SELECT id, title, provider, model, updated_at FROM chats ORDER BY datetime(updated_at) DESC"
    ).fetchall()


def get_chat(chat_id: int):
    return get_db().execute(
        "SELECT id, title, provider, model, created_at, updated_at FROM chats WHERE id = ?",
        (chat_id,),
    ).fetchone()


def get_messages(chat_id: int):
    return get_db().execute(
        "SELECT role, content, created_at FROM messages WHERE chat_id = ? ORDER BY id ASC",
        (chat_id,),
    ).fetchall()


def delete_chat(chat_id: int) -> None:
    """Delete a chat and its messages."""
    db = get_db()
    # Delete messages first to be safe regardless of PRAGMA being applied
    db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
