"""
Tests for streaming chat functionality.
"""

import json
import pytest


def test_streaming_chat_endpoint_missing_message(client):
    """Test streaming endpoint returns error for missing message."""
    resp = client.post("/api/chat/stream", json={"provider": "openai", "model": "gpt-4"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "message is required"


def test_streaming_chat_endpoint_missing_provider(client):
    """Test streaming endpoint returns error for missing provider."""
    resp = client.post("/api/chat/stream", json={"message": "Hello", "model": "gpt-4"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "provider is required"


def test_streaming_chat_endpoint_missing_model(client):
    """Test streaming endpoint returns error for missing model."""
    resp = client.post("/api/chat/stream", json={"message": "Hello", "provider": "openai"})
    assert resp.status_code == 400
    data = resp.get_json()
    assert data["error"] == "model is required"


def test_streaming_chat_basic_flow(client):
    """Test basic streaming chat flow."""
    payload = {
        "message": "Hello streaming",
        "provider": "openai",
        "model": "gpt-4",
        "title": "Test Stream Chat"
    }
    
    resp = client.post("/api/chat/stream", json=payload)
    assert resp.status_code == 200
    assert resp.content_type == "text/event-stream; charset=utf-8"
    
    # Just verify we get a response - parsing the full streaming response is complex in tests
    response_data = resp.get_data(as_text=True)
    assert "data:" in response_data
    assert "Test Stream Chat" in response_data or "metadata" in response_data


def test_streaming_chat_with_existing_chat_id(client):
    """Test streaming endpoint works with existing chat ID."""
    # First create a chat via non-streaming endpoint
    create_payload = {
        "message": "First message",
        "provider": "openai",
        "model": "gpt-4",
        "title": "Existing Chat"
    }
    
    create_resp = client.post("/api/chat", json=create_payload)
    assert create_resp.status_code == 200
    chat_id = create_resp.get_json()["chat_id"]
    
    # Now use streaming endpoint with existing chat ID
    stream_payload = {
        "message": "Second message via streaming",
        "provider": "openai",
        "model": "gpt-4",
        "chat_id": chat_id
    }
    
    resp = client.post("/api/chat/stream", json=stream_payload)
    assert resp.status_code == 200
    
    # Just verify we get a streaming response
    response_data = resp.get_data(as_text=True)
    assert "data:" in response_data
