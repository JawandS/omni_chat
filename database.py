import os
import sqlite3
from datetime import datetime, UTC
from typing import Optional, Union

from flask import current_app, g, Flask
from utils import get_timestamp


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
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
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
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            frequency TEXT NOT NULL CHECK(frequency IN ('none', 'daily', 'weekly', 'monthly', 'yearly')),
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            output TEXT NOT NULL CHECK(output IN ('application', 'email')),
            email TEXT,
            status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'running', 'completed', 'failed')),
            last_run TEXT,
            next_run TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
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
    ts = get_timestamp(now)
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
    ts = get_timestamp(now)
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
    ts = get_timestamp(now)

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

    ts = get_timestamp(now)
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
    ts = get_timestamp(now)
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


def count_all_history() -> dict[str, int]:
    """Count total number of chats and messages in the database.
    
    Returns:
        Dictionary with 'chats' and 'messages' counts.
    """
    db = get_db()
    chat_count = db.execute("SELECT COUNT(*) FROM chats").fetchone()[0]
    message_count = db.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return {"chats": chat_count, "messages": message_count}


def delete_all_history() -> dict[str, int]:
    """Delete all chats and messages from the database.
    
    Returns:
        Dictionary with counts of deleted 'chats' and 'messages'.
    """
    db = get_db()
    
    # Get counts before deletion
    counts = count_all_history()
    
    # Delete all messages first, then all chats
    db.execute("DELETE FROM messages")
    db.execute("DELETE FROM chats")
    
    return counts


# Project management functions -----------------------------------------------


def create_project(name: str, now: Optional[str] = None) -> int:
    """Create a new project.

    Args:
        name: The project name.
        now: Optional timestamp. If None, current time is used.

    Returns:
        The ID of the created project.
    """
    db = get_db()
    ts = get_timestamp(now)
    cur = db.execute(
        "INSERT INTO projects (name, created_at, updated_at) VALUES (?, ?, ?)",
        (name, ts, ts),
    )
    last_id = cur.lastrowid
    if not isinstance(last_id, int):
        raise RuntimeError("SQLite cursor did not return an integer lastrowid")
    return last_id


def list_projects() -> list:
    """Get all projects ordered by most recent activity.

    Returns:
        List of project records with id, name, created_at, updated_at, and chat_count.
    """
    db = get_db()
    projects = db.execute(
        """
        SELECT p.id, p.name, p.created_at, p.updated_at,
               COUNT(c.id) as chat_count,
               MAX(c.updated_at) as last_chat_activity
        FROM projects p
        LEFT JOIN chats c ON p.id = c.project_id
        GROUP BY p.id, p.name, p.created_at, p.updated_at
        ORDER BY last_chat_activity DESC, p.updated_at DESC
        """
    ).fetchall()
    return [dict(row) for row in projects]


def get_project(project_id: int) -> Optional[dict]:
    """Get a single project by ID.

    Args:
        project_id: The project ID to retrieve.

    Returns:
        Project record or None if not found.
    """
    row = get_db().execute(
        "SELECT id, name, created_at, updated_at FROM projects WHERE id = ?",
        (project_id,)
    ).fetchone()
    return dict(row) if row else None


def delete_project(project_id: int) -> None:
    """Delete a project and set all its chats' project_id to NULL.

    Args:
        project_id: The project ID to delete.
    """
    db = get_db()
    # Update chats to remove project association
    db.execute("UPDATE chats SET project_id = NULL WHERE project_id = ?", (project_id,))
    # Delete the project
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))


def add_chat_to_project(chat_id: int, project_id: int, now: Optional[str] = None) -> None:
    """Add a chat to a project.

    Args:
        chat_id: The chat ID to add to project.
        project_id: The project ID to add chat to.
        now: Optional timestamp. If None, current time is used.
    """
    db = get_db()
    ts = get_timestamp(now)
    db.execute("UPDATE chats SET project_id = ?, updated_at = ? WHERE id = ?", (project_id, ts, chat_id))
    # Update project's updated_at timestamp
    db.execute("UPDATE projects SET updated_at = ? WHERE id = ?", (ts, project_id))


def remove_chat_from_project(chat_id: int, now: Optional[str] = None) -> None:
    """Remove a chat from its project.

    Args:
        chat_id: The chat ID to remove from project.
        now: Optional timestamp. If None, current time is used.
    """
    db = get_db()
    ts = get_timestamp(now)
    db.execute("UPDATE chats SET project_id = NULL, updated_at = ? WHERE id = ?", (ts, chat_id))


