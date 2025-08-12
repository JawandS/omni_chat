import os
import sqlite3
from datetime import datetime, UTC
from typing import Optional, Union

from flask import current_app, g, Flask


def init_app(app: Flask) -> None:
    """Configure database path and teardown for the Flask app.

    Args:
        app: The Flask application instance to configure.
    """
    # Ensure instance folder exists for sqlite database
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.setdefault("DATABASE", os.path.join(app.instance_path, "omni_chat.db"))

    @app.teardown_appcontext
    def close_db(
        exception: Optional[BaseException],
    ) -> None:  # noqa: ARG001 - Flask signature
        """Close database connection if it exists.

        Args:
            exception: Any exception that occurred during request processing.
        """
        db = g.pop("db", None)
        if db is not None:
            db.close()


def get_db() -> sqlite3.Connection:
    """Get sqlite connection stored on Flask's `g` object.

    Returns:
        A sqlite3.Connection instance with row factory configured.
    """
    if "db" not in g:
        conn = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        conn.row_factory = sqlite3.Row
        # Ensure foreign key constraints are enforced (for ON DELETE CASCADE)
        conn.execute("PRAGMA foreign_keys = ON")
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
            provider TEXT,
            model TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
        );
        """
    )
    db.commit()
    _ensure_message_columns_exist()


def _ensure_message_columns_exist() -> None:
    """Lightweight migration to ensure provider/model columns exist on messages table."""
    try:
        db = get_db()
        cols = [r[1] for r in db.execute("PRAGMA table_info(messages)").fetchall()]
        columns_to_add = []
        if "provider" not in cols:
            columns_to_add.append("ALTER TABLE messages ADD COLUMN provider TEXT")
        if "model" not in cols:
            columns_to_add.append("ALTER TABLE messages ADD COLUMN model TEXT")

        for stmt in columns_to_add:
            db.execute(stmt)
        if columns_to_add:
            db.commit()
    except Exception:
        # Best-effort migration; ignore if PRAGMA or ALTER not supported
        pass


def commit() -> None:
    """Commit the current database transaction."""
    get_db().commit()


# Data helpers ---------------------------------------------------------------


def _get_timestamp(now: Optional[str] = None) -> str:
    """Get current timestamp or provided timestamp.

    Args:
        now: Optional timestamp string. If None, current UTC time is used.

    Returns:
        ISO formatted timestamp string.
    """
    return now or datetime.now(UTC).isoformat()


def create_chat(
    title: str, provider: str, model: str, now: Optional[str] = None
) -> int:
    """Create a new chat record.

    Args:
        title: The chat title.
        provider: The AI provider name.
        model: The AI model name.
        now: Optional timestamp. If None, current time is used.

    Returns:
        The ID of the created chat.
    """
    db = get_db()
    ts = _get_timestamp(now)
    cur = db.execute(
        "INSERT INTO chats (title, provider, model, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (title, provider, model, ts, ts),
    )
    last_id = cur.lastrowid  # Optional[int] per typeshed
    if not isinstance(last_id, int):  # pragma: no cover - defensive
        raise RuntimeError("SQLite cursor did not return an integer lastrowid")
    return last_id


def update_chat_meta(
    chat_id: int,
    provider: Optional[str],
    model: Optional[str],
    now: Optional[str] = None,
) -> None:
    """Update chat provider and model metadata.

    Args:
        chat_id: The chat ID to update.
        provider: New provider name.
        model: New model name.
        now: Optional timestamp. If None, current time is used.
    """
    ts = _get_timestamp(now)
    get_db().execute(
        "UPDATE chats SET provider = ?, model = ?, updated_at = ? WHERE id = ?",
        (provider, model, ts, chat_id),
    )


def update_chat(
    chat_id: int,
    *,
    title: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    now: Optional[str] = None,
) -> None:
    """Update chat fields selectively.

    Args:
        chat_id: The chat ID to update.
        title: New title (optional).
        provider: New provider (optional).
        model: New model (optional).
        now: Optional timestamp. If None, current time is used.
    """
    db = get_db()
    ts = _get_timestamp(now)

    if title:
        db.execute(
            "UPDATE chats SET title = ?, updated_at = ? WHERE id = ?",
            (title, ts, chat_id),
        )
    if provider is not None or model is not None:
        db.execute(
            "UPDATE chats SET provider = COALESCE(?, provider), model = COALESCE(?, model), updated_at = ? WHERE id = ?",
            (provider, model, ts, chat_id),
        )


def insert_message(
    chat_id: int,
    role: str,
    content: str,
    now: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Insert a new message into a chat.

    Args:
        chat_id: The chat ID to add the message to.
        role: The message role ('user' or 'assistant').
        content: The message content.
        now: Optional timestamp. If None, current time is used.
        provider: Optional provider name for the message.
        model: Optional model name for the message.

    Raises:
        ValueError: If role is not 'user' or 'assistant'.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"Invalid role: {role}. Must be 'user' or 'assistant'")

    ts = _get_timestamp(now)
    get_db().execute(
        "INSERT INTO messages (chat_id, role, content, provider, model, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (chat_id, role, content, provider, model, ts),
    )


def touch_chat(chat_id: int, now: Optional[str] = None) -> None:
    """Update a chat's last updated timestamp.

    Args:
        chat_id: The chat ID to update.
        now: Optional timestamp. If None, current time is used.
    """
    ts = _get_timestamp(now)
    get_db().execute("UPDATE chats SET updated_at = ? WHERE id = ?", (ts, chat_id))


def list_chats() -> list[sqlite3.Row]:
    """Get all chats ordered by most recent update.

    Returns:
        List of chat records with id, title, provider, model, and updated_at fields.
    """
    return (
        get_db()
        .execute(
            "SELECT id, title, provider, model, updated_at FROM chats ORDER BY datetime(updated_at) DESC"
        )
        .fetchall()
    )


def get_chat(chat_id: int) -> Optional[sqlite3.Row]:
    """Get a specific chat by ID.

    Args:
        chat_id: The chat ID to retrieve.

    Returns:
        Chat record or None if not found.
    """
    return (
        get_db()
        .execute(
            "SELECT id, title, provider, model, created_at, updated_at FROM chats WHERE id = ?",
            (chat_id,),
        )
        .fetchone()
    )


def get_messages(chat_id: int) -> list[sqlite3.Row]:
    """Get all messages for a specific chat.

    Args:
        chat_id: The chat ID to get messages for.

    Returns:
        List of message records ordered by creation time.
    """
    return (
        get_db()
        .execute(
            "SELECT role, content, provider, model, created_at FROM messages WHERE chat_id = ? ORDER BY id ASC",
            (chat_id,),
        )
        .fetchall()
    )


def delete_chat(chat_id: int) -> None:
    """Delete a chat and its messages.

    Args:
        chat_id: The chat ID to delete.
    """
    db = get_db()
    # Delete messages first to be safe regardless of PRAGMA being applied
    db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    db.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
