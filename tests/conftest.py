# Ensure the project root is on sys.path so `import app` works when running pytest
import sys
import json
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
    # Prepare isolated providers.json BEFORE app creation so factory picks it up
    # Always use providers_template.json as the baseline for tests
    providers_template = Path(ROOT / "static" / "providers_template.json")
    providers_dst = tmp_path / "providers.json"
    if providers_template.exists():
        providers_dst.write_text(providers_template.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        # Fallback minimal providers config if template doesn't exist
        minimal_config = {
            "default": {"provider": "openai", "model": "gpt-4o"},
            "favorites": [],
            "providers": [
                {"id": "openai", "name": "OpenAI", "models": ["gpt-4o", "gpt-5-mini"]},
                {"id": "gemini", "name": "Google Gemini", "models": ["gemini-2.5-flash"]}
            ],
            "blacklist": []
        }
        providers_dst.write_text(json.dumps(minimal_config, indent=2), encoding="utf-8")
    
    import os
    os.environ["PROVIDERS_JSON_PATH"] = str(providers_dst)

    app = create_app()
    app.config.update(TESTING=True)

    # Point to a temp DB file and initialize tables (isolate from prod DB)
    app.config["DATABASE"] = str(tmp_path / "test.db")

    # Point to a temp .env file (isolate from prod .env file)
    app.config["ENV_PATH"] = str(tmp_path / ".env.test")

    with app.app_context():
        init_db()
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _force_test_isolation(monkeypatch, tmp_path):
    """Ensure complete test isolation from production resources.

    This isolates tests from external services, production database,
    production .env files, and keeps assertions stable.
    """
    import chat as chat_mod  # import here to ensure module is loaded
    import os

    # Clear all relevant environment variables for tests
    env_vars_to_clear = [
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE",  # In case it's set in environment
    ]
    for key in env_vars_to_clear:
        monkeypatch.delenv(key, raising=False)

    # Force fallback path by monkeypatching the new unified API key getter
    def mock_get_api_key(provider):
        """Mock API key getter that never returns real keys."""
        return "PUT_API_KEY_HERE" if provider.lower() in ["openai", "gemini"] else ""

    # Import utils module and patch the get_api_key function there
    import utils as utils_mod
    monkeypatch.setattr(utils_mod, "get_api_key", mock_get_api_key)

    # Disable the actual client libraries to prevent any real API calls
    try:
        monkeypatch.setattr(chat_mod, "OpenAI", None, raising=False)
    except Exception:
        pass

    try:
        monkeypatch.setattr(chat_mod, "genai", None, raising=False)
    except Exception:
        pass

    # Set a test-specific working directory if needed
    # This ensures any relative path operations don't affect production files
    original_cwd = os.getcwd()
    test_work_dir = tmp_path / "work"
    test_work_dir.mkdir()
    os.chdir(str(test_work_dir))

    # Restore original working directory after test
    yield
    os.chdir(original_cwd)