def list_chats_by_project(project_id: Optional[int] = None) -> list:
    """Get chats filtered by project.

    Args:
        project_id: Project ID to filter by. If None, returns chats not in any project.

    Returns:
        List of chat records ordered by most recent update.
    """
    db = get_db()
    if project_id is None:
        # Get chats not assigned to any project
        rows = db.execute(
            "SELECT id, title, provider, model, project_id, created_at, updated_at FROM chats WHERE project_id IS NULL ORDER BY updated_at DESC"
        ).fetchall()
    else:
        # Get chats for specific project
        rows = db.execute(
            "SELECT id, title, provider, model, project_id, created_at, updated_at FROM chats WHERE project_id = ? ORDER BY updated_at DESC",
            (project_id,)
        ).fetchall()
    return [dict(row) for row in rows]


# Task management functions ----------------------------------------------

def create_task(name: str, description: str, date: str, time: str, frequency: str, 
                provider: str, model: str, output: str, email: Optional[str], now: str) -> int:
    """Create a new task.
    
    Args:
        name: Task name
        description: Task description/prompt
        date: Execution date (YYYY-MM-DD)
        time: Execution time (HH:MM)
        frequency: Frequency ('none', 'daily', 'weekly', 'monthly', 'yearly')
        provider: AI provider
        model: AI model
        output: Output destination ('application', 'email')
        email: Email address (required if output is 'email')
        now: Current timestamp
        
    Returns:
        The ID of the created task
    """
    db = get_db()
    ts = get_timestamp(now)
    
    # Calculate next_run based on date and time
    next_run = f"{date}T{time}:00Z"
    
    cursor = db.execute(
        """INSERT INTO tasks 
           (name, description, date, time, frequency, provider, model, output, email, 
            next_run, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, description, date, time, frequency, provider, model, output, email,
         next_run, ts, ts)
    )
    return cursor.lastrowid


def list_tasks() -> list:
    """Get all tasks ordered by next execution time.
    
    Returns:
        List of task records
    """
    db = get_db()
    rows = db.execute(
        """SELECT id, name, description, date, time, frequency, provider, model, 
                  output, email, status, last_run, next_run, created_at, updated_at
           FROM tasks ORDER BY next_run ASC"""
    ).fetchall()
    return [dict(row) for row in rows]


def get_task(task_id: int) -> Optional[dict]:
    """Get a specific task by ID.
    
    Args:
        task_id: The task ID to retrieve
        
    Returns:
        Task record or None if not found
    """
    db = get_db()
    row = db.execute(
        """SELECT id, name, description, date, time, frequency, provider, model,
                  output, email, status, last_run, next_run, created_at, updated_at
           FROM tasks WHERE id = ?""",
        (task_id,)
    ).fetchone()
    return dict(row) if row else None


def update_task(task_id: int, name: str, description: str, date: str, time: str,
                frequency: str, provider: str, model: str, output: str, 
                email: Optional[str], now: str) -> None:
    """Update an existing task.
    
    Args:
        task_id: The task ID to update
        name: Task name
        description: Task description/prompt
        date: Execution date (YYYY-MM-DD)
        time: Execution time (HH:MM)
        frequency: Frequency ('none', 'daily', 'weekly', 'monthly', 'yearly')
        provider: AI provider
        model: AI model
        output: Output destination ('application', 'email')
        email: Email address (required if output is 'email')
        now: Current timestamp
    """
    db = get_db()
    ts = get_timestamp(now)
    
    # Calculate next_run based on date and time
    next_run = f"{date}T{time}:00Z"
    
    db.execute(
        """UPDATE tasks SET 
           name = ?, description = ?, date = ?, time = ?, frequency = ?,
           provider = ?, model = ?, output = ?, email = ?, next_run = ?, updated_at = ?
           WHERE id = ?""",
        (name, description, date, time, frequency, provider, model, output, email,
         next_run, ts, task_id)
    )


def delete_task(task_id: int) -> None:
    """Delete a task.
    
    Args:
        task_id: The task ID to delete
    """
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def update_task_status(task_id: int, status: str, last_run: Optional[str] = None,
                      next_run: Optional[str] = None, now: str = None) -> None:
    """Update task execution status.
    
    Args:
        task_id: The task ID to update
        status: New status ('pending', 'running', 'completed', 'failed')
        last_run: Last execution timestamp (optional)
        next_run: Next execution timestamp (optional)
        now: Current timestamp (optional, defaults to current time)
    """
    db = get_db()
    if now is None:
        now = datetime.now(UTC).isoformat()
    ts = get_timestamp(now)
    
    if last_run is not None and next_run is not None:
        db.execute(
            "UPDATE tasks SET status = ?, last_run = ?, next_run = ?, updated_at = ? WHERE id = ?",
            (status, last_run, next_run, ts, task_id)
        )
    elif last_run is not None:
        db.execute(
            "UPDATE tasks SET status = ?, last_run = ?, updated_at = ? WHERE id = ?",
            (status, last_run, ts, task_id)
        )
    else:
        db.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, ts, task_id)
        )
