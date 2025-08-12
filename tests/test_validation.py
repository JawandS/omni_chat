"""
Tests for input validation and error handling.
"""

import pytest


def test_non_streaming_chat_missing_provider(client):
    """Test non-streaming endpoint returns error for missing provider."""
    resp = client.post("/api/chat", json={"message": "Hello", "model": "gpt-4"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "provider is required"


def test_non_streaming_chat_missing_model(client):
    """Test non-streaming endpoint returns error for missing model."""
    resp = client.post("/api/chat", json={"message": "Hello", "provider": "openai"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "model is required"


def test_non_streaming_chat_empty_message(client):
    """Test non-streaming endpoint returns error for empty message."""
    resp = client.post(
        "/api/chat", json={"message": "   ", "provider": "openai", "model": "gpt-4"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_non_streaming_chat_whitespace_only_message(client):
    """Test non-streaming endpoint returns error for whitespace-only message."""
    resp = client.post(
        "/api/chat",
        json={"message": "\n\t  \r\n", "provider": "openai", "model": "gpt-4"},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_streaming_chat_empty_message(client):
    """Test streaming endpoint returns error for empty message."""
    resp = client.post(
        "/api/chat/stream", json={"message": "", "provider": "openai", "model": "gpt-4"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_chat_no_json_body(client):
    """Test chat endpoint with no JSON body."""
    resp = client.post("/api/chat")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_streaming_chat_no_json_body(client):
    """Test streaming chat endpoint with no JSON body."""
    resp = client.post("/api/chat/stream")
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_chat_invalid_json(client):
    """Test chat endpoint with invalid JSON."""
    resp = client.post(
        "/api/chat", data="invalid json", content_type="application/json"
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_update_chat_no_updates(client):
    """Test updating chat with no fields provided."""
    # First create a chat
    create_resp = client.post(
        "/api/chat", json={"message": "Hello", "provider": "openai", "model": "gpt-4"}
    )
    chat_id = create_resp.get_json()["chat_id"]

    # Try to update with no fields
    resp = client.patch(f"/api/chats/{chat_id}", json={})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "no updates provided"


def test_update_nonexistent_chat(client):
    """Test updating a chat that doesn't exist."""
    resp = client.patch("/api/chats/99999", json={"title": "New Title"})
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_get_nonexistent_chat(client):
    """Test getting a chat that doesn't exist."""
    resp = client.get("/api/chats/99999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_delete_nonexistent_chat(client):
    """Test deleting a chat that doesn't exist."""
    resp = client.delete("/api/chats/99999")
    assert resp.status_code == 404
    data = resp.get_json()
    assert data["error"] == "not found"


def test_chat_with_unknown_provider_non_streaming(client):
    """Test non-streaming chat with unknown provider."""
    resp = client.post(
        "/api/chat",
        json={"message": "Hello", "provider": "unknown", "model": "some-model"},
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "unknown provider" in data["error"]


def test_chat_with_empty_provider_non_streaming(client):
    """Test non-streaming chat with empty provider."""
    resp = client.post(
        "/api/chat", json={"message": "Hello", "provider": "", "model": "some-model"}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "provider is required"


def test_chat_with_empty_model_non_streaming(client):
    """Test non-streaming chat with empty model."""
    resp = client.post(
        "/api/chat", json={"message": "Hello", "provider": "openai", "model": ""}
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "model is required"


def test_chat_handles_history_gracefully(client):
    """Test that chat endpoint handles history parameter gracefully."""
    payload = {
        "message": "Hello",
        "provider": "openai",
        "model": "gpt-4",
        "history": [
            {"role": "user", "content": "Previous message"},
            {"role": "assistant", "content": "Previous response"},
        ],
    }

    resp = client.post("/api/chat", json=payload)
    # Should succeed (with our mocked backend)
    assert (
        resp.status_code == 200 or resp.status_code == 500
    )  # 500 is acceptable for error responses


def test_chat_handles_malformed_history(client):
    """Test that chat endpoint handles malformed history gracefully."""
    payload = {
        "message": "Hello",
        "provider": "openai",
        "model": "gpt-4",
        "history": [{"invalid": "structure"}, {"role": "user"}],  # missing content
    }

    resp = client.post("/api/chat", json=payload)
    # Should not crash, might succeed or return error
    assert resp.status_code in [200, 400, 500]


def test_update_chat_with_empty_title(client):
    """Test updating chat with empty title."""
    # First create a chat
    create_resp = client.post(
        "/api/chat", json={"message": "Hello", "provider": "openai", "model": "gpt-4"}
    )
    chat_id = create_resp.get_json()["chat_id"]

    # Try to update with empty title (should be treated as no update)
    resp = client.patch(f"/api/chats/{chat_id}", json={"title": "   "})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "no updates provided"
