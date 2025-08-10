from app import create_app
from database import init_db


def test_model_switch_updates_backend(client):
    # Send first message with model A
    payload = {
        "message": "Hello",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
        "title": "Switch Test"
    }
    r1 = client.post("/api/chat", json=payload)
    assert r1.status_code == 200
    chat_id = r1.get_json()["chat_id"]

    # Send second message after switching model to B
    payload2 = {
        "message": "Second",
        "history": [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": r1.get_json()["reply"]}],
        "provider": "openai",
        "model": "gpt-4o-realtime-preview-2024-12-17",
        "chat_id": chat_id,
    }
    r2 = client.post("/api/chat", json=payload2)
    assert r2.status_code == 200

    # Fetch messages and verify the last assistant message carries the new model
    resp = client.get(f"/api/chats/{chat_id}")
    assert resp.status_code == 200
    data = resp.get_json()
    msgs = data["messages"]
    assert len(msgs) == 4  # user, assistant, user, assistant
    last = msgs[-1]
    assert last["role"] == "assistant"
    assert last["model"] == "gpt-4o-realtime-preview-2024-12-17"
    assert last["provider"] == "openai"
