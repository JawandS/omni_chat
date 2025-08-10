import os
import types


def _set_keys_via_api(client, openai=None, gemini=None):
    payload = {}
    if openai is not None:
        payload["openai"] = openai
    if gemini is not None:
        payload["gemini"] = gemini
    resp = client.put("/api/keys", json=payload)
    assert resp.status_code == 200
    return resp.get_json()


def test_keys_crud_and_dynamic_reload_openai(client, monkeypatch):
    # Ensure no key set initially
    os.environ.pop("OPENAI_API_KEY", None)

    # Fake openai call that only works if a usable key is present
    import chat as chat_mod

    def fake_openai_call(model, history, message):
        k = os.getenv("OPENAI_API_KEY", "")
        if not k or k.startswith("PUT_"):
            return None
        return f"OK-OAI:{model}:{message}"

    monkeypatch.setattr(chat_mod, "_openai_call", fake_openai_call, raising=True)

    # First call should be missing key
    r1 = client.post("/api/chat", json={
        "message": "Hi",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    assert r1.status_code == 200
    b1 = r1.get_json()
    assert b1.get("error")
    assert b1.get("missing_key_for") == "openai"

    # Set key via settings API (hot-reloads into process env)
    _set_keys_via_api(client, openai="sk-test-123")

    # Now chat should succeed via fake call
    r2 = client.post("/api/chat", json={
        "message": "Hi",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    assert r2.status_code == 200
    b2 = r2.get_json()
    assert b2.get("error") is None
    assert b2["reply"].startswith("OK-OAI:gpt-4o-mini:")

    # Delete key and verify we get missing key again
    d = client.delete("/api/keys/openai")
    assert d.status_code == 200
    r3 = client.post("/api/chat", json={
        "message": "Hi",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
    })
    assert r3.status_code == 200
    b3 = r3.get_json()
    assert b3.get("error")
    assert b3.get("missing_key_for") == "openai"


def test_openai_reasoning_model_uses_responses_api(client, monkeypatch):
    # Provide a key via API
    _set_keys_via_api(client, openai="sk-reasoning-123")

    import chat as chat_mod

    # Fake OpenAI client with Responses API
    class FakeResponses:
        def __init__(self, recorder):
            self.recorder = recorder

        def create(self, model, input, reasoning=None):  # noqa: A003 - using SDK-like name
            self.recorder["model"] = model
            self.recorder["path"] = "responses"
            # Return object with output_text
            return types.SimpleNamespace(output_text="REASONED")

    class FakeOpenAI:
        def __init__(self, api_key=None):
            self.recorder = {}
            self.responses = FakeResponses(self.recorder)
            self.chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **_: None))

    # Swap in our fake client and ensure reasoning predicate remains true for o3 models
    monkeypatch.setattr(chat_mod, "OpenAI", FakeOpenAI, raising=True)

    r = client.post("/api/chat", json={
        "message": "Think",
        "history": [],
        "provider": "openai",
        "model": "o3-mini",
    })
    assert r.status_code == 200
    body = r.get_json()
    # REASONED comes from FakeResponses via Responses API path
    assert body["reply"] == "REASONED"


def test_gemini_with_fake_client(client, monkeypatch):
    # Provide Gemini key
    _set_keys_via_api(client, gemini="g-123")

    import chat as chat_mod

    class FakeChat:
        def __init__(self, history):
            self.history = history

        def send_message(self, text):
            return types.SimpleNamespace(text="GEMINI-OK")

    class FakeModel:
        def __init__(self, name):
            self.name = name

        def start_chat(self, history):
            return FakeChat(history)

    class FakeGenAI:
        def configure(self, api_key=None):  # noqa: D401 - mimic SDK signature
            self.api_key = api_key

        GenerativeModel = FakeModel

    monkeypatch.setattr(chat_mod, "genai", FakeGenAI(), raising=True)

    r = client.post("/api/chat", json={
        "message": "Hi",
        "history": [],
        "provider": "gemini",
        "model": "gemini-2.5-pro",
    })
    assert r.status_code == 200
    assert r.get_json()["reply"] == "GEMINI-OK"


def test_patch_without_fields_returns_400(client):
    # Create a chat
    r = client.post("/api/chat", json={
        "message": "Hello",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
        "title": "X",
    })
    cid = r.get_json().get("chat_id")
    assert cid

    # Patch with no fields
    p = client.patch(f"/api/chats/{cid}", json={})
    assert p.status_code == 400


def test_get_chat_not_found_and_delete_key_unknown_provider(client):
    # Missing chat id
    r = client.get("/api/chats/999999")
    assert r.status_code == 404

    # Delete unknown key provider
    r2 = client.delete("/api/keys/not-a-provider")
    assert r2.status_code == 400
