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
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS project_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            provider TEXT,
            model TEXT,
            project_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
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
    _ensure_project_columns_exist()


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


def _ensure_project_columns_exist() -> None:
    """Lightweight migration to ensure project_id column exists on chats table."""
    try:
        db = get_db()
        cols = [r[1] for r in db.execute("PRAGMA table_info(chats)").fetchall()]
        if "project_id" not in cols:
            db.execute("ALTER TABLE chats ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")
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
    title: str, provider: str, model: str, now: Optional[str] = None, project_id: Optional[int] = None
) -> int:
    """Create a new chat record.

    Args:
        title: The chat title.
        provider: The AI provider name.
        model: The AI model name.
        now: Optional timestamp. If None, current time is used.
        project_id: Optional project ID to associate with this chat.

    Returns:
        The ID of the created chat.
    """
    db = get_db()
    ts = _get_timestamp(now)
    cur = db.execute(
        "INSERT INTO chats (title, provider, model, project_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, provider, model, project_id, ts, ts),
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
    project_id: Optional[int] = None,
    now: Optional[str] = None,
) -> None:
    """Update chat fields selectively.

    Args:
        chat_id: The chat ID to update.
        title: New title (optional).
        provider: New provider (optional).
        model: New model (optional).
        project_id: New project ID (optional).
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
    if project_id is not None:
        db.execute(
            "UPDATE chats SET project_id = ?, updated_at = ? WHERE id = ?",
            (project_id, ts, chat_id),
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
        List of chat records with id, title, provider, model, project_id, and updated_at fields.
    """
    return (
        get_db()
        .execute(
            "SELECT id, title, provider, model, project_id, updated_at FROM chats ORDER BY datetime(updated_at) DESC"
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
            "SELECT id, title, provider, model, project_id, created_at, updated_at FROM chats WHERE id = ?",
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


# Project management functions -----------------------------------------------


def create_project(
    name: str, description: Optional[str] = None, system_prompt: Optional[str] = None, now: Optional[str] = None
) -> int:
    """Create a new project record.

    Args:
        name: The project name.
        description: Optional project description.
        system_prompt: Optional system prompt for the project.
        now: Optional timestamp. If None, current time is used.

    Returns:
        The ID of the created project.
    """
    db = get_db()
    ts = _get_timestamp(now)
    cur = db.execute(
        "INSERT INTO projects (name, description, system_prompt, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (name, description, system_prompt, ts, ts),
    )
    last_id = cur.lastrowid
    if not isinstance(last_id, int):  # pragma: no cover - defensive
        raise RuntimeError("SQLite cursor did not return an integer lastrowid")
    return last_id


def get_project(project_id: int) -> Optional[sqlite3.Row]:
    """Get a specific project by ID.

    Args:
        project_id: The project ID to retrieve.

    Returns:
        Project record or None if not found.
    """
    return (
        get_db()
        .execute(
            "SELECT id, name, description, system_prompt, created_at, updated_at FROM projects WHERE id = ?",
            (project_id,),
        )
        .fetchone()
    )


def list_projects() -> list[sqlite3.Row]:
    """Get all projects ordered by most recent update.

    Returns:
        List of project records with id, name, description, system_prompt, and updated_at fields.
    """
    return (
        get_db()
        .execute(
            "SELECT id, name, description, system_prompt, updated_at FROM projects ORDER BY datetime(updated_at) DESC"
        )
        .fetchall()
    )


def update_project(
    project_id: int,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    system_prompt: Optional[str] = None,
    now: Optional[str] = None,
) -> None:
    """Update project fields selectively.

    Args:
        project_id: The project ID to update.
        name: New name (optional).
        description: New description (optional).
        system_prompt: New system prompt (optional).
        now: Optional timestamp. If None, current time is used.
    """
    db = get_db()
    ts = _get_timestamp(now)

    if name is not None:
        db.execute(
            "UPDATE projects SET name = ?, updated_at = ? WHERE id = ?",
            (name, ts, project_id),
        )
    if description is not None:
        db.execute(
            "UPDATE projects SET description = ?, updated_at = ? WHERE id = ?",
            (description, ts, project_id),
        )
    if system_prompt is not None:
        db.execute(
            "UPDATE projects SET system_prompt = ?, updated_at = ? WHERE id = ?",
            (system_prompt, ts, project_id),
        )


def delete_project(project_id: int) -> None:
    """Delete a project and set all associated chats' project_id to NULL.

    Args:
        project_id: The project ID to delete.
    """
    db = get_db()
    # Delete project files first
    db.execute("DELETE FROM project_files WHERE project_id = ?", (project_id,))
    # Delete the project (chats will have project_id set to NULL due to ON DELETE SET NULL)
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def touch_project(project_id: int, now: Optional[str] = None) -> None:
    """Update a project's last updated timestamp.

    Args:
        project_id: The project ID to update.
        now: Optional timestamp. If None, current time is used.
    """
    ts = _get_timestamp(now)
    get_db().execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ts, project_id))


# Project file management functions ------------------------------------------


def create_project_file(
    project_id: int, filename: str, content: str, now: Optional[str] = None
) -> int:
    """Create a new project file record.

    Args:
        project_id: The project ID the file belongs to.
        filename: The file name.
        content: The file content.
        now: Optional timestamp. If None, current time is used.

    Returns:
        The ID of the created project file.
    """
    db = get_db()
    ts = _get_timestamp(now)
    cur = db.execute(
        "INSERT INTO project_files (project_id, filename, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (project_id, filename, content, ts, ts),
    )
    last_id = cur.lastrowid
    if not isinstance(last_id, int):  # pragma: no cover - defensive
        raise RuntimeError("SQLite cursor did not return an integer lastrowid")
    return last_id


def get_project_files(project_id: int) -> list[sqlite3.Row]:
    """Get all files for a specific project.

    Args:
        project_id: The project ID to get files for.

    Returns:
        List of file records ordered by filename.
    """
    return (
        get_db()
        .execute(
            "SELECT id, project_id, filename, content, created_at, updated_at FROM project_files WHERE project_id = ? ORDER BY filename ASC",
            (project_id,),
        )
        .fetchall()
    )


def get_project_file(file_id: int) -> Optional[sqlite3.Row]:
    """Get a specific project file by ID.

    Args:
        file_id: The file ID to retrieve.

    Returns:
        File record or None if not found.
    """
    return (
        get_db()
        .execute(
            "SELECT id, project_id, filename, content, created_at, updated_at FROM project_files WHERE id = ?",
            (file_id,),
        )
        .fetchone()
    )


def update_project_file(
    file_id: int,
    *,
    filename: Optional[str] = None,
    content: Optional[str] = None,
    now: Optional[str] = None,
) -> None:
    """Update project file fields selectively.

    Args:
        file_id: The file ID to update.
        filename: New filename (optional).
        content: New content (optional).
        now: Optional timestamp. If None, current time is used.
    """
    db = get_db()
    ts = _get_timestamp(now)

    if filename is not None:
        db.execute(
            "UPDATE project_files SET filename = ?, updated_at = ? WHERE id = ?",
            (filename, ts, file_id),
        )
    if content is not None:
        db.execute(
            "UPDATE project_files SET content = ?, updated_at = ? WHERE id = ?",
            (content, ts, file_id),
        )


def delete_project_file(file_id: int) -> None:
    """Delete a project file.

    Args:
        file_id: The file ID to delete.
    """
    get_db().execute("DELETE FROM project_files WHERE id = ?", (file_id,))
