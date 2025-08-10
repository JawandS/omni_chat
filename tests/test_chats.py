from app import create_app  # unused but keeps import under test for coverage


def _create_chat(client, *, message="Hello", provider="openai", model="gpt-4o-mini", title="Test Chat"):
    resp = client.post("/api/chat", json={
        "message": message,
        "history": [],
        "provider": provider,
        "model": model,
        "title": title,
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert "chat_id" in data
    return data["chat_id"], data


def test_create_and_get_chat(client):
    chat_id, data = _create_chat(client, title="My Chat")
    assert data["reply"].startswith("[openai/gpt-4o-mini]:") or data["reply"].startswith("Hello")

    # Fetch chat details
    r = client.get(f"/api/chats/{chat_id}")
    assert r.status_code == 200
    body = r.get_json()
    assert body["chat"]["id"] == chat_id
    assert body["chat"]["title"] == "My Chat"
    msgs = body["messages"]
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"


def test_list_chats_contains_new_chat(client):
    chat_id, _ = _create_chat(client, title="List Me")
    r = client.get("/api/chats")
    assert r.status_code == 200
    body = r.get_json()
    titles = [c["title"] for c in body.get("chats", [])]
    assert "List Me" in titles


def test_update_chat_title(client):
    chat_id, _ = _create_chat(client, title="Old Title")
    r = client.patch(f"/api/chats/{chat_id}", json={"title": "New Title"})
    assert r.status_code == 200
    assert r.get_json().get("ok") is True

    r2 = client.get(f"/api/chats/{chat_id}")
    assert r2.status_code == 200
    assert r2.get_json()["chat"]["title"] == "New Title"


def test_delete_chat(client):
    chat_id, _ = _create_chat(client, title="Delete Me")
    r = client.delete(f"/api/chats/{chat_id}")
    assert r.status_code == 200
    assert r.get_json().get("ok") is True

    # Now it should be gone
    r2 = client.get(f"/api/chats/{chat_id}")
    assert r2.status_code == 404


def test_missing_message_returns_400(client):
    r = client.post("/api/chat", json={"message": "   "})
    assert r.status_code == 400
