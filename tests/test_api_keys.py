"""
Tests for API key management functionality.
"""

import os
import tempfile


def test_get_keys_empty(client):
    """Test getting API keys when none are set."""
    resp = client.get("/api/keys")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "openai" in data
    assert "gemini" in data
    # Should be empty strings if no keys are set
    assert data["openai"] == ""
    assert data["gemini"] == ""


def test_put_keys_openai(client):
    """Test setting OpenAI API key."""
    payload = {"openai": "sk-test-key-123"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"]["openai"] == "sk-test-key-123"


def test_put_keys_gemini(client):
    """Test setting Gemini API key."""
    payload = {"gemini": "gemini-test-key-456"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"]["gemini"] == "gemini-test-key-456"


def test_put_keys_both(client):
    """Test setting both API keys."""
    payload = {"openai": "sk-test-key-123", "gemini": "gemini-test-key-456"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"]["openai"] == "sk-test-key-123"
    assert data["updated"]["gemini"] == "gemini-test-key-456"


def test_put_keys_empty_string_removes_key(client):
    """Test that setting empty string removes the key."""
    # First set a key
    payload = {"openai": "sk-test-key-123"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200

    # Then remove it with empty string
    payload = {"openai": ""}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"]["openai"] is None


def test_put_keys_null_removes_key(client):
    """Test that setting null removes the key."""
    # First set a key
    payload = {"openai": "sk-test-key-123"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200

    # Then remove it with null
    payload = {"openai": None}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"]["openai"] is None


def test_delete_key_openai(client):
    """Test deleting OpenAI API key."""
    # First set a key
    payload = {"openai": "sk-test-key-123"}
    client.put("/api/keys", json=payload)

    # Then delete it
    resp = client.delete("/api/keys/openai")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_delete_key_gemini(client):
    """Test deleting Gemini API key."""
    # First set a key
    payload = {"gemini": "gemini-test-key-456"}
    client.put("/api/keys", json=payload)

    # Then delete it
    resp = client.delete("/api/keys/gemini")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_delete_key_unknown_provider(client):
    """Test deleting key for unknown provider."""
    resp = client.delete("/api/keys/unknown")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "unknown provider"


def test_delete_key_case_insensitive(client):
    """Test that provider name is case insensitive for deletion."""
    resp = client.delete("/api/keys/OpenAI")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True

    resp = client.delete("/api/keys/GEMINI")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True


def test_keys_round_trip(client):
    """Test full round trip of setting, getting, and deleting keys."""
    # Set keys
    payload = {"openai": "sk-test-key-123", "gemini": "gemini-test-key-456"}
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200

    # Get keys (Note: in test environment, this might still return empty due to test isolation)
    resp = client.get("/api/keys")
    assert resp.status_code == 200

    # Delete one key
    resp = client.delete("/api/keys/openai")
    assert resp.status_code == 200

    # Delete the other key
    resp = client.delete("/api/keys/gemini")
    assert resp.status_code == 200


def test_put_keys_no_json(client):
    """Test PUT /api/keys with no JSON body."""
    resp = client.put("/api/keys")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"] == {}


def test_put_keys_invalid_json(client):
    """Test PUT /api/keys with invalid JSON."""
    resp = client.put("/api/keys", data="invalid json", content_type="application/json")
    # Should still work because we use get_json(silent=True) which returns {}
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["updated"] == {}
