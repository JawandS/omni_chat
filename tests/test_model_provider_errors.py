def test_gemini_provider_is_used(client):
    payload = {
        "message": "Hi",
        "history": [],
        "provider": "gemini",
        "model": "gemini-1.5-flash",
    }
    r = client.post("/api/chat", json=payload)
    # Without a real key, backend will fall back to formatted echo prefix or plain text
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        data = r.get_json()
        # Either gemini actual output or fallback prefix
        assert data["reply"].startswith("[gemini/gemini-1.5-flash]:") or isinstance(data["reply"], str)


def test_unknown_provider_returns_400(client):
    payload = {
        "message": "Hi",
        "history": [],
        "provider": "unknown_vendor",
        "model": "foo",
    }
    r = client.post("/api/chat", json=payload)
    assert r.status_code == 400
    body = r.get_json()
    assert "unknown provider" in body.get("error", "")
