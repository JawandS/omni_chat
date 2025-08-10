import pytest
from app import create_app


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client


def test_home_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    # Look for provider/model selects and composer form
    assert b"data-testid=\"provider-select\"" in resp.data
    assert b"data-testid=\"model-select\"" in resp.data
    assert b"id=\"composer\"" in resp.data


def test_api_chat_echo(client):
    payload = {
        "message": "Hello",
        "history": [],
        "provider": "openai",
        "model": "gpt-4o-mini"
    }
    resp = client.post("/api/chat", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["reply"].startswith("[openai/gpt-4o-mini] Echo: Hello")
