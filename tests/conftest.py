# Ensure the project root is on sys.path so `import app` works when running pytest
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from database import init_db  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    """Flask test client backed by a fresh temp SQLite database per test."""
    app = create_app()
    app.config.update(TESTING=True)
    # Point to a temp DB file and initialize tables
    app.config["DATABASE"] = str(tmp_path / "test.db")
    with app.app_context():
        init_db()
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _force_echo_backend(monkeypatch):
    """Ensure tests never hit the real OpenAI API and always use echo.

    This isolates tests from external services and keeps assertions stable,
    even if OPENAI_API_KEY is present in the environment.
    """
    import chat as chat_mod  # import here to ensure module is loaded
    # Force fallback path: placeholder key and no client
    monkeypatch.setattr(chat_mod, "OPENAI_API_KEY", "PUT_OPENAI_API_KEY_HERE", raising=True)
    try:
        monkeypatch.setattr(chat_mod, "OpenAI", None, raising=True)
    except Exception:
        pass
