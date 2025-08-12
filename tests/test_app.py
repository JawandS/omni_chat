from app import create_app  # unused but keeps import under test for coverage


def test_home_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    # Look for provider/model selects and composer form
    assert b'data-testid="provider-select"' in resp.data
    assert b'data-testid="model-select"' in resp.data
    assert b'id="composer"' in resp.data


def test_api_chat_echo(client):
    payload = {
        "message": "Hello",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini",
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    # Either a normal reply, or an error with missing key indicator
    if data.get("error"):
        assert data.get("missing_key_for") == "openai"
        assert data.get("reply", "") == ""
    else:
        assert data["reply"].startswith("[openai/gpt-4o-mini]: Hello") or data[
            "reply"
        ].startswith("Hello")
