"""
Tests to ensure complete isolation from production resources.
"""

import os
import tempfile
from pathlib import Path


def test_database_isolation(client):
    """Test that tests use isolated database, not production DB."""
    # Get the database path from the app config
    db_path = client.application.config.get("DATABASE")
    
    # Should be a temp path, not the production instance/omni_chat.db
    assert db_path is not None
    assert "tmp" in db_path or "test" in db_path
    assert "instance/omni_chat.db" not in db_path
    
    # The file should exist (created by test setup)
    assert os.path.exists(db_path)


def test_env_file_isolation(client):
    """Test that tests use isolated .env file, not production .env."""
    # Get the env path from the app config
    env_path = client.application.config.get("ENV_PATH")
    
    # Should be a temp path, not the production .env
    assert env_path is not None
    assert "tmp" in env_path or "test" in env_path
    assert not env_path.endswith("omni_chat/.env")


def test_api_key_operations_isolated(client):
    """Test that API key operations don't affect production .env file."""
    import tempfile
    
    # Store the original .env file modification time if it exists
    project_env = Path.cwd() / ".env"
    original_mtime = None
    if project_env.exists():
        original_mtime = project_env.stat().st_mtime
    
    # Perform API key operations that would normally modify .env
    client.put("/api/keys", json={"openai": "test-key-123"})
    client.put("/api/keys", json={"gemini": "test-gemini-key"})
    client.delete("/api/keys/openai")
    
    # Check that production .env file was not modified
    if project_env.exists() and original_mtime is not None:
        current_mtime = project_env.stat().st_mtime
        assert current_mtime == original_mtime, "Production .env file was modified by tests!"


def test_no_real_api_calls():
    """Test that the chat module is properly mocked to prevent real API calls."""
    from chat import _get_api_key, OpenAI, genai
    
    # API key functions should return mock values
    openai_key = _get_api_key("openai")
    gemini_key = _get_api_key("gemini")
    
    assert openai_key == "PUT_API_KEY_HERE"
    assert gemini_key == "PUT_API_KEY_HERE"
    
    # Client libraries should be disabled
    assert OpenAI is None
    assert genai is None


def test_working_directory_isolation():
    """Test that tests run in isolated working directory."""
    current_dir = os.getcwd()
    
    # Should be in a temp directory, not the main project directory
    assert "tmp" in current_dir.lower() or "test" in current_dir.lower()
    
    # Should not be in the main omni_chat directory
    assert not current_dir.endswith("omni_chat")
