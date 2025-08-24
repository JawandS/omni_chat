"""Tests to ensure complete isolation from production resources.

This module tests that the test environment is properly isolated from:
- Production database (instance/omni_chat.db)
- Production .env file
- Production providers.json file
- External API calls
- Production working directory
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


def test_providers_json_isolation(client):
    """Test that tests use isolated providers.json, not production file."""
    # Check that PROVIDERS_JSON_PATH points to a temp file
    providers_path = os.environ.get("PROVIDERS_JSON_PATH")
    assert providers_path is not None
    assert "tmp" in providers_path
    assert "static/providers.json" not in providers_path

    # Verify the file uses template content
    import json

    with open(providers_path) as f:
        config = json.load(f)

    # Should have the basic structure from template
    assert "providers" in config
    assert "favorites" in config
    assert "default" in config


def test_api_key_operations_isolated(client):
    """Test that API key operations don't affect production .env file."""
    # Get the actual project root directory (parent of tests directory)
    tests_dir = Path(__file__).parent
    project_root = tests_dir.parent
    project_env = project_root / ".env"

    original_mtime = None
    if project_env.exists():
        original_mtime = project_env.stat().st_mtime

    # Perform API key operations that would normally modify .env
    client.put("/api/keys", json={"openai": "test-key-123"})
    client.put("/api/keys", json={"gemini": "test-gemini-key"})
    client.delete("/api/keys/openai")

    # Check that production .env file was not modified
    if project_env.exists():
        current_mtime = project_env.stat().st_mtime
        assert (
            current_mtime == original_mtime
        ), "Production .env file was modified by tests!"


def test_no_real_api_calls():
    """Test that API client libraries are mocked to prevent real calls."""
    import utils

    # Verify that the API key getter is mocked
    openai_key = utils.get_api_key("openai")
    gemini_key = utils.get_api_key("gemini")

    # Should return mock values, not real API keys
    assert openai_key == "PUT_API_KEY_HERE"
    assert gemini_key == "PUT_API_KEY_HERE"

    # Unknown providers should return empty
    unknown_key = utils.get_api_key("unknown")
    assert unknown_key == ""


def test_working_directory_isolation():
    """Test that tests run in isolated working directory."""
    current_cwd = os.getcwd()

    # Should be in a temp directory during test execution
    assert "tmp" in current_cwd or "test" in current_cwd

    # Should not be in the production project directory
    assert not current_cwd.endswith("omni_chat")


def test_providers_config_uses_template_data(client):
    """Test that provider configuration uses template data, not production data."""
    response = client.get("/api/providers-config")
    assert response.status_code == 200
    data = response.get_json()

    # Should have providers from template
    providers = data["providers"]
    provider_ids = [p["id"] for p in providers]

    # Template should have these basic providers
    assert "openai" in provider_ids
    assert "gemini" in provider_ids

    # Verify models are from template (not production modifications)
    openai_provider = next(p for p in providers if p["id"] == "openai")
    assert "gpt-4o" in openai_provider["models"]
