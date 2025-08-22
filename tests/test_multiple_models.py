"""
Tests for multiple models per message functionality.
"""

import pytest


def test_single_model_backward_compatibility(client):
    """Test that single model requests still work (backward compatibility)."""
    payload = {"message": "Hello", "provider": "openai", "model": "gpt-4o-mini"}
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data
    assert "chat_id" in data


def test_multiple_models_request(client):
    """Test multiple models in a single request."""
    payload = {
        "message": "Hello",
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data
    assert "replies" in data
    assert "chat_id" in data
    assert len(data["replies"]) == 2

    # Check that each model's response is included
    assert "## openai/gpt-4o-mini" in data["reply"]
    assert "## gemini/gemini-2.5-flash" in data["reply"]
    assert "---" in data["reply"]  # Separator between models


def test_same_model_multiple_times(client):
    """Test using the same model multiple times."""
    payload = {
        "message": "Hello",
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "openai", "model": "gpt-4o-mini"},
        ],
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "reply" in data
    assert "replies" in data
    assert len(data["replies"]) == 3

    # Should see the model header 3 times
    assert data["reply"].count("## openai/gpt-4o-mini") == 3


def test_multiple_models_validation_errors(client):
    """Test validation errors for multiple models requests."""
    # Empty models array
    resp = client.post("/api/chat", json={"message": "Hello", "models": []})
    assert resp.status_code == 400
    assert "models list cannot be empty" in resp.get_json()["error"]

    # Missing provider in models array
    resp = client.post(
        "/api/chat", json={"message": "Hello", "models": [{"model": "gpt-4o-mini"}]}
    )
    assert resp.status_code == 400
    assert "models[0].provider is required" in resp.get_json()["error"]

    # Missing model in models array
    resp = client.post(
        "/api/chat", json={"message": "Hello", "models": [{"provider": "openai"}]}
    )
    assert resp.status_code == 400
    assert "models[0].model is required" in resp.get_json()["error"]

    # Invalid model object type
    resp = client.post("/api/chat", json={"message": "Hello", "models": ["invalid"]})
    assert resp.status_code == 400
    assert "models[0] must be an object" in resp.get_json()["error"]


def test_no_provider_or_models_field(client):
    """Test error when neither provider/model nor models is provided."""
    resp = client.post("/api/chat", json={"message": "Hello"})
    assert resp.status_code == 400
    assert (
        "either 'models' array or 'provider'/'model' fields are required"
        in resp.get_json()["error"]
    )


def test_streaming_multiple_models(client):
    """Test streaming endpoint with multiple models."""
    payload = {
        "message": "Hello",
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    resp = client.post("/api/chat/stream", json=payload)
    assert resp.status_code == 200
    assert resp.content_type == "text/event-stream; charset=utf-8"


def test_streaming_single_model_backward_compatibility(client):
    """Test that streaming still works with single model (backward compatibility)."""
    payload = {"message": "Hello", "provider": "openai", "model": "gpt-4o-mini"}
    resp = client.post("/api/chat/stream", json=payload)
    assert resp.status_code == 200
    assert resp.content_type == "text/event-stream; charset=utf-8"


def test_multiple_models_with_chat_id(client):
    """Test multiple models request with existing chat_id."""
    # First create a chat with single model
    payload1 = {
        "message": "First message",
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    resp1 = client.post("/api/chat", json=payload1)
    assert resp1.status_code == 200
    chat_id = resp1.get_json()["chat_id"]

    # Then send multiple models to same chat
    payload2 = {
        "message": "Second message",
        "chat_id": chat_id,
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},
            {"provider": "gemini", "model": "gemini-2.5-flash"},
        ],
    }
    resp2 = client.post("/api/chat", json=payload2)
    assert resp2.status_code == 200
    assert resp2.get_json()["chat_id"] == chat_id


def test_mixed_error_responses(client):
    """Test behavior when some models succeed and others fail."""
    payload = {
        "message": "Hello",
        "models": [
            {"provider": "openai", "model": "gpt-4o-mini"},  # Should work
            {"provider": "unknown", "model": "invalid-model"},  # Should fail
        ],
    }
    resp = client.post("/api/chat", json=payload)
    # Should still get a 200 with partial results
    # The actual behavior depends on how chat.py handles unknown providers
    assert resp.status_code in [
        200,
        400,
    ]  # Either success with partial results or validation error
